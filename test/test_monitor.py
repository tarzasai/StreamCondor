import unittest
from unittest.mock import patch, MagicMock
import time

from streamcondor.model import Configuration, Stream
from streamcondor.monitor import StreamMonitor


class TestMonitor(unittest.TestCase):
    def setUp(self):
        # Minimal configuration with two streams written to a temp file
        import tempfile
        import json
        from pathlib import Path

        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        cfg = {
            'streams': {
                'https://a.example/': {'url': 'https://a.example/', 'name': 'A', 'type': 't1'},
                'https://b.example/': {'url': 'https://b.example/', 'name': 'B', 'type': 't2'},
            },
            'check_interval_mins': 1,
            'autostart_monitoring': False
        }
        json.dump(cfg, tmp)
        tmp.flush()
        tmp.close()
        self.tmpfile = Path(tmp.name)
        self.cfg = Configuration(self.tmpfile)
        self.monitor = StreamMonitor(self.cfg)

    def test_check_single_stream_online_emits(self):
        from test.test_helpers import mock_is_stream_live
        # Simulate is_stream_live returning online
        with mock_is_stream_live(return_value=('youtube', True)):
            emitted = []
            self.monitor.stream_online.connect(lambda s: emitted.append(('online', s)))
            self.monitor._check_single_stream(self.cfg.streams['https://a.example/'])
            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0][0], 'online')

    def test_check_single_stream_offline_emits(self):
        from test.test_helpers import mock_is_stream_live
        # First set previous status to True, then simulate offline
        self.monitor.stream_status['https://a.example/'] = True
        with mock_is_stream_live(return_value=('youtube', False)):
            emitted = []
            self.monitor.stream_offline.connect(lambda s: emitted.append(('offline', s)))
            self.monitor._check_single_stream(self.cfg.streams['https://a.example/'])
            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0][0], 'offline')

    def test_check_streams_respects_interval_and_selects_oldest(self):
        from test.test_helpers import mock_is_stream_live
        # Make both streams appear online, call _check_streams twice with interval
        with mock_is_stream_live(return_value=('youtube', True)):
            # first call: both last_check are 0, should check one
            self.monitor._check_streams()
        # one stream should have a last_check set
        self.assertTrue(any(v > 0 for v in self.monitor.last_check_time.values()))
        # set both streams as just-checked and ensure no further checks occur
        now = time.time()
        for url in self.monitor.cfg.streams:
            self.monitor.last_check_time[url] = now
        prev = dict(self.monitor.last_check_time)
        self.monitor._check_streams()
        self.assertEqual(prev, self.monitor.last_check_time)

    def test_pause_resume_stop_and_get_online_streams(self):
        # Create simple config
        import tempfile, json
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        cfg = {
            'streams': {
                'https://x.example/': {'url': 'https://x.example/', 'name': 'X', 'type': 'a'},
                'https://y.example/': {'url': 'https://y.example/', 'name': 'Y', 'type': 'b'},
            },
            'check_interval_mins': 1,
            'autostart_monitoring': False
        }
        json.dump(cfg, tmp)
        tmp.flush(); tmp.close()
        from streamcondor.model import Configuration
        cfgobj = Configuration(Path(tmp.name))
        mon = StreamMonitor(cfgobj)
        # No streams online initially
        self.assertEqual(mon.get_online_streams(), [])
        # Set statuses and verify sorting by type then name
        mon.stream_status['https://y.example/'] = True
        mon.stream_status['https://x.example/'] = True
        online = mon.get_online_streams()
        self.assertEqual([s.url for s in online], ['https://x.example/', 'https://y.example/'])
        # Pause/resume/stop simple checks
        mon.pause()
        self.assertTrue(mon.paused)
        mon.resume()
        self.assertFalse(mon.paused)
        mon.stop()
        self.assertFalse(mon.running)

    def test_run_loop_and_exception_handling(self):
        # Patch msleep to avoid sleeping, and simulate an exception from sls
        import tempfile, json
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        cfg = {
            'streams': {
                'https://err.example/': {'url': 'https://err.example/', 'name': 'Err', 'type': 'err'},
            },
            'check_interval_mins': 0,
            'autostart_monitoring': True
        }
        json.dump(cfg, tmp)
        tmp.flush(); tmp.close()
        from streamcondor.model import Configuration
        cfgobj = Configuration(Path(tmp.name))
        mon = StreamMonitor(cfgobj)
        from test.test_helpers import mock_is_stream_live
        # Force is_stream_live to raise
        with mock_is_stream_live(side_effect=Exception('boom')):
            # Patch msleep to rapidly break the loop after one iteration
            called = {'count': 0}
            def fake_msleep(ms):
                called['count'] += 1
                if called['count'] > 1:
                    mon.stop()
            mon.msleep = fake_msleep
            # Run in current thread (not starting QThread) — should run a couple iterations and then stop
            mon.run()
            # Ensure that an attempt to check was made and we recorded a status (False)
            self.assertIn('https://err.example/', mon.stream_status)


if __name__ == '__main__':
    unittest.main()
