#!/usr/bin/env python3
import os
import sys
import logging
import argparse
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from streamlink.exceptions import StreamlinkError, NoPluginError

from streamcondor.ui.trayicon import TrayIcon
from streamcondor.resources import get_app_icon

log = logging.getLogger(__name__)

os.environ.setdefault('QT_QPA_ORG_NAME', 'StreamCondor')
os.environ.setdefault('QT_QPA_APPLICATION_NAME', 'StreamCondor')
os.environ.setdefault('QT_LOGGING_RULES', 'qt.qpa.services=false')


def setup_logging(args) -> None:
  logging.basicConfig(
    level=getattr(logging, args.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
  )
  if args.denoise_logging:
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('charset_normalizer').setLevel(logging.WARNING)

def excepthook(exc_type, exc_value, exc_tb):
  log.critical(f"Uncaught exception {exc_type}", exc_info=(exc_type, exc_value, exc_tb))
  msg = f"{exc_value}"
  if issubclass(exc_type, NoPluginError):
    msg = "No Streamlink plugin found for this stream."
  elif issubclass(exc_type, StreamlinkError):
    msg = f"Streamlink error '{exc_value}'"
  else:
    msg = f"Error '{exc_value or exc_type}'"
  QMessageBox.critical(None, "StreamCondor Error", msg)

def parse_arguments() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description='StreamCondor - Monitor livestreams from system tray'
  )
  parser.add_argument(
    '-c', '--config',
    type=Path,
    help='Path to custom configuration file'
  )
  parser.add_argument(
    '-l', '--log-level',
    default='INFO',
    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    help='Set logging verbosity level'
  )
  parser.add_argument(
    '--denoise-logging',
    action='store_true',
    help='Reduce logging noise from dependencies'
  )
  return parser.parse_args()

def main() -> int:
  args = parse_arguments()
  setup_logging(args)
  app = QApplication([])
  app.setApplicationName('StreamCondor')
  app.setWindowIcon(get_app_icon('app'))
  try:
    app.setDesktopFileName('streamcondor.desktop')
  except Exception:
    pass ## Older Qt bindings or platforms may not support this; ignore safely.
  app.setQuitOnLastWindowClosed(False)
  sys.excepthook = excepthook ## uses QMessageBox so must be set after QApplication
  tray_icon = TrayIcon(app, args.config)
  tray_icon.show()
  return app.exec()


if __name__ == '__main__':
  sys.exit(main())
