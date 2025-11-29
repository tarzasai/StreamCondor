import json
from pathlib import Path
from unittest.mock import patch

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


def test_settings_toggle_notify_changes_icon(app, tmp_path):
    from streamcondor.model import Configuration
    from streamcondor.ui.settings import SettingsWindow
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    win = SettingsWindow(cfg)
    orig = win.cfg.default_notify
    # toggle via checkbox to simulate user action
    win.check_default_notify.setChecked(not orig)
    assert win.cfg.default_notify != orig
    # cleanup
    win.close()
import pytest
import tempfile
import json
from pathlib import Path
from streamcondor.model import Stream

from PyQt6.QtCore import Qt


def _make_cfg(tmp_path):
    tmp = tmp_path / 'cfg.json'
    tmp.write_text(json.dumps({
        'streams': {
            'https://a.example/': {'url': 'https://a.example/', 'name': 'A', 'type': 't1', 'notify': True},
            'https://b.example/': {'url': 'https://b.example/', 'name': 'B', 'type': 't2', 'notify': False},
        },
        'check_interval': 60,
        'autostart_monitoring': False,
        'windows': {'settings_window': {'x': 100, 'y': 100, 'width': 700, 'height': 600}}
    }))
    from streamcondor.model import Configuration
    return Configuration(Path(tmp))


def test_settings_load_and_toggle_stream_notify(qtbot, tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    from streamcondor.ui.settings import SettingsWindow
    win = SettingsWindow(cfg)
    qtbot.addWidget(win)
    win.show()

    # Find first group and first child index
    model = win.stream_model
    # Expand and get the first stream node index
    index_group = model.index(0, 0)
    assert index_group.isValid()
    index_stream = model.index(0, 0, index_group)
    assert index_stream.isValid()

    # Read current check state
    state = model.data(index_stream, Qt.ItemDataRole.CheckStateRole)
    assert state in (Qt.CheckState.Checked, Qt.CheckState.Unchecked, Qt.CheckState.PartiallyChecked)

    # Toggle it via setData and ensure config.save() is called (monkeypatch)
    saved = {'called': False}
    def fake_save():
        saved['called'] = True
    monkeypatch.setattr(cfg, 'save', fake_save)
    assert model.setData(index_stream, None, Qt.ItemDataRole.CheckStateRole)
    assert saved['called']
