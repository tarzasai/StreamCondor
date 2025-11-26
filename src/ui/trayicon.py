"""
System tray icon for StreamCondor.
"""
import logging
import pyperclip
from typing import Optional
from PyQt6.QtWidgets import (
  QSystemTrayIcon, QMenu, QInputDialog, QApplication
)
from PyQt6.QtGui import QIcon, QAction

from configuration import Configuration, TrayClickAction
from monitor import StreamMonitor
from launcher import StreamLauncher
from favicons import Favicons
from resources import get_asset_path
from sluser import sls
from ui.settings import SettingsWindow


log = logging.getLogger(__name__)


class TrayIcon(QSystemTrayIcon):
  """System tray icon with context menu and notifications."""

  def __init__(self, parent, config_path: str):
    super().__init__(parent)
    self.cfg = Configuration(config_path)
    self.favicons = Favicons()
    self.settings_window: Optional[SettingsWindow] = None
    self.streamlink_launcher = StreamLauncher(self.cfg)
    self.monitoring_active = self.cfg.autostart_monitoring
    self.monitor = StreamMonitor(self.cfg)
    self.monitor.stream_online.connect(self._on_stream_online)
    self.monitor.stream_offline.connect(self._on_stream_offline)
    self.monitor.start()
    self._load_icons()
    self._create_menu()
    self.setToolTip('StreamCondor')
    self.activated.connect(self._on_left_click)


  def _load_icons(self) -> None:
    # Create checkbox icons
    self.icon_checked = QIcon.fromTheme('ok', QIcon.fromTheme('dialog-ok'))
    self.icon_unchecked = QIcon.fromTheme('emblem-none', QIcon.fromTheme('dialog-cancel'))
    # Load tray state icons from assets directory using resources module
    # This works both in development and when installed as a package
    icon_path = get_asset_path('icon_monitoring_off.png')
    self.icon_monitoring_off = QIcon(str(icon_path)) if icon_path.exists() else QIcon.fromTheme('media-playback-pause')
    icon_path = get_asset_path('icon_monitoring_idle.png')
    self.icon_monitoring_idle = QIcon(str(icon_path)) if icon_path.exists() else QIcon.fromTheme('applications-multimedia')
    icon_path = get_asset_path('icon_monitoring_live.png')
    self.icon_monitoring_live = QIcon(str(icon_path)) if icon_path.exists() else QIcon.fromTheme('emblem-important')
    icon_path = get_asset_path('icon_monitoring_idle_muted.png')
    self.icon_monitoring_idle_muted = QIcon(str(icon_path)) if icon_path.exists() else QIcon.fromTheme('applications-multimedia')
    icon_path = get_asset_path('icon_monitoring_live_muted.png')
    self.icon_monitoring_live_muted = QIcon(str(icon_path)) if icon_path.exists() else QIcon.fromTheme('emblem-important')
    # Set initial icon
    self._update_tray_icon()

  def _create_menu(self) -> None:
    self.menu = QMenu()
    # Open URL action
    self.action_open_url = QAction('Open URL', self.menu)
    self.action_open_url.triggered.connect(self._open_url)
    self.menu.addAction(self.action_open_url)
    # Separator before online streams
    self.list_top_sep = self.menu.addSeparator()
    # Online streams will be added above this separator
    self.menu.addSeparator()
    # Toggle monitoring
    self.action_toggle_monitoring = QAction('Monitoring', self.menu)
    self.action_toggle_monitoring.triggered.connect(self._toggle_monitoring)
    self.menu.addAction(self.action_toggle_monitoring)
    # Toggle notifications
    self.action_toggle_notifications = QAction('Notifications', self.menu)
    self.action_toggle_notifications.triggered.connect(self._toggle_notifications)
    self.menu.addAction(self.action_toggle_notifications)
    self.menu.addSeparator()
    # Settings
    action_settings = QAction('Settings', self.menu)
    action_settings.triggered.connect(self._open_settings)
    self.menu.addAction(action_settings)
    # Quit
    action_quit = QAction('Quit', self.menu)
    action_quit.triggered.connect(self._quit)
    self.menu.addAction(action_quit)
    # Finish
    self.setContextMenu(self.menu)
    self.menu.aboutToShow.connect(self._on_menu_before_show)

  def _open_url(self) -> None:
    stream_url = pyperclip.paste().strip()  ## QApplication.clipboard() doesn't work in this class, idk why
    if stream_url is None or stream_url == '':
      stream_url, ok = QInputDialog.getText(None, 'Open Stream', 'Enter stream URL:')
      if not ok or not stream_url:
        return
    meta = sls.resolve_url(stream_url)  ## if the url is not a
    stream_type = meta[0]
    stream_name = 'Unknown'
    self.streamlink_launcher.launch_stream({
      'url': stream_url,
      'type': stream_type,
      'name': stream_name,
    })

  def _launch_stream(self, stream: dict) -> None:
    self.streamlink_launcher.launch_stream(stream)

  def _toggle_monitoring(self) -> None:
    self.monitoring_active = not self.monitoring_active
    if self.monitoring_active:
      self.monitor.resume()
    else:
      self.monitor.pause()
    self._update_tray_icon()

  def _toggle_notifications(self) -> None:
    enabled = self.cfg.default_notify
    self.cfg.default_notify = not enabled
    self._update_tray_icon()

  def _open_settings(self) -> None:
    if self.settings_window is None:
      self.settings_window = SettingsWindow(
        self.cfg,
        self.favicons,
        self.streamlink_launcher
      )
    self.settings_window.show()
    self.settings_window.raise_()
    self.settings_window.activateWindow()

  def _quit(self) -> None:
    self.monitor.stop()
    self.monitor.wait()
    self.monitor.quit()
    QApplication.quit()

  def _update_tray_icon(self) -> None:
    """Update tray icon based on monitoring state, streams status, and notification settings."""
    online_streams = self.monitor.get_online_streams()
    has_live_streams = len(online_streams) > 0
    notifications_enabled = self.cfg.default_notify
    # Update icon
    if not self.monitoring_active:
      # Monitoring off
      self.setIcon(self.icon_monitoring_off)
    elif has_live_streams and not notifications_enabled:
      # Monitoring on, streams live, notifications muted
      self.setIcon(self.icon_monitoring_live_muted)
    elif has_live_streams:
      # Monitoring on, streams live, notifications enabled
      self.setIcon(self.icon_monitoring_live)
    elif not notifications_enabled:
      # Monitoring on, no streams live, notifications muted
      self.setIcon(self.icon_monitoring_idle_muted)
    else:
      # Monitoring on, no streams live, notifications enabled
      self.setIcon(self.icon_monitoring_idle)
    # Update tooltip
    tooltip = ['StreamCondor']
    if not self.monitoring_active:
      tooltip.append('IDLE (monitoring is off)')
    elif has_live_streams:
      tooltip.append(f'{len(online_streams)} stream(s) online!')
    self.setToolTip('\n'.join(tooltip))

  def _on_menu_before_show(self) -> None:
    # Update toggle icons
    self.action_toggle_monitoring.setIcon(self.icon_checked if self.monitoring_active else self.icon_unchecked)
    default_notify = self.cfg.default_notify
    self.action_toggle_notifications.setIcon(self.icon_checked if default_notify else self.icon_unchecked)
    # Update online streams in menu
    all_actions = self.menu.actions()
    start_index = all_actions.index(self.list_top_sep) + 1
    end_index = all_actions.index(self.action_toggle_monitoring)
    for i in range(start_index, end_index):
      self.menu.removeAction(all_actions[i])
    online_streams = self.monitor.get_online_streams()
    for stream in online_streams:
      name = stream.get('name', stream.get('url', 'Unknown'))
      action = QAction(name, self.menu)
      stream_type = stream.get('type', 'unknown')
      if (pixmap := self.favicons.get_favicon(stream_type, 16)) is not None:
        action.setIcon(QIcon(pixmap))
      action.triggered.connect(lambda checked, s=stream: self._launch_stream(s))
      self.menu.insertAction(self.action_toggle_monitoring, action)
    if len(online_streams) > 0:
      self.menu.insertSeparator(self.action_toggle_monitoring)

  def _on_left_click(self, reason: QSystemTrayIcon.ActivationReason) -> None:
    if reason == QSystemTrayIcon.ActivationReason.Trigger:  ## Left click
      action = self.cfg.left_click_action
      if action == TrayClickAction.OPEN_CONFIG:
        self._open_settings()
      elif action == TrayClickAction.OPEN_URL:
        self._open_url()
      elif action == TrayClickAction.TOGGLE_MONITORING:
        self._toggle_monitoring()
      elif action == TrayClickAction.TOGGLE_NOTIFICATIONS:
        self._toggle_notifications()
      # LeftClickAction.NOTHING does nothing

  def _on_stream_online(self, stream: dict) -> None:
    self._update_tray_icon()
    if stream.get('notify', self.cfg.default_notify) and self.supportsMessages():
      self.showMessage(
        'Stream Online',
        f'{stream.get("name")} is now live on {stream.get("type")}!',
        QSystemTrayIcon.MessageIcon.Information,
        5000
      )

  def _on_stream_offline(self, stream: dict) -> None:
    self._update_tray_icon()

