import logging
import pyperclip
from pathlib import Path
from pydantic import HttpUrl, ValidationError
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QInputDialog, QApplication

from streamcondor.model import Configuration, TrayIconColor, TrayIconStatus, TrayIconAction, Stream
from streamcondor.monitor import StreamMonitor
from streamcondor.slhelper import is_stream_live, launch_process, build_sl_command
from streamcondor.favicons import get_stream_icon
from streamcondor.resources import get_app_icon
from streamcondor.ui.settings import SettingsWindow

log = logging.getLogger(__name__)


class TrayIcon(QSystemTrayIcon):

  def __init__(self, parent, config_path: str):
    super().__init__(parent)
    if not config_path:
      config_dir = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.ConfigLocation
      ))
      config_path = config_dir / 'StreamCondor.json'
    self.cfg = Configuration(config_path)
    self.cfg.config_changed.connect(self._update_icon)
    self.activated.connect(self._on_tray_icon_action)
    self.settings = SettingsWindow(self.cfg)
    self.notify = self.cfg.default_notify
    self._create_icons()
    self._create_menu()
    self._create_monitor()
    self._update_icon()
    log.info('StreamCondor started')

  def _create_icons(self) -> None:
    self.tray_icons = {
      TrayIconColor.WHITE: {
        TrayIconStatus.OFF: get_app_icon('sc_w_off'),
        TrayIconStatus.IDLE: get_app_icon('sc_w_idle'),
        TrayIconStatus.LIVE: get_app_icon('sc_w_live'),
        TrayIconStatus.VIPS: get_app_icon('sc_w_vips'),
      },
      TrayIconColor.BLACK: {
        TrayIconStatus.OFF: get_app_icon('sc_b_off'),
        TrayIconStatus.IDLE: get_app_icon('sc_b_idle'),
        TrayIconStatus.LIVE: get_app_icon('sc_b_live'),
        TrayIconStatus.VIPS: get_app_icon('sc_b_vips'),
      }
    }
    # Initial tray icon
    self.setIcon(self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.OFF])
    # Icons to emulate checkbox states in menu (with both icons and standard checkboxes the menu looks weird)
    self.icon_checked = QIcon.fromTheme('ok', QIcon.fromTheme('dialog-ok'))
    self.icon_unchecked = QIcon.fromTheme('emblem-none', QIcon.fromTheme('dialog-cancel'))

  def _create_menu(self) -> None:
    self.menu = QMenu()
    # Open URL action
    self.action_open_url = QAction(TrayIconAction.OPEN_URL.display_name, self.menu)
    self.action_open_url.triggered.connect(self._open_url)
    self.menu.addAction(self.action_open_url)
    # Separator before online streams
    self.list_top_separator = self.menu.addSeparator()
    # Toggle monitoring (online streams will be added above)
    self.action_toggle_monitoring = QAction('Monitoring', self.menu)
    self.action_toggle_monitoring.triggered.connect(self._toggle_monitoring)
    self.menu.addAction(self.action_toggle_monitoring)
    # Toggle notifications
    self.action_toggle_notifications = QAction('Notifications', self.menu)
    self.action_toggle_notifications.triggered.connect(self._toggle_notifications)
    self.menu.addAction(self.action_toggle_notifications)
    # Settings
    action_settings = QAction('Settings', self.menu)
    action_settings.triggered.connect(self._open_settings)
    self.menu.addAction(action_settings)
    # Quit
    action_quit = QAction('Quit', self.menu)
    action_quit.triggered.connect(self._quit)
    self.menu.addAction(action_quit)
    # Finish
    self.menu.insertSeparator(action_settings)
    self.menu.aboutToShow.connect(self._update_menu)
    self.setContextMenu(self.menu)

  def _create_monitor(self) -> None:
    self.monitor = StreamMonitor(self.cfg)
    self.monitor.stream_online.connect(self._on_stream_online)
    self.monitor.stream_offline.connect(self._on_stream_offline)
    self.monitor.start()

  def _update_menu(self) -> None:
    # Update toggle icons
    self.action_toggle_monitoring.setIcon(self.icon_unchecked if self.monitor.paused else self.icon_checked)
    self.action_toggle_notifications.setIcon(self.icon_checked if self.notify else self.icon_unchecked)
    # Update online streams in menu
    all_actions = self.menu.actions()
    for i in range(
      all_actions.index(self.list_top_separator) + 1,
      all_actions.index(self.action_toggle_monitoring)
    ):
      self.menu.removeAction(all_actions[i])
    online_streams = self.monitor.get_online_streams()
    for stream in online_streams:
      action = QAction(stream.name, self.menu)
      if (pixmap := get_stream_icon(stream, 16)) is not None:
        action.setIcon(QIcon(pixmap))
      action.triggered.connect(lambda checked, s=stream: self._launch_stream(s))
      self.menu.insertAction(self.action_toggle_monitoring, action)
    if len(online_streams) > 0:
      self.menu.insertSeparator(self.action_toggle_monitoring)

  def _update_icon(self) -> None:
    online_streams = self.monitor.get_online_streams()
    has_lives = len(online_streams) > 0
    has_vips = any(s.notify == True for s in online_streams)
    self.setIcon(
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.OFF] if self.monitor.paused else
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.VIPS] if has_vips else
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.LIVE] if has_lives else
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.IDLE]
    )
    tooltip = ['StreamCondor']
    if self.monitor.paused:
      tooltip.append('OFF (not checking streams)')
    elif has_lives:
      tooltip.append(f'{len(online_streams)} stream(s) online!')
    self.setToolTip('\n'.join(tooltip))

  def _open_url(self) -> None:
    stream_url = _check_url(pyperclip.paste().strip())  ## QApplication.clipboard() doesn't work in this class, idk why
    if stream_url is None or stream_url == '':
      stream_url, ok = QInputDialog.getText(None, 'Open Stream', 'Enter stream URL:')
      if not ok or not stream_url:
        return
    stream = self.cfg.streams.get(stream_url)
    if stream is None:
      stream_type, is_live = is_stream_live(stream_url)  ## can throw NoPluginError (catched by main.excepthook)
      if not is_live:
        self.showMessage(
          'Stream Offline',
          f'Stream at {stream_url} is not broadcasting.',
          QSystemTrayIcon.MessageIcon.Warning,
          5000
        )
        return
      stream_name = 'Unknown'
      stream = Stream(url=stream_url, type=stream_type, name=stream_name)
    self._launch_stream(stream)

  def _launch_stream(self, stream: Stream) -> None:
    launch_process(build_sl_command(self.cfg, stream))

  def _toggle_monitoring(self) -> None:
    if self.monitor.paused:
      self.monitor.resume()
    else:
      self.monitor.pause()
    self._update_icon()

  def _toggle_notifications(self) -> None:
    self.notify = not self.notify
    self._update_icon()

  def _open_settings(self) -> None:
    self.settings.show()
    self.settings.raise_()
    self.settings.activateWindow()

  def _quit(self) -> None:
    self.monitor.stop()
    self.monitor.wait()
    self.monitor.quit()
    QApplication.quit()

  def _on_tray_icon_action(self, reason: QSystemTrayIcon.ActivationReason) -> None:
    if reason != QSystemTrayIcon.ActivationReason.Trigger:
      pass
    elif self.cfg.tray_icon_action == TrayIconAction.OPEN_URL:
      self._open_url()
    elif self.cfg.tray_icon_action == TrayIconAction.OPEN_CONFIG:
      self._open_settings()
    elif self.cfg.tray_icon_action == TrayIconAction.TOGGLE_MONITORING:
      self._toggle_monitoring()
    elif self.cfg.tray_icon_action == TrayIconAction.TOGGLE_NOTIFICATIONS:
      self._toggle_notifications()

  def _on_stream_online(self, stream: Stream) -> None:
    self._update_icon()
    if self.notify and (stream.notify is None or stream.notify) and self.supportsMessages():
      self.showMessage(
        'Stream Online',
        f'{stream.name} is now live on {stream.type}!',
        QSystemTrayIcon.MessageIcon.Information,
        5000
      )

  def _on_stream_offline(self, stream: Stream) -> None:
    self._update_icon()


def _check_url(url: str) -> str:
  try:
    HttpUrl(url)
    return url
  except ValidationError:
    return None
