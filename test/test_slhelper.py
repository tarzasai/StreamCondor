import unittest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from lurkiti.model import Configuration, Stream
import lurkiti.command as slhelper

class DummyCfg:
    def __init__(self):
        self.default_streamlink_args = '--flag'
        self.default_player = 'mpv'
        self.default_player_args = '--no-border'
        self.alternate_player = 'vlc'
        self.alternate_player_args = '--fullscreen'
        self.default_quality = 'best'
        self.clippiti_path = None

class TestSlHelper(unittest.TestCase):
    def test_build_launch_command_basic(self):
        cfg = DummyCfg()
        s = Stream(url='https://example.com/stream', name='N', type='twitch', quality='best', player=None, sl_args='--http-no-ssl-verify', mp_args='--no-osc')
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[0], 'streamlink')
        self.assertIn('https://example.com/stream', cmd)

    def test_build_launch_command_player_args_are_raw_string(self):
        cfg = DummyCfg()
        s = Stream(
            url='https://example.com/stream',
            name='HannaDuval',
            type='livejasmin',
            quality='720p',
            player='mpv',
            sl_args='--http-no-ssl-verify',
            mp_args='--screenshot-template=$SC.name.%tY%tm%td%tH%tM%tS'
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertIn(
            '--player-args=--screenshot-template=HannaDuval.%tY%tm%td%tH%tM%tS',
            cmd
        )

    def test_build_launch_command_player_args_quotes_placeholder_with_spaces(self):
        cfg = DummyCfg()
        s = Stream(
            url='https://example.com/stream',
            name='2 strangers',
            type='livejasmin',
            quality='720p',
            player='mpv',
            sl_args='--http-no-ssl-verify',
            mp_args='--screenshot-template=$SC.name.%tY%tm%td%tH%tM%tS'
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertIn(
            "--player-args=--screenshot-template='2 strangers'.%tY%tm%td%tH%tM%tS",
            cmd
        )

    def test_build_launch_command_alt_player_ignores_default_player_args(self):
        cfg = DummyCfg()
        s = Stream(
            url='https://example.com/stream',
            name='N',
            type='twitch',
            quality='best',
            player='mpv',
            sl_args='',
            mp_args=None
        )
        cmd = slhelper.build_launch_command(cfg, s, alt_player=True)
        self.assertNotIn('--player-args=--no-border', cmd)
        self.assertFalse(any(item.startswith('--player-args=') for item in cmd))

    def test_build_launch_command_alt_player_uses_only_stream_player_args(self):
        cfg = DummyCfg()
        s = Stream(
            url='https://example.com/stream',
            name='N',
            type='twitch',
            quality='best',
            player='mpv',
            sl_args='',
            mp_args='--force-window=immediate'
        )
        cmd = slhelper.build_launch_command(cfg, s, alt_player=True)
        self.assertIn('--player-args=--force-window=immediate', cmd)
        self.assertNotIn('--player-args=--fullscreen', cmd)

    @patch('lurkiti.command.subprocess.Popen')
    def test_launch_process_success(self, mock_popen):
        mock_popen.return_value = MagicMock()
        ok = slhelper.launch_process(['echo', 'hi'])
        self.assertTrue(ok)
        mock_popen.assert_called()

    @patch('lurkiti.command.subprocess.Popen')
    def test_launch_process_keeps_list_tokens(self, mock_popen):
        mock_popen.return_value = MagicMock()
        ok = slhelper.launch_process(['streamlink', '--title', 'hello world'])
        self.assertTrue(ok)
        passed_tokens = mock_popen.call_args[0][0]
        self.assertIn('hello world', passed_tokens)

    @patch('lurkiti.command.subprocess.Popen', side_effect=Exception('boom'))
    def test_launch_process_failure(self, mock_popen):
        ok = slhelper.launch_process('bad command')
        self.assertFalse(ok)

    def test_build_launch_command_uses_clippiti_when_player_is_clippiti(self):
        cfg = DummyCfg()
        cfg.clippiti_path = '/usr/local/bin/clippiti'
        cfg.default_player_args = ''  # Clear default player args for this test
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='720p',
            player='clippiti',
            sl_args='--http-no-ssl-verify',
            mp_args=None
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[0], '/usr/local/bin/clippiti')
        self.assertIn('https://example.com/stream', cmd)
        # Quality is a comma-separated string like '720p,best'
        self.assertTrue(any('720p' in item for item in cmd))

    def test_build_launch_command_clippiti_includes_streamlink_args(self):
        cfg = DummyCfg()
        cfg.clippiti_path = '/usr/bin/clippiti'
        cfg.default_streamlink_args = '--retry-max 5 --stream-segment-timeout 20'
        cfg.default_player_args = ''  # Clear for this test
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='best',
            player='clippiti',
            sl_args='--http-no-ssl-verify',
            mp_args=None
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertIn('--', cmd)
        # Streamlink args are forwarded as individual tokens after the '--' separator
        sep_idx = cmd.index('--')
        sl_tokens = cmd[sep_idx + 1:]
        self.assertIn('--retry-max', sl_tokens)
        self.assertIn('5', sl_tokens)
        self.assertIn('--stream-segment-timeout', sl_tokens)
        self.assertIn('--http-no-ssl-verify', sl_tokens)

    def test_build_launch_command_clippiti_removes_title_from_streamlink_args(self):
        cfg = DummyCfg()
        cfg.clippiti_path = '/usr/bin/clippiti'
        cfg.default_streamlink_args = '--title "Stream Title" --retry-max 5'
        cfg.default_player_args = ''
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='best',
            player='clippiti',
            sl_args=None,
            mp_args=None
        )
        cmd = slhelper.build_launch_command(cfg, s)
        sep_idx = cmd.index('--')
        sl_tokens = cmd[sep_idx + 1:]
        self.assertNotIn('--title', sl_tokens)
        self.assertIn('--retry-max', sl_tokens)

    def test_build_launch_command_clippiti_includes_mpv_args(self):
        cfg = DummyCfg()
        cfg.clippiti_path = '/usr/bin/clippiti'
        cfg.default_player = 'mpv'  # Must be mpv to include args
        cfg.default_player_args = '--no-border'
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='best',
            player='clippiti',
            sl_args=None,
            mp_args='--force-window=immediate'
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertIn('--mpv', cmd)
        mpv_idx = cmd.index('--mpv')
        mpv_args = cmd[mpv_idx + 1]
        self.assertIn('--force-window=immediate', mpv_args)

    def test_build_launch_command_clippiti_omits_mpv_args_when_player_not_mpv(self):
        cfg = DummyCfg()
        cfg.clippiti_path = '/usr/bin/clippiti'
        cfg.default_player = 'vlc'  # Not mpv, so args should be omitted
        cfg.default_player_args = '--fullscreen'
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='best',
            player='clippiti',
            sl_args=None,
            mp_args=None
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertNotIn('--mpv', cmd)

    @patch('lurkiti.command.shutil.which', return_value=None)
    def test_build_launch_command_uses_streamlink_when_clippiti_path_not_set(self, mock_which):
        cfg = DummyCfg()
        cfg.clippiti_path = None  # Not set, and not found in PATH (mocked)
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='720p',
            player='clippiti',  # Even though player is clippiti, should use streamlink
            sl_args=None,
            mp_args=None
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertEqual(cmd[0], 'streamlink')
        mock_which.assert_called_with('clippiti')

    @patch('lurkiti.command.shutil.which', return_value='/usr/local/bin/clippiti')
    def test_build_launch_command_finds_clippiti_in_path(self, mock_which):
        cfg = DummyCfg()
        cfg.clippiti_path = None  # Not explicitly set, but found in PATH
        cfg.default_player = 'mpv'  # Must be mpv to include args
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='best',
            player='clippiti',
            sl_args=None,
            mp_args='--force-window=immediate'
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertEqual(cmd[0], '/usr/local/bin/clippiti')
        mock_which.assert_called_with('clippiti')

    def test_build_launch_command_uses_streamlink_when_player_is_not_clippiti(self):
        cfg = DummyCfg()
        cfg.clippiti_path = '/usr/bin/clippiti'
        s = Stream(
            url='https://example.com/stream',
            name='Test',
            type='twitch',
            quality='720p',
            player='mpv',  # Not clippiti
            sl_args=None,
            mp_args=None
        )
        cmd = slhelper.build_launch_command(cfg, s)
        self.assertEqual(cmd[0], 'streamlink')


if __name__ == '__main__':
    unittest.main()
