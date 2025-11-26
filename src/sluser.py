import os
import platform
import configparser
from streamlink import Streamlink

sls = Streamlink(
  plugins_builtin=True
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
