import logging
import io
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QStandardPaths
from PIL import Image

from streamcondor.model import Stream

log = logging.getLogger(__name__)


class _Favicons:

  def __init__(self):
    cache_dir = Path(QStandardPaths.writableLocation(
      QStandardPaths.StandardLocation.CacheLocation
    ))
    self.cache_dir = cache_dir / 'favicons'
    self.cache_dir.mkdir(parents=True, exist_ok=True)
    self.favicon_cache: dict[str, dict[int, QPixmap]] = {}
    self._load_cached_favicons()

  def _load_cached_favicons(self) -> None:
    for file_path in self.cache_dir.glob('*_16x16.png'):
      stream_type = file_path.stem.replace('_16x16', '')
      if stream_type not in self.favicon_cache:
        self.favicon_cache[stream_type] = {}
      pixmap_16 = QPixmap(str(file_path))
      if not pixmap_16.isNull():
        self.favicon_cache[stream_type][16] = pixmap_16
      file_path_24 = self.cache_dir / f'{stream_type}_24x24.png'
      if file_path_24.exists():
        pixmap_24 = QPixmap(str(file_path_24))
        if not pixmap_24.isNull():
          self.favicon_cache[stream_type][24] = pixmap_24
    log.info(f'Loaded {len(self.favicon_cache)} cached favicons')

  def _get_base_url(self, url: str) -> str:
    parsed = urlparse(url)
    return f'{parsed.scheme}://{parsed.netloc}'

  def _discover_favicons(self, base_url: str) -> list[str]:
    favicon_urls = []
    # Method 1: Parse HTML for link tags
    try:
      response = requests.get(base_url, timeout=10, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
      })
      response.raise_for_status()
      soup = BeautifulSoup(response.text, 'html.parser')
      # Find all link tags with icon-related rel attributes
      icon_rels = ['icon', 'shortcut icon', 'apple-touch-icon',
                   'apple-touch-icon-precomposed', 'mask-icon', 'fluid-icon']
      for link in soup.find_all('link'):
        rel = link.get('rel', [])
        if isinstance(rel, list):
          rel = ' '.join(rel)
        rel = rel.lower()
        if any(icon_rel in rel for icon_rel in icon_rels):
          href = link.get('href')
          if href:
            favicon_urls.append(urljoin(base_url, href))
      # Check meta tags as fallback
      for meta in soup.find_all('meta'):
        property_val = meta.get('property', '')
        name_val = meta.get('name', '')
        if property_val == 'og:image' or name_val == 'msapplication-TileImage':
          content = meta.get('content')
          if content:
            favicon_urls.append(urljoin(base_url, content))
    except Exception as e:
      log.debug(f'Error parsing HTML for favicons: {e}')
    # Method 2: Root directory conventions
    conventions = [
      '/favicon.ico',
      '/favicon.png',
      '/favicon.svg'
    ]
    for convention in conventions:
      favicon_urls.append(urljoin(base_url, convention))
    # Method 3: Common locations
    common_paths = [
      '/images/favicon.ico',
      'assets/favicon.ico',
      '/static/favicon.ico'
    ]
    for path in common_paths:
      favicon_urls.append(urljoin(base_url, path))
    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for url in favicon_urls:
      if url not in seen:
        seen.add(url)
        unique_urls.append(url)
    return unique_urls

  def _download_and_save_favicon(self, url: str, stream_type: str) -> bool:
    try:
      response = requests.get(url, timeout=10, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
      })
      response.raise_for_status()
      img = Image.open(io.BytesIO(response.content))
      # Handle ICO files with multiple sizes
      if hasattr(img, 'n_frames') and img.n_frames > 1:
        # Extract largest size from ICO
        largest_size = 0
        largest_img = None
        for i in range(img.n_frames):
          img.seek(i)
          if img.size[0] > largest_size:
            largest_size = img.size[0]
            largest_img = img.copy()
        if largest_img:
          img = largest_img
      # Convert to RGBA for transparency
      if img.mode != 'RGBA':
        img = img.convert('RGBA')
      # Don't upscale if image is too small
      if img.size[0] < 16 or img.size[1] < 16:
        log.debug(f'Favicon too small: {img.size}')
        return False
      # Save in both sizes
      for size in [16, 24]:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        # Convert PIL image to QPixmap
        buffer = io.BytesIO()
        resized.save(buffer, format='PNG')
        buffer.seek(0)
        qimage = QImage.fromData(buffer.read())
        pixmap = QPixmap.fromImage(qimage)
        # Save to cache
        cache_path = self.cache_dir / f'{stream_type}_{size}x{size}.png'
        pixmap.save(str(cache_path), 'PNG')
        # Add to memory cache
        if stream_type not in self.favicon_cache:
          self.favicon_cache[stream_type] = {}
        self.favicon_cache[stream_type][size] = pixmap
      log.info(f'Successfully saved favicon for {stream_type}')
      return True
    except Exception as e:
      log.debug(f'Failed to download favicon from {url}: {e}')
      return False

  def get_favicon(self, stream_url: str, stream_type: str, size: int = 16) -> QPixmap | None:
    if stream_type not in self.favicon_cache:
      try:
        base_url = self._get_base_url(stream_url)
        favicon_urls = self._discover_favicons(base_url)
        if not favicon_urls:
          log.warning(f'No favicons found for {base_url}')
          return None
        # Try each discovered favicon URL
        for favicon_url in favicon_urls:
          if self._download_and_save_favicon(favicon_url, stream_type):
            break
        else:
          log.warning(f'Failed to download any favicon for {base_url}')
          return None
      except Exception as e:
        log.error(f'Error fetching favicon: {e}')
        return None
    return self.favicon_cache[stream_type].get(size)


favicons = None

def get_stream_icon(stream: Stream, size: int = 16) -> QPixmap | None:
  global favicons
  if favicons is None:
    favicons = _Favicons()
  return favicons.get_favicon(stream.url, stream.type, size)
