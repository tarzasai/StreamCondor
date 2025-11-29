import unittest
from model import Stream


class TestStreamModel(unittest.TestCase):
    def test_basic_properties(self):
        s = Stream(url='https://example.com/stream', name='Example', type='twitch', quality='best', player='mpv', sl_args='--http-no-ssl-verify', mp_args='--no-border', notify=True)
        self.assertEqual(s.url, 'https://example.com/stream')
        self.assertEqual(s.name, 'Example')
        self.assertEqual(s.type, 'twitch')
        self.assertEqual(s.quality, 'best')
        self.assertEqual(s.player, 'mpv')
        self.assertEqual(s.sl_args, '--http-no-ssl-verify')
        self.assertEqual(s.mp_args, '--no-border')
        self.assertTrue(s.notify)

    def test_model_dump_and_copy(self):
        s = Stream(url='u', name='n', type='t')
        d = s.model_dump()
        self.assertIsInstance(d, dict)
        self.assertEqual(d['url'], 'u')
        c = s.model_copy()
        self.assertIsInstance(c, Stream)
        self.assertEqual(c.url, s.url)
        # modifying copy doesn't change original
        c.name = 'changed'
        self.assertEqual(s.name, 'n')

    def test_model_dump_get_default(self):
        s = Stream(url='u', name='n', type='t')
        d = s.model_dump()
        self.assertEqual(d.get('nonexistent', 'def'), 'def')
        self.assertEqual(d.get('url'), 'u')


if __name__ == '__main__':
    unittest.main()
