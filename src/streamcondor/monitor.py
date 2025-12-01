import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from streamcondor.model import Configuration, Stream
from streamcondor.slhelper import is_stream_live

log = logging.getLogger(__name__)


class StreamMonitor(QThread):
  stream_online = pyqtSignal(Stream)
  stream_offline = pyqtSignal(Stream)

  def __init__(self, configuration: Configuration):
    super().__init__()
    self.cfg = configuration
    self.running = True
    self.paused = not self.cfg.autostart_monitoring
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
    for url in self.cfg.streams:
      last_check = self.last_check_time.get(url, 0)
      time_since_check = time.time() - last_check
      # Check if never checked or check_interval has elapsed
      if last_check == 0 or time_since_check >= self.cfg.check_interval:
        streams_to_check.append((url, last_check, self.cfg.streams[url]))
    # Sort by last check time (oldest first, never checked go first)
    streams_to_check.sort(key=lambda x: x[1])
    # Check only the first stream that's due
    if streams_to_check:
      url, _, stream = streams_to_check[0]
      self._check_single_stream(stream)
      self.last_check_time[url] = time.time()

  def _check_single_stream(self, stream: Stream) -> None:
    try:
      _, is_online = is_stream_live(stream.url, self.cfg.default_streamlink_args, stream.sl_args)
    except Exception as e:
      log.debug(f'Stream offline or error checking {stream.url}: {e}')
      is_online = False
    previous_status = self.stream_status.get(stream.url, False)
    # Detect status changes
    if is_online and not previous_status:
      log.info(f'Stream online: {stream.name}')
      self.stream_online.emit(stream)
    elif not is_online and previous_status:
      log.info(f'Stream offline: {stream.name}')
      self.stream_offline.emit(stream)
    self.stream_status[stream.url] = is_online

  def stop(self) -> None:
    self.running = False

  def pause(self) -> None:
    self.paused = True

  def resume(self) -> None:
    self.paused = False

  def get_online_streams(self) -> list[Stream]:
    online = [stream for stream in self.cfg.streams.values() if self.stream_status.get(stream.url, False)]
    return sorted(online, key=lambda s: (s.type or '', s.name or s.url or ''))
