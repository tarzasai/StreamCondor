import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def write_tmp_config(tmp_path):
    cfgf = tmp_path / 'cfg.json'
    cfgf.write_text(json.dumps({
        'streams': {}, 'check_interval': 60, 'autostart_monitoring': False,
        'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}
    }))
    return cfgf


def test_tray_update_menu_adds_online_streams(app, tmp_path):
    from streamcondor.model import Configuration, Stream
    from streamcondor.ui.trayicon import TrayIcon
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    with patch('streamcondor.ui.trayicon.get_stream_icon') as mock_fav:
        mock_fav.return_value = None
        ti = TrayIcon(None, str(cfg.config_path))
        # inject fake online streams into monitor
        fake = Stream(url='https://x', name='X', type='youtube')
        ti.monitor.get_online_streams = MagicMock(return_value=[fake])
        ti._update_menu()
        actions = [a.text() for a in ti.menu.actions() if a.text()]
        assert 'X' in actions
        ti.monitor.stop(); ti.monitor.wait(); ti.monitor.quit()
import json
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

from PyQt6.QtCore import Qt


def _make_cfg(tmp_path):
    tmp = tmp_path / 'cfg.json'
    tmp.write_text(json.dumps({
        'streams': {},
        'check_interval': 60,
        'autostart_monitoring': False,
        'windows': {'settings_window': {'x': 100, 'y': 100, 'width': 700, 'height': 600}}
    }))
    from streamcondor.model import Configuration
    return Configuration(Path(tmp))


def test_tray_toggle_and_notifications(qtbot, tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    # Monkeypatch configuration loading to use our cfg path by writing its path string
    from streamcondor.ui.trayicon import TrayIcon
    # Create a temporary app parent widget
    parent = None
    # Use a small config file path
    ti = TrayIcon(parent, str(cfg.config_path))

    # Toggle notifications
    orig = ti.notify
    ti._toggle_notifications()
    assert ti.notify != orig

    # Toggle monitoring (pause/resume)
    was_paused = ti.monitor.paused
    ti._toggle_monitoring()
    assert ti.monitor.paused != was_paused

    # Simulate an online stream signal and ensure showMessage is called when notify True
    s = MagicMock()
    s.name = 'X'
    s.type = 't'
    s.notify = True
    # Patch supportsMessages to True and showMessage to capture
    monkeypatch.setattr(ti, 'supportsMessages', lambda: True)
    called = {'msg': False}
    def fake_show(*args, **kwargs):
        called['msg'] = True
    ti.showMessage = fake_show
    ti.notify = True
    ti._on_stream_online(s)
    assert called['msg']
