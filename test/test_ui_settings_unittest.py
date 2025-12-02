import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication


class TestUISettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_settings_window_toggle_notify(self):
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        tmp.write(json.dumps({'streams': {}, 'check_interval_mins': 60, 'autostart_monitoring': False, 'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}}))
        tmp.flush(); tmp.close()
        from streamcondor.model import Configuration
        cfg = Configuration(Path(tmp.name))
        from streamcondor.ui.settings import SettingsWindow
        win = SettingsWindow(cfg)
        # toggle default notify and ensure config.save called via set
        called = {'saved': False}
        def fake_save():
            called['saved'] = True
        cfg.save = fake_save
        # emulate user toggling
        win.check_default_notify.setChecked(not cfg.default_notify)
        self.assertTrue(called['saved'])
