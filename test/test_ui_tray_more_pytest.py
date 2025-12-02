import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QSize


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def write_tmp_config(tmp_path):
    cfgf = tmp_path / 'cfg.json'
    cfgf.write_text(json.dumps({
        'streams': {}, 'check_interval_mins': 60, 'autostart_monitoring': False,
        'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}
    }))
    return cfgf


def test_update_icon_states(app, tmp_path):
    from streamcondor.model import Configuration, Stream
    from streamcondor.ui.trayicon import TrayIcon
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    ti = TrayIcon(None, str(cfg.config_path))
    try:
        # paused state
        ti.monitor.paused = True
        ti._update_icon()
        assert 'OFF (not checking streams)' in ti.toolTip()

        # no streams
        ti.monitor.paused = False
        ti.monitor.get_online_streams = MagicMock(return_value=[])
        ti._update_icon()
        assert 'StreamCondor' in ti.toolTip()

        # one live stream
        s = Stream(url='https://x', name='X', type='youtube', notify=False)
        ti.monitor.get_online_streams = MagicMock(return_value=[s])
        ti.monitor.live_streams_count = MagicMock(return_value=1)
        ti.monitor.vips_streams_count = MagicMock(return_value=0)
        ti._update_icon()
        assert 'stream(s) online' in ti.toolTip()

        # vip stream (notify True)
        sv = Stream(url='https://v', name='V', type='youtube', notify=True)
        ti.monitor.get_online_streams = MagicMock(return_value=[sv])
        ti.monitor.live_streams_count = MagicMock(return_value=1)
        ti.monitor.vips_streams_count = MagicMock(return_value=1)
        ti.notify = True
        ti._update_icon()
        assert 'stream(s) online' in ti.toolTip()
    finally:
        ti.monitor.stop(); ti.monitor.wait(); ti.monitor.quit()


def test_update_menu_with_favicons(app, tmp_path):
    from streamcondor.model import Configuration, Stream
    from streamcondor.ui.trayicon import TrayIcon
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    with patch('streamcondor.ui.trayicon.get_stream_icon') as mock_fav:
        # return a small pixmap
        pix = QPixmap(16, 16)
        pix.fill()
        mock_fav.return_value = pix
        ti = TrayIcon(None, str(cfg.config_path))
        try:
            s1 = Stream(url='https://a', name='A', type='youtube')
            s2 = Stream(url='https://b', name='B', type='youtube')
            ti.monitor.get_online_streams = MagicMock(return_value=[s1, s2])
            ti._update_menu()
            texts = [a.text() for a in ti.menu.actions() if a.text()]
            assert 'A' in texts and 'B' in texts
        finally:
            ti.monitor.stop(); ti.monitor.wait(); ti.monitor.quit()


def test_on_tray_icon_action_calls_methods(app, tmp_path):
    from streamcondor.model import Configuration
    from streamcondor.ui.trayicon import TrayIcon, TrayIconAction
    from PyQt6.QtWidgets import QSystemTrayIcon
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    ti = TrayIcon(None, str(cfg.config_path))
    try:
        # patch methods
        with patch.object(ti, '_open_settings') as mock_settings, \
             patch.object(ti, '_open_url') as mock_openurl, \
             patch.object(ti, '_toggle_monitoring') as mock_togglemon, \
             patch.object(ti, '_toggle_notifications') as mock_togglenot:
            ti.cfg.tray_icon_action = TrayIconAction.OPEN_CONFIG
            ti._on_tray_icon_action(QSystemTrayIcon.ActivationReason.Trigger)
            mock_settings.assert_called()

            ti.cfg.tray_icon_action = TrayIconAction.OPEN_URL
            ti._on_tray_icon_action(QSystemTrayIcon.ActivationReason.Trigger)
            mock_openurl.assert_called()

            ti.cfg.tray_icon_action = TrayIconAction.TOGGLE_MONITORING
            ti._on_tray_icon_action(QSystemTrayIcon.ActivationReason.Trigger)
            mock_togglemon.assert_called()

            ti.cfg.tray_icon_action = TrayIconAction.TOGGLE_NOTIFICATIONS
            ti._on_tray_icon_action(QSystemTrayIcon.ActivationReason.Trigger)
            mock_togglenot.assert_called()
    finally:
        ti.monitor.stop(); ti.monitor.wait(); ti.monitor.quit()


def test_open_url_cancel_noop(app, tmp_path):
    from streamcondor.model import Configuration
    from streamcondor.ui.trayicon import TrayIcon
    from PyQt6.QtWidgets import QInputDialog
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    ti = TrayIcon(None, str(cfg.config_path))
    try:
        with patch('streamcondor.ui.trayicon.pyperclip') as mock_clip, \
                 patch('streamcondor.ui.trayicon.QInputDialog.getText', return_value=('', False)):
            mock_clip.paste.return_value = ''
            # should not raise
            ti._open_url()
    finally:
        ti.monitor.stop(); ti.monitor.wait(); ti.monitor.quit()


def test_on_stream_online_shows_message(app, tmp_path):
    from streamcondor.model import Configuration, Stream
    from streamcondor.ui.trayicon import TrayIcon
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    ti = TrayIcon(None, str(cfg.config_path))
    try:
        s = Stream(url='https://x', name='X', type='youtube', notify=None)
        ti.notify = True
        with patch.object(ti, 'supportsMessages', return_value=True), \
             patch.object(ti, 'showMessage') as mock_show:
            ti._on_stream_online(s)
            mock_show.assert_called()
    finally:
        ti.monitor.stop(); ti.monitor.wait(); ti.monitor.quit()
