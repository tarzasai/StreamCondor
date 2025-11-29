import json
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from PyQt6.QtCore import QObject, pyqtSignal


class TrayIconColor(Enum):
  WHITE = 'white'
  BLACK = 'black'

  @property
  def prefix(self) -> str:
    return 'sc_w_' if self == TrayIconColor.WHITE else 'sc_b_'


class TrayIconStatus(Enum):
  OFF = 'off'
  IDLE = 'idle'
  LIVE = 'live'
  VIPS = 'vips'


class TrayIconAction(Enum):
  NOTHING = 'nothing'
  OPEN_URL = 'open_url'
  OPEN_CONFIG = 'open_config'
  TOGGLE_MONITORING = 'toggle_monitoring'
  TOGGLE_NOTIFICATIONS = 'toggle_notifications'

  @property
  def display_name(self) -> str:
    """Get user-friendly display name for the action."""
    names = {
      TrayIconAction.OPEN_CONFIG: 'Open configuration',
      TrayIconAction.OPEN_URL: 'Open URL dialog',
      TrayIconAction.TOGGLE_MONITORING: 'Toggle monitoring',
      TrayIconAction.TOGGLE_NOTIFICATIONS: 'Toggle notifications',
      TrayIconAction.NOTHING: 'Nothing'
    }
    return names[self]


class BaseModelWithEmptyToNone(BaseModel):
  @field_validator('*')
  @classmethod
  def empty_str_to_none(cls, v):
    return None if v == "" else v


class Stream(BaseModelWithEmptyToNone):
  url: str = Field(..., description="URL of the stream")
  name: str = Field(..., description="Name of the stream")
  type: str = Field(..., description="Stream platform (e.g., twitch, youtube)")
  quality: str | None = Field(None, description="Preferred stream quality")
  player: str | None = Field(None, description="Media player command to use")
  sl_args: str | None = Field(None, description="Additional Streamlink arguments")
  mp_args: str | None = Field(None, description="Additional media player arguments")
  notify: bool | None = Field(None, description="Whether to notify when stream goes live")


class Geometry(BaseModel):
  x: int = Field(..., description="X position of the application window")
  y: int = Field(..., description="Y position of the application window")
  width: int = Field(..., description="Width of the application window")
  height: int = Field(..., description="Height of the application window")


class ConfigModel(BaseModelWithEmptyToNone):
  autostart_monitoring: bool = Field(default=False, description="Whether monitoring starts automatically")
  check_interval: int = Field(default=60, description="Interval in seconds between stream checks")
  default_notify: bool = Field(default=False, description="Default notification setting for streams")
  default_streamlink_args: str | None = Field(default="", description="Default Streamlink arguments")
  default_quality: str | None = Field(default="best", description="Default stream quality")
  default_media_player: str | None = Field(default="", description="Default media player command")
  default_media_player_args: str | None = Field(default="", description="Default media player arguments")
  tray_icon_color: TrayIconColor = Field(default=TrayIconColor.WHITE, description="Base color of the tray icon")
  tray_icon_action: TrayIconAction = Field(default=TrayIconAction.NOTHING, description="Action on tray icon left-click")
  streams: dict[str, Stream] = Field(default_factory=dict, description="Configured streams")
  windows: dict[str, Geometry] | None = Field(default_factory=dict, description="Window geometry settings")


class Configuration(QObject):
  config_changed = pyqtSignal()

  def __init__(self, config_path: Path):
    super().__init__()
    self.config_path = config_path
    self._cfg: ConfigModel = ConfigModel()
    self.load()

  def load(self) -> None:
    with open(self.config_path, 'r', encoding='utf-8') as f:
      self._cfg = ConfigModel(**json.load(f))

  def save(self) -> None:
    with open(self.config_path, 'w', encoding='utf-8') as f:
      json.dump(self._cfg.model_dump(mode='json', exclude_none=True), f, indent=2, ensure_ascii=False)
    self.config_changed.emit()

  def set(self, key: str, value) -> None:
    if value == getattr(self._cfg, key):
      return
    new_cfg = self._cfg.model_dump()
    new_cfg[key] = value
    self._cfg = ConfigModel(**new_cfg)
    self.save()

  @property
  def autostart_monitoring(self) -> bool:
    return self._cfg.autostart_monitoring

  @autostart_monitoring.setter
  def autostart_monitoring(self, value: bool) -> None:
    self.set('autostart_monitoring', value)

  @property
  def default_notify(self) -> bool:
    return self._cfg.default_notify

  @default_notify.setter
  def default_notify(self, value: bool) -> None:
    self.set('default_notify', value)

  @property
  def tray_icon_color(self) -> TrayIconColor:
    return self._cfg.tray_icon_color

  @tray_icon_color.setter
  def tray_icon_color(self, value: TrayIconColor) -> None:
    self.set('tray_icon_color', value)

  @property
  def tray_icon_action(self) -> TrayIconAction:
    return self._cfg.tray_icon_action

  @tray_icon_action.setter
  def tray_icon_action(self, value: TrayIconAction) -> None:
    self.set('tray_icon_action', value)

  @property
  def check_interval(self) -> int:
    return self._cfg.check_interval

  @check_interval.setter
  def check_interval(self, value: int) -> None:
    self.set('check_interval', value)

  @property
  def default_streamlink_args(self) -> str:
    return self._cfg.default_streamlink_args

  @default_streamlink_args.setter
  def default_streamlink_args(self, value: str) -> None:
    self.set('default_streamlink_args', value)

  @property
  def default_quality(self) -> str:
    return self._cfg.default_quality

  @default_quality.setter
  def default_quality(self, value: str) -> None:
    self.set('default_quality', value)

  @property
  def default_media_player(self) -> str:
    return self._cfg.default_media_player

  @default_media_player.setter
  def default_media_player(self, value: str) -> None:
    self.set('default_media_player', value)

  @property
  def default_media_player_args(self) -> str:
    return self._cfg.default_media_player_args

  @default_media_player_args.setter
  def default_media_player_args(self, value: str) -> None:
    self.set('default_media_player_args', value)

  @property
  def streams(self) -> dict[str, Stream]:
    return self._cfg.streams

  def get_stream(self, url: str) -> Stream | None:
    return self._cfg.streams.get(url)

  def set_stream(self, stream: Stream) -> None:
    new_streams = self._cfg.streams.copy()
    new_streams[stream.url] = stream
    self.set('streams', dict(sorted(new_streams.items())))

  def del_stream(self, stream: Stream) -> None:
    if stream.url in self._cfg.streams:
      new_streams = self._cfg.streams.copy()
      del new_streams[stream.url]
      self.set('streams', new_streams)

  def get_geometry(self, window_name: str) -> Geometry | None:
    return self._cfg.windows.get(window_name)

  def set_geometry(self, window_name: str, geometry: Geometry) -> None:
    new_windows = self._cfg.windows.copy()
    new_windows[window_name] = geometry
    self.set('windows', new_windows)
