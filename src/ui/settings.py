"""
Settings window for StreamCondor.
"""
import logging
from PyQt6.QtWidgets import (
  QWidget, QFormLayout, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeView, QPushButton,
  QLabel, QSpinBox, QCheckBox, QComboBox, QLineEdit, QTextEdit,
  QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QAbstractItemModel, QModelIndex, QItemSelection
from PyQt6.QtGui import QIcon, QFont

from configuration import Configuration, TrayClickAction
from favicons import Favicons
from launcher import StreamLauncher
from ui.stream import StreamDialog


log = logging.getLogger(__name__)


class StreamTreeNode:
  """Node in the stream tree (either a type group or a stream)."""

  def __init__(self, data: dict | str, parent: 'StreamTreeNode' | None = None):
    """Initialize tree node.

    Args:
      data: Either a stream dict or a type string (for group nodes)
      parent: Parent node
    """
    self.data = data
    self.parent = parent
    self.children: list[StreamTreeNode] = []

  def is_group(self) -> bool:
    return isinstance(self.data, str)

  def is_stream(self) -> bool:
    return isinstance(self.data, dict)

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
  """Model for hierarchical stream list grouped by type."""

  def __init__(self, configuration: Configuration, favicons: Favicons):
    """Initialize stream list model.

    Args:
      configuration: ConfigManager instance
      favicons: FaviconManager instance
    """
    super().__init__()
    self.configuration = configuration
    self.favicons = favicons
    self.root_node = StreamTreeNode(None)
    self._build_tree()

  def _build_tree(self) -> None:
    # Clear existing tree
    self.root_node = StreamTreeNode(None)
    # Group streams by type
    streams_by_type: dict[str, list[dict]] = {}
    for stream in self.configuration.streams:
      stream_type = stream.get('type', 'unknown')
      if stream_type not in streams_by_type:
        streams_by_type[stream_type] = []
      streams_by_type[stream_type].append(stream)
    # Build tree with sorted types
    for stream_type in sorted(streams_by_type.keys()):
      # Create type group node
      type_node = StreamTreeNode(stream_type, self.root_node)
      self.root_node.add_child(type_node)
      # Add streams sorted by name
      streams = sorted(
        streams_by_type[stream_type],
        key=lambda s: s.get('name', s.get('url', 'Unknown')).lower()
      )
      for stream in streams:
        stream_node = StreamTreeNode(stream, type_node)
        type_node.add_child(stream_node)

  def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
    """Create index for row and column under parent."""
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
    """Get parent index."""
    if not index.isValid():
      return QModelIndex()

    child_node = index.internalPointer()
    parent_node = child_node.parent

    if parent_node == self.root_node or parent_node is None:
      return QModelIndex()

    return self.createIndex(parent_node.row(), 0, parent_node)

  def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
    """Get number of rows under parent."""
    if parent.column() > 0:
      return 0

    if not parent.isValid():
      parent_node = self.root_node
    else:
      parent_node = parent.internalPointer()

    return parent_node.child_count()

  def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
    """Get number of columns."""
    return 1  # Single column with checkbox + icon + text

  def data(self, index: QModelIndex, role: int):
    """Get data for index and role."""
    if not index.isValid():
      return None

    node = index.internalPointer()

    if role == Qt.ItemDataRole.DisplayRole:
      if node.is_group():
        # Group node: show type name
        return node.data.capitalize()
      else:
        # Stream node: show stream name
        stream = node.data
        return stream.get('name', stream.get('url', 'Unknown'))

    elif role == Qt.ItemDataRole.DecorationRole:
      if node.is_group():
        # Group node: show type icon
        stream_type = node.data
        # Fetch favicon for the first stream of this type to get the icon
        for child in node.children:
          if child.is_stream():
            stream = child.data
            if self.favicons.fetch_favicon(stream.get('url', ''), stream_type):
              pixmap = self.favicons.get_favicon(stream_type, 16)
              return QIcon(pixmap) if pixmap else None
            break
      # Stream nodes don't show icons (already shown in parent)
      return None

    elif role == Qt.ItemDataRole.CheckStateRole:
      # Only stream nodes have checkboxes
      if node.is_stream():
        stream = node.data
        notify_value = stream.get('notify')
        if notify_value is None:
          return Qt.CheckState.PartiallyChecked
        return Qt.CheckState.Checked if notify_value else Qt.CheckState.Unchecked
      return None

    elif role == Qt.ItemDataRole.UserRole:
      return node

    return None

  def setData(self, index: QModelIndex, value, role: int) -> bool:
    """Set data for index."""
    if not index.isValid():
      return False

    node = index.internalPointer()

    if role == Qt.ItemDataRole.CheckStateRole:
      # Only handle stream nodes
      if node.is_stream():
        # Cycle through three states: Checked -> Unchecked -> PartiallyChecked -> Checked
        stream = node.data
        current_value = stream.get('notify')
        if current_value is True:
          stream['notify'] = False # Checked -> Unchecked
        elif current_value is False:
          stream['notify'] = None # Unchecked -> PartiallyChecked (None)
        else:
          stream['notify'] = True # PartiallyChecked (None) -> Checked
        self.configuration.update_stream(stream)
        self.dataChanged.emit(index, index)
        return True

    return False

  def flags(self, index: QModelIndex) -> Qt.ItemFlag:
    """Get item flags."""
    if not index.isValid():
      return Qt.ItemFlag.NoItemFlags

    node = index.internalPointer()
    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # Only stream nodes have checkboxes (tristate for indeterminate support)
    if node.is_stream():
      flags |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsUserTristate

    return flags

  def refresh(self) -> None:
    """Refresh the model."""
    self.beginResetModel()
    self._build_tree()
    self.endResetModel()

  def get_group_types(self) -> list[str]:
    """Get list of all group types in the tree.

    Returns:
      List of type names (group identifiers)
    """
    types = []
    for i in range(self.root_node.child_count()):
      node = self.root_node.child(i)
      if node and node.is_group():
        types.append(node.data)
    return types


class SettingsWindow(QWidget):
  """Main settings window with tabs."""

  def __init__(self, configuration: Configuration, favicons: Favicons, launcher: StreamLauncher):
    """Initialize settings window.

    Args:
      configuration: ConfigManager instance
      favicons: FaviconManager instance
      streamlink_launcher: StreamlinkLauncher instance
    """
    super().__init__()
    self.cfg = configuration
    self.favicons = favicons
    self.launcher = launcher
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
    self.stream_model = StreamListModel(self.cfg, self.favicons)
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
    widget = QWidget()
    layout = QVBoxLayout()

    # Auto-start monitoring
    self.check_autostart_monitoring = QCheckBox('Start monitoring at startup')
    self.check_autostart_monitoring.stateChanged.connect(
      lambda state: self.cfg.set_value('autostart_monitoring', state == Qt.CheckState.Checked.value)
    )
    layout.addWidget(self.check_autostart_monitoring)

    # Default notify
    self.check_default_notify = QCheckBox('Enable notifications by default')
    self.check_default_notify.stateChanged.connect(
      lambda state: self.cfg.set_value('default_notify', state == Qt.CheckState.Checked.value)
    )
    layout.addWidget(self.check_default_notify)

    # Create form layout for proper two-column alignment
    form_layout = QFormLayout()
    form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    # Left click action
    self.combo_left_click = QComboBox()
    for action in TrayClickAction:
      self.combo_left_click.addItem(action.display_name, action)
    self.combo_left_click.currentIndexChanged.connect(
      lambda index: self.cfg.set_value(
        'left_click_action',
        self.combo_left_click.itemData(index).value
      )
    )
    form_layout.addRow('Tray icon left click:', self.combo_left_click)

    # Check interval
    self.spin_check_interval = QSpinBox()
    self.spin_check_interval.setMinimum(10)
    self.spin_check_interval.setMaximum(3600)
    self.spin_check_interval.setValue(60)
    self.spin_check_interval.valueChanged.connect(
      lambda value: self.cfg.set_value('check_interval', value)
    )
    form_layout.addRow('Check interval (sec):', self.spin_check_interval)

    # Default streamlink args (text area with monospace font)
    self.text_default_sl_args = QTextEdit()
    self.text_default_sl_args.setMaximumHeight(120)
    font = QFont('monospace')
    self.text_default_sl_args.setFont(font)
    self.text_default_sl_args.setPlaceholderText('e.g., --retry-max 5 --stream-segment-timeout 20')
    self.text_default_sl_args.textChanged.connect(
      lambda: self.cfg.set_value(
        'default_streamlink_args',
        self.text_default_sl_args.toPlainText()
      )
    )
    form_layout.addRow('Default Streamlink \narguments:', self.text_default_sl_args)

    # Default media player
    self.text_default_player = QLineEdit()
    self.text_default_player.setPlaceholderText('e.g., mpv, vlc')
    self.text_default_player.textChanged.connect(
      lambda text: self.cfg.set_value('default_media_player', text)
    )
    form_layout.addRow('Default player:', self.text_default_player)

    # Default media player args (text area with monospace font)
    self.text_default_mp_args = QTextEdit()
    self.text_default_mp_args.setMaximumHeight(100)
    font = QFont('monospace')
    self.text_default_mp_args.setFont(font)
    self.text_default_mp_args.setPlaceholderText('e.g., --no-border --no-osc')
    self.text_default_mp_args.textChanged.connect(
      lambda: self.cfg.set_value(
        'default_media_player_args',
        self.text_default_mp_args.toPlainText()
      )
    )
    form_layout.addRow('Default player \narguments:', self.text_default_mp_args)

    # Default quality
    self.combo_default_quality = QComboBox()
    self.combo_default_quality.addItems(['best', '1080p', '720p', '480p', '360p', '160p', 'worst'])
    self.combo_default_quality.currentTextChanged.connect(
      lambda text: self.cfg.set_value('default_quality', text)
    )
    form_layout.addRow('Default quality:', self.combo_default_quality)

    layout.addLayout(form_layout)
    layout.addStretch()

    widget.setLayout(layout)
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
      '<p><a href="https://github.com/yourusername/streamcondor">GitHub Repository</a></p>'
      '<p><a href="https://github.com/yourusername/streamcondor/wiki">Documentation</a></p>'
    )
    links.setAlignment(Qt.AlignmentFlag.AlignCenter)
    links.setOpenExternalLinks(True)
    layout.addWidget(links)

    copyright_text = QLabel('<p>© 2025 StreamCondor Contributors</p>')
    copyright_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(copyright_text)

    layout.addStretch(2)

    widget.setLayout(layout)
    return widget

  def _load_settings(self) -> None:
    # Temporarily block signals to avoid triggering saves during load
    self.check_autostart_monitoring.blockSignals(True)
    self.check_default_notify.blockSignals(True)
    self.spin_check_interval.blockSignals(True)
    self.combo_default_quality.blockSignals(True)
    self.text_default_sl_args.blockSignals(True)
    self.text_default_player.blockSignals(True)
    self.text_default_mp_args.blockSignals(True)
    self.combo_left_click.blockSignals(True)
    # Settings tab values
    self.check_autostart_monitoring.setChecked(self.cfg.autostart_monitoring)
    self.check_default_notify.setChecked(self.cfg.default_notify)
    self.spin_check_interval.setValue(self.cfg.check_interval)
    default_quality = self.cfg.default_quality
    index = self.combo_default_quality.findText(default_quality)
    if index >= 0:
      self.combo_default_quality.setCurrentIndex(index)
    self.text_default_sl_args.setPlainText(
      self.cfg.default_streamlink_args
    )
    self.text_default_player.setText(
      self.cfg.default_media_player
    )
    self.text_default_mp_args.setPlainText(
      self.cfg.default_media_player_args
    )
    left_click_action = self.cfg.left_click_action
    for i in range(self.combo_left_click.count()):
      if self.combo_left_click.itemData(i) == left_click_action:
        self.combo_left_click.setCurrentIndex(i)
        break
    # Re-enable signals and connect to auto-save
    self.check_autostart_monitoring.blockSignals(False)
    self.check_default_notify.blockSignals(False)
    self.spin_check_interval.blockSignals(False)
    self.combo_default_quality.blockSignals(False)
    self.text_default_sl_args.blockSignals(False)
    self.text_default_player.blockSignals(False)
    self.text_default_mp_args.blockSignals(False)
    self.combo_left_click.blockSignals(False)

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
      self.favicons,
      self.launcher,
      stream=None,
    )
    if dialog.exec():
      stream = dialog.get_stream()
      self.cfg.add_stream(stream)
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
      self.favicons,
      self.launcher,
      stream=node.data,
    )
    if dialog.exec():
      updated_stream = dialog.get_stream()
      self.cfg.update_stream(updated_stream)
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
      self.favicons,
      self.launcher,
      stream=node.data,
      is_clone=True,
    )
    if dialog.exec():
      cloned_stream = dialog.get_stream()
      self.cfg.add_stream(cloned_stream)
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
      f"Delete {stream.get('type')} stream",
      f"Are you sure you want to delete '{stream.get('name')}'?",
      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if reply == QMessageBox.StandardButton.Yes:
      self.cfg.remove_stream(stream)
      self._reload_treeview()

  def _restore_geometry(self) -> None:
    geometry = self.cfg.load_window_geometry('settings_window')
    self.setGeometry(
      geometry.get('x', 100),
      geometry.get('y', 100),
      geometry.get('width', 700),
      geometry.get('height', 600)
    )

  def _save_geometry(self) -> None:
    geometry = self.geometry()
    self.cfg.save_window_geometry('settings_window', {
      'x': geometry.x(),
      'y': geometry.y(),
      'width': geometry.width(),
      'height': geometry.height(),
    })

  def closeEvent(self, event) -> None:
    """Handle window close event."""
    self._save_geometry()
    event.accept()
