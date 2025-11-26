"""
Edit Stream dialog for StreamCondor.
"""
import logging
from PyQt6.QtWidgets import (
  QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QLineEdit, QDialogButtonBox,
  QCheckBox, QTextEdit, QPushButton, QGridLayout, QWidget, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from configuration import Configuration
from favicons import Favicons
from sluser import sls
from launcher import StreamLauncher


log = logging.getLogger(__name__)


class StreamDialog(QDialog):
  """Dialog for adding or editing a stream."""

  def __init__(
    self,
    parent: QWidget,
    configuration: Configuration,
    favicons: Favicons,
    launcher: StreamLauncher,
    stream: dict | None = None,
    is_clone: bool = False,
  ):
    """Initialize edit stream dialog.

    Args:
      parent: Parent widget
      configuration: Configuration instance
      favicons: Favicons instance
      launcher: StreamLauncher instance
      stream: Stream configuration to edit (None for new stream)
      is_clone: Whether this is a clone of an existing stream
    """
    super().__init__(parent)
    self.cfg = configuration
    self.favicons = favicons
    self.launcher = launcher
    self.stream = stream.copy() if stream else {}
    self.is_new = stream is None and not is_clone
    self.is_clone = is_clone
    self.original_url = stream.get('url', '') if is_clone else ''
    self.original_name = stream.get('name', '') if is_clone else ''
    self._init_ui()
    self._check_clipboard_for_url()
    self._load_stream_data()
    self._connect_signals()

  def _init_ui(self) -> None:
    self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False) ## working in Linux
    self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False) ## working in Linux
    self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)    ## working in Linux
    self.setMinimumSize(600, 290)
    self.setWindowTitle(f"{ 'Clone' if self.is_clone else 'Add' if self.is_new else 'Edit' } Stream")
    layout = QVBoxLayout()
    self.tabs = QTabWidget()
    self.tab_general = self._create_general_tab()
    self.tab_sl_args = self._create_sl_args_tab()
    self.tab_mp_args = self._create_mp_args_tab()
    self.tab_preview = self._create_preview_tab()
    self.tabs.addTab(self.tab_general, 'General')
    self.tabs.addTab(self.tab_sl_args, 'Streamlink Arguments')
    self.tabs.addTab(self.tab_mp_args, 'Player Arguments')
    self.tabs.addTab(self.tab_preview, 'Launch Command')
    layout.addWidget(self.tabs)
    self.buttonBox = QDialogButtonBox(self)
    self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
    self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
    layout.addWidget(self.buttonBox)
    self.setLayout(layout)
    # Save is disabled for new streams until URL is valid, and for clones until URL or name changes
    self._toggle_save_state(not self.is_new and not self.is_clone)

  def _create_general_tab(self) -> QWidget:
    widget = QWidget()
    layout = QGridLayout()
    row = 0
    # URL
    layout.addWidget(QLabel('Stream URL:'), row, 0)
    url_layout = QHBoxLayout()
    self.text_url = QLineEdit()
    self.text_url.setPlaceholderText('https://...')
    url_layout.addWidget(self.text_url)
    self.btn_refresh = QPushButton('🔄')
    self.btn_refresh.setMaximumWidth(30)
    self.btn_refresh.setToolTip('Re-evaluate stream URL')
    self.btn_refresh.clicked.connect(self._refresh_stream_info)
    url_layout.addWidget(self.btn_refresh)
    layout.addLayout(url_layout, row, 1)
    row += 1
    # Type (read-only)
    layout.addWidget(QLabel('Stream type:'), row, 0)
    self.text_type = QLineEdit()
    self.text_type.setReadOnly(True)
    self.text_type.setPlaceholderText('Auto-detected from URL')
    layout.addWidget(self.text_type, row, 1)
    row += 1
    # Display name
    layout.addWidget(QLabel('Display name:'), row, 0)
    self.text_name = QLineEdit()
    self.text_name.setPlaceholderText('Optional custom name')
    layout.addWidget(self.text_name, row, 1)
    row += 1
    # Media player
    layout.addWidget(QLabel('Media player:'), row, 0)
    self.text_player = QLineEdit()
    self.text_player.setPlaceholderText('Leave blank for default')
    layout.addWidget(self.text_player, row, 1)
    row += 1
    # Preferred quality
    layout.addWidget(QLabel('Preferred quality:'), row, 0)
    self.text_quality = QLineEdit()
    self.text_quality.setPlaceholderText('e.g., best, 720p (leave blank for default)')
    layout.addWidget(self.text_quality, row, 1)
    row += 1
    # Notify toggle
    layout.addWidget(QLabel('Notify when live:'), row, 0)
    self.check_notify = QCheckBox()
    self.check_notify.stateChanged.connect(self._update_notify_descr)
    self.check_notify.setTristate(True)
    self.check_notify.setCheckState(Qt.CheckState.Checked)
    layout.addWidget(self.check_notify, row, 1)
    row += 1
    # Add stretch at bottom
    layout.setRowStretch(row, 1)
    widget.setLayout(layout)
    return widget

  def _create_sl_args_tab(self) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    # Text area
    self.text_sl_args = QTextEdit()
    self.text_sl_args.setPlaceholderText('Enter custom streamlink arguments...')
    # Set monospace font
    font = QFont('monospace')
    font.setStyleHint(QFont.StyleHint.Monospace)
    self.text_sl_args.setFont(font)
    self.text_sl_args.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    layout.addWidget(self.text_sl_args)
    # Hint text
    hint = QLabel('Hint: Add custom streamlink options here (e.g., --http-no-ssl-verify)')
    hint.setStyleSheet('color: gray; font-size: 10pt;')
    layout.addWidget(hint)
    widget.setLayout(layout)
    return widget

  def _create_mp_args_tab(self) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    # Text area
    self.text_mp_args = QTextEdit()
    self.text_mp_args.setPlaceholderText('Enter custom media player arguments...')
    # Set monospace font
    font = QFont('monospace')
    font.setStyleHint(QFont.StyleHint.Monospace)
    self.text_mp_args.setFont(font)
    self.text_mp_args.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    layout.addWidget(self.text_mp_args)
    # Hint text
    hint = QLabel('Hint: Add custom media player options here')
    hint.setStyleSheet('color: gray; font-size: 10pt;')
    layout.addWidget(hint)
    widget.setLayout(layout)
    return widget

  def _create_preview_tab(self) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    # Read-only text area
    self.text_preview = QTextEdit()
    self.text_preview.setReadOnly(True)
    # Set monospace font
    font = QFont('monospace')
    font.setStyleHint(QFont.StyleHint.Monospace)
    self.text_preview.setFont(font)
    self.text_preview.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    layout.addWidget(self.text_preview)
    widget.setLayout(layout)
    return widget

  def _toggle_save_state(self, enabled: bool) -> None:
    self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(enabled)

  def _check_clipboard_for_url(self) -> None:
    if not self.is_new:
      return
    clipboard = QApplication.clipboard()
    text = clipboard.text().strip()
    if text and (text.startswith('http://') or text.startswith('https://')):
      log.debug(f"Found URL in clipboard: {text}")
      self.text_url.setText(text)
      # This method is intentionally called before connecting text_url's
      # signal, so we have to manually call this:
      self._refresh_stream_info()

  def _load_stream_data(self) -> None:
    if not self.stream:
      return
    self.text_url.setText(self.stream.get('url', ''))
    self.text_type.setText(self.stream.get('type', ''))
    self.text_name.setText(self.stream.get('name', ''))
    self.check_notify.setCheckState(_optionalBoolToCheckState(self.stream.get('notify')))
    self.text_quality.setText(self.stream.get('quality', ''))
    self.text_player.setText(self.stream.get('player', ''))
    self.text_sl_args.setPlainText(self.stream.get('sl_args', ''))
    self.text_mp_args.setPlainText(self.stream.get('mp_args', ''))
    self._update_preview()

  def _connect_signals(self) -> None:
    self.text_url.textChanged.connect(self._on_url_changed)
    self.text_name.textChanged.connect(self._on_name_changed)
    self.text_quality.textChanged.connect(self._update_preview)
    self.text_player.textChanged.connect(self._update_preview)
    self.text_sl_args.textChanged.connect(self._update_preview)
    self.text_mp_args.textChanged.connect(self._update_preview)
    self.buttonBox.accepted.connect(self.accept)
    self.buttonBox.rejected.connect(self.reject)

  def _on_url_changed(self, url: str) -> None:
    if not url:
      self.text_type.clear()
      self._toggle_save_state(False)
      return
    if self.is_clone:
      current_name = self.text_name.text().strip()
      url_changed = url.strip() != self.original_url
      name_changed = current_name != self.original_name
      self._toggle_save_state(url_changed or name_changed)
    else:
      self._toggle_save_state(True)
    self._refresh_stream_info()

  def _on_name_changed(self, name: str) -> None:
    current_url = self.text_url.text().strip()
    if self.is_clone:
      url_changed = current_url != self.original_url
      name_changed = name.strip() != self.original_name
    else:
      url_changed = current_url != ''
      name_changed = name.strip() != ''
    self._toggle_save_state(url_changed or name_changed)
    self._update_preview()

  def _refresh_stream_info(self) -> None:
    url = self.text_url.text().strip()
    if url is not None:
      try:
        sls_info = sls.resolve_url(url)
        stream_type = sls_info[0]  ## The plugin name
        self.text_type.setText(stream_type)
        self._update_preview()
        self.favicons.fetch_favicon(url, stream_type)
      except Exception as e:
        self._toggle_save_state(False)
        raise e

  def _update_preview(self) -> None:
    url = self.text_url.text().strip()
    command = None if url == '' else self.launcher.format_command_display({
      'url': url,
      'name': self.text_name.text().strip(),
      'type': self.text_type.text().strip(),
      'quality': self.text_quality.text().strip(),
      'player': self.text_player.text().strip(),
      'sl_args': self.text_sl_args.toPlainText().strip(),
      'mp_args': self.text_mp_args.toPlainText().strip()
    })
    self.text_preview.setPlainText(command)

  def _update_notify_descr(self) -> None:
    if self.check_notify.checkState() == Qt.CheckState.PartiallyChecked:
      self.check_notify.setText(f"{'Yes' if self.cfg.default_notify else 'No'} (configuration default)")
    else:
      self.check_notify.setText("Yes" if self.check_notify.checkState() == Qt.CheckState.Checked else "No")

  def get_stream(self) -> dict:
    return {
      'url': self.text_url.text().strip(),
      'name': self.text_name.text().strip() or self.text_url.text().strip(),
      'type': self.text_type.text().strip(),
      'quality': self.text_quality.text().strip(),
      'player': self.text_player.text().strip(),
      'sl_args': self.text_sl_args.toPlainText().strip(),
      'mp_args': self.text_mp_args.toPlainText().strip(),
      'notify': _checkStateToOptionalBool(self.check_notify.checkState())
    }


def _checkStateToOptionalBool(state: Qt.CheckState) -> bool | None:
  return None if state == Qt.CheckState.PartiallyChecked else state == Qt.CheckState.Checked

def _optionalBoolToCheckState(value: bool | None) -> Qt.CheckState:
  return Qt.CheckState.PartiallyChecked if value is None else Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
