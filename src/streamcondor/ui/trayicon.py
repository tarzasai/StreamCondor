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
    self.activated.connect(self._on_tray_action)
    self.settings = SettingsWindow(self.cfg)
    self.notify = self.cfg.default_notify
    self.click = self.cfg.tray_icon_action
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
    self.menu.aboutToShow.connect(self._update_menu)
    self.setContextMenu(self.menu)

  def _create_monitor(self) -> None:
    self.monitor = StreamMonitor(self.cfg)
    self.monitor.stream_online.connect(self._on_stream_online)
    self.monitor.stream_offline.connect(self._on_stream_offline)
    self.monitor.start()

  def _update_menu(self) -> None:
    self.menu.clear()
    def create_stream_action(stream: Stream) -> QAction:
      action = QAction(stream.name, self.menu)
      if (pixmap := get_stream_icon(stream, 16)) is not None:
        action.setIcon(QIcon(pixmap))
      action.setData(stream)
      action.triggered.connect(lambda checked, s=stream: self._launch_stream(s))
      return action
    # add alive streams
    alive_streams = self.monitor.get_alive_streams()
    for stream in alive_streams:
      self.menu.addAction(create_stream_action(stream))
    if len(alive_streams) > 0:
      self.menu.addSeparator()
    # add always on streams
    perma_streams = self.monitor.get_perma_streams()
    for stream in perma_streams:
      self.menu.addAction(create_stream_action(stream))
    if len(perma_streams) > 0:
      self.menu.addSeparator()
    # add toggle monitoring
    toggle_monitoring = QAction('Monitoring', self.menu)
    toggle_monitoring.triggered.connect(self._toggle_monitoring)
    if not self.monitor.paused:
      toggle_monitoring.setIcon(self.icon_checked)
    self.menu.addAction(toggle_monitoring)
    # add toggle notifications
    toggle_notifications = QAction('Notifications', self.menu)
    toggle_notifications.triggered.connect(self._toggle_notifications)
    if self.notify:
      toggle_notifications.setIcon(self.icon_checked)
    self.menu.addAction(toggle_notifications)
    # add click action toggle submenu
    def set_tray_action(action: TrayIconAction) -> None:
      self.click = action
    tray_click_menu = self.menu.addMenu('Click Action')
    for tray_action in TrayIconAction:
      action = QAction(tray_action.display_name, tray_click_menu)
      action.triggered.connect(lambda checked, ta=tray_action: set_tray_action(ta))
      if tray_action == self.click:
        action.setIcon(self.icon_checked)
      tray_click_menu.addAction(action)
    # Settings
    self.menu.addSeparator()
    action_settings = QAction('Settings', self.menu)
    action_settings.triggered.connect(self._open_settings)
    self.menu.addAction(action_settings)
    # Quit
    self.menu.addSeparator()
    action_quit = QAction('Quit', self.menu)
    action_quit.triggered.connect(self._quit)
    self.menu.addAction(action_quit)

  def _update_icon(self) -> None:
    has_lives = self.monitor.live_streams_count() > 0
    has_vips = self.monitor.vips_streams_count() > 0
    self.setIcon(
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.OFF] if self.monitor.paused else
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.VIPS] if has_vips else
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.LIVE] if has_lives else
      self.tray_icons[self.cfg.tray_icon_color][TrayIconStatus.IDLE]
    )
    tooltip = ['StreamCondor']
    if self.monitor.paused:
      tooltip.append('OFF (not checking streams)')
    elif has_lives or has_vips:
      count = self.monitor.live_streams_count()
      tooltip.append(f'{count} stream(s) online')
    self.setToolTip('\n'.join(tooltip))

  def _launch_stream(self, stream: Stream) -> None:
    launch_process(build_sl_command(self.cfg, stream))

  def _on_tray_action(self, reason: QSystemTrayIcon.ActivationReason) -> None:
    if reason != QSystemTrayIcon.ActivationReason.Trigger:
      pass
    elif self.click == TrayIconAction.OPEN_URL:
      self._open_url()
    elif self.click == TrayIconAction.OPEN_CONFIG:
      self._open_settings()
    elif self.click == TrayIconAction.TOGGLE_MONITORING:
      self._toggle_monitoring()
    elif self.click == TrayIconAction.TOGGLE_NOTIFICATIONS:
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

  def _toggle_monitoring(self) -> None:
    if self.monitor.paused:
      self.monitor.resume()
    else:
      self.monitor.pause()
    self._update_icon()

  def _toggle_notifications(self) -> None:
    self.notify = not self.notify
    self._update_icon()

  def _open_url(self) -> None:
    stream_url = _check_url(pyperclip.paste().strip())  ## QApplication.clipboard() doesn't work in this class, idk why
    if stream_url is None or stream_url == '':
      stream_url, ok = QInputDialog.getText(None, 'Open Stream', 'Enter stream URL:')
      if not ok or not stream_url:
        return
    stream = self.cfg.streams.get(stream_url)
    if stream is None:
      stream_type, is_live = is_stream_live(stream_url, self.cfg.plugin_auth_args)  ## can throw NoPluginError
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

  def _open_settings(self) -> None:
    self.settings.show()
    self.settings.raise_()
    self.settings.activateWindow()

  def _quit(self) -> None:
    self.monitor.stop()
    self.monitor.wait()
    self.monitor.quit()
    QApplication.quit()

  def _on_stream_offline(self, stream: Stream) -> None:
    self._update_icon()


def _check_url(url: str) -> str:
  try:
    HttpUrl(url)
    return url
  except ValidationError:
    return None
