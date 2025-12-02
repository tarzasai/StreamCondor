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


def test_stream_preview_updates(app, tmp_path, mock_sls):
    from streamcondor.model import Configuration
    from streamcondor.ui.stream import StreamDialog
    cfg_path = write_tmp_config(tmp_path)
    cfg = Configuration(Path(cfg_path))
    # patch sls.resolve_url so dialog creation and updates won't call real Streamlink
    with mock_sls(resolve_return=('youtube',)) as mock_sls_obj:
        # create dialog and fill fields while patched
        dlg = StreamDialog(None, cfg)
        dlg.text_url.setText('https://example.com/video')
    # set some fields and update preview
    dlg.text_name.setText('Test')
    dlg.text_quality.setText('best')
    dlg.text_player.setText('mpv')
    dlg.text_sl_args.setPlainText('--opt val')
    dlg._update_preview()
    preview = dlg.text_preview.toPlainText()
    assert 'streamlink' in preview
    assert 'https://example.com/video' in preview
from streamcondor.model import Stream


def test_stream_dialog_load_and_get_stream(qtbot):
    # Create a Stream instance to edit
    s = Stream(url='https://py.example/', name='Py', type='py', quality='best', notify=True)
    # Create a minimal Configuration object backed by a temp file
    import tempfile, json
    from pathlib import Path
    tmp = tempfile.NamedTemporaryFile('w+', delete=False)
    json.dump({'streams': {}, 'check_interval_mins': 1, 'autostart_monitoring': False}, tmp)
    tmp.flush(); tmp.close()
    from streamcondor.model import Configuration
    from streamcondor.ui.stream import StreamDialog
    cfg = Configuration(Path(tmp.name))
    dlg = StreamDialog(None, cfg, stream=s)
    qtbot.addWidget(dlg)
    dlg.show()
    # Ensure fields are populated
    assert dlg.text_url.text() == s.url
    assert dlg.text_name.text() == s.name
    # Simulate user changing name
    dlg.text_name.setText('PyChanged')
    # Accept the dialog and read back stream
    from PyQt6.QtWidgets import QDialogButtonBox
    ok_btn = dlg.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    from PyQt6.QtCore import Qt
    qtbot.mouseClick(ok_btn, Qt.MouseButton.LeftButton)
    new_s = dlg.get_stream()
    assert new_s.name == 'PyChanged'
