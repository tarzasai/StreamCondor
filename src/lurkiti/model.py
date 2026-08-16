import json
import time
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from PyQt6.QtCore import QObject, pyqtSignal, QStandardPaths


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
      TrayIconAction.NOTHING: 'Do nothing',
      TrayIconAction.OPEN_URL: 'Open stream from URL',
      TrayIconAction.OPEN_CONFIG: 'Open configuration',
      TrayIconAction.TOGGLE_MONITORING: 'Toggle monitoring',
      TrayIconAction.TOGGLE_NOTIFICATIONS: 'Toggle notifications',
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
  always_on: bool = Field(default=False, description="Whether to always consider the stream as live")


class Geometry(BaseModel):
  x: int = Field(..., description="X position of the application window")
  y: int = Field(..., description="Y position of the application window")
  width: int = Field(..., description="Width of the application window")
  height: int = Field(..., description="Height of the application window")


class ConfigModel(BaseModelWithEmptyToNone):
  autostart_monitoring: bool = Field(default=False, description="Whether monitoring starts automatically")
  check_interval_mins: int = Field(default=5, description="Interval in minutes between stream checks")
  default_notify: bool = Field(default=False, description="Default notification setting for streams")
  default_streamlink_args: str | None = Field(default="--title \"{author} - {title}\"", description="Default Streamlink arguments")
  default_quality: str | None = Field(default="best", description="Default stream quality")
  default_player: str | None = Field(default="", description="Default media player command")
  default_player_args: str | None = Field(default="", description="Default media player arguments")
  alternate_player: str | None = Field(default=None, description="Alternate media player command")
  alternate_player_args: str | None = Field(default=None, description="Alternate media player arguments")
  clippiti_path: str | None = Field(default=None, description="Path to Clippiti executable")
  tray_icon_action: TrayIconAction = Field(default=TrayIconAction.NOTHING, description="Action on tray icon left-click")
  always_on_submenu: bool = Field(default=False, description="Always group always-on streams in a tray submenu")
  streams: dict[str, Stream] = Field(default_factory=dict, description="Configured streams")
  windows: dict[str, Geometry] | None = Field(default_factory=dict, description="Window geometry settings")


class StreamState(BaseModel):
  is_online: bool = Field(default=False, exclude=True, description='Whether stream is currently online')
  last_online_ts: float | None = Field(default=None, description='Last time stream was seen online (unix timestamp)')
  last_watched_ts: float | None = Field(default=None, description='Last time stream was launched/watched (unix timestamp)')


class StateModel(BaseModel):
  streams: dict[str, StreamState] = Field(default_factory=dict, description='Per-stream runtime state')


