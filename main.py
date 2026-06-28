import sys
import os
import winreg

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QSystemTrayIcon, QMenu, QButtonGroup,
    QMessageBox, QDialog, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QRect, QEvent
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction, QBitmap

from data_manager import DataManager
from hole_page import HolePage
from memo_page import MemoPage
from settings_dialog import SettingsDialog


def create_icon(color="#4A90D9"):
    """创建托盘图标"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.setPen(Qt.white)
    font = QFont("Microsoft YaHei", 14, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "HL")
    painter.end()
    return QIcon(pixmap)


class HeaderWidget(QWidget):
    """自定义标题栏，支持拖拽移动 + 双击最大化"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setObjectName("header")
        self.setFixedHeight(40)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            window = self.window()
            if window.isMaximized():
                window.showNormal()
            delta = event.globalPosition().toPoint() - self._drag_pos
            window.move(window.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            window = self.window()
            if window.isMaximized():
                window.showNormal()
            else:
                window.showMaximized()


class CentralWidget(QWidget):
    """中央控件 - 通过全局事件过滤器处理窗口边缘拖拽缩放"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._main = parent
        self._resize_edge = None
        self._resize_start = None
        self._resize_geo = None
        self.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

    @staticmethod
    def _get_edge(pos, w, h, b=5):
        left = pos.x() < b
        right = pos.x() > w - b
        top = pos.y() < b
        bottom = pos.y() > h - b
        if top and left: return "tl"
        if top and right: return "tr"
        if bottom and left: return "bl"
        if bottom and right: return "br"
        if top: return "t"
        if bottom: return "b"
        if left: return "l"
        if right: return "r"
        return None

    def _map_pos(self, event):
        """将事件坐标映射到本控件"""
        gp = event.globalPosition().toPoint()
        return self.mapFromGlobal(gp)

    def eventFilter(self, obj, event):
        """全局事件过滤器：捕获鼠标事件以处理窗口缩放"""
        if not isinstance(obj, QWidget) or obj.window() is not self._main:
            return super().eventFilter(obj, event)
        t = event.type()
        if t == QEvent.MouseMove:
            self._on_mouse_move(event)
        elif t == QEvent.MouseButtonPress:
            self._on_mouse_press(event)
        elif t == QEvent.MouseButtonRelease:
            self._on_mouse_release(event)
        return super().eventFilter(obj, event)

    def _on_mouse_move(self, event):
        if self._main.pinned or self._main.isMaximized():
            self.setCursor(Qt.ArrowCursor)
            return
        if self._resize_edge:
            self._do_resize(event)
            return
        pos = self._map_pos(event)
        edge = self._get_edge(pos, self.width(), self.height())
        cursors = {
            "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
            "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
            "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
        }
        self.setCursor(cursors.get(edge, Qt.ArrowCursor))

    def _on_mouse_press(self, event):
        if event.button() != Qt.LeftButton or self._main.pinned:
            return
        pos = self._map_pos(event)
        edge = self._get_edge(pos, self.width(), self.height())
        if edge:
            self._resize_edge = edge
            self._resize_start = event.globalPosition().toPoint()
            self._resize_geo = self._main.geometry()
            event.accept()

    def _on_mouse_release(self, event):
        self._resize_edge = None

    def _do_resize(self, event):
        delta = event.globalPosition().toPoint() - self._resize_start
        geo = QRect(self._resize_geo)
        min_w = self._main.minimumWidth()
        min_h = self._main.minimumHeight()
        edge = self._resize_edge

        if "l" in edge:
            nw = geo.width() - delta.x()
            if nw >= min_w:
                geo.setX(geo.x() + delta.x())
                geo.setWidth(nw)
        if "r" in edge:
            geo.setWidth(max(geo.width() + delta.x(), min_w))
        if "t" in edge:
            nh = geo.height() - delta.y()
            if nh >= min_h:
                geo.setY(geo.y() + delta.y())
                geo.setHeight(nh)
        if "b" in edge:
            geo.setHeight(max(geo.height() + delta.y(), min_h))

        self._main.setGeometry(geo)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        self.settings = self.data_manager.load_settings()
        self.pinned = False
        self._closing = False

        self.setWindowTitle("挖坑备忘录")
        self.setMinimumSize(600, 400)
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.setup_ui()
        self.setup_tray()
        self.apply_theme()
        self.restore_geometry()
        self.refresh_all()

        self._save_timer = QTimer()
        self._save_timer.setInterval(2000)
        self._save_timer.timeout.connect(self._save_window_state)
        self._save_timer.start()

        self.tab_hole.setChecked(True)
        self.stack.setCurrentIndex(0)

        # 应用默认设置
        default_tab = self.settings.get("default_tab", 0)
        if default_tab == 1:
            self.tab_memo.setChecked(True)
            self.stack.setCurrentIndex(1)
        else:
            self.tab_hole.setChecked(True)
            self.stack.setCurrentIndex(0)

        if self.settings.get("default_pinned", False):
            self.pinned = True
            self._pin_window()

    # ========== UI 构建 ==========

    def setup_ui(self):
        central = CentralWidget(self)
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部导航栏
        layout.addWidget(self._create_header())

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("headerSep")
        layout.addWidget(sep)

        # 内容区
        self.stack = QStackedWidget()
        self.hole_page = HolePage(self.data_manager)
        self.memo_page = MemoPage(self.data_manager)
        self.stack.addWidget(self.hole_page)
        self.stack.addWidget(self.memo_page)
        layout.addWidget(self.stack)

    def _create_header(self):
        header = HeaderWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(6)

        # 主题切换
        self.theme_btn = QPushButton()
        self.theme_btn.setFixedSize(38, 28)
        self.theme_btn.setToolTip("切换白天/黑夜/自定义模式")
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)

        # 设置按钮
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(38, 28)
        self.settings_btn.setToolTip("设置")
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        layout.addStretch()

        # 固定按钮
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(38, 28)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setToolTip("固定在桌面上（半透明悬挂）")
        self.pin_btn.clicked.connect(self.toggle_pin)
        layout.addWidget(self.pin_btn)

        layout.addSpacing(12)

        # Tab 切换
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        self.tab_hole = QPushButton("坑")
        self.tab_hole.setCheckable(True)
        self.tab_hole.setFixedSize(84, 28)
        self.tab_hole.setObjectName("tabBtn")
        self.tab_hole.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.tab_group.addButton(self.tab_hole)

        self.tab_memo = QPushButton("备忘录")
        self.tab_memo.setCheckable(True)
        self.tab_memo.setFixedSize(100, 28)
        self.tab_memo.setObjectName("tabBtn")
        self.tab_memo.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.tab_group.addButton(self.tab_memo)

        layout.addWidget(self.tab_hole)
        layout.addWidget(self.tab_memo)

        layout.addStretch()

        # 窗口控制按钮
        self.min_btn = QPushButton("─")
        self.min_btn.setFixedSize(32, 28)
        self.min_btn.setObjectName("winBtn")
        self.min_btn.setToolTip("最小化")
        self.min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(self.min_btn)

        self.max_btn = QPushButton("□")
        self.max_btn.setFixedSize(32, 28)
        self.max_btn.setObjectName("winBtn")
        self.max_btn.setToolTip("最大化")
        self.max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.max_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 28)
        self.close_btn.setObjectName("winCloseBtn")
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        return header

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")
        else:
            self.showMaximized()
            self.max_btn.setText("❐")

    # ========== 系统托盘 ==========

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(create_icon())
        self.tray_icon.setToolTip("挖坑备忘录")

        tray_menu = QMenu()
        restore_action = QAction("恢复窗口", self)
        restore_action.triggered.connect(self.restore_from_tray)
        tray_menu.addAction(restore_action)

        tray_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_from_tray()

    def restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def quit_app(self):
        self._closing = True
        self._save_window_state()
        self.tray_icon.hide()
        QApplication.quit()

    # ========== 主题 ==========

    def apply_theme(self):
        theme = self.settings.get("theme", "light")
        colors = self.settings.get("colors", {})
        dark_colors = self.settings.get("dark_colors", {})

        if theme == "dark":
            bg, text, border = (
                dark_colors.get("bg", "#1E1E1E"),
                dark_colors.get("text", "#D4D4D4"),
                dark_colors.get("border", "#444444"),
            )
            self.theme_btn.setText("☀")
        elif theme == "custom":
            bg = colors.get("bg", "#FFFFFF")
            text = colors.get("text", "#333333")
            border = colors.get("border", "#CCCCCC")
            self.theme_btn.setText("🎨")
        else:
            bg = colors.get("bg", "#FFFFFF")
            text = colors.get("text", "#333333")
            border = colors.get("border", "#CCCCCC")
            self.theme_btn.setText("☾")

        self._current_bg = bg
        self._current_text = text
        self._current_border = border

        font_size = self.settings.get("font_size", 12)

        stylesheet = f"""
            QMainWindow, QWidget {{
                background-color: {bg};
                color: {text};
                font-size: {font_size}px;
            }}
            #central {{
                border: 1px solid {border};
            }}
            #header {{
                background-color: {bg};
                border-bottom: 1px solid {border};
            }}
            #headerSep {{
                color: {border};
            }}
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {self._blend(bg, text, 0.08)};
            }}
            QPushButton:pressed {{
                background-color: {self._blend(bg, text, 0.15)};
            }}
            QPushButton:checked {{
                background-color: {self._blend(bg, "#4A90D9", 0.25)};
                border-color: #4A90D9;
            }}
            #tabBtn {{
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0;
                padding: 4px 12px;
                font-weight: bold;
            }}
            #tabBtn:checked {{
                border-bottom: 2px solid #4A90D9;
                color: #4A90D9;
                background-color: transparent;
            }}
            #addBtn {{
                border: 2px dashed {border};
                border-radius: 6px;
                padding: 8px;
                font-size: {font_size}px;
                background-color: transparent;
            }}
            #addBtn:hover {{
                border-color: #4A90D9;
                color: #4A90D9;
            }}
            #deleteBtn {{
                border: none;
                background-color: transparent;
                color: {text};
                font-size: {font_size}px;
            }}
            #deleteBtn:hover {{
                color: #E74C3C;
                background-color: transparent;
            }}
            #timeLabel {{
                font-size: {font_size - 2}px;
                color: {self._blend(text, bg, 0.5)};
            }}
            #descLabel {{
                font-size: {font_size - 2}px;
                color: {self._blend(text, bg, 0.5)};
            }}
            #countLabel {{
                font-size: {font_size - 2}px;
                color: {self._blend(text, bg, 0.5)};
            }}
            #numLabel {{
                font-size: {font_size - 2}px;
                color: {self._blend(text, bg, 0.5)};
            }}
            QListWidget {{
                background-color: {self._blend(bg, text, 0.03)};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px;
            }}
            QListWidget::item {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
                margin: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {self._blend(bg, "#4A90D9", 0.15)};
            }}
            QLineEdit, QTextEdit, QSpinBox {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {border};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                background: #4A90D9;
                border-radius: 8px;
                margin: -5px 0;
            }}
            QGroupBox {{
                border: 1px solid {border};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QCheckBox, QRadioButton {{
                spacing: 6px;
            }}
            QSplitter::handle {{
                background-color: {border};
                width: 2px;
            }}
            QMenu {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
            }}
            QMenu::item:selected {{
                background-color: {self._blend(bg, "#4A90D9", 0.2)};
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {bg};
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            #winBtn {{
                border: none;
                background-color: transparent;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            #winBtn:hover {{
                background-color: {self._blend(bg, text, 0.1)};
            }}
            #winCloseBtn {{
                border: none;
                background-color: transparent;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            #winCloseBtn:hover {{
                background-color: #E81123;
                color: white;
            }}
        """
        self.setStyleSheet(stylesheet)
        app = QApplication.instance()
        font = QFont()
        font.setPointSize(font_size)
        app.setFont(font)

    @staticmethod
    def _blend(c1, c2, ratio):
        """混合两个颜色"""
        qc1 = QColor(c1)
        qc2 = QColor(c2)
        r = int(qc1.red() * (1 - ratio) + qc2.red() * ratio)
        g = int(qc1.green() * (1 - ratio) + qc2.green() * ratio)
        b = int(qc1.blue() * (1 - ratio) + qc2.blue() * ratio)
        return QColor(r, g, b).name()

    def toggle_theme(self):
        current = self.settings.get("theme", "light")
        if current == "light":
            self.settings["theme"] = "dark"
        elif current == "dark":
            self.settings["theme"] = "custom"
        else:
            self.settings["theme"] = "light"
        self.data_manager.save_settings(self.settings)
        self.apply_theme()

    # ========== 设置 ==========

    def open_settings(self):
        dialog = SettingsDialog(self.data_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self.settings = self.data_manager.load_settings()
            self.apply_theme()
            self._handle_auto_start()

    def _handle_auto_start(self):
        enabled = self.settings.get("auto_start", False)
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            if enabled:
                exe_path = sys.executable
                if getattr(sys, 'frozen', False):
                    exe_path = sys.executable
                else:
                    exe_path = sys.argv[0]
                winreg.SetValueEx(key, "HoleList", 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, "HoleList")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    # ========== 桌面固定 ==========

    def toggle_pin(self):
        self.pinned = not self.pinned
        if self.pinned:
            self._pin_window()
        else:
            self._unpin_window()

    def _pin_window(self):
        self.pin_btn.setChecked(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        transparency = self.settings.get("transparency", 60) / 100.0
        self.setWindowOpacity(transparency)
        self.stack.setEnabled(False)
        self.hole_page.set_pinned(True)
        self.memo_page.set_pinned(True)
        self.show()
        self._update_mask()

    def _unpin_window(self):
        self.pin_btn.setChecked(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(1.0)
        self.stack.setEnabled(True)
        self.hole_page.set_pinned(False)
        self.memo_page.set_pinned(False)
        self.show()
        self._update_mask()

    # ========== 窗口状态 ==========

    def restore_geometry(self):
        w = self.settings.get("window", {})
        x = w.get("x", 100)
        y = w.get("y", 100)
        width = w.get("width", 800)
        height = w.get("height", 600)
        self.setGeometry(x, y, width, height)

    def _save_window_state(self):
        if self.pinned:
            return
        geo = self.geometry()
        self.settings["window"] = {
            "x": geo.x(),
            "y": geo.y(),
            "width": geo.width(),
            "height": geo.height(),
        }
        self.data_manager.save_settings(self.settings)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._save_window_state()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._save_window_state()
        self._update_mask()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_mask()

    def _update_mask(self):
        """用位图遮罩实现窗口圆角"""
        bitmap = QBitmap(self.size())
        bitmap.fill(Qt.color0)
        painter = QPainter(bitmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.color1)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)
        painter.end()
        self.setMask(bitmap)

    # ========== 关闭事件 ==========

    def closeEvent(self, event):
        if self._closing:
            event.accept()
            return
        # 最小化到托盘
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "挖坑备忘录", "已最小化到系统托盘，双击图标恢复窗口。",
            QSystemTrayIcon.Information, 2000,
        )

    # ========== 刷新 ==========

    def refresh_all(self):
        self.hole_page.refresh()
        self.memo_page.refresh()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 处理开机自启
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ,
        )
        try:
            winreg.QueryValueEx(key, "HoleList")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except Exception:
        pass

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()