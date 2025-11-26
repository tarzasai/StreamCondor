"""
Configuration management for StreamCondor.
"""
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any


log = logging.getLogger(__name__)


DEFAULT_CONFIG = {
  'autostart_monitoring': True,
  'default_notify': True,
  'check_interval': 60,
  'default_streamlink_args': '',
  'default_quality': 'best',
  'default_media_player': '',
  'default_media_player_args': '',
  'left_click_action': 'open_config',  # LeftClickAction.OPEN_CONFIG.value
  'streams': [],
  'settings_window': {
    'width': 800,
    'height': 600,
    'x': 100,
    'y': 100
  }
}


class TrayClickAction(Enum):
  """Actions that can be performed when left-clicking the tray icon."""

  OPEN_CONFIG = 'open_config'
  OPEN_URL = 'open_url'
  TOGGLE_MONITORING = 'toggle_monitoring'
  TOGGLE_NOTIFICATIONS = 'toggle_notifications'
  NOTHING = 'nothing'

  @property
  def display_name(self) -> str:
    """Get user-friendly display name for the action."""
    names = {
      TrayClickAction.OPEN_CONFIG: 'Open configuration',
      TrayClickAction.OPEN_URL: 'Open URL dialog',
      TrayClickAction.TOGGLE_MONITORING: 'Toggle monitoring',
      TrayClickAction.TOGGLE_NOTIFICATIONS: 'Toggle notifications',
      TrayClickAction.NOTHING: 'Nothing'
    }
    return names[self]

  @classmethod
  def from_string(cls, value: str) -> 'TrayClickAction':
    """Convert string to LeftClickAction enum.

    Args:
      value: String value (e.g., 'open_config')

    Returns:
      LeftClickAction enum value, defaults to NOTHING if invalid
    """
    try:
      return cls(value)
    except ValueError:
      return cls.NOTHING


class Configuration:
  """Manages application configuration loading and saving."""

  def __init__(self, config_path: Path):
    self.config_path = Path(config_path)
    self.config: dict[str, Any] = {}
    self.load()

  def load(self) -> None:
    if self.config_path.exists():
      try:
        with open(self.config_path, 'r', encoding='utf-8') as f:
          self.config = _clean_empty_fields(json.load(f))
        log.info(f'Configuration loaded from {self.config_path}')
      except Exception as e:
        log.error(f'Error loading configuration: {e}')
        self.config = {}
    else:
      log.info('No configuration file found, using defaults')
      self.config = {}

  def save(self) -> None:
    try:
      self.config_path.parent.mkdir(parents=True, exist_ok=True)
      with open(self.config_path, 'w', encoding='utf-8') as f:
        json.dump(_clean_empty_fields(self.config), f, indent=2, ensure_ascii=False)
      log.info(f'Configuration saved to {self.config_path}')
    except Exception as e:
      log.error(f'Error saving configuration: {e}')

  def set_value(self, key: str, value: Any) -> None:
    self.config[key] = value
    self.save()

  def add_stream(self, stream: dict[str, Any]) -> None:
    url = stream.get('url')
    if (found := next((s for s in self.streams if s.get('url') == url), None)) is not None:
      raise ValueError(f"Duplicate URL of '{found.get('name')}'; cannot add.")
    self.streams.append(stream)
    self.save()

  def update_stream(self, stream: dict[str, Any]) -> None:
    url = stream.get('url')
    actual_index = next((i for i, s in enumerate(self.streams) if s.get('url') == url), None)
    if actual_index is None:
      raise ValueError(f"No existing stream with URL '{url}'; cannot update.")
    self.streams[actual_index] = stream
    self.save()

  def remove_stream(self, stream: dict[str, Any]) -> None:
    url = stream.get('url')
    actual_index = next((i for i, s in enumerate(self.streams) if s.get('url') == url), None)
    if actual_index is None:
      raise ValueError(f"No existing stream with URL '{url}'; cannot update.")
    self.streams.pop(actual_index)
    self.save()

  @property
  def streams(self) -> list[dict[str, Any]]:
    return self.config.setdefault('streams', [])

  @property
  def autostart_monitoring(self) -> bool:
    return self.config.get('autostart_monitoring', False)

  @autostart_monitoring.setter
  def autostart_monitoring(self, value: bool) -> None:
    if self.autostart_monitoring != value:
      self.config['autostart_monitoring'] = value
      self.save()

  @property
  def default_notify(self) -> bool:
    return self.config.get('default_notify', False)

  @default_notify.setter
  def default_notify(self, value: bool) -> None:
    if self.default_notify != value:
      self.config['default_notify'] = value
      self.save()

  @property
  def check_interval(self) -> int:
    return self.config.get('check_interval', 60)

  @check_interval.setter
  def check_interval(self, value: int) -> None:
    if self.check_interval != value:
      self.config['check_interval'] = value
      self.save()

  @property
  def default_streamlink_args(self) -> str:
    return self.config.get('default_streamlink_args', '')

  @default_streamlink_args.setter
  def default_streamlink_args(self, value: str) -> None:
    if self.default_streamlink_args != value:
      self.config['default_streamlink_args'] = value
      self.save()

  @property
  def default_quality(self) -> str:
    return self.config.get('default_quality', 'best')

  @default_quality.setter
  def default_quality(self, value: str) -> None:
    if self.default_quality != value:
      self.config['default_quality'] = value
      self.save()

  @property
  def default_media_player(self) -> str:
    return self.config.get('default_media_player', '')

  @default_media_player.setter
  def default_media_player(self, value: str) -> None:
    if self.default_media_player != value:
      self.config['default_media_player'] = value
      self.save()

  @property
  def default_media_player_args(self) -> str:
    return self.config.get('default_media_player_args', '')

  @default_media_player_args.setter
  def default_media_player_args(self, value: str) -> None:
    if self.default_media_player_args != value:
      self.config['default_media_player_args'] = value
      self.save()

  @property
  def left_click_action(self) -> TrayClickAction:
    action_str = self.config.get('left_click_action', 'nothing')
    return TrayClickAction.from_string(action_str)

  @left_click_action.setter
  def left_click_action(self, value: TrayClickAction) -> None:
    if self.left_click_action != value:
      self.config['left_click_action'] = value.value
      self.save()

  def load_window_geometry(self, name: str) -> dict[str, int]:
    return self.config.setdefault('windows', {}).get(name, {})

  def save_window_geometry(self, name: str, geometry: dict[str, int]) -> None:
    self.config.setdefault('windows', {})[name] = geometry
    self.save()


def _clean_empty_fields(data: Any) -> Any:
  """Remove empty string and None fields from data recursively.

  Args:
    data: Data to clean

  Returns:
    Cleaned data with empty strings and None values removed
  """
  if isinstance(data, dict):
    cleaned = {}
    for key, value in data.items():
      cleaned_value = _clean_empty_fields(value)
      # Skip empty strings and None values
      if cleaned_value is None or (isinstance(cleaned_value, str) and not cleaned_value):
        continue
      cleaned[key] = cleaned_value
    return cleaned
  elif isinstance(data, list):
    return [_clean_empty_fields(item) for item in data]
  else:
    return data
