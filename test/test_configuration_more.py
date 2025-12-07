import unittest
import json
from pathlib import Path
from streamcondor.model import Configuration, Stream, TrayIconColor, TrayIconAction

class TestConfigurationMore(unittest.TestCase):
    def test_setters_and_persistence(self):
        # Create a minimal config file
        cfg_data = Configuration.__annotations__ if False else {
            'autostart_monitoring': False,
            'check_interval_mins': 60,
            'default_notify': False,
            'default_streamlink_args': '',
            'default_quality': 'best',
            'default_player': '',
            'default_player_args': '',
            'tray_icon_color': TrayIconColor.WHITE.value,
            'tray_icon_action': TrayIconAction.NOTHING.value,
            'streams': {}
        }
        tmp = Path('test_tmp_cfg.json')
        tmp.write_text(json.dumps(cfg_data))
        try:
            cfg = Configuration(tmp)
            cfg.autostart_monitoring = True
            cfg.default_notify = True
            cfg.default_streamlink_args = '--flag'
            cfg.default_quality = '720p'
            cfg.default_player = 'vlc'
            cfg.default_player_args = '--no-border'
            cfg.tray_icon_color = TrayIconColor.BLACK
            cfg.tray_icon_action = TrayIconAction.OPEN_URL
            cfg.check_interval_mins = 123
            # verify properties
            self.assertTrue(cfg.autostart_monitoring)
            self.assertTrue(cfg.default_notify)
            self.assertEqual(cfg.default_streamlink_args, '--flag')
            self.assertEqual(cfg.default_quality, '720p')
            self.assertEqual(cfg.default_player, 'vlc')
            self.assertEqual(cfg.default_player_args, '--no-border')
            self.assertEqual(cfg.tray_icon_color, TrayIconColor.BLACK)
            self.assertEqual(cfg.tray_icon_action, TrayIconAction.OPEN_URL)
            self.assertEqual(cfg.check_interval_mins, 123)
            # stream operations
            s = Stream(url='https://x/', name='X', type='t')
            cfg.set_stream(s)
            self.assertIn('https://x/', cfg.streams)
            got = cfg.get_stream('https://x/')
            self.assertIsNotNone(got)
            self.assertEqual(got.name, 'X')
            cfg.del_stream(s)
            self.assertNotIn('https://x/', cfg.streams)
        finally:
            try:
                tmp.unlink()
            except Exception:
                pass

    def test_empty_string_to_none_validator(self):
        s = Stream(url='u', name='', type='t')
        # name should be converted to None by validator
        self.assertIsNone(s.name)

if __name__ == '__main__':
    unittest.main()
