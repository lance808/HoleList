from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QLineEdit, QTextEdit,
    QMessageBox, QCheckBox, QMenu, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont


class MemoListWidget(QListWidget):
    """支持拖拽排序的备忘录列表"""
    order_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QListWidget.SingleSelection)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()

    def get_memo_ids(self):
        ids = []
        for i in range(self.count()):
            ids.append(self.item(i).data(Qt.UserRole))
        return ids


class MemoItemWidget(QWidget):
    """单条备忘录的展示控件"""
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    completed_toggled = Signal(str, bool)

    def __init__(self, memo, index, parent=None):
        super().__init__(parent)
        self.memo = memo
        self.index = index
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # 序号
        num_label = QLabel(f"[{self.index}]")
        num_label.setObjectName("numLabel")
        num_label.setFixedWidth(36)
        layout.addWidget(num_label)

        # 复选框
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.memo.get("completed", False))
        self.checkbox.toggled.connect(
            lambda checked: self.completed_toggled.emit(self.memo["id"], checked)
        )
        layout.addWidget(self.checkbox)

        # 文字区域
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(4)

        title_label = QLabel(self.memo["title"])
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_row.addWidget(title_label)
        title_row.addStretch()

        time_label = QLabel(self.memo["created_time"])
        time_label.setObjectName("timeLabel")
        title_row.addWidget(time_label)

        text_layout.addLayout(title_row)

        if self.memo.get("content"):
            content = self.memo["content"]
            content_label = QLabel(content[:50] + ("..." if len(content) > 50 else ""))
            content_label.setObjectName("descLabel")
            text_layout.addWidget(content_label)

        layout.addLayout(text_layout, 1)

        # 删除按钮
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(28, 28)
        del_btn.setObjectName("deleteBtn")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.memo["id"]))
        layout.addWidget(del_btn)

        # 已完成状态设置透明度
        self._update_opacity()

    def _update_opacity(self):
        if self.memo.get("completed", False):
            effect = QGraphicsOpacityEffect()
            effect.setOpacity(0.70)
            self.setGraphicsEffect(effect)
        else:
            self.setGraphicsEffect(None)


class MemoEditDialog(QDialog):
    """备忘录的编辑对话框"""

    def __init__(self, title="", content="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑备忘录" if title else "添加备忘录")
        self.setMinimumWidth(420)
        self.setup_ui(title, content)

    def setup_ui(self, title, content):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("标题:"))
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("输入标题...")
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("内容:"))
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("输入内容（可选）...")
        self.content_edit.setPlainText(content)
        self.content_edit.setMaximumHeight(120)
        layout.addWidget(self.content_edit)

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
        return self.title_edit.text().strip(), self.content_edit.toPlainText().strip()


class MemoPage(QWidget):
    """备忘录页面"""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 列表
        self.list_widget = MemoListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.order_changed.connect(self._on_order_changed)
        layout.addWidget(self.list_widget)

        # 添加按钮
        add_btn = QPushButton("＋ 添加 ＋")
        add_btn.setObjectName("addBtn")
        add_btn.clicked.connect(self._on_add)
        layout.addWidget(add_btn)

    def _on_double_click(self, item):
        memo_id = item.data(Qt.UserRole)
        self._edit_memo(memo_id)

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        memo_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == edit_action:
            self._edit_memo(memo_id)
        elif action == delete_action:
            self._delete_memo(memo_id)

    def _on_order_changed(self):
        ids = self.list_widget.get_memo_ids()
        self.data_manager.reorder_memos(ids)

    def _on_add(self):
        dialog = MemoEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            title, content = dialog.get_data()
            if title:
                self.data_manager.add_memo(title, content)
                self.refresh()

    def _edit_memo(self, memo_id):
        memos = self.data_manager.load_memos()
        memo = next((m for m in memos if m["id"] == memo_id), None)
        if not memo:
            return
        dialog = MemoEditDialog(memo["title"], memo["content"], parent=self)
        if dialog.exec() == QDialog.Accepted:
            title, content = dialog.get_data()
            if title:
                self.data_manager.update_memo(memo_id, title=title, content=content)
                self.refresh()

    def _delete_memo(self, memo_id):
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这条备忘录吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.data_manager.delete_memo(memo_id)
            self.refresh()

    def _on_completed_toggled(self, memo_id, completed):
        self.data_manager.update_memo(memo_id, completed=completed)
        self.refresh()

    def refresh(self):
        memos = self.data_manager.load_memos()
        memos.sort(key=lambda m: m["order"])
        self.list_widget.clear()
        for i, memo in enumerate(memos, 1):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, memo["id"])
            item.setSizeHint(QSize(0, 56))
            widget = MemoItemWidget(memo, i)
            widget.edit_requested.connect(lambda mid=memo["id"]: self._edit_memo(mid))
            widget.delete_requested.connect(lambda mid=memo["id"]: self._delete_memo(mid))
            widget.completed_toggled.connect(self._on_completed_toggled)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)