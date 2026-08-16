import logging
import time
from datetime import datetime
from PyQt6.QtWidgets import (
  QWidget, QFormLayout, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeView, QPushButton, QToolButton,
  QLabel, QSpinBox, QCheckBox, QComboBox, QLineEdit, QTextEdit, QSizePolicy,
  QMessageBox, QAbstractItemView, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QAbstractItemModel, QModelIndex, QItemSelection
from PyQt6.QtGui import QIcon, QFont
from importlib.metadata import version, PackageNotFoundError

from lurkiti.model import Configuration, Stream, TrayIconAction
from lurkiti.command import launch_process, build_launch_command
from lurkiti.session import load_sl_user_stuff
from lurkiti.favicons import get_stream_icon
from lurkiti.ui.stream import StreamDialog

# Determine version: prefer installed distribution metadata, fallback to package __version__
try:
  dist_ver = version('lurkiti')
except PackageNotFoundError:
  import lurkiti
  dist_ver = getattr(lurkiti, '__version__', 'dev')

log = logging.getLogger(__name__)


def _create_stream_action_button(
  label: str,
  handler,
  *,
  tooltip: str | None = None,
  fixed_width: int | None = None,
  fixed_height: int | None = None,
) -> QToolButton:
  button = QToolButton()
  button.setText(label)
  button.setAutoRaise(False)
  button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
  button.clicked.connect(handler)
  if tooltip is not None:
    button.setToolTip(tooltip)
  if fixed_width is not None:
    button.setFixedWidth(fixed_width)
  if fixed_height is not None:
    button.setFixedHeight(fixed_height)
  return button


def _format_relative_time(timestamp: float | None) -> str:
  if timestamp is None:
    return ''
  delta_seconds = max(0, int(time.time() - timestamp))
  if delta_seconds < 60:
    return 'just now'
  if delta_seconds < 3600:
    minutes = delta_seconds // 60
    return f'{minutes} minute ago' if minutes == 1 else f'{minutes} minutes ago'
  if delta_seconds < 86400:
    hours = delta_seconds // 3600
    return f'{hours} hour ago' if hours == 1 else f'{hours} hours ago'
  if delta_seconds < 2592000:
    days = delta_seconds // 86400
    return f'{days} day ago' if days == 1 else f'{days} days ago'
  if delta_seconds < 31536000:
    months = delta_seconds // 2592000
    return f'{months} month ago' if months == 1 else f'{months} months ago'
  years = delta_seconds // 31536000
  return f'{years} year ago' if years == 1 else f'{years} years ago'


def _format_absolute_time(timestamp: float | None) -> str:
  if timestamp is None:
    return 'Never'
  return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


class StreamTreeNode:

  def __init__(self, data: Stream | str | None, parent: 'StreamTreeNode' | None = None):
    """Initialize tree node.

    Args:
      data: Either a Stream object or a type string (for group nodes)
      parent: Parent node
    """
    self.data = data
    self.parent = parent
    self.children: list[StreamTreeNode] = []

  def is_group(self) -> bool:
    return isinstance(self.data, str)

  def is_stream(self) -> bool:
    return isinstance(self.data, Stream)

  def add_child(self, child: 'StreamTreeNode') -> None:
    self.children.append(child)

  def child(self, row: int) -> 'StreamTreeNode' | None:
    if 0 <= row < len(self.children):
      return self.children[row]
    return None

  def child_count(self) -> int:
    return len(self.children)

  def row(self) -> int:
    if self.parent:
      return self.parent.children.index(self)
    return 0


class StreamListModel(QAbstractItemModel):

  def __init__(self, configuration: Configuration):
    super().__init__()
    self.cfg = configuration
    self.root_node = StreamTreeNode(None)
    self.blockSignals(True)
    self._build_tree()
    self.blockSignals(False)

  def _build_tree(self) -> None:
    # Clear existing tree
    self.root_node = StreamTreeNode(None)
    # Group streams by type
    streams_by_type: dict[str, list[Stream]] = {}
    for stream in self.cfg.streams.values():
      if stream.type not in streams_by_type:
        streams_by_type[stream.type] = []
      streams_by_type[stream.type].append(stream)
    # Build tree with sorted types
    for stream_type in sorted(streams_by_type.keys()):
      # Create type group node
      type_node = StreamTreeNode(stream_type, self.root_node)
      self.root_node.add_child(type_node)
      # Add streams sorted by name
      streams = sorted(
        streams_by_type[stream_type],
        key=lambda s: (s.name or s.url or 'Unknown').lower()
      )
      for stream in streams:
        stream_node = StreamTreeNode(stream, type_node)
        type_node.add_child(stream_node)

  def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
    if not self.hasIndex(row, column, parent):
      return QModelIndex()
    if not parent.isValid():
      parent_node = self.root_node
    else:
      parent_node = parent.internalPointer()
    child_node = parent_node.child(row)
    if child_node:
      return self.createIndex(row, column, child_node)
    return QModelIndex()

  def parent(self, index: QModelIndex) -> QModelIndex:
    if not index.isValid():
      return QModelIndex()
    child_node = index.internalPointer()
    parent_node = child_node.parent
    if parent_node == self.root_node or parent_node is None:
      return QModelIndex()
    return self.createIndex(parent_node.row(), 0, parent_node)

  def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
    if parent.column() > 0:
      return 0
    if not parent.isValid():
      parent_node = self.root_node
    else:
      parent_node = parent.internalPointer()
    return parent_node.child_count()

  def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
    return 6  # Name (with checkbox/icon), Quality, Player, Online, Last online, Last watched

  def headerData(self, section: int, orientation, role: int):
    if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
      if section == 0:
        return 'Stream'
      elif section == 1:
        return 'Pref. quality'
      elif section == 2:
        return 'Player'
      elif section == 3:
        return 'Online'
      elif section == 4:
        return 'Last online'
      elif section == 5:
        return 'Last watched'
    return None

  def data(self, index: QModelIndex, role: int):
    if not index.isValid():
      return None
    node = index.internalPointer()
    if role == Qt.ItemDataRole.UserRole:
      return node
    column = index.column()
    if role == Qt.ItemDataRole.DisplayRole:
      if column == 0:
        return node.data.capitalize() if node.is_group() else node.data.name
      if node.is_stream():
        stream = node.data
        if column == 1:
          return stream.quality or self.cfg.default_quality
        if column == 2:
          return stream.player or self.cfg.default_player
        if column == 3:
          return '✓' if self.cfg.is_stream_online(stream.url) else ''
        if column == 4:
          return _format_relative_time(self.cfg.get_stream_last_online_ts(stream.url))
        if column == 5:
          return _format_relative_time(self.cfg.get_stream_last_watched_ts(stream.url))
      return None
    if role == Qt.ItemDataRole.ToolTipRole and node.is_stream():
      stream = node.data
      if column == 3:
        return 'Online now' if self.cfg.is_stream_online(stream.url) else 'Offline'
      if column == 4:
        return _format_absolute_time(self.cfg.get_stream_last_online_ts(stream.url))
      if column == 5:
        return _format_absolute_time(self.cfg.get_stream_last_watched_ts(stream.url))
      return None
    if role == Qt.ItemDataRole.TextAlignmentRole and column == 3:
      return Qt.AlignmentFlag.AlignCenter
    if role == Qt.ItemDataRole.DecorationRole and column == 0:
      if node.is_group():
        stream = node.children[0].data
        pixmap = get_stream_icon(stream, 16)
        return QIcon(pixmap) if pixmap else None
      if node.is_stream():
        stream = node.data
        if stream.always_on:
          return QIcon.fromTheme('network-wireless', QIcon.fromTheme('network-transmit-receive'))
      return None
    if role == Qt.ItemDataRole.CheckStateRole and column == 0:
      if node.is_stream():
        stream = node.data
        return None if stream.always_on \
          else Qt.CheckState.PartiallyChecked if stream.notify is None \
          else Qt.CheckState.Checked if stream.notify \
          else Qt.CheckState.Unchecked
      return None
    return None

  def getData(self, index: QModelIndex) -> StreamTreeNode | None:
    return None if not index.isValid() else index.internalPointer()

  def setData(self, index: QModelIndex, value, role: int) -> bool:
    node = self.getData(index)
    if not (node and node.is_stream() and role == Qt.ItemDataRole.CheckStateRole):
      return False
    stream = node.data
    # the value argument seems only useful to toggle True/False, so we'll cycle through our three states
    is_true = stream.notify
    if is_true is None:
      stream.notify = True # PartiallyChecked (None) -> Checked
    elif is_true:
      stream.notify = False # Checked -> Unchecked
    else:
      stream.notify = None # Unchecked -> PartiallyChecked (None)
    self.cfg.save()
    self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
    return True

  def flags(self, index: QModelIndex) -> Qt.ItemFlag:
    if not index.isValid():
      return Qt.ItemFlag.NoItemFlags
    node = index.internalPointer()
    column = index.column()
    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    # Only non-always_on stream nodes in first column have checkboxes (tristate for indeterminate support)
    if column == 0 and node.is_stream():
      stream = node.data
      if not stream.always_on:
        flags |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsUserTristate
    return flags

  def refresh(self) -> None:
    self.beginResetModel()
    self._build_tree()
    self.endResetModel()


class SettingsWindow(QWidget):

  def __init__(self, configuration: Configuration):
    super().__init__()
    self.cfg = configuration
    self._init_ui()
    self._load_settings()
    self._restore_geometry()

  def _init_ui(self) -> None:
    self.setWindowTitle('Lurkiti Settings')
    self.tabs = QTabWidget()
    self.tab_streams = self._create_streams_tab()
    self.tabs.addTab(self.tab_streams, 'Streams')
    self.tab_settings = self._create_settings_tab()
    self.tabs.addTab(self.tab_settings, 'Settings')
    self.tab_about = self._create_about_tab()
    self.tabs.addTab(self.tab_about, 'About')
    layout = QVBoxLayout()
    layout.addWidget(self.tabs)
    self.setLayout(layout)
    self._on_stream_selected(None, None)

  def _create_streams_tab(self) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout()
    # Stream list
    self.stream_model = StreamListModel(self.cfg)
    self.cfg.state_changed.connect(self._reload_treeview)
    self.stream_list = QTreeView()
    self.stream_list.setModel(self.stream_model)
    self.stream_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.stream_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.stream_list.setRootIsDecorated(True)  # Show expand/collapse indicators
    self.stream_list.setItemsExpandable(True)
    self.stream_list.setExpandsOnDoubleClick(False)  # Don't expand on double-click (we use it for edit)
    self.stream_list.expandAll()  # Expand all groups by default
    self.stream_list.doubleClicked.connect(self._edit_stream)
    self.stream_list.setHeaderHidden(False)  # Show header for multiple columns
    self.stream_list.header().setStretchLastSection(False)
    self.stream_list.header().resizeSection(0, 300)  # Name column
    self.stream_list.header().resizeSection(1, 100)  # Quality column
    self.stream_list.header().resizeSection(2, 100)  # Player column
    self.stream_list.header().resizeSection(3, 65)   # Online indicator column
    self.stream_list.header().resizeSection(4, 130)  # Last online column
    self.stream_list.header().resizeSection(5, 130)  # Last watched column
    self.stream_list.selectionModel().selectionChanged.connect(self._on_stream_selected)
    layout.addWidget(self.stream_list)
    # Buttons on the right side
    self.btn_add = _create_stream_action_button(
      'Add',
      self._add_stream,
      fixed_width=80,
      fixed_height=30,
    )
    self.btn_edit = _create_stream_action_button(
      'Edit',
      self._edit_stream,
      fixed_width=80,
      fixed_height=30,
    )
    self.btn_clone = _create_stream_action_button(
      'Clone',
      self._clone_stream,
      fixed_width=80,
      fixed_height=30,
    )
    self.btn_delete = _create_stream_action_button(
      'Delete',
      self._delete_stream,
      fixed_width=80,
      fixed_height=30,
    )
    self.btn_run_defp = _create_stream_action_button(
      'Launch\ndefault\nplayer',
      self._launch_stream_default_player,
      tooltip='Launch stream with default media player',
      fixed_width=80,
    )
    self.btn_run_altp = _create_stream_action_button(
      'Launch\nalternate\nplayer',
      self._launch_stream_alternate_player,
      tooltip='Launch stream with alternate media player',
      fixed_width=80,
    )
    btn_box = QVBoxLayout()
    btn_box.addWidget(self.btn_add)
    btn_box.addWidget(self.btn_edit)
    btn_box.addWidget(self.btn_clone)
    btn_box.addWidget(self.btn_delete)
    btn_box.addSpacing(20)
    btn_box.addWidget(self.btn_run_defp)
    btn_box.addWidget(self.btn_run_altp)
    btn_box.addStretch()
    layout.addLayout(btn_box)
    widget.setLayout(layout)
    return widget

  def _create_settings_tab(self) -> QWidget:
    # Auto-start monitoring
    self.check_autostart_monitoring = QCheckBox("to start monitoring on application launch")
    self.check_autostart_monitoring.setMinimumHeight(24)
    self.check_autostart_monitoring.stateChanged.connect(
      lambda state: self.cfg.set('autostart_monitoring', state == Qt.CheckState.Checked.value)
    )
    # Check interval (minutes)
    self.spin_check_interval = QSpinBox()
    self.spin_check_interval.setMinimum(1)   # 1 minute
    self.spin_check_interval.setMaximum(60)  # 1 hour
    self.spin_check_interval.setValue(5)     # default: 5 minutes
    self.spin_check_interval.setSuffix(' min')
    self.spin_check_interval.setToolTip('Interval between stream checks (in minutes)')
    self.spin_check_interval.valueChanged.connect(
      lambda value: self.cfg.set('check_interval_mins', value)
    )
    # Default notify
    self.check_default_notify = QCheckBox("to notify when streams go online")
    self.check_default_notify.setMinimumHeight(24)
    self.check_default_notify.stateChanged.connect(
      lambda state: self.cfg.set('default_notify', state == Qt.CheckState.Checked.value)
    )
    # tray icon action
    self.combo_tray_icon_action = QComboBox()
    for action in TrayIconAction:
      self.combo_tray_icon_action.addItem(action.display_name, action)
    self.combo_tray_icon_action.currentIndexChanged.connect(
      lambda index: self.cfg.set('tray_icon_action', self.combo_tray_icon_action.itemData(index).value)
    )
    # Always-on streams submenu
    self.check_always_on_submenu = QCheckBox("to always group always-on streams in a submenu")
    self.check_always_on_submenu.setMinimumHeight(24)
    self.check_always_on_submenu.stateChanged.connect(
      lambda state: self.cfg.set('always_on_submenu', state == Qt.CheckState.Checked.value)
    )
    # Default quality
    self.combo_default_quality = QComboBox()
    self.combo_default_quality.addItems(['best', '1080p', '720p', '480p', '360p', '160p', 'worst'])
    self.combo_default_quality.currentTextChanged.connect(
      lambda text: self.cfg.set('default_quality', text)
    )
    # Default streamlink args (text area with monospace font)
    self.text_default_sl_args = QTextEdit()
    self.text_default_sl_args.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    font = QFont('monospace')
    self.text_default_sl_args.setFont(font)
    self.text_default_sl_args.setPlaceholderText('e.g., --retry-max 5 --stream-segment-timeout 20')
    self.text_default_sl_args.textChanged.connect(
      lambda: self.cfg.set('default_streamlink_args', self.text_default_sl_args.toPlainText())
    )
    hint_sl_args = QLabel('''<html><head/><body>
      <a href="https://streamlink.github.io/cli.html#command-line-usage" title="asd">
        <span style=" text-decoration: underline; color:#4285f4;">Streamlink args</span>
      </a>
    </body></html>''')
    hint_sl_args.setOpenExternalLinks(True)
    hint_sl_args.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    hint_sl_args.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    hint_sl_args.setContentsMargins(0, 6, 0, 0)
    hint_sl_args.setToolTip('Click to open Streamlink command-line usage documentation')
    # Reload Streamlink button: reloads config files and sideloaded plugins at runtime
    self.btn_reload_streamlink = QPushButton('Reload configuration files')
    self.btn_reload_streamlink.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_reload_streamlink.setToolTip(
      'Reload Streamlink configuration files and sideloaded plugins without restarting Lurkiti'
    )
    self.btn_reload_streamlink.clicked.connect(self._reload_streamlink)
    label_reload_streamlink = QLabel('Do this when you add a new plugin or change Streamlink or plugins config files.')
    self.row_reload_streamlink = QHBoxLayout()
    self.row_reload_streamlink.addWidget(self.btn_reload_streamlink)
    self.row_reload_streamlink.addWidget(label_reload_streamlink)
    self.row_reload_streamlink.addStretch()
    # Default media player
    self.text_default_player = QLineEdit()
    self.text_default_player.setPlaceholderText('e.g., mpv, vlc')
    self.text_default_player.textChanged.connect(self._default_player_changed)
    # Default media player args (text area with monospace font)
    self.text_default_player_args = QTextEdit()
    self.text_default_player_args.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    font = QFont('monospace')
    self.text_default_player_args.setFont(font)
    self.text_default_player_args.setPlaceholderText('e.g., --no-border --no-osc')
    self.text_default_player_args.textChanged.connect(
      lambda: self.cfg.set('default_player_args', self.text_default_player_args.toPlainText())
    )
    # Alternate media player
    self.text_alternate_player = QLineEdit()
    self.text_alternate_player.setPlaceholderText('e.g., mpv, vlc')
    self.text_alternate_player.textChanged.connect(self._alternate_player_changed)
    # Clippiti executable path
    self.text_clippiti_path = QLineEdit()
    self.text_clippiti_path.setPlaceholderText('e.g., /usr/local/bin/clippiti')
    self.text_clippiti_path.textChanged.connect(
      lambda text: self.cfg.set('clippiti_path', text)
    )
    hint_clippiti = QLabel('''<html><head/><body><span>
      OPTIONAL: Clippiti is an open source livestream player with built-in clipping support.
      <a href="https://github.com/tarzasai/clippiti#clippiti" title="asd">
        <span style=" text-decoration: underline; color:#4285f4;">More info on the homepage</span>
      </a></span>
    </body></html>''')
    hint_clippiti.setOpenExternalLinks(True)
    hint_clippiti.setContentsMargins(0, 0, 6, 0)
    _hint_clippiti_dim = QGraphicsOpacityEffect(hint_clippiti)
    _hint_clippiti_dim.setOpacity(0.7)
    hint_clippiti.setGraphicsEffect(_hint_clippiti_dim)
    # Alternate media player args (text area with monospace font)
    self.text_alternate_player_args = QTextEdit()
    self.text_alternate_player_args.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    font = QFont('monospace')
    self.text_alternate_player_args.setFont(font)
    self.text_alternate_player_args.setPlaceholderText('e.g., --no-border --no-osc')
    self.text_alternate_player_args.textChanged.connect(
      lambda: self.cfg.set('alternate_player_args', self.text_alternate_player_args.toPlainText())
    )
    # Form
    form_layout = QFormLayout()
    form_layout.setVerticalSizeConstraint(QFormLayout.SizeConstraint.SetMinimumSize)
    form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form_layout.addRow('Monitoring', self.check_autostart_monitoring)
    form_layout.addRow('Check interval', self.spin_check_interval)
    form_layout.addRow('Notifications', self.check_default_notify)
    form_layout.addRow('Icon left click', self.combo_tray_icon_action)
    form_layout.addRow('AoS submenu', self.check_always_on_submenu)
    form_layout.addRow('Default quality', self.combo_default_quality)
    form_layout.addRow('Streamlink cfg', self.row_reload_streamlink)
    form_layout.addRow(hint_sl_args, self.text_default_sl_args)
    form_layout.addRow('Clippiti path', self.text_clippiti_path)
    form_layout.addRow(None, hint_clippiti)
    form_layout.addRow('Default player', self.text_default_player)
    form_layout.addRow('Def. player args', self.text_default_player_args)
    form_layout.addRow('Alternate player', self.text_alternate_player)
    form_layout.addRow('Alt. player args', self.text_alternate_player_args)
    widget = QWidget()
    widget.setLayout(form_layout)
    # Set minimum height for text areas to match line edit height
    line_h = self.text_default_player.sizeHint().height()
    self.text_default_sl_args.setMinimumHeight(line_h)
    self.text_default_player_args.setMinimumHeight(line_h)
    self.text_alternate_player_args.setMinimumHeight(line_h)
    return widget

  def _reload_streamlink(self) -> None:
    '''Reload Streamlink config files and sideloaded plugins without restarting.'''
    try:
      load_sl_user_stuff()
    except Exception as err:
      log.error(f'Error reloading Streamlink: {err}')
      QMessageBox.warning(self, 'Reload Streamlink', f'Failed to reload Streamlink:\n{err}')
      return
    log.info('Reloaded Streamlink configuration and plugins')
    QMessageBox.information(self, 'Reload Streamlink', 'Streamlink configuration and plugins reloaded.')

  def _create_about_tab(self) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.addStretch(1)
    title = QLabel('<h1>Lurkiti</h1>')
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    description = QLabel('<h4>A system tray application for monitoring livestreams status.</h4>')
    description.setAlignment(Qt.AlignmentFlag.AlignCenter)
    description.setWordWrap(True)
    layout.addWidget(description)
    version = QLabel(f'<p>Version {dist_ver}</p>')
    version.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(version)
    links = QLabel(
      '<p><a href="https://github.com/tarzasai/Lurkiti">GitHub Repository</a></p>'
      '<p><a href="https://github.com/tarzasai/Lurkiti/wiki">Documentation</a></p>'
    )
    links.setAlignment(Qt.AlignmentFlag.AlignCenter)
    links.setOpenExternalLinks(True)
    layout.addWidget(links)
    copyright_text = QLabel('<p>© 2025 Tarzasai</p>')
    copyright_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(copyright_text)
    layout.addStretch(2)
    widget.setLayout(layout)
    return widget

  def _load_settings(self) -> None:
    # Temporarily block signals to avoid triggering saves during load
    self.check_autostart_monitoring.blockSignals(True)
    self.check_default_notify.blockSignals(True)
    self.combo_tray_icon_action.blockSignals(True)
    self.check_always_on_submenu.blockSignals(True)
    self.spin_check_interval.blockSignals(True)
    self.combo_default_quality.blockSignals(True)
    self.text_default_sl_args.blockSignals(True)
    self.text_default_player.blockSignals(True)
    self.text_default_player_args.blockSignals(True)
    self.text_alternate_player.blockSignals(True)
    self.text_clippiti_path.blockSignals(True)
    self.text_alternate_player_args.blockSignals(True)
    # Settings tab values
    self.check_autostart_monitoring.setChecked(self.cfg.autostart_monitoring)
    self.check_default_notify.setChecked(self.cfg.default_notify)
    for i in range(self.combo_tray_icon_action.count()):
      if self.combo_tray_icon_action.itemData(i) == self.cfg.tray_icon_action:
        self.combo_tray_icon_action.setCurrentIndex(i)
        break
    self.check_always_on_submenu.setChecked(self.cfg.always_on_submenu)
    self.spin_check_interval.setValue(self.cfg.check_interval_mins)
    default_quality = self.cfg.default_quality
    index = self.combo_default_quality.findText(default_quality)
    if index >= 0:
      self.combo_default_quality.setCurrentIndex(index)
    self.text_default_sl_args.setPlainText(self.cfg.default_streamlink_args)
    self.text_default_player.setText(self.cfg.default_player)
    self.text_default_player_args.setPlainText(self.cfg.default_player_args)
    self.text_alternate_player.setText(self.cfg.alternate_player)
    self.text_clippiti_path.setText(self.cfg.clippiti_path or '')
    self.text_alternate_player_args.setPlainText(self.cfg.alternate_player_args)
    # Re-enable signals and connect to auto-save
    self.check_autostart_monitoring.blockSignals(False)
    self.check_default_notify.blockSignals(False)
    self.combo_tray_icon_action.blockSignals(False)
    self.check_always_on_submenu.blockSignals(False)
    self.spin_check_interval.blockSignals(False)
    self.combo_default_quality.blockSignals(False)
    self.text_default_sl_args.blockSignals(False)
    self.text_default_player.blockSignals(False)
    self.text_default_player_args.blockSignals(False)
    self.text_alternate_player.blockSignals(False)
    self.text_clippiti_path.blockSignals(False)
    self.text_alternate_player_args.blockSignals(False)

  def _on_stream_selected(self, selected:QItemSelection, deselected:QItemSelection) -> None:
    if not selected or selected.isEmpty():
      self.btn_edit.setEnabled(False)
      self.btn_clone.setEnabled(False)
      self.btn_delete.setEnabled(False)
      self.btn_run_defp.setVisible(False)
      self.btn_run_altp.setVisible(False)
      return
    index = selected.indexes()[0]
    if not index.isValid():
      self.btn_edit.setEnabled(False)
      self.btn_clone.setEnabled(False)
      self.btn_delete.setEnabled(False)
      self.btn_run_defp.setVisible(False)
      self.btn_run_altp.setVisible(False)
      return
    node = self.stream_model.getData(index)
    if not node or node.is_group():
      self.btn_edit.setEnabled(False)
      self.btn_clone.setEnabled(False)
      self.btn_delete.setEnabled(False)
      self.btn_run_defp.setVisible(False)
      self.btn_run_altp.setVisible(False)
    else:
      self.btn_edit.setEnabled(True)
      self.btn_clone.setEnabled(True)
      self.btn_delete.setEnabled(True)
      self.btn_run_defp.setVisible(True)
      self.btn_run_altp.setVisible(self.cfg.alternate_player is not None and self.cfg.alternate_player.strip() != '')

  def _reload_treeview(self) -> None:
    # Save Treeview current expansion state
    expanded_groups = set()
    for row in range(self.stream_model.rowCount()):
      index = self.stream_model.index(row, 0)
      if self.stream_list.isExpanded(index):
        node = self.stream_model.getData(index)
        if node and node.is_group():
          expanded_groups.add(node.data)
    # Config is already saved by property setters
    self.stream_model.refresh()
    # Restore Treeview expansion state
    for row in range(self.stream_model.rowCount()):
      index = self.stream_model.index(row, 0)
      node = self.stream_model.getData(index)
      if node and node.is_group():
        if node.data in expanded_groups:
          self.stream_list.expand(index)
        else:
          self.stream_list.collapse(index)

  def _add_stream(self) -> None:
    dialog = StreamDialog(
      self,
      self.cfg,
      stream=None,
    )
    if dialog.exec():
      stream = dialog.get_stream()
      self.cfg.set_stream(stream)
      self._reload_treeview()

  def _edit_stream(self) -> None:
    index = self.stream_list.currentIndex()
    if not index.isValid():
      return
    node = self.stream_model.getData(index)
    if not node or node.is_group():
      return
    dialog = StreamDialog(
      self,
      self.cfg,
      stream=node.data,
    )
    if dialog.exec():
      updated_stream = dialog.get_stream()
      self.cfg.set_stream(updated_stream)
      if not dialog.is_clone and updated_stream.url != node.data.url:
        self.cfg.del_stream(node.data)  ## URL changed, remove old stream entry
      self._reload_treeview()

  def _clone_stream(self) -> None:
    index = self.stream_list.currentIndex()
    if not index.isValid():
      return
    node = self.stream_model.getData(index)
    if not node or node.is_group():
      return
    dialog = StreamDialog(
      self,
      self.cfg,
      stream=node.data,
      is_clone=True,
    )
    if dialog.exec():
      cloned_stream = dialog.get_stream()
      self.cfg.set_stream(cloned_stream)
      self._reload_treeview()

  def _delete_stream(self) -> None:
    index = self.stream_list.currentIndex()
    if not index.isValid():
      return
    node = self.stream_model.getData(index)
    if not node or node.is_group():
      return
    stream = node.data
    reply = QMessageBox.question(
      self,
      f"Delete {stream.type} stream",
      f"Are you sure you want to delete '{stream.name}'?",
      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if reply == QMessageBox.StandardButton.Yes:
      self.cfg.del_stream(stream)
      self._reload_treeview()

  def _launch_stream_default_player(self) -> None:
    index = self.stream_list.currentIndex()
    if not index.isValid():
      return
    node = self.stream_model.getData(index)
    if not node or node.is_group():
      return
    self.cfg.mark_stream_watched(node.data.url)
    launch_process(build_launch_command(self.cfg, node.data))

  def _launch_stream_alternate_player(self) -> None:
    index = self.stream_list.currentIndex()
    if not index.isValid():
      return
    node = self.stream_model.getData(index)
    if not node or node.is_group():
      return
    self.cfg.mark_stream_watched(node.data.url)
    launch_process(build_launch_command(self.cfg, node.data, True))

  def _default_player_changed(self, text: str) -> None:
    self.cfg.default_player = text
    no_player = text is None or text.strip() == ''
    self.text_default_player_args.setDisabled(no_player)
    self.text_alternate_player.setDisabled(no_player)
    self.text_alternate_player_args.setDisabled(no_player)

  def _alternate_player_changed(self, text: str) -> None:
    self.cfg.alternate_player = text
    no_player = text is None or text.strip() == ''
    self.text_alternate_player_args.setDisabled(no_player)

  def _restore_geometry(self) -> None:
    geometry = self.cfg.get_geometry('settings_window')
    self.setGeometry(
      geometry.x or 100,
      geometry.y or 100,
      geometry.width or 700,
      geometry.height or 600
    )

  def _save_geometry(self) -> None:
    geometry = self.geometry()
    self.cfg.set_geometry('settings_window', {
      'x': geometry.x(),
      'y': geometry.y(),
      'width': geometry.width(),
      'height': geometry.height(),
    })

  def closeEvent(self, event) -> None:
    if self.isVisible():
      self._save_geometry()
    event.accept()
