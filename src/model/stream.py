

class Stream:

  def __init__(self, **kwargs):
    if kwargs and len(kwargs) == 1 and isinstance(next(iter(kwargs.values())), dict):
      self.data = next(iter(kwargs.values()))
    else:
      self.data = kwargs
    self.is_online = False
    self.last_checked: float | None = None

  @property
  def url(self) -> str:
    return self.data.get('url')

  @url.setter
  def url(self, value: str) -> None:
    self.data['url'] = value

  @property
  def name(self) -> str:
    return self.data.get('name')

  @name.setter
  def name(self, value: str) -> None:
    self.data['name'] = value

  @property
  def type(self) -> str:
    return self.data.get('type', 'unknown')

  @type.setter
  def type(self, value: str) -> None:
    self.data['type'] = value

  @property
  def quality(self) -> str:
    return self.data.get('quality')

  @quality.setter
  def quality(self, value: str) -> None:
    self.data['quality'] = value

  @property
  def player(self) -> str:
    return self.data.get('player')

  @player.setter
  def player(self, value: str) -> None:
    self.data['player'] = value

  @property
  def sl_args(self) -> str:
    return self.data.get('sl_args')

  @sl_args.setter
  def sl_args(self, value: str) -> None:
    self.data['sl_args'] = value

  @property
  def mp_args(self) -> str:
    return self.data.get('mp_args')

  @mp_args.setter
  def mp_args(self, value: str) -> None:
    self.data['mp_args'] = value

  @property
  def notify(self) -> bool:
    return self.data.get('notify')

  @notify.setter
  def notify(self, value: bool) -> None:
    self.data['notify'] = value