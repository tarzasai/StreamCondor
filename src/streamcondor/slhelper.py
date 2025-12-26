import os
import logging
import configparser
import shlex
import subprocess
from streamlink import Streamlink
from PyQt6.QtCore import QStandardPaths

from streamcondor.model import Configuration, Stream

log = logging.getLogger(__name__)

sls = Streamlink(
  plugins_builtin=True,
)


def load_sl_user_stuff() -> None:
  # Load user config
  config_dir = QStandardPaths.writableLocation(
    QStandardPaths.StandardLocation.ConfigLocation
  )
  cfg_file = os.path.join(config_dir, 'streamlink', 'config')
  if os.path.exists(cfg_file):
    cfg = configparser.ConfigParser(strict=False)
    with open(cfg_file) as ini:
      cfg.read_string("[dummy]\n" + ini.read())
    for key in cfg['dummy']:
      try:
        sls.set_option(key, cfg['dummy'][key])
        log.debug(f"Loaded Streamlink config option {key}={cfg['dummy'][key]}")
      except Exception as err:
        log.error(f"Streamlink config option {key} error: {err}")
  # Load user plugins
  plugins_dir = QStandardPaths.writableLocation(
    QStandardPaths.StandardLocation.GenericDataLocation
  )
  plugins_path = os.path.join(plugins_dir, 'streamlink', 'plugins')
  if os.path.exists(plugins_path) and sls.plugins.load_path(plugins_path):
    log.debug(f"Loaded Streamlink user plugins from {plugins_path}: {', '.join(sls.plugins.get_names())}")


def is_stream_live(
  stream_url: str,
  auth_args: list[str],
  global_args: str = None,
  stream_args: str = None
) -> tuple[str, bool]:
  '''
  Check if a stream is live using Streamlink, considering required plugin arguments.

  Args:
    url: Stream URL
    req_args: List of required plugin argument names to check (e.g. username, password, etc)
    global_args: Global Streamlink arguments string
    stream_args: Stream-specific Streamlink arguments string

  Returns:
    Tuple of (plugin_name, is_live)
  '''
  # Let's try right away if it's a valid stream, otherwise it will raise NoPluginError
  plugin_name, plugin_class, _ = sls.resolve_url(stream_url)
  # Quick check; if streamlink find the streams we can return immediately
  if len(sls.streams(stream_url)) > 0:
    return plugin_name, True
  # No streams? The plugin might require authentication
  required_args = {}
  arg_prefix = plugin_name + '-'
  for k in plugin_class.arguments.keys():
    if next((a for a in auth_args if a in k), None) is not None:
      required_args[f"{arg_prefix}{k}"] = None
  if not required_args:
    return plugin_name, False # No authentication args for this plugin, I guess the stream is really offline
  # We'll merge all the session options, global Streamlink args and stream-specific args in a single dict
  # to find the values for the authentication arguments
  all_args = sls.options.copy() | _parse_args_string(global_args) | _parse_args_string(stream_args)
  for k in required_args.keys():
    if k in all_args:
      required_args[k] = all_args[k]
    else:
      raise ValueError(f"Required argument {k} for plugin {plugin_name} not found in merged args")
  # We need to remove the prefix from the arguments before passing them to the plugin
  plugin_args = {}
  for k in list(required_args.keys()):
    plugin_args[k[len(arg_prefix):]] = required_args[k]
  log.debug(f"Checking stream {stream_url} with plugin {plugin_name} and args {plugin_args}")
  # Now we can create the plugin instance passing the arguments with the correct names. Sadly this whole
  # process is only needed by plugins that require authentication (e.g. BBCIplayer, maybe Twitch, etc)
  plugin_instance = plugin_class(sls, stream_url, plugin_args)
  streams = plugin_instance.streams()
  log.debug(f"Stream {stream_url} has currently {len(streams)} available streams")
  return plugin_name, bool(streams)


def launch_process(command: str | list[str]) -> bool:
  '''
  Launch a command as a detached process.
  '''
  if isinstance(command, list):
    command = " ".join(command)
  try:
    log.debug(f'Launching process: {command}')
    # Launch process as a detached process
    subprocess.Popen(
      shlex.split(command),
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      start_new_session=True
    )
    return True
  except Exception as e:
    log.error(f'Error launching process: {e}')
    return False


