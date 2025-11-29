"""Resource management for StreamCondor.

This module provides utilities for accessing package resources (icons, assets)
that work both in development and when the package is installed.
"""
from pathlib import Path
import sys

def get_assets_dir() -> Path:
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

  # Common locations to look for an `assets` directory:
  candidates = [
    # Package-installed location: <package>/assets
    Path(__file__).parent / 'assets',
    # Development layout: src/assets (one level up from package)
    Path(__file__).parent.parent / 'assets',
    # Project root assets (two levels up)
    Path(__file__).parent.parent.parent / 'assets',
  ]
  for c in candidates:
    if c.exists():
      return c
  # Fallback to package assets path even if it doesn't exist (keeps behavior predictable)
  return candidates[0]


def get_asset_path(filename: str) -> Path:
  """Get the path to a specific asset file.

  Args:
    filename: The name of the asset file (e.g., 'icon_monitoring_live.png')

  Returns:
    Path: The absolute path to the asset file.
  """
  return get_assets_dir() / filename
