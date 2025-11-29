import unittest
from streamcondor.model import TrayIconColor, TrayIconAction, Geometry, Stream


class TestModelAdditional(unittest.TestCase):
    def test_tray_icon_color_prefixes(self):
        self.assertEqual(TrayIconColor.WHITE.prefix, 'sc_w_')
        self.assertEqual(TrayIconColor.BLACK.prefix, 'sc_b_')

    def test_tray_icon_action_display(self):
        for action in TrayIconAction:
            self.assertIsInstance(action.display_name, str)

    def test_geometry_and_stream_minimal(self):
        g = Geometry(x=1, y=2, width=100, height=200)
        self.assertEqual(g.x, 1)
        s = Stream(url='u', name='n', type='t')
        self.assertEqual(s.url, 'u')


if __name__ == '__main__':
    unittest.main()
