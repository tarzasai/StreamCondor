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
        'streams': {}, 'check_interval_mins': 60, 'autostart_monitoring': False,
        'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}
    }))
    return cfgf


def test_settings_toggle_notify_changes_icon(app, tmp_path):
    from lurkiti.model import Configuration
    from lurkiti.ui.settings import SettingsWindow
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    win = SettingsWindow(cfg)
    orig = win.cfg.default_notify
    # toggle via checkbox to simulate user action
    win.check_default_notify.setChecked(not orig)
    assert win.cfg.default_notify != orig
    # cleanup
    win.close()


def test_settings_exposes_tray_click_action_selector(app, tmp_path):
    from lurkiti.model import Configuration, TrayIconAction
    from lurkiti.ui.settings import SettingsWindow

    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    win = SettingsWindow(cfg)
    try:
        actions = [win.combo_tray_icon_action.itemData(i) for i in range(win.combo_tray_icon_action.count())]
        assert actions == list(TrayIconAction)

        win.combo_tray_icon_action.setCurrentIndex(actions.index(TrayIconAction.OPEN_CONFIG))
        assert cfg.tray_icon_action == TrayIconAction.OPEN_CONFIG
    finally:
        win.close()


def test_settings_updates_clippiti_path(app, tmp_path):
    from lurkiti.model import Configuration
    from lurkiti.ui.settings import SettingsWindow

    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    win = SettingsWindow(cfg)
    try:
        win.text_clippiti_path.setText('/usr/local/bin/clippiti')
        assert cfg.clippiti_path == '/usr/local/bin/clippiti'
        win.text_clippiti_path.setText('')
        assert cfg.clippiti_path is None
    finally:
        win.close()
import pytest
import tempfile
import json
from pathlib import Path
from lurkiti.model import Stream

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QToolButton


def _make_cfg(tmp_path):
    tmp = tmp_path / 'cfg.json'
    tmp.write_text(json.dumps({
        'streams': {
            'https://a.example/': {'url': 'https://a.example/', 'name': 'A', 'type': 't1', 'notify': True},
            'https://b.example/': {'url': 'https://b.example/', 'name': 'B', 'type': 't2', 'notify': False},
        },
        'check_interval_mins': 60,
        'autostart_monitoring': False,
        'windows': {'settings_window': {'x': 100, 'y': 100, 'width': 700, 'height': 600}}
    }))
    from lurkiti.model import Configuration
    return Configuration(Path(tmp))


def test_settings_load_and_toggle_stream_notify(app, tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    from lurkiti.ui.settings import SettingsWindow
    win = SettingsWindow(cfg)
    try:
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
    finally:
        win.close()


def test_stream_action_toolbutton_click_keeps_selection(app, tmp_path):
    cfg = _make_cfg(tmp_path)
    from lurkiti.ui.settings import SettingsWindow
    from unittest.mock import patch

    win = SettingsWindow(cfg)
    try:
        model = win.stream_model
        index_group = model.index(0, 0)
        index_stream = model.index(0, 0, index_group)
        assert index_stream.isValid()

        win.stream_list.setCurrentIndex(index_stream)
        selection_model = win.stream_list.selectionModel()
        assert len(selection_model.selectedRows()) == 1
        assert isinstance(win.btn_edit, QToolButton)
        assert win.btn_edit.focusPolicy() == Qt.FocusPolicy.NoFocus

        with patch('lurkiti.ui.settings.StreamDialog') as mock_dialog:
            mock_dialog.return_value.exec.return_value = False
            win.btn_edit.click()  ## synchronous; avoids pytest-qt event-loop teardown that segfaults headless

        assert len(selection_model.selectedRows()) == 1
        assert selection_model.currentIndex() == index_stream
    finally:
        win.close()
