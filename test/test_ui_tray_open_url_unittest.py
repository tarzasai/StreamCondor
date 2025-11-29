import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication


class TestTrayOpenUrl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_check_url_helper(self):
        from ui.trayicon import _check_url
        self.assertEqual(_check_url('https://example.com'), 'https://example.com')
        self.assertIsNone(_check_url('not-a-url'))

    @patch('ui.trayicon.build_sl_command')
    @patch('ui.trayicon.launch_process')
    @patch('ui.trayicon.sls')
    @patch('ui.trayicon.pyperclip')
    def test_open_url_uses_clipboard_and_launches(self, mock_clip, mock_sls, mock_launch, mock_build):
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        tmp.write(json.dumps({'streams': {}, 'check_interval': 60, 'autostart_monitoring': False, 'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}}))
        tmp.flush(); tmp.close()
        from model import Configuration
        cfg = Configuration(Path(tmp.name))
        from ui.trayicon import TrayIcon
        # prepare mocks
        mock_clip.paste.return_value = 'https://x'
        mock_sls.resolve_url.return_value = ('youtube',)
        mock_build.return_value = ['streamlink', 'https://x']
        mock_launch.return_value = True

        ti = TrayIcon(None, str(cfg.config_path))
        try:
            ti._open_url()
            mock_launch.assert_called()
        finally:
            ti.monitor.stop()
            ti.monitor.wait()
            ti.monitor.quit()