class Configuration(QObject):
  config_changed = pyqtSignal()
  state_changed = pyqtSignal()

  def __init__(self, config_path: Path):
    super().__init__()
    self.config_path = config_path
    self.state_path = self._resolve_state_path()
    self._config: ConfigModel = ConfigModel()
    self._state: StateModel = StateModel()
    self.load()
    self.load_state()

  def _resolve_state_path(self) -> Path:
    state_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericStateLocation))
    if str(state_dir) == '.':
      state_dir = self.config_path.parent
    return state_dir / 'Lurkiti.state.json'

  def load(self) -> None:
    with open(self.config_path, 'r', encoding='utf-8') as f:
      self._config = ConfigModel(**json.load(f))

  def load_state(self) -> None:
    if not self.state_path.exists():
      self._state = StateModel()
      return
    with open(self.state_path, 'r', encoding='utf-8') as f:
      self._state = StateModel(**json.load(f))

  def save(self) -> None:
    with open(self.config_path, 'w', encoding='utf-8') as f:
      json.dump(self._config.model_dump(mode='json', exclude_none=True), f, indent=2, ensure_ascii=False)
    self.config_changed.emit()

  def save_state(self) -> None:
    self.state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(self.state_path, 'w', encoding='utf-8') as f:
      json.dump(self._state.model_dump(mode='json', exclude_none=True), f, indent=2, ensure_ascii=False)
    self.state_changed.emit()

  def set(self, key: str, value) -> None:
    if value == getattr(self._config, key):
      return
    new_cfg = self._config.model_dump()
    new_cfg[key] = value
    self._config = ConfigModel(**new_cfg)
    self.save()

  @property
  def autostart_monitoring(self) -> bool:
    return self._config.autostart_monitoring

  @autostart_monitoring.setter
  def autostart_monitoring(self, value: bool) -> None:
    self.set('autostart_monitoring', value)

  @property
  def default_notify(self) -> bool:
    return self._config.default_notify

  @default_notify.setter
  def default_notify(self, value: bool) -> None:
    self.set('default_notify', value)

  @property
  def always_on_submenu(self) -> bool:
    return self._config.always_on_submenu

  @always_on_submenu.setter
  def always_on_submenu(self, value: bool) -> None:
    self.set('always_on_submenu', value)

  @property
  def tray_icon_action(self) -> TrayIconAction:
    return self._config.tray_icon_action

  @tray_icon_action.setter
  def tray_icon_action(self, value: TrayIconAction) -> None:
    self.set('tray_icon_action', value)

  @property
  def check_interval_mins(self) -> int:
    return self._config.check_interval_mins

  @check_interval_mins.setter
  def check_interval_mins(self, value: int) -> None:
    self.set('check_interval_mins', value)

  @property
  def default_streamlink_args(self) -> str:
    return self._config.default_streamlink_args

  @default_streamlink_args.setter
  def default_streamlink_args(self, value: str) -> None:
    self.set('default_streamlink_args', value)

  @property
  def default_quality(self) -> str:
    return self._config.default_quality

  @default_quality.setter
  def default_quality(self, value: str) -> None:
    self.set('default_quality', value)

  @property
  def default_player(self) -> str:
    return self._config.default_player

  @default_player.setter
  def default_player(self, value: str) -> None:
    self.set('default_player', value)

  @property
  def default_player_args(self) -> str:
    return self._config.default_player_args

  @default_player_args.setter
  def default_player_args(self, value: str) -> None:
    self.set('default_player_args', value)

  @property
  def alternate_player(self) -> str:
    return self._config.alternate_player

  @alternate_player.setter
  def alternate_player(self, value: str) -> None:
    self.set('alternate_player', value)

  @property
  def alternate_player_args(self) -> str:
    return self._config.alternate_player_args

  @alternate_player_args.setter
  def alternate_player_args(self, value: str) -> None:
    self.set('alternate_player_args', value)

  @property
  def clippiti_path(self) -> str | None:
    return self._config.clippiti_path

  @clippiti_path.setter
  def clippiti_path(self, value: str | None) -> None:
    self.set('clippiti_path', value)

  @property
  def streams(self) -> dict[str, Stream]:
    return self._config.streams

  def get_stream(self, url: str) -> Stream | None:
    return self._config.streams.get(url)

  def set_stream(self, stream: Stream) -> None:
    new_streams = self._config.streams.copy()
    new_streams[stream.url] = stream
    self.set('streams', dict(sorted(new_streams.items())))

  def del_stream(self, stream: Stream) -> None:
    if stream.url in self._config.streams:
      new_streams = self._config.streams.copy()
      del new_streams[stream.url]
      self.set('streams', new_streams)
    if stream.url in self._state.streams:
      new_states = self._state.streams.copy()
      del new_states[stream.url]
      self._state = StateModel(streams=new_states)
      self.save_state()

  def _update_stream_state(self, url: str, **updates) -> None:
    new_states = self._state.streams.copy()
    stream_state = new_states.get(url, StreamState())
    for key, value in updates.items():
      setattr(stream_state, key, value)
    new_states[url] = stream_state
    self._state = StateModel(streams=new_states)
    self.save_state()

  def mark_stream_online(self, url: str) -> None:
    self._update_stream_state(url, is_online=True, last_online_ts=time.time())

  def mark_stream_offline(self, url: str) -> None:
    self._update_stream_state(url, is_online=False)

  def mark_stream_watched(self, url: str) -> None:
    self._update_stream_state(url, last_watched_ts=time.time())

  def is_stream_online(self, url: str) -> bool:
    stream = self._config.streams.get(url)
    if stream is not None and stream.always_on:
      return True
    stream_state = self._state.streams.get(url)
    return False if stream_state is None else stream_state.is_online

  def get_stream_last_online_ts(self, url: str) -> float | None:
    stream_state = self._state.streams.get(url)
    return None if stream_state is None else stream_state.last_online_ts

  def get_stream_last_watched_ts(self, url: str) -> float | None:
    stream_state = self._state.streams.get(url)
    return None if stream_state is None else stream_state.last_watched_ts

  def get_geometry(self, window_name: str) -> Geometry | None:
    return self._config.windows.get(window_name)

  def set_geometry(self, window_name: str, geometry: Geometry) -> None:
    new_windows = self._config.windows.copy()
    new_windows[window_name] = geometry
    self.set('windows', new_windows)
