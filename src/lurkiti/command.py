import os
import sys
import logging
import shlex
import shutil
import tempfile
import subprocess

from lurkiti.model import Configuration, Stream

LOG_LEVEL_MAP = {
  logging.CRITICAL: 'critical',
  logging.ERROR: 'error',
  logging.WARNING: 'warning',
  logging.INFO: 'info',
  logging.DEBUG: 'debug',
  logging.NOTSET: 'trace',
}

log = logging.getLogger(__name__)


def launch_process(command: str | list[str]) -> bool:
  '''
  Launch a command as a detached process.
  '''
  if isinstance(command, list):
    tokens = command.copy()
  else:
    command = command or ''
    tokens = shlex.split(command)
  # we want to run streamlink as a Python module in case it's installed system-wide
  # but SC is running in a virtualenv OR a newer version is installed in home
  if not tokens:
    log.error('Empty command')
    return False
  if tokens[0] == 'streamlink':
    tokens = [sys.executable, '-m', 'streamlink'] + tokens[1:]
    log.debug(f'Using Python module: {shlex.join(tokens[:3])}')
  log.debug(f'Launching process: {shlex.join(tokens)}')
  try:
    is_debug = log.isEnabledFor(logging.DEBUG)
    log_dir = os.path.join(tempfile.gettempdir(), 'lurkiti')
    os.makedirs(log_dir, exist_ok=True)
    log_file = tempfile.NamedTemporaryFile(
      mode='w',
      suffix='.log',
      dir=log_dir,
      delete=False,
      delete_on_close=not is_debug
    )
    if is_debug:
      cmd_file = tempfile.NamedTemporaryFile(
        mode='w',
        prefix='cmd_',
        suffix='.log',
        dir=log_dir,
        delete=False
      )
      cmd_file.write(shlex.join(tokens) + '\n')
      cmd_file.close()
      log.debug(f'Command written to: {cmd_file.name}')
    log.debug(f'Process errors will be logged to: {log_file.name}')
    subprocess.Popen(
      tokens,
      stdout=log_file if is_debug else subprocess.DEVNULL,
      stderr=log_file,
      start_new_session=True
    )
    return True
  except Exception as e:
    log.error(f'Error launching process: {e}')
    return False


def build_launch_command(cfg: Configuration, stream: Stream, alt_player: bool = False) -> list[str]:
  '''
  Build the launch command for a stream, either using Clippiti or Streamlink.
  Clippiti is used when the player is set to "clippiti" and clippiti_path is configured or found in PATH.
  '''
  url = stream.url
  if not url:
    raise ValueError('Stream URL is required')
  # Determine the player
  player = cfg.alternate_player if alt_player and cfg.alternate_player else (stream.player or cfg.default_player)
  # Check if we should use Clippiti
  if player == 'clippiti':
    # Use explicit clippiti_path if set, otherwise search for it in PATH
    clippiti_path = cfg.clippiti_path or shutil.which('clippiti')
    if clippiti_path:
      return _build_clippiti_command(cfg, stream, alt_player, clippiti_path)
  # Fallback to Streamlink
  return _build_streamlink_command(cfg, stream, alt_player, player)


def _resolve_quality(cfg: Configuration, stream: Stream) -> str:
  '''
  Build the comma-separated quality priority list, appending "best" as a fallback.
  Duplicates are dropped (order preserved) so it doesn't end up as "best,best".
  '''
  qualities = []
  for q in [stream.quality or cfg.default_quality, 'best']:
    if q and q not in qualities:
      qualities.append(q)
  return ','.join(qualities)


def _build_streamlink_command(cfg: Configuration, stream: Stream, alt_player: bool, player: str) -> list[str]:
  '''
  Build the Streamlink command merging stream-specific settings with global defaults.
  '''
  url = stream.url
  # Merge default and custom streamlink arguments
  default_sl_args = cfg.default_streamlink_args.replace('$SC.name', stream.name or '').replace('$SC.type', stream.type or '')
  custom_sl_args = (stream.sl_args or '').replace('$SC.name', stream.name or '').replace('$SC.type', stream.type or '')
  merged_args = _merge_args_strings(default_sl_args, custom_sl_args)
  # Set log level according to our own
  merged_args += f" --loglevel {LOG_LEVEL_MAP.get(logging.getLogger().getEffectiveLevel(), 'info')}"
  # The media player is optional
  if player:
    merged_args += f" --player {player}"
  # Alternate launches must not inherit any global player args.
  # Only stream-specific args are allowed when using alt_player.
  player_args = stream.mp_args if alt_player else (stream.mp_args or cfg.default_player_args)
  resolved_player_args = None
  if player_args:
    # Player args are treated as a raw single string. Only replace Lurkiti placeholders.
    sc_name = shlex.quote(stream.name) if stream.name else ''
    sc_type = shlex.quote(stream.type) if stream.type else ''
    resolved_player_args = player_args.replace('$SC.name', sc_name).replace('$SC.type', sc_type)
  # Quality: both the default and the stream-specific quality that we save in configuration may not be valid,
  # because every stream has its own set, and if our string doesn't match one of the available qualities the
  # command will fail (i.e. "720p60" instead of "720p"). Checking every time would be too much overhead, so
  # we just append "best" as fallback. Eh oh.
  quality = _resolve_quality(cfg, stream)
  # Build final command list
  command = ['streamlink']
  command.extend(_split_args_with_values(merged_args))
  if resolved_player_args:
    command.append(f'--player-args={resolved_player_args}')
  command.append(url)
  command.append(quality)
  return command


