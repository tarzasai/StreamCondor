"""
Streamlink launcher for StreamCondor.
"""
import logging
import shlex
import subprocess
import platform

from configuration import Configuration

log = logging.getLogger(__name__)


class StreamLauncher:
  """Handles launching streamlink with configured options."""

  def __init__(self, configuration: Configuration):
    """Initialize StreamlinkLauncher.

    Args:
      configuration: ConfigManager instance
    """
    self.cfg = configuration

  def launch_stream(self, stream: dict) -> bool:
    """Launch a stream using streamlink.

    Args:
      stream: Stream configuration dictionary with url, quality, player, etc.

    Returns:
      True if launch was successful
    """
    try:
      command = self.build_command(stream)
      command_line = " ".join(command)
      log.debug(f'Launching stream: {command_line}')
      # Launch streamlink as a detached process
      subprocess.Popen(
        shlex.split(command_line),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
      )
      return True
    except Exception as e:
      log.error(f'Error launching stream: {e}')
      return False

  def build_command(self, stream: dict) -> list[str]:
    """Build streamlink command with all options.

    Args:
      stream: Stream configuration dictionary

    Returns:
      Command as list of strings
    """
    # Get stream URL (required)
    url = stream.get('url', '')
    if not url:
      raise ValueError('Stream URL is required')
    # Merge default and custom streamlink arguments
    default_sl_args = self.cfg.default_streamlink_args.replace('$SC.name', stream['name']).replace('$SC.type', stream['type'])
    custom_sl_args = stream.get('sl_args', '').replace('$SC.name', stream['name']).replace('$SC.type', stream['type'])
    merged_args = merge_args_strings(default_sl_args, custom_sl_args)
    #
    player = stream.get('player') or self.cfg.default_media_player
    if player:
      merged_args += f" --player {player}"
    #
    player_args = stream.get('mp_args') or self.cfg.default_media_player_args
    if player_args:
      merged_args += f" --player-args {player_args}"
    #
    command = ['streamlink']
    command.extend(split_args_with_values(merged_args))
    command.append(url)
    command.append(stream.get('quality') or self.cfg.default_quality)
    return command

  def format_command_display(self, stream: dict) -> str:
    """Format command for display with proper line breaks.

    Args:
      stream: Stream configuration dictionary

    Returns:
      Formatted command string
    """
    # Determine line continuation character based on OS
    is_windows = platform.system() == 'Windows'
    continuation = '^' if is_windows else '\\'
    command = self.build_command(stream)
    lines = [command.pop(0)]  # Start with the program name
    lines.extend([f'  {c}' for c in command])  # Indent the rest
    return f' {continuation}\n'.join(lines)


def parse_args_string(args_string: str) -> dict[str, str | None]:
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

def split_args_with_values(args_string: str) -> list[str]:
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

def merge_args_strings(default_args: str, override_args: str) -> str:
  """
  Merge two command-line argument strings, with override_args taking precedence.

  Args:
    default_args: String containing default command-line arguments
    override_args: String containing override or additional arguments

  Returns:
    Merged command-line arguments string
  """
  # Parse both strings into dictionaries
  default_dict = parse_args_string(default_args)
  override_dict = parse_args_string(override_args)
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


# Example usage and tests
if __name__ == "__main__":
  # Test split_args_with_values
  print("=== Testing split_args_with_values ===")
  test_string = "--flag --option 123 -x -y hello"
  split_result = split_args_with_values(test_string)
  print(f"Input:  {test_string}")
  print(f"Result: {split_result}")
  print()

  # Test with quoted values
  test_string2 = '--message "hello world" --flag -n 42'
  split_result2 = split_args_with_values(test_string2)
  print(f"Input:  {test_string2}")
  print(f"Result: {split_result2}")
  print()

  print("=== Testing merge_args_strings ===")
  # Test case 1: Basic merging
  default = '--flag --option 123 -x -y hello'
  override = '--option 456 -z'
  result = merge_args_strings(default, override)
  print(f"Default:  {default}")
  print(f"Override: {override}")
  print(f"Result:   {result}")
  print()

  # Test case 2: Override with value changes flag to valued arg
  default = '--verbose --output file.txt'
  override = '--verbose info --debug'
  result = merge_args_strings(default, override)
  print(f"Default:  {default}")
  print(f"Override: {override}")
  print(f"Result:   {result}")
  print()

  # Test case 3: Values with spaces
  default = '--message "hello world" --count 5'
  override = '--message "goodbye universe"'
  result = merge_args_strings(default, override)
  print(f"Default:  {default}")
  print(f"Override: {override}")
  print(f"Result:   {result}")
  print()

  # Test case 4: Empty override
  default = '--flag --option 123'
  override = ''
  result = merge_args_strings(default, override)
  print(f"Default:  {default}")
  print(f"Override: {override}")
  print(f"Result:   {result}")
  print()

  # Test case 5: Mix of single and double dash args, including -ab style
  default = '-a 1 --beta 2 -c -ab value'
  override = '--beta 3 -d 4 -ab newvalue'
  result = merge_args_strings(default, override)
  print(f"Default:  {default}")
  print(f"Override: {override}")
  print(f"Result:   {result}")
