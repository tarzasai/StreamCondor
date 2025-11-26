"""
Stream monitoring thread for StreamCondor.
"""
import logging
import time
from typing import Any
from PyQt6.QtCore import QThread, pyqtSignal

from configuration import Configuration
from sluser import sls

log = logging.getLogger(__name__)


class StreamMonitor(QThread):
  stream_online = pyqtSignal(dict)  # Emitted when a stream comes online
  stream_offline = pyqtSignal(dict)  # Emitted when a stream goes offline

  def __init__(self, configuration: Configuration):
    super().__init__()
    self.configuration = configuration
    self.running = True
    self.paused = not self.configuration.autostart_monitoring
    self.stream_status: dict[str, bool] = {}
    self.last_check_time: dict[str, float] = {}

  def run(self) -> None:
    while self.running:
      if not self.paused:
        self._check_streams()
      self.msleep(150)  ## it must be short to keep the app responsive

  def _check_streams(self) -> None:
    # Filter enabled streams that need checking
    streams_to_check = []
    for stream in self.configuration.streams:
      url = stream.get('url', '')
      if not url:
        continue
      last_check = self.last_check_time.get(url, 0)
      time_since_check = time.time() - last_check
      # Check if never checked or check_interval has elapsed
      if last_check == 0 or time_since_check >= self.configuration.check_interval:
        streams_to_check.append((url, last_check, stream))
    # Sort by last check time (oldest first, never checked go first)
    streams_to_check.sort(key=lambda x: x[1])
    # Check only the first stream that's due
    if streams_to_check:
      url, _, stream = streams_to_check[0]
      self._check_single_stream(url, stream)
      self.last_check_time[url] = time.time()

  def _check_single_stream(self, url: str, stream: dict) -> None:
    try:
      is_online = bool(sls.streams(url))
    except Exception as e:
      log.debug(f'Stream offline or error checking {url}: {e}')
      is_online = False
    previous_status = self.stream_status.get(url, False)
    # Detect status changes
    if is_online and not previous_status:
      log.info(f'Stream online: {stream.get("name", url)}')
      self.stream_online.emit(stream)
    elif not is_online and previous_status:
      log.info(f'Stream offline: {stream.get("name", url)}')
      self.stream_offline.emit(stream)
    self.stream_status[url] = is_online

  def stop(self) -> None:
    self.running = False

  def pause(self) -> None:
    self.paused = True

  def resume(self) -> None:
    self.paused = False

  def get_online_streams(self) -> list[dict[str, Any]]:
    streams = self.configuration.streams
    online = []
    for stream in streams:
      if self.stream_status.get(stream.get('url'), False):
        online.append(stream)
    return sorted(online, key=lambda s: (s.get('type', ''), s.get('name', s.get('url', ''))))
