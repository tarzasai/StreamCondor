import unittest
import json
from pathlib import Path
from model import Configuration, Stream


class TestConfigurationLoadSave(unittest.TestCase):
    def test_configuration_load_save(self, tmp_path=None):
        # Use tmp_path if provided by pytest, otherwise create a temporary file
        if tmp_path is None:
            from tempfile import TemporaryDirectory
            td = TemporaryDirectory()
            cfg_path = Path(td.name) / 'cfg.json'
        else:
            cfg_path = Path(tmp_path) / 'cfg.json'
        data = {
            'autostart_monitoring': False,
            'default_notify': True,
            'check_interval': 60,
            'default_streamlink_args': '',
            'default_quality': 'best',
            'default_media_player': '',
            'default_media_player_args': '',
            'tray_icon_action': 'open_config',
            'streams': {
                'https://example.com/stream': {
                    'url': 'https://example.com/stream',
                    'name': 'Example',
                    'type': 'twitch',
                    'quality': 'best',
                    'player': 'mpv',
                    'notify': True
                }
            }
        }
        cfg_path.write_text(json.dumps(data))
        cfg = Configuration(cfg_path)
        streams = cfg.streams
        # streams should be a dict mapping URL -> Stream
        self.assertIsInstance(streams, dict)
        s = streams.get('https://example.com/stream')
        self.assertIsInstance(s, Stream)
        self.assertEqual(s.url, 'https://example.com/stream')
        # modify and save
        s.name = 'Changed'
        cfg.save()
        loaded = json.loads(cfg_path.read_text())
        self.assertEqual(loaded['streams']['https://example.com/stream']['name'], 'Changed')


if __name__ == '__main__':
    unittest.main()
