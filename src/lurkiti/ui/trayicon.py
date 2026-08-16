import logging
import pyperclip
from pathlib import Path
from pydantic import HttpUrl, ValidationError
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QInputDialog, QApplication

from lurkiti.model import Configuration, TrayIconStatus, TrayIconAction, Stream
from lurkiti.monitor import StreamMonitor
from lurkiti.session import is_stream_live
from lurkiti.command import launch_process, build_launch_command
from lurkiti.favicons import get_stream_icon
from lurkiti.ui.settings import SettingsWindow

log = logging.getLogger(__name__)


class TrayIcon(QSystemTrayIcon):

  def __init__(self, parent, config_path: str):
    super().__init__(parent)
    if not config_path:
      config_dir = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.ConfigLocation
      ))
      config_path = config_dir / 'Lurkiti.json'
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
    log.info('Lurkiti started')

  def _create_icons(self) -> None:
    icons_dir = Path(__file__).resolve().parent.parent / 'resources' / 'icons'
    self.tray_icons = {
      TrayIconStatus.OFF: QIcon(str(icons_dir / 'app-off.png')),
      TrayIconStatus.IDLE: QIcon(str(icons_dir / 'app-idle.png')),
      TrayIconStatus.LIVE: QIcon(str(icons_dir / 'app-live.png')),
      TrayIconStatus.VIPS: QIcon(str(icons_dir / 'app-vips.png')),
    }
    # Initial tray icon
    self.setIcon(self.tray_icons[TrayIconStatus.OFF])
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
    def add_stream_actions(streams: list[Stream], menu: QMenu) -> None:
      for stream in streams:
        menu.addAction(create_stream_action(stream))
    # add alive streams
    alive_streams = self.monitor.get_alive_streams()
    add_stream_actions(alive_streams, self.menu)
    if len(alive_streams) > 0:
      self.menu.addSeparator()
    # add always on streams
    perma_streams = self.monitor.get_perma_streams()
    if (self.cfg.always_on_submenu or len(alive_streams) > 10) and len(perma_streams) > 0:
      perma_menu = self.menu.addMenu('Always Live')
      perma_icon = QIcon.fromTheme('network-wireless', QIcon.fromTheme('network-transmit-receive'))
      if not perma_icon.isNull():
        perma_menu.setIcon(perma_icon)
      add_stream_actions(perma_streams, perma_menu)
    else:
      add_stream_actions(perma_streams, self.menu)
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
      self.tray_icons[TrayIconStatus.OFF] if self.monitor.paused else
      self.tray_icons[TrayIconStatus.VIPS] if has_vips else
      self.tray_icons[TrayIconStatus.LIVE] if has_lives else
      self.tray_icons[TrayIconStatus.IDLE]
    )
    tooltip = ['Lurkiti']
    if self.monitor.paused:
      tooltip.append('OFF (not checking streams)')
    elif has_lives or has_vips:
      count = self.monitor.live_streams_count()
      tooltip.append(f'{count} stream(s) online')
    self.setToolTip('\n'.join(tooltip))

  def _launch_stream(self, stream: Stream) -> None:
    self.cfg.mark_stream_watched(stream.url)
    launch_process(build_launch_command(self.cfg, stream))

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
    self.cfg.mark_stream_online(stream.url)
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
      stream_type, is_live = is_stream_live(stream_url)  ## can throw NoPluginError
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
    self.cfg.mark_stream_offline(stream.url)
    self._update_icon()


def _check_url(url: str) -> str:
  try:
    HttpUrl(url)
    return url
  except ValidationError:
    return None
