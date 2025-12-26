import logging
import platform
from PyQt6.QtWidgets import (
  QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QLineEdit, QDialogButtonBox, QFormLayout,
  QCheckBox, QTextEdit, QPushButton, QWidget, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from streamcondor.model import Configuration, Stream
from streamcondor.favicons import get_stream_icon
from streamcondor.slhelper import sls, build_sl_command

SL_ARGS_HINT = '''
<html><head/><body>
  <a href="https://streamlink.github.io/cli.html#general-options">
    <span style=" text-decoration: underline; color:#4285f4;">Streamlink command-line arguments</span>
  </a>
</body></html>
'''
MONOSPACE_FONT = QFont('monospace')
MONOSPACE_FONT.setStyleHint(QFont.StyleHint.Monospace)

log = logging.getLogger(__name__)


class StreamDialog(QDialog):

  def __init__(self, parent: QWidget, cfg: Configuration, stream: Stream | None = None, is_clone: bool = False):
    super().__init__(parent)
    self.cfg = cfg
    self.stream = stream
    self.is_clone = is_clone
    self.is_new = stream is None and not is_clone
    self.original_url = stream.url if stream else ''
    self.original_name = stream.name if stream else ''
    self._init_ui()
    self._check_clipboard_for_url()
    self._load_stream_data()
    self._connect_signals()

  def _can_save(self) -> bool:
    url = self.text_url.text().strip()
    name = self.text_name.text().strip()
    stype = self.text_type.text().strip()
    if not url or not name or not stype:
      return False
    if self.is_clone:
      return url != self.original_url
    return True

  def _init_ui(self) -> None:
    self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False) ## not working in Linux
    self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False) ## not working in Linux
    self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)    ## not working in Linux
    self.setMinimumSize(600, 320)
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
    self.tabs.currentChanged.connect(self._on_tab_changed)
    layout.addWidget(self.tabs)
    bottom = QHBoxLayout()
    self.sl_args_hint = QLabel(SL_ARGS_HINT)
    self.sl_args_hint.setStyleSheet('color: gray; font-size: 10pt;')
    self.sl_args_hint.setOpenExternalLinks(True)
    self.sl_args_hint.setVisible(False)
    bottom.addWidget(self.sl_args_hint)
    self.buttonBox = QDialogButtonBox(self)
    self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
    self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
    bottom.addWidget(self.buttonBox)
    layout.addLayout(bottom)
    self.setLayout(layout)
    # Save is disabled for new streams until URL is valid, and for clones until URL or name changes
    self._toggle_save_state(not self.is_new and not self.is_clone)

  def _create_general_tab(self) -> QWidget:
    # URL
    self.text_url = QLineEdit()
    self.text_url.setPlaceholderText('https://...')
    self.btn_refresh = QPushButton()
    self.btn_refresh.setIcon(QIcon.fromTheme("view-refresh"))
    self.btn_refresh.setToolTip('Re-evaluate stream URL')
    self.btn_refresh.clicked.connect(self._refresh_stream_info)
    url_box = QHBoxLayout()
    url_box.addWidget(self.text_url)
    url_box.addWidget(self.btn_refresh)
    # Type (read-only)
    self.text_type = QLineEdit()
    self.text_type.setReadOnly(True)
    self.text_type.setPlaceholderText('Auto-detected from URL')
    # Display name
    self.text_name = QLineEdit()
    self.text_name.setPlaceholderText('Optional custom name')
    # Media player
    self.text_player = QLineEdit()
    self.text_player.setPlaceholderText('Leave blank for default')
    # Preferred quality
    self.text_quality = QLineEdit()
    self.text_quality.setPlaceholderText('e.g., best, 720p (leave blank for default)')
    # Notify toggle
    self.check_notify = QCheckBox()
    self.check_notify.stateChanged.connect(self._update_notify_descr)
    self.check_notify.setTristate(True)
    self.check_notify.setCheckState(Qt.CheckState.Checked)
    # Always on toggle
    self.check_always_on = QCheckBox()
    self.check_always_on.setText("This stream is always live (disable notifications and monitoring)")
    # Form
    form_layout = QFormLayout()
    form_layout.setVerticalSizeConstraint(QFormLayout.SizeConstraint.SetMinimumSize)
    form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form_layout.addRow('Stream URL', url_box)
    form_layout.addRow('Stream type', self.text_type)
    form_layout.addRow('Display name', self.text_name)
    form_layout.addRow('Media player', self.text_player)
    form_layout.addRow('Preferred quality', self.text_quality)
    form_layout.addRow('Notify when live', self.check_notify)
    form_layout.addRow('Always streaming', self.check_always_on)
    widget = QWidget()
    widget.setLayout(form_layout)
    return widget

  def _create_sl_args_tab(self) -> QWidget:
    self.text_sl_args = QTextEdit()
    self.text_sl_args.setPlaceholderText('Enter custom streamlink arguments...')
    self.text_sl_args.setFont(MONOSPACE_FONT)
    self.text_sl_args.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    layout = QVBoxLayout()
    layout.addWidget(self.text_sl_args)
    widget = QWidget()
    widget.setLayout(layout)
    return widget

  def _create_mp_args_tab(self) -> QWidget:
    self.text_mp_args = QTextEdit()
    self.text_mp_args.setPlaceholderText('Enter custom media player arguments...')
    self.text_mp_args.setFont(MONOSPACE_FONT)
    self.text_mp_args.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    layout = QVBoxLayout()
    layout.addWidget(self.text_mp_args)
    widget = QWidget()
    widget.setLayout(layout)
    return widget

  def _create_preview_tab(self) -> QWidget:
    top_label = QLabel('This is the command that will be executed to launch the stream:')
    top_label.setStyleSheet('font-size: 10pt;')
    self.text_preview = QTextEdit()
    self.text_preview.setReadOnly(True)
    self.text_preview.setFont(MONOSPACE_FONT)
    self.text_preview.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    layout = QVBoxLayout()
    layout.addWidget(top_label)
    layout.addWidget(self.text_preview)
    widget = QWidget()
    widget.setLayout(layout)
    return widget

  def _on_tab_changed(self, index: int) -> None:
    self.sl_args_hint.setVisible(self.tabs.widget(index) == self.tab_sl_args)

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
    self.text_url.setText(str(self.stream.url))
    self.text_type.setText(self.stream.type)
    self.text_name.setText(self.stream.name)
    self.text_quality.setText(self.stream.quality)
    self.text_player.setText(self.stream.player)
    self.text_sl_args.setPlainText(self.stream.sl_args)
    self.text_mp_args.setPlainText(self.stream.mp_args)
    self.check_always_on.setChecked(self.stream.always_on)
    if self.stream.always_on:
      self.check_notify.setChecked(False)
      self.check_notify.setEnabled(False)
    else:
      self.check_notify.setCheckState(_optionalBoolToCheckState(self.stream.notify))
    self._update_title()
    self._update_preview()

  def _connect_signals(self) -> None:
    self.text_url.textChanged.connect(self._on_url_changed)
    self.text_name.textChanged.connect(self._on_name_changed)
    self.text_quality.textChanged.connect(self._update_preview)
    self.text_player.textChanged.connect(self._update_preview)
    self.text_sl_args.textChanged.connect(self._update_preview)
    self.text_mp_args.textChanged.connect(self._update_preview)
    self.check_always_on.checkStateChanged.connect(self._on_alwayson_changed)
    self.buttonBox.accepted.connect(self.accept)
    self.buttonBox.rejected.connect(self.reject)

  def _on_url_changed(self, url: str) -> None:
    if not url:
      self.text_type.clear()
    else:
      self._refresh_stream_info()
    self._toggle_save_state(self._can_save())

  def _on_name_changed(self, name: str) -> None:
    self._update_title()
    self._update_preview()
    self._toggle_save_state(self._can_save())

  def _on_alwayson_changed(self, state: Qt.CheckState) -> None:
    if state == Qt.CheckState.Checked:
      self.check_notify.setChecked(False)
      self.check_notify.setEnabled(False)
    else:
      self.check_notify.setEnabled(True)

  def _refresh_stream_info(self) -> None:
    url = self.text_url.text().strip()
    if url is not None:
      try:
        sls_info = sls.resolve_url(url)
        stream_type = sls_info[0]  ## The plugin name
        self.text_type.setText(stream_type)
        self._update_preview()
        get_stream_icon(self.get_stream(), size=16)  ## Preload favicon
      except Exception as e:
        self.text_type.clear()
        self._toggle_save_state(self._can_save())
        raise e

  def _update_title(self) -> None:
    self.setWindowTitle(
      f"Clone '{self.original_name}'" if self.is_clone else
      "Add Stream" if self.is_new else
      f"Edit '{self.original_name}'"
    )

  def _update_preview(self) -> None:
    url = self.text_url.text().strip()
    if url == '':
      self.text_preview.clear()
      return
    is_windows = platform.system() == 'Windows'
    continuation = '^' if is_windows else '\\'
    command = build_sl_command(self.cfg, self.get_stream())
    lines = [command.pop(0)]  # Start with the program name
    lines.extend([f'  {c}' for c in command])  # Indent the rest
    self.text_preview.setPlainText(f' {continuation}\n'.join(lines))

  def _update_notify_descr(self) -> None:
    if self.check_notify.checkState() == Qt.CheckState.PartiallyChecked:
      self.check_notify.setText(f"{'Yes' if self.cfg.default_notify else 'No'} (configuration default)")
    else:
      self.check_notify.setText("Yes" if self.check_notify.checkState() == Qt.CheckState.Checked else "No")

  def get_stream(self) -> Stream:
    return Stream(
      url=self.text_url.text().strip(),
      name=self.text_name.text().strip() or self.text_url.text().strip(),
      type=self.text_type.text().strip(),
      quality=self.text_quality.text().strip(),
      player=self.text_player.text().strip(),
      sl_args=self.text_sl_args.toPlainText().strip(),
      mp_args=self.text_mp_args.toPlainText().strip(),
      notify=_checkStateToOptionalBool(self.check_notify.checkState()),
      always_on=self.check_always_on.isChecked()
    )


def _checkStateToOptionalBool(state: Qt.CheckState) -> bool | None:
  return None if state == Qt.CheckState.PartiallyChecked else state == Qt.CheckState.Checked

def _optionalBoolToCheckState(value: bool | None) -> Qt.CheckState:
  return Qt.CheckState.PartiallyChecked if value is None else Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
