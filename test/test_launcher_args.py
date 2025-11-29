import unittest
from slhelper import _parse_args_string, _split_args_with_values, _merge_args_strings


class TestLauncherArgHelpers(unittest.TestCase):
    def test_parse_args_string_basic(self):
        s = '--flag --option 123 -x -y hello'
        d = _parse_args_string(s)
        self.assertIsNone(d['--flag'])
        self.assertEqual(d['--option'], '123')
        self.assertIsNone(d['-x'])
        self.assertEqual(d['-y'], 'hello')

    def test_split_args_with_values_quotes(self):
        s = '--message "hello world" --flag -n 42'
        l = _split_args_with_values(s)
        self.assertIn('--message "hello world"', l)
        self.assertIn('--flag', l)
        self.assertIn('-n 42', l)

    def test_merge_args_strings_override(self):
        default = '--flag --option 123 -x -y hello'
        override = '--option 456 -z'
        out = _merge_args_strings(default, override)
        # --option should be 456
        self.assertIn('--option 456', out)
        self.assertIn('--flag', out)
        self.assertIn('-z', out)


if __name__ == '__main__':
    unittest.main()
