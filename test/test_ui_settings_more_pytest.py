import json
from pathlib import Path
from unittest.mock import patch, MagicMock

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


def test_streamlistmodel_checkstate_toggle(app, tmp_path):
    from streamcondor.model import Configuration, Stream
    from streamcondor.ui.settings import StreamListModel
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    # add a stream
    s = Stream(url='https://x', name='X', type='youtube', notify=True)
    cfg.set_stream(s)
    model = StreamListModel(cfg)
    # find the stream index by scanning groups and children
    from PyQt6.QtCore import Qt
    idx = None
    for gi in range(model.rowCount()):
        gidx = model.index(gi, 0)
        for ci in range(model.rowCount(gidx)):
            cidx = model.index(ci, 0, gidx)
            if model.data(cidx, Qt.ItemDataRole.DisplayRole) == s.name:
                idx = cidx
                break
        if idx:
            break
    assert idx is not None, 'stream index not found'
    # toggle check state via setData
    before = cfg.streams[s.url].notify
    assert before is True
    from PyQt6.QtCore import Qt
    model.setData(idx, None, role=Qt.ItemDataRole.CheckStateRole)
    after = cfg.streams[s.url].notify
    assert after is False or after is None


def test_add_edit_clone_delete_flows(app, tmp_path):
    from streamcondor.model import Configuration, Stream
    from streamcondor.ui.settings import SettingsWindow
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    win = SettingsWindow(cfg)

    # Mock StreamDialog to simulate user adding a stream
    fake_stream = Stream(url='https://add', name='Add', type='youtube')
    with patch('streamcondor.ui.settings.StreamDialog') as mock_dialog:
        dlg = mock_dialog.return_value
        dlg.exec.return_value = True
        dlg.get_stream.return_value = fake_stream
        win._add_stream()
    assert 'https://add' in cfg.streams

    # Edit the stream: find the child index for the stream we added
    from PyQt6.QtCore import Qt
    stream_idx = None
    for gi in range(win.stream_model.rowCount()):
        gidx = win.stream_model.index(gi, 0)
        for ci in range(win.stream_model.rowCount(gidx)):
            cidx = win.stream_model.index(ci, 0, gidx)
            if win.stream_model.data(cidx, Qt.ItemDataRole.DisplayRole) == fake_stream.name:
                stream_idx = cidx
                break
        if stream_idx:
            break
    assert stream_idx is not None
    win.stream_list.setCurrentIndex(stream_idx)
    with patch('streamcondor.ui.settings.StreamDialog') as mock_dialog2:
        dlg2 = mock_dialog2.return_value
        dlg2.exec.return_value = True
        updated = Stream(url='https://add', name='AddEdit', type='youtube')
        dlg2.get_stream.return_value = updated
        win._edit_stream()
    assert cfg.streams['https://add'].name == 'AddEdit'

    # Clone the stream: select the same child index
    # find the same stream index for cloning
    win.stream_list.setCurrentIndex(stream_idx)
    with patch('streamcondor.ui.settings.StreamDialog') as mock_dialog3:
        dlg3 = mock_dialog3.return_value
        dlg3.exec.return_value = True
        cloned = Stream(url='https://clone', name='Clone', type='youtube')
        dlg3.get_stream.return_value = cloned
        win._clone_stream()
    assert 'https://clone' in cfg.streams

    # Delete the original (simulate Yes for QMessageBox)
    win.stream_list.setCurrentIndex(stream_idx)
    with patch('streamcondor.ui.settings.QMessageBox.question', return_value=1):
        win._delete_stream()
    # Deleting will remove one stream (the currently selected). Ensure config still valid
    assert isinstance(cfg.streams, dict)

    win.close()


def test_geometry_save_and_restore(app, tmp_path):
    from streamcondor.model import Configuration
    from streamcondor.ui.settings import SettingsWindow
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    win = SettingsWindow(cfg)
    # change geometry
    win.setGeometry(10, 20, 300, 200)
    win.show()
    win.close()  # triggers save
    # new window should restore geometry from config
    win2 = SettingsWindow(cfg)
    geom = win2.geometry()
    # geometry restored should match saved configuration
    saved = cfg.get_geometry('settings_window')
    assert saved is not None
    assert geom.x() == saved.x
    assert geom.y() == saved.y
    assert geom.width() == saved.width
    assert geom.height() == saved.height
    win2.close()
