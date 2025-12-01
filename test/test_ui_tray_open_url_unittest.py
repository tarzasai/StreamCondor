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
        from streamcondor.ui.trayicon import _check_url
        self.assertEqual(_check_url('https://example.com'), 'https://example.com')
        self.assertIsNone(_check_url('not-a-url'))

    @patch('streamcondor.ui.trayicon.build_sl_command')
    @patch('streamcondor.ui.trayicon.launch_process')
    @patch('streamcondor.ui.trayicon.is_stream_live')
    @patch('streamcondor.ui.trayicon.pyperclip')
    def test_open_url_uses_clipboard_and_launches(self, mock_clip, mock_is_live, mock_launch, mock_build):
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        tmp.write(json.dumps({'streams': {}, 'check_interval': 60, 'autostart_monitoring': False, 'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}}))
        tmp.flush(); tmp.close()
        from streamcondor.model import Configuration
        cfg = Configuration(Path(tmp.name))
        from streamcondor.ui.trayicon import TrayIcon
        # prepare mocks using helpers
        from test.test_helpers import mock_sls, mock_is_stream_live
        mock_clip.paste.return_value = 'https://x'
        mock_build.return_value = ['streamlink', 'https://x']
        mock_launch.return_value = True

        with mock_is_stream_live(return_value=('youtube', True)):
            with mock_sls(resolve_return=('youtube',)):
                ti = TrayIcon(None, str(cfg.config_path))
                try:
                    ti._open_url()
                    mock_launch.assert_called()
                finally:
                    ti.monitor.stop()
                    ti.monitor.wait()
                    ti.monitor.quit()
