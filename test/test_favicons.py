import unittest
from unittest.mock import patch, MagicMock
import io
from PIL import Image
from pathlib import Path
import requests

from streamcondor.favicons import _Favicons, get_stream_icon, favicons
from streamcondor.model import Stream


def _create_png_bytes(size=(32, 32), color=(255, 0, 0, 255)):
    img = Image.new('RGBA', size, color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class TestFavicons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure a QApplication exists for QPixmap/QImage usage
        try:
            from PyQt6.QtWidgets import QApplication
            if QApplication.instance() is None:
                cls._app = QApplication([])
        except Exception:
            cls._app = None

    @patch('streamcondor.favicons.requests.get')
    def test_discover_and_download(self, mock_get):
        # Mock HTML response for discovery
        html = '<html><head><link rel="icon" href="/favicon.png"></head><body></body></html>'
        resp_html = MagicMock()
        resp_html.text = html
        resp_html.raise_for_status = MagicMock()
        mock_get.side_effect = [resp_html, MagicMock()]
        # Second call (download) returns PNG bytes
        resp_img = MagicMock()
        resp_img.content = _create_png_bytes((64, 64))
        resp_img.raise_for_status = MagicMock()
        mock_get.side_effect = [resp_html, resp_img]
        f = _Favicons()
        s = Stream(url='https://example.com/somepage', name='Example', type='twitch')
        pix = f.get_favicon(s.url, s.type, 16)
        self.assertIsNotNone(pix)

    @patch('streamcondor.favicons.requests.get')
    def test_download_too_small(self, mock_get):
        resp_img = MagicMock()
        resp_img.content = _create_png_bytes((8, 8))
        resp_img.raise_for_status = MagicMock()
        mock_get.return_value = resp_img
        f = _Favicons()
        ok = f._download_and_save_favicon('https://example.com/small.png', 'smalltest')
        self.assertFalse(ok)

    @patch('streamcondor.favicons.requests.get')
    @patch('streamcondor.favicons.QStandardPaths.writableLocation')
    def test_ico_multiframe_and_cache(self, mock_writable, mock_get):
        # Create a temporary cache dir
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        mock_writable.return_value = tmp.name

        # Build a multi-frame ICO by saving two PNG frames as ICO
        frame1 = Image.new('RGBA', (16, 16), (255, 0, 0, 255))
        frame2 = Image.new('RGBA', (32, 32), (0, 255, 0, 255))
        buf = io.BytesIO()
        frame1.save(buf, format='ICO', sizes=[(16, 16), (32, 32)])
        ico_bytes = buf.getvalue()

        resp_img = MagicMock()
        resp_img.content = ico_bytes
        resp_img.raise_for_status = MagicMock()
        mock_get.return_value = resp_img

        f = _Favicons()
        s = Stream(url='https://example.org/', name='Org', type='org')
        # First fetch will download and save to cache
        pix = f.get_favicon(s.url, s.type, 16)
        self.assertIsNotNone(pix)
        # Now create a new instance that should load from cache without network
        mock_get.reset_mock()
        f2 = _Favicons()
        pix2 = f2.get_favicon(s.url, s.type, 16)
        self.assertIsNotNone(pix2)
        mock_get.assert_not_called()

    @patch('streamcondor.favicons.requests.get')
    @patch('streamcondor.favicons.QStandardPaths.writableLocation')
    def test_discover_rel_variants(self, mock_writable, mock_get):
        tmp = __import__('tempfile').TemporaryDirectory()
        mock_writable.return_value = tmp.name

        html = ('<html><head>'
                '<link rel="apple-touch-icon" href="/apple.png">'
                '<link rel="mask-icon" href="/mask.svg">'
                '</head><body></body></html>')
        resp_html = MagicMock()
        resp_html.text = html
        resp_html.raise_for_status = MagicMock()

        resp_img = MagicMock()
        resp_img.content = _create_png_bytes((48, 48))
        resp_img.raise_for_status = MagicMock()

        mock_get.side_effect = [resp_html, resp_img]

        f = _Favicons()
        s = Stream(url='https://apple.example/', name='Apple', type='apple')
        pix = f.get_favicon(s.url, s.type, 16)
        self.assertIsNotNone(pix)

    @patch('streamcondor.favicons.requests.get')
    @patch('streamcondor.favicons.QStandardPaths.writableLocation')
    def test_meta_fallback(self, mock_writable, mock_get):
        tmp = __import__('tempfile').TemporaryDirectory()
        mock_writable.return_value = tmp.name

        html = ('<html><head>'
                '<meta property="og:image" content="/og.png">'
                '</head><body></body></html>')
        resp_html = MagicMock()
        resp_html.text = html
        resp_html.raise_for_status = MagicMock()

        resp_img = MagicMock()
        resp_img.content = _create_png_bytes((32, 32))
        resp_img.raise_for_status = MagicMock()

        mock_get.side_effect = [resp_html, resp_img]

        f = _Favicons()
        s = Stream(url='https://meta.example/', name='Meta', type='meta')
        pix = f.get_favicon(s.url, s.type, 16)
        self.assertIsNotNone(pix)

    @patch('streamcondor.favicons.requests.get')
    @patch('streamcondor.favicons.QStandardPaths.writableLocation')
    def test_root_and_common_paths(self, mock_writable, mock_get):
        tmp = __import__('tempfile').TemporaryDirectory()
        mock_writable.return_value = tmp.name

        # First call (HTML fetch) will raise to force falling back to conventions
        resp_img = MagicMock()
        resp_img.content = _create_png_bytes((32, 32))
        resp_img.raise_for_status = MagicMock()

        mock_get.side_effect = [requests.exceptions.RequestException('no html'), resp_img]

        f = _Favicons()
        s = Stream(url='https://root.example/', name='Root', type='root')
        pix = f.get_favicon(s.url, s.type, 16)
        self.assertIsNotNone(pix)

    @patch('streamcondor.favicons.requests.get')
    def test_invalid_image_bytes(self, mock_get):
        resp_img = MagicMock()
        resp_img.content = b'not an image'
        resp_img.raise_for_status = MagicMock()
        mock_get.return_value = resp_img

        f = _Favicons()
        ok = f._download_and_save_favicon('https://example.com/invalid', 'badimg')
        self.assertFalse(ok)

    @patch('streamcondor.favicons.requests.get')
    @patch('streamcondor.favicons.QStandardPaths.writableLocation')
    def test_all_downloads_fail(self, mock_writable, mock_get):
        tmp = __import__('tempfile').TemporaryDirectory()
        mock_writable.return_value = tmp.name

        html = '<html><head><link rel="icon" href="/one.png"></head></html>'
        resp_html = MagicMock()
        resp_html.text = html
        resp_html.raise_for_status = MagicMock()

        # After the HTML fetch, all subsequent download attempts raise
        failures = [requests.exceptions.RequestException('fail')] * 10
        mock_get.side_effect = [resp_html] + failures

        f = _Favicons()
        s = Stream(url='https://fail.example/', name='Fail', type='fail')
        pix = f.get_favicon(s.url, s.type, 16)
        self.assertIsNone(pix)

    def test_no_favicons_found(self):
        # Patch _discover_favicons to return empty and ensure get_favicon returns None
        f = _Favicons()
        original = f._discover_favicons
        try:
            f._discover_favicons = lambda base: []
            s = Stream(url='https://empty.example/', name='Empty', type='empty')
            pix = f.get_favicon(s.url, s.type, 16)
            self.assertIsNone(pix)
        finally:
            f._discover_favicons = original


if __name__ == '__main__':
    unittest.main()
