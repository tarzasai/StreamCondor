import sys
import logging
from pathlib import Path
from PyQt6.QtGui import QIcon

log = logging.getLogger(__name__)


def get_asset_path() -> Path:
  """Get the path to the assets directory.

  Returns:
    Path: The absolute path to the assets directory.

  This works both in development (when running from source) and when
  installed as a package. When installed, assets are part of package data.
  """
  # In development or when running from source
  if hasattr(sys, '_MEIPASS'):
    # Running in a PyInstaller bundle
    return Path(sys._MEIPASS) / 'assets'

  # Development mode - assets are in src/assets
  return Path(__file__).parent / 'assets'


def get_app_icon(base_name: str) -> QIcon:
  """Get a QIcon for the specified base name, preferring SVG if available.

  Args:
    base_name: The base name of the icon file without extension
               (e.g., 'sc_w_live' for 'sc_w_live.svg' or 'sc_w_live.png')

  Returns:
    QIcon: The QIcon object for the specified icon.
  """
  try:
    return QIcon(str(get_asset_path() / f"{base_name}.svg"))
  except Exception as e:
    log.debug(f"Unable to load SVG icon {base_name}, falling back to PNG: {e}")
    return QIcon(str(get_asset_path() / f"{base_name}.png"))

