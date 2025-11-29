import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QDialogButtonBox
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

from streamcondor.model import Stream


class TestUIStreamDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_stream_dialog_accepts_and_returns_stream(self):
        # prepare config file
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        json.dump({'streams': {}, 'check_interval': 60, 'autostart_monitoring': False, 'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}}, tmp)
        tmp.flush(); tmp.close()
        from streamcondor.model import Configuration
        cfg = Configuration(Path(tmp.name))
        s = Stream(url='https://un.example/', name='U', type='u', quality='best', notify=True)
        from streamcondor.ui.stream import StreamDialog
        dlg = StreamDialog(None, cfg, stream=s)
        # ensure fields populated
        self.assertEqual(dlg.text_url.text(), s.url)
        self.assertEqual(dlg.text_name.text(), s.name)
        # change name
        dlg.text_name.setText('U2')
        ok_btn = dlg.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        QTest.mouseClick(ok_btn, Qt.MouseButton.LeftButton)
        new_s = dlg.get_stream()
        self.assertEqual(new_s.name, 'U2')