def build_sl_command(cfg: Configuration, stream: Stream, alt_player: bool = False) -> list[str]:
  '''
  Build the Streamlink command merging stream-specific settings with global defaults.
  '''
  url = stream.url
  if not url:
    raise ValueError('Stream URL is required')
  # Merge default and custom streamlink arguments
  default_sl_args = cfg.default_streamlink_args.replace('$SC.name', stream.name or '').replace('$SC.type', stream.type or '')
  custom_sl_args = (stream.sl_args or '').replace('$SC.name', stream.name or '').replace('$SC.type', stream.type or '')
  merged_args = _merge_args_strings(default_sl_args, custom_sl_args)
  # The media player is optional
  player = cfg.alternate_player if alt_player and cfg.alternate_player else (stream.player or cfg.default_player)
  if player:
    merged_args += f" --player {player}"
  # Stream's player args override defaults (too complex to merge, even IF default and custom player are the same)
  player_args = cfg.alternate_player_args if alt_player and cfg.alternate_player_args else (stream.mp_args or cfg.default_player_args)
  if player_args:
    merged_args += f" --player-args {player_args}"
  # Quality: both the default and the stream-specific quality that we save in configuration may not be valid,
  # because every stream has its own set, and if our string doesn't match one of the available qualities the
  # command will fail (i.e. "720p60" instead of "720p"). Checking every time would be too much overhead, so
  # we just append "best" as a fallback. Eh oh.
  quality = filter(None, [stream.quality or cfg.default_quality, 'best'])
  # Build final command list
  command = ['streamlink']
  command.extend(_split_args_with_values(merged_args))
  command.append(url)
  command.append(','.join(quality))  ## this may ends up as "best,best", but streamlink doesn't care
  return command


def _parse_args_string(args_string: str) -> dict[str, str | None]:
  """
  Parse a command-line arguments string into a dictionary.

  Args:
    args_string: String containing command-line arguments

  Returns:
    Dictionary where keys are argument names (with dashes included) and values are
    either the argument value (str) or None for flags without values
  """
  if args_string is None or not args_string.strip():
    return {}
  # Use shlex to properly handle quoted values
  tokens = shlex.split(args_string)
  args_dict = {}
  i = 0
  while i < len(tokens):
    token = tokens[i]
    # Check if token starts with dash(es)
    if token.startswith('-'):
      # Keep the full argument name with dashes
      arg_name = token
      # Check if next token exists and is a value (not starting with dash)
      if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
        args_dict[arg_name] = tokens[i + 1]
        i += 2
      else:
        # Flag without value
        args_dict[arg_name] = None
        i += 1
    else:
      # This shouldn't happen if input is well-formed, but skip orphaned values
      i += 1
  return args_dict

def _split_args_with_values(args_string: str) -> list[str]:
  """
  Split a command-line arguments string into a list, keeping argument-value pairs together.

  Args:
    args_string: String containing command-line arguments

  Returns:
    List of strings where each element is either a flag (e.g., "--flag") or
    an argument with its value (e.g., "--option 123")
  """
  if not args_string.strip():
    return []
  # Use shlex to properly handle quoted values
  tokens = shlex.split(args_string)
  result = []
  i = 0
  while i < len(tokens):
    token = tokens[i]
    # Check if token starts with dash(es)
    if token.startswith('-'):
      # Check if next token exists and is a value (not starting with dash)
      if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
        # Combine argument with its value
        value = tokens[i + 1]
        # Quote the value if it contains spaces or special chars
        if ' ' in value or '"' in value or "'" in value:
          escaped_value = value.replace('"', '\\"')
          result.append(f'{token} "{escaped_value}"')
        else:
          result.append(f"{token} {value}")
        i += 2
      else:
        # Flag without value
        result.append(token)
        i += 1
    else:
      # Orphaned value (shouldn't happen with well-formed input)
      i += 1
  return result

def _merge_args_strings(default_args: str, override_args: str) -> str:
  """
  Merge two command-line argument strings, with override_args taking precedence.

  Args:
    default_args: String containing default command-line arguments
    override_args: String containing override or additional arguments

  Returns:
    Merged command-line arguments string
  """
  # Parse both strings into dictionaries
  default_dict = _parse_args_string(default_args)
  override_dict = _parse_args_string(override_args)
  # Merge dictionaries (override takes precedence)
  merged_dict = {**default_dict, **override_dict}
  # Reconstruct the command-line string
  result_parts = []
  for arg_name, arg_value in merged_dict.items():
    if arg_value is None:
      # Flag without value
      result_parts.append(arg_name)
    else:
      # Argument with value - quote if contains spaces or special chars
      if ' ' in arg_value or '"' in arg_value or "'" in arg_value:
        # Escape quotes and wrap in quotes
        escaped_value = arg_value.replace('"', '\\"')
        result_parts.append(f'{arg_name} "{escaped_value}"')
      else:
        result_parts.append(f"{arg_name} {arg_value}")
  return ' '.join(result_parts)