def _build_clippiti_command(cfg: Configuration, stream: Stream, alt_player: bool, clippiti_path: str) -> list[str]:
  '''
  Build the Clippiti command merging stream-specific settings with global defaults.
  Clippiti uses a different argument structure than Streamlink: Streamlink arguments
  are passed after a '--' separator (as individual tokens), while Clippiti-specific
  arguments (like --mpv) come before it.
  Player args are only included if the configured player is mpv (the only player clippiti understands).
  '''
  url = stream.url
  # Merge default and custom streamlink arguments, but exclude --title and --player
  default_sl_args = cfg.default_streamlink_args.replace('$SC.name', stream.name or '').replace('$SC.type', stream.type or '')
  custom_sl_args = (stream.sl_args or '').replace('$SC.name', stream.name or '').replace('$SC.type', stream.type or '')
  merged_sl_args = _merge_args_strings(default_sl_args, custom_sl_args)
  # Remove --title and --player from streamlink args for Clippiti
  merged_sl_args = _remove_args_from_string(merged_sl_args, ['--title', '--player'])
  # Resolve quality
  quality = _resolve_quality(cfg, stream)
  # Build Clippiti command
  command = [clippiti_path, url, quality]
  # Determine the player whose args we'd be using
  relevant_player = cfg.alternate_player if alt_player and cfg.alternate_player else cfg.default_player
  # Only add mpv args if the relevant player is actually mpv (the only player clippiti understands)
  if relevant_player == 'mpv':
    player_args = stream.mp_args if alt_player else (stream.mp_args or cfg.default_player_args)
    if player_args:
      # Player args are treated as a raw single string. Only replace Lurkiti placeholders.
      sc_name = shlex.quote(stream.name) if stream.name else ''
      sc_type = shlex.quote(stream.type) if stream.type else ''
      resolved_player_args = player_args.replace('$SC.name', sc_name).replace('$SC.type', sc_type)
      command.append('--mpv')
      command.append(resolved_player_args)
  # Streamlink args are forwarded after a '--' separator as individual tokens
  if merged_sl_args.strip():
    command.append('--')
    command.extend(_split_args_with_values(merged_sl_args))
  return command


def _remove_args_from_string(args_string: str, args_to_remove: list[str]) -> str:
  '''
  Remove specified arguments from a command-line arguments string.
  Handles both flags and options with values.

  Args:
    args_string: String containing command-line arguments
    args_to_remove: List of argument names to remove (with dashes)

  Returns:
    String with specified arguments removed
  '''
  if not args_string.strip():
    return ''
  tokens = shlex.split(args_string)
  filtered_tokens = []
  i = 0
  while i < len(tokens):
    token = tokens[i]
    # Check if this token is an argument we should remove
    should_remove = False
    for arg_to_remove in args_to_remove:
      if token == arg_to_remove or token.startswith(arg_to_remove + '='):
        should_remove = True
        break
    if should_remove:
      # If it's a flag-only argument (no '=' and no following value), just skip it
      if '=' not in token and (i + 1 >= len(tokens) or tokens[i + 1].startswith('-')):
        i += 1
      # If it's an argument with '=', skip just this token
      elif '=' in token:
        i += 1
      # If it's an argument with a following value, skip both
      else:
        i += 2
    else:
      filtered_tokens.append(token)
      i += 1
  return ' '.join(filtered_tokens)


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
  Split a command-line arguments string into tokens.

  Args:
    args_string: String containing command-line arguments

  Returns:
    List of argument tokens preserving quoted values as single entries.
  """
  if not args_string.strip():
    return []
  return shlex.split(args_string)


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
