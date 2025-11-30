import logging
from PyQt6.QtWidgets import (
  QWidget, QFormLayout, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeView, QPushButton,
  QLabel, QSpinBox, QCheckBox, QComboBox, QLineEdit, QTextEdit, QSizePolicy,
  QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QAbstractItemModel, QModelIndex, QItemSelection
from PyQt6.QtGui import QIcon, QFont

from streamcondor.model import Configuration, Stream, TrayIconColor, TrayIconAction
from streamcondor.favicons import get_favicon
from streamcondor.ui.stream import StreamDialog

log = logging.getLogger(__name__)


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
    return 1  # Single column with checkbox + icon + text

  def data(self, index: QModelIndex, role: int):
    if not index.isValid():
      return None
    node = index.internalPointer()
    if role == Qt.ItemDataRole.DisplayRole:
      if node.is_group():
        return node.data.capitalize() # Group node: show type name
      else:
        return node.data.name # Stream node: show stream name
    elif role == Qt.ItemDataRole.DecorationRole:
      if node.is_group():
        stream = node.children[0].data
        pixmap = get_favicon(stream, 16)
        return QIcon(pixmap) if pixmap else None
      return None # Stream nodes don't show icons
    elif role == Qt.ItemDataRole.CheckStateRole:
      if node.is_stream():
        stream = node.data
        return Qt.CheckState.PartiallyChecked if stream.notify is None \
          else Qt.CheckState.Checked if stream.notify else Qt.CheckState.Unchecked
      return None
    elif role == Qt.ItemDataRole.UserRole:
      return node
    return None

  def setData(self, index: QModelIndex, value, role: int) -> bool:
    if not index.isValid():
      return False
    node = index.internalPointer()
    if role == Qt.ItemDataRole.CheckStateRole and node.is_stream(): # Only handle stream nodes
      stream = node.data
      current_value = stream.notify
      if current_value is True:
        stream.notify = False # Checked -> Unchecked
      elif current_value is False:
        stream.notify = None # Unchecked -> PartiallyChecked (None)
      else:
        stream.notify = True # PartiallyChecked (None) -> Checked
      self.cfg.save()
      self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
      return True
    return False

  def flags(self, index: QModelIndex) -> Qt.ItemFlag:
    if not index.isValid():
      return Qt.ItemFlag.NoItemFlags
    node = index.internalPointer()
    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    # Only stream nodes have checkboxes (tristate for indeterminate support)
    if node.is_stream():
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
    self.setWindowTitle('StreamCondor Settings')
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
    self.stream_list = QTreeView()
    self.stream_list.setModel(self.stream_model)
    self.stream_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.stream_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.stream_list.setRootIsDecorated(True)  # Show expand/collapse indicators
    self.stream_list.setItemsExpandable(True)
    self.stream_list.setExpandsOnDoubleClick(False)  # Don't expand on double-click (we use it for edit)
    self.stream_list.expandAll()  # Expand all groups by default
    self.stream_list.doubleClicked.connect(self._edit_stream)
    self.stream_list.setHeaderHidden(True)  # Hide header (we only have one column)
    self.stream_list.selectionModel().selectionChanged.connect(self._on_stream_selected)
    layout.addWidget(self.stream_list)
    # Buttons on the right side
    button_layout = QVBoxLayout()
    self.btn_add = QPushButton('Add')
    self.btn_add.clicked.connect(self._add_stream)
    button_layout.addWidget(self.btn_add)
    self.btn_edit = QPushButton('Edit')
    self.btn_edit.clicked.connect(self._edit_stream)
    button_layout.addWidget(self.btn_edit)
    self.btn_clone = QPushButton('Clone')
    self.btn_clone.clicked.connect(self._clone_stream)
    button_layout.addWidget(self.btn_clone)
    self.btn_delete = QPushButton('Delete')
    self.btn_delete.clicked.connect(self._delete_stream)
    button_layout.addWidget(self.btn_delete)
    button_layout.addStretch()
    layout.addLayout(button_layout)
    widget.setLayout(layout)
    return widget

  def _create_settings_tab(self) -> QWidget:
    # Auto-start monitoring
    self.check_autostart_monitoring = QCheckBox("to start monitoring on application launch")
    self.check_autostart_monitoring.setMinimumHeight(24)
    self.check_autostart_monitoring.stateChanged.connect(
      lambda state: self.cfg.set('autostart_monitoring', state == Qt.CheckState.Checked.value)
    )
    # Check interval
    self.spin_check_interval = QSpinBox()
    self.spin_check_interval.setMinimum(10)
    self.spin_check_interval.setMaximum(3600)
    self.spin_check_interval.setValue(60)
    self.spin_check_interval.valueChanged.connect(
      lambda value: self.cfg.set('check_interval', value)
    )
    # Default notify
    self.check_default_notify = QCheckBox("to notify when streams go online")
    self.check_default_notify.setMinimumHeight(24)
    self.check_default_notify.stateChanged.connect(
      lambda state: self.cfg.set('default_notify', state == Qt.CheckState.Checked.value)
    )
    # tray icon color
    self.combo_tray_icon_color = QComboBox()
    for color in TrayIconColor:
      self.combo_tray_icon_color.addItem(color.value.capitalize(), color)
    self.combo_tray_icon_color.currentIndexChanged.connect(
      lambda index: self.cfg.set('tray_icon_color', self.combo_tray_icon_color.itemData(index).value)
    )
    # tray icon action
    self.combo_tray_icon_action = QComboBox()
    for action in TrayIconAction:
      self.combo_tray_icon_action.addItem(action.display_name, action)
    self.combo_tray_icon_action.currentIndexChanged.connect(
      lambda index: self.cfg.set('tray_icon_action', self.combo_tray_icon_action.itemData(index).value)
    )
    # Default quality
    self.combo_default_quality = QComboBox()
    self.combo_default_quality.addItems(['best', '1080p', '720p', '480p', '360p', '160p', 'worst'])
    self.combo_default_quality.currentTextChanged.connect(
      lambda text: self.cfg.set('default_quality', text)
    )
    # Default streamlink args (text area with monospace font)
    self.text_default_sl_args = QTextEdit()
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
    hint_sl_args.setToolTip('Click to open Streamlink command-line usage documentation')
    # Default media player
    self.text_default_player = QLineEdit()
    self.text_default_player.setPlaceholderText('e.g., mpv, vlc')
    self.text_default_player.textChanged.connect(
      lambda text: self.cfg.set('default_media_player', text)
    )
    # Default media player args (text area with monospace font)
    self.text_default_mp_args = QTextEdit()
    font = QFont('monospace')
    self.text_default_mp_args.setFont(font)
    self.text_default_mp_args.setPlaceholderText('e.g., --no-border --no-osc')
    self.text_default_mp_args.textChanged.connect(
      lambda: self.cfg.set('default_media_player_args', self.text_default_mp_args.toPlainText())
    )
    # Form
    form_layout = QFormLayout()
    form_layout.setVerticalSizeConstraint(QFormLayout.SizeConstraint.SetMinimumSize)
    form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form_layout.addRow('Monitoring', self.check_autostart_monitoring)
    form_layout.addRow('Check interval', self.spin_check_interval)
    form_layout.addRow('Notifications', self.check_default_notify)
    form_layout.addRow('Icon base color', self.combo_tray_icon_color)
    form_layout.addRow('Icon left click', self.combo_tray_icon_action)
    form_layout.addRow('Default quality', self.combo_default_quality)
    form_layout.addRow(hint_sl_args, self.text_default_sl_args)
    form_layout.addRow('Default player', self.text_default_player)
    form_layout.addRow('Player args', self.text_default_mp_args)
    widget = QWidget()
    widget.setLayout(form_layout)
    return widget

  def _create_about_tab(self) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout()
    layout.addStretch(1)
    # Application name and version
    title = QLabel('<h1>StreamCondor</h1>')
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    description = QLabel('<h4>A system tray application for monitoring livestreams status.</h4>')
    description.setAlignment(Qt.AlignmentFlag.AlignCenter)
    description.setWordWrap(True)
    layout.addWidget(description)
    version = QLabel('<p>Version 1.0.0</p>')
    version.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(version)
    links = QLabel(
      '<p><a href="https://github.com/tarzasai/StreamCondor">GitHub Repository</a></p>'
      '<p><a href="https://github.com/tarzasai/StreamCondor/wiki">Documentation</a></p>'
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
    self.combo_tray_icon_color.blockSignals(True)
    self.combo_tray_icon_action.blockSignals(True)
    self.spin_check_interval.blockSignals(True)
    self.text_default_sl_args.blockSignals(True)
    self.text_default_player.blockSignals(True)
    self.text_default_mp_args.blockSignals(True)
    self.combo_default_quality.blockSignals(True)
    # Settings tab values
    self.check_autostart_monitoring.setChecked(self.cfg.autostart_monitoring)
    self.check_default_notify.setChecked(self.cfg.default_notify)
    for i in range(self.combo_tray_icon_action.count()):
      if self.combo_tray_icon_action.itemData(i) == self.cfg.tray_icon_action:
        self.combo_tray_icon_action.setCurrentIndex(i)
        break
    for i in range(self.combo_tray_icon_color.count()):
      if self.combo_tray_icon_color.itemData(i) == self.cfg.tray_icon_color:
        self.combo_tray_icon_color.setCurrentIndex(i)
        break
    self.spin_check_interval.setValue(self.cfg.check_interval)
    self.text_default_sl_args.setPlainText(self.cfg.default_streamlink_args)
    self.text_default_player.setText(self.cfg.default_media_player)
    self.text_default_mp_args.setPlainText(self.cfg.default_media_player_args)
    default_quality = self.cfg.default_quality
    index = self.combo_default_quality.findText(default_quality)
    if index >= 0:
      self.combo_default_quality.setCurrentIndex(index)
    # Re-enable signals and connect to auto-save
    self.check_autostart_monitoring.blockSignals(False)
    self.check_default_notify.blockSignals(False)
    self.combo_tray_icon_color.blockSignals(False)
    self.combo_tray_icon_action.blockSignals(False)
    self.spin_check_interval.blockSignals(False)
    self.text_default_sl_args.blockSignals(False)
    self.text_default_player.blockSignals(False)
    self.text_default_mp_args.blockSignals(False)
    self.combo_default_quality.blockSignals(False)

  def _on_stream_selected(self, selected:QItemSelection, deselected:QItemSelection) -> None:
    if not selected or selected.isEmpty():
      self.btn_edit.setEnabled(False)
      self.btn_clone.setEnabled(False)
      self.btn_delete.setEnabled(False)
      return
    index = selected.indexes()[0]
    if not index.isValid():
      self.btn_edit.setEnabled(False)
      self.btn_clone.setEnabled(False)
      self.btn_delete.setEnabled(False)
      return
    node = self.stream_model.data(index, Qt.ItemDataRole.UserRole)
    if not node or node.is_group():
      self.btn_edit.setEnabled(False)
      self.btn_clone.setEnabled(False)
      self.btn_delete.setEnabled(False)
    else:
      self.btn_edit.setEnabled(True)
      self.btn_clone.setEnabled(True)
      self.btn_delete.setEnabled(True)

  def _reload_treeview(self) -> None:
    # Save Treeview current expansion state
    expanded_groups = set()
    for row in range(self.stream_model.rowCount()):
      index = self.stream_model.index(row, 0)
      if self.stream_list.isExpanded(index):
        node = self.stream_model.data(index, Qt.ItemDataRole.UserRole)
        if node and node.is_group():
          expanded_groups.add(node.data)
    # Config is already saved by property setters
    self.stream_model.refresh()
    # Restore Treeview expansion state
    for row in range(self.stream_model.rowCount()):
      index = self.stream_model.index(row, 0)
      node = self.stream_model.data(index, Qt.ItemDataRole.UserRole)
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
    node = self.stream_model.data(index, Qt.ItemDataRole.UserRole)
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
      self._reload_treeview()

  def _clone_stream(self) -> None:
    index = self.stream_list.currentIndex()
    if not index.isValid():
      return
    node = self.stream_model.data(index, Qt.ItemDataRole.UserRole)
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
    node = self.stream_model.data(index, Qt.ItemDataRole.UserRole)
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
