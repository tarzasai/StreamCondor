import logging
import shlex
from streamlink import Streamlink
from streamlink.user_input import UserInputRequester
from streamlink_cli.argparser import (
  build_parser,
  setup_plugin_args,
  setup_plugin_options,
  setup_session_options,
)
from streamlink_cli.constants import CONFIG_FILES, PLUGIN_DIRS

log = logging.getLogger(__name__)


class _NonInteractiveUserInputRequester(UserInputRequester):
  '''
  Fail clearly instead of prompting: Lurkiti probes streams headlessly, so there
  is no console to answer Streamlink's interactive credential prompts.
  '''

  def ask(self, prompt: str) -> str:
    raise OSError(
      f'Streamlink requested interactive input ({prompt!r}), which Lurkiti cannot provide. '
      'Set the required value via Streamlink arguments or the Streamlink config file.'
    )

  def ask_password(self, prompt: str) -> str:
    raise OSError(
      f'Streamlink requested a password ({prompt!r}), which Lurkiti cannot provide. '
      'Set credentials via Streamlink arguments or the Streamlink config file.'
    )


sls = Streamlink({'user-input-requester': _NonInteractiveUserInputRequester()})

# Cached Streamlink CLI parser (built once, rebuilt whenever plugins are (re)loaded)
# and the discovered main config `@file` token(s). Both are populated by
# load_sl_user_stuff() at startup so the expensive parser build and config
# discovery don't happen on every liveness check.
_parser = None
_main_config_tokens: list[str] = []


def _build_streamlink_parser():
  '''
  Build a Streamlink CLI parser with plugin-specific arguments registered, so
  argument and config handling match the real `streamlink` command exactly.
  '''
  parser = build_parser()
  setup_plugin_args(sls, parser)
  return parser


def _main_streamlink_config_tokens() -> list[str]:
  '''Return the argparse `@file` token for the first existing main config file.'''
  for config_file in CONFIG_FILES:
    if config_file.is_file():
      return [f'@{config_file}']
  return []


def _plugin_streamlink_config_tokens(pluginname: str) -> list[str]:
  '''
  Return the argparse `@file` token for the first existing per-plugin config
  file (`config.<pluginname>`), where per-plugin credentials are often stored.
  '''
  if not pluginname:
    return []
  for config_file in CONFIG_FILES:
    plugin_config = config_file.with_name(f'{config_file.name}.{pluginname}')
    if plugin_config.is_file():
      return [f'@{plugin_config}']
  return []


def _parse_streamlink_tokens(tokens: list[str]):
  '''
  Parse Streamlink argument tokens using the cached CLI parser. The parser is
  built lazily if load_sl_user_stuff() hasn't run yet.
  '''
  global _parser
  if _parser is None:
    _parser = _build_streamlink_parser()
  try:
    args, extras = _parser.parse_known_args(tokens)
  except SystemExit as exc:
    raise RuntimeError('invalid Streamlink arguments') from exc
  if extras:
    log.warning(f'Ignoring unrecognized Streamlink arguments: {" ".join(extras)}')
  return args


def load_sl_user_stuff() -> None:
  '''
  Load (or reload) the user's Streamlink configuration and sideloaded plugins
  from Streamlink's standard directories, matching the `streamlink` command so a
  custom plugin or config dropped into e.g. `~/.local/share/streamlink/plugins`
  or `~/.config/streamlink/config` is picked up.

  This does the expensive work once: it loads plugins, rebuilds the cached CLI
  parser and applies the main config's session options to the shared session.
  It is safe to call again at runtime (e.g. from the settings "Reload Streamlink"
  button) to pick up changes without restarting the application.
  '''
  global _parser, _main_config_tokens
  # (Re)load user-provided ("sideloaded") plugins from Streamlink's standard plugin directories
  for directory in PLUGIN_DIRS:
    if not directory.is_dir():
      continue
    try:
      if sls.plugins.load_path(directory):
        log.debug(f'Loaded Streamlink user plugins from {directory}: {", ".join(sls.plugins.get_names())}')
    except Exception as err:
      log.error(f'Error loading Streamlink plugins from {directory}: {err}')
  # Rebuild the cached parser so newly loaded plugins' arguments are recognized
  _parser = _build_streamlink_parser()
  # Cache the main config token and apply its session options to the shared session
  # so it inherits the user's baseline (proxies, HTTP settings, etc.)
  _main_config_tokens = _main_streamlink_config_tokens()
  if _main_config_tokens:
    try:
      setup_session_options(sls, _parse_streamlink_tokens(_main_config_tokens))
      log.debug(f'Loaded Streamlink config from {_main_config_tokens}')
    except Exception as err:
      log.error(f'Error loading Streamlink config: {err}')


def is_stream_live(
  stream_url: str,
  global_args: str = None,
  stream_args: str = None
) -> tuple[str, bool]:
  '''
  Check whether a stream is currently live using Streamlink.

  Arguments, configuration files (including per-plugin config files) and plugin
  authentication are handled by Streamlink's own CLI argument parser, so behavior
  matches the real `streamlink` command. Plugins, the CLI parser and the main
  config are loaded once by load_sl_user_stuff(); only the (small) per-plugin
  config and per-stream arguments are parsed here on each check.

  Args:
    stream_url: Stream URL
    global_args: Global Streamlink arguments string
    stream_args: Stream-specific Streamlink arguments string (takes precedence)

  Returns:
    Tuple of (plugin_name, is_live)
  '''
  # Resolve the plugin first (raises NoPluginError for unsupported URLs) so the
  # matching per-plugin config file can be loaded alongside the CLI arguments.
  pluginname, pluginclass, resolved_url = sls.resolve_url(stream_url)
  # Build the token list the way the streamlink command would: config files first
  # (main config carries prefixed plugin args like `--twitch-password`, per-plugin
  # config carries the same for a single plugin), then global arguments, then
  # stream-specific arguments (last occurrence wins).
  tokens = (
    _main_config_tokens
    + _plugin_streamlink_config_tokens(pluginname)
    + shlex.split(global_args or '')
    + shlex.split(stream_args or '')
  )
  args = _parse_streamlink_tokens(tokens)
  # Apply session-level options and resolve plugin options (the latter carry
  # authentication credentials), then probe for available streams.
  setup_session_options(sls, args)
  options = setup_plugin_options(sls, args, pluginname, pluginclass)
  streams = pluginclass(sls, resolved_url, options).streams()
  log.debug(f'Stream {stream_url} [{pluginname}] has currently {len(streams)} available stream(s)')
  return pluginname, bool(streams)
