#!/usr/bin/env python3
"""
StreamCondor - A system tray application for monitoring livestreams.
"""
import sys
import argparse
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QStandardPaths
from streamlink.exceptions import StreamlinkError, NoPluginError

from ui.trayicon import TrayIcon

log = logging.getLogger(__name__)


def setup_logging(log_level: str) -> None:
  numeric_level = getattr(logging, log_level.upper(), logging.INFO)
  logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
  )


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
  return parser.parse_args()


if __name__ == '__main__':
  args = parse_arguments()
  setup_logging(args.log_level)
  log.info('Starting StreamCondor...')
  sys.excepthook = excepthook
  # Create QApplication
  app = QApplication(sys.argv)
  app.setApplicationName('StreamCondor')
  app.setQuitOnLastWindowClosed(False)
  app.setStyle('Fusion')  # Temporarily disabled - may interfere with notifications
  # Initialize configuration
  config_path = args.config
  if not config_path:
    config_dir = Path(QStandardPaths.writableLocation(
      QStandardPaths.StandardLocation.ConfigLocation
    ))
    config_path = config_dir / 'StreamCondor.json'
  # Create and show system tray icon
  tray_icon = TrayIcon(app, config_path)
  tray_icon.show()
  log.info('StreamCondor started successfully')
  sys.exit(app.exec())
