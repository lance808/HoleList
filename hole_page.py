from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QLineEdit, QTextEdit,
    QMessageBox, QSplitter, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon


STATUS_MAP = {
    "digging": "挖坑",
    "filling": "填坑",
    "completed": "完结坑",
}

STATUS_ORDER = ["digging", "filling", "completed"]


class HoleListWidget(QListWidget):
    """支持跨列拖拽的坑列表"""
    order_changed = Signal()

    def __init__(self, status, parent=None):
        super().__init__(parent)
        self.status = status
        self.setDragDropMode(QListWidget.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self._pending_move = None

    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, HoleListWidget) and source != self:
            item = source.currentItem()
            if item:
                hole_id = item.data(Qt.UserRole)
                source.takeItem(source.row(item))
                self._pending_move = hole_id
                self.order_changed.emit()
                event.setDropAction(Qt.MoveAction)
                event.accept()
                return
        super().dropEvent(event)
        self.order_changed.emit()

    def get_hole_ids(self):
        ids = []
        for i in range(self.count()):
            ids.append(self.item(i).data(Qt.UserRole))
        return ids


class HoleItemWidget(QWidget):
    """单个坑项的展示控件"""
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    move_requested = Signal(str, str)

    def __init__(self, hole, parent=None):
        super().__init__(parent)
        self.hole = hole
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # 左侧文字区域
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(4)

        title_label = QLabel(self.hole["title"])
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_row.addWidget(title_label)
        title_row.addStretch()

        time_label = QLabel(self.hole["created_time"])
        time_label.setObjectName("timeLabel")
        title_row.addWidget(time_label)

        text_layout.addLayout(title_row)

        if self.hole.get("description"):
            desc = self.hole["description"]
            desc_label = QLabel(desc[:60] + ("..." if len(desc) > 60 else ""))
            desc_label.setObjectName("descLabel")
            desc_label.setWordWrap(True)
            desc_label.setMaximumHeight(36)
            text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        # 右侧按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)

        status = self.hole["status"]

        if status in ("filling", "completed"):
            left_btn = QPushButton("↑")
            left_btn.setFixedSize(32, 28)
            left_btn.setToolTip("回退到上一状态")
            if status == "filling":
                left_btn.clicked.connect(lambda: self.move_requested.emit(self.hole["id"], "digging"))
            else:
                left_btn.clicked.connect(lambda: self.move_requested.emit(self.hole["id"], "filling"))
            btn_layout.addWidget(left_btn)

        if status in ("digging", "filling"):
            right_btn = QPushButton("↓")
            right_btn.setFixedSize(32, 28)
            right_btn.setToolTip("推进到下一状态")
            if status == "digging":
                right_btn.clicked.connect(lambda: self.move_requested.emit(self.hole["id"], "filling"))
            else:
                right_btn.clicked.connect(lambda: self.move_requested.emit(self.hole["id"], "completed"))
            btn_layout.addWidget(right_btn)

        if status == "completed":
            redo_btn = QPushButton("↺")
            redo_btn.setFixedSize(32, 28)
            redo_btn.setToolTip("重新挖坑")
            redo_btn.clicked.connect(lambda: self.move_requested.emit(self.hole["id"], "digging"))
            btn_layout.addWidget(redo_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(28, 28)
        del_btn.setObjectName("deleteBtn")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.hole["id"]))
        btn_layout.addWidget(del_btn)

        layout.addLayout(btn_layout)


