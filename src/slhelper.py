import os
import logging
import platform
import configparser
import shlex
import subprocess
from streamlink import Streamlink

from model import Configuration, Stream

log = logging.getLogger(__name__)

sls = Streamlink(
  plugins_builtin=True,
)

# Determine the path where a user config and plugins would be located based on the OS
# There is probably a better way to do it... also I don't know where they should be in MacOS
sl_user_path = \
    os.path.join('.local', 'share') if platform.system() == 'Linux' else \
    os.path.join('AppData', 'Roaming') if platform.system() == 'Windows' else \
    None

# This is needed to load the user streamlink config (if any)
cfg_file = os.path.join(os.path.expanduser('~'), sl_user_path, 'streamlink', 'config')
if os.path.exists(cfg_file):
    cfg = configparser.ConfigParser(strict=False)
    with open(cfg_file) as ini:
        cfg.read_string("[dummy]\n" + ini.read())
    for key in cfg['dummy']:
        try:
            sls.set_option(key, cfg['dummy'][key])
        except Exception as err:
            print(f"SL config: {err}")

# This is needed to load any user streamlink plugins
sls.plugins.load_path(os.path.join(os.path.expanduser('~'), sl_user_path, 'streamlink', 'plugins'))


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


def build_sl_command(cfg: Configuration, stream: Stream) -> list[str]:
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
  player = stream.player or cfg.default_media_player
  if player:
    merged_args += f" --player {player}"
  # Stream's player args override defaults (too complex to merge, even IF default and custom player are the same)
  player_args = stream.mp_args or cfg.default_media_player_args
  if player_args:
    merged_args += f" --player-args {player_args}"
  #
  command = ['streamlink']
  command.extend(_split_args_with_values(merged_args))
  command.append(url)
  command.append(stream.quality or cfg.default_quality)
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
  if not args_string.strip():
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
