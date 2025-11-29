#!/usr/bin/env python3
"""
StreamCondor - A system tray application for monitoring livestreams.
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from streamlink.exceptions import StreamlinkError, NoPluginError

from ui.trayicon import TrayIcon

log = logging.getLogger(__name__)

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
  """Parse command-line arguments."""
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
  app.setQuitOnLastWindowClosed(False)
  sys.excepthook = excepthook  ## uses QMessageBox so must be set after QApplication
  tray_icon = TrayIcon(app, args.config)
  tray_icon.show()
  log.info('StreamCondor started')
  return app.exec()


if __name__ == '__main__':
  sys.exit(main())