class HoleEditDialog(QDialog):
    """坑的编辑对话框"""

    def __init__(self, title="", description="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑坑" if title else "挖新坑")
        self.setMinimumWidth(420)
        self.setup_ui(title, description)

    def setup_ui(self, title, description):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("标题:"))
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("输入标题...")
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("描述:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("输入描述（可选）...")
        self.desc_edit.setPlainText(description)
        self.desc_edit.setMaximumHeight(120)
        layout.addWidget(self.desc_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        return self.title_edit.text().strip(), self.desc_edit.toPlainText().strip()


class HoleColumn(QWidget):
    """单个坑列（挖坑/填坑/完结坑）"""

    def __init__(self, status, data_manager, parent=None):
        super().__init__(parent)
        self.status = status
        self.data_manager = data_manager
        self.pinned = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 标题
        header = QHBoxLayout()
        title_label = QLabel(STATUS_MAP[self.status])
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        header.addWidget(title_label)
        header.addStretch()
        count_label = QLabel("0")
        count_label.setObjectName("countLabel")
        header.addWidget(count_label)
        layout.addLayout(header)

        self.count_label = count_label

        # 列表
        self.list_widget = HoleListWidget(self.status)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list_widget)

        # 添加按钮 (仅挖坑列)
        if self.status == "digging":
            self.add_btn = QPushButton(" 挖坑 ")
            self.add_btn.setObjectName("addBtn")
            self.add_btn.clicked.connect(self._on_add)
            layout.addWidget(self.add_btn)
        else:
            self.add_btn = None

    def set_pinned(self, pinned):
        self.pinned = pinned
        if self.add_btn:
            self.add_btn.setEnabled(not pinned)
        self.list_widget.setEnabled(not pinned)

    def _on_double_click(self, item):
        if self.pinned:
            return
        hole_id = item.data(Qt.UserRole)
        self._edit_hole(hole_id)

    def _on_context_menu(self, pos):
        if self.pinned:
            return
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        hole_id = item.data(Qt.UserRole)
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == edit_action:
            self._edit_hole(hole_id)
        elif action == delete_action:
            self._delete_hole(hole_id)

    def _on_add(self):
        if self.pinned:
            return
        dialog = HoleEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            title, desc = dialog.get_data()
            if title:
                self.data_manager.add_hole(title, desc)
                self.parent().parent().refresh()

    def _edit_hole(self, hole_id):
        holes = self.data_manager.load_holes()
        hole = next((h for h in holes if h["id"] == hole_id), None)
        if not hole:
            return
        dialog = HoleEditDialog(hole["title"], hole["description"], parent=self)
        if dialog.exec() == QDialog.Accepted:
            title, desc = dialog.get_data()
            if title:
                self.data_manager.update_hole(hole_id, title=title, description=desc)
                self.parent().parent().refresh()

    def _delete_hole(self, hole_id):
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这个坑吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.data_manager.delete_hole(hole_id)
            self.parent().parent().refresh()

    def populate(self, holes):
        self.list_widget.clear()
        for hole in holes:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, hole["id"])
            item.setSizeHint(QSize(0, 56))
            widget = HoleItemWidget(hole)
            widget.edit_requested.connect(lambda hid=hole["id"]: self._edit_hole(hid))
            widget.delete_requested.connect(lambda hid=hole["id"]: self._delete_hole(hid))
            widget.move_requested.connect(self._on_move)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
        self.count_label.setText(str(len(holes)))

    def _on_move(self, hole_id, new_status):
        self.data_manager.move_hole(hole_id, new_status)
        self.parent().parent().refresh()


class HolePage(QWidget):
    """坑页面 - 上中下三行布局"""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.pinned = False
        self.setup_ui()

    def set_pinned(self, pinned):
        self.pinned = pinned
        for col in self.columns:
            col.set_pinned(pinned)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Vertical)
        self.columns = []
        for status in STATUS_ORDER:
            column = HoleColumn(status, self.data_manager)
            column.list_widget.order_changed.connect(self._on_column_order_changed)
            self.columns.append(column)
            splitter.addWidget(column)
        splitter.setSizes([200, 200, 200])
        layout.addWidget(splitter)

    def _on_column_order_changed(self):
        sender = self.sender()
        if hasattr(sender, '_pending_move') and sender._pending_move:
            hole_id = sender._pending_move
            self.data_manager.move_hole(hole_id, sender.status)
            sender._pending_move = None
        for column in self.columns:
            ids = column.list_widget.get_hole_ids()
            self.data_manager.reorder_holes(column.status, ids)
        self.refresh()

    def refresh(self):
        holes = self.data_manager.load_holes()
        for column in self.columns:
            status_holes = [h for h in holes if h["status"] == column.status]
            status_holes.sort(key=lambda h: h["order"])
            column.populate(status_holes)