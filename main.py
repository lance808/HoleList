import sys
import os
import winreg

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QSystemTrayIcon, QMenu, QButtonGroup,
    QMessageBox, QDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction

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
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "H")
    painter.end()
    return QIcon(pixmap)


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

        self.setup_ui()
        self.setup_tray()
        self.apply_theme()
        self.restore_geometry()
        self.refresh_all()

        # 保存窗口位置
        self._save_timer = QTimer()
        self._save_timer.setInterval(2000)
        self._save_timer.timeout.connect(self._save_window_state)
        self._save_timer.start()

        # 加载数据
        self.tab_hole.setChecked(True)
        self.stack.setCurrentIndex(0)

    # ========== UI 构建 ==========

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部导航栏
        layout.addWidget(self._create_header())

        # 分隔线
        from PySide6.QtWidgets import QFrame
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
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(40)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 主题切换
        self.theme_btn = QPushButton()
        self.theme_btn.setFixedSize(32, 28)
        self.theme_btn.setToolTip("切换白天/黑夜模式")
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)

        # 设置按钮
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(32, 28)
        self.settings_btn.setToolTip("设置")
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        layout.addStretch()

        # 固定按钮
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(32, 28)
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
        self.tab_hole.setFixedSize(72, 28)
        self.tab_hole.setObjectName("tabBtn")
        self.tab_hole.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.tab_group.addButton(self.tab_hole)

        self.tab_memo = QPushButton("备忘录")
        self.tab_memo.setCheckable(True)
        self.tab_memo.setFixedSize(72, 28)
        self.tab_memo.setObjectName("tabBtn")
        self.tab_memo.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.tab_group.addButton(self.tab_memo)

        layout.addWidget(self.tab_hole)
        layout.addWidget(self.tab_memo)

        return header

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
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
        )
        transparency = self.settings.get("transparency", 60) / 100.0
        self.setWindowOpacity(transparency)
        # 禁用内容区操作
        self.stack.setEnabled(False)
        self.show()

    def _unpin_window(self):
        self.pin_btn.setChecked(False)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setWindowOpacity(1.0)
        self.stack.setEnabled(True)
        self.show()

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