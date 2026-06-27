from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QSpinBox, QLineEdit, QButtonGroup,
    QRadioButton, QGroupBox, QWidget, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont


class ColorInput(QWidget):
    """带预览的颜色输入框"""
    color_changed = Signal()

    def __init__(self, label_text, default_color="#FFFFFF", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel(label_text))

        self.edit = QLineEdit(default_color)
        self.edit.setMaximumWidth(100)
        self.edit.setPlaceholderText("#FFFFFF")
        layout.addWidget(self.edit)

        self.preview = QFrame()
        self.preview.setFixedSize(24, 24)
        self.preview.setStyleSheet(
            f"background-color: {default_color}; border: 1px solid #999; border-radius: 2px;"
        )
        layout.addWidget(self.preview)

        layout.addStretch()

        self.edit.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text):
        color = QColor(text)
        if color.isValid():
            self.preview.setStyleSheet(
                f"background-color: {text}; border: 1px solid #999; border-radius: 2px;"
            )
            self.color_changed.emit()

    def get_color(self):
        return self.edit.text().strip()


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.settings = data_manager.load_settings()
        self.setWindowTitle("设置")
        self.setMinimumWidth(400)
        self.setup_ui()
        self._load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # === 主题选择 ===
        theme_group = QGroupBox("主题")
        theme_layout = QVBoxLayout(theme_group)

        self.theme_group = QButtonGroup(self)
        theme_row = QHBoxLayout()
        self.radio_light = QRadioButton("白天")
        self.radio_dark = QRadioButton("黑夜")
        self.radio_custom = QRadioButton("自定义")
        self.theme_group.addButton(self.radio_light, 0)
        self.theme_group.addButton(self.radio_dark, 1)
        self.theme_group.addButton(self.radio_custom, 2)
        theme_row.addWidget(self.radio_light)
        theme_row.addWidget(self.radio_dark)
        theme_row.addWidget(self.radio_custom)
        theme_row.addStretch()
        theme_layout.addLayout(theme_row)

        layout.addWidget(theme_group)

        # === 自定义颜色 ===
        color_group = QGroupBox("自定义颜色")
        color_layout = QVBoxLayout(color_group)

        self.color_bg = ColorInput("背景色:", "#FFFFFF")
        self.color_text = ColorInput("文字色:", "#333333")
        self.color_border = ColorInput("边框色:", "#CCCCCC")

        color_layout.addWidget(self.color_bg)
        color_layout.addWidget(self.color_text)
        color_layout.addWidget(self.color_border)

        self.color_group_widget = color_group
        layout.addWidget(color_group)

        # === 透明度 ===
        transp_layout = QHBoxLayout()
        transp_layout.addWidget(QLabel("窗口透明度:"))
        self.transp_slider = QSlider(Qt.Horizontal)
        self.transp_slider.setRange(10, 100)
        self.transp_slider.setValue(60)
        self.transp_label = QLabel("60%")
        self.transp_label.setFixedWidth(40)
        self.transp_slider.valueChanged.connect(
            lambda v: self.transp_label.setText(f"{v}%")
        )
        transp_layout.addWidget(self.transp_slider)
        transp_layout.addWidget(self.transp_label)
        layout.addLayout(transp_layout)

        # === 字体大小 ===
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("字体大小:"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 24)
        self.font_spin.setValue(12)
        self.font_spin.setSuffix(" px")
        font_layout.addWidget(self.font_spin)
        font_layout.addStretch()
        layout.addLayout(font_layout)

        # === 开机自启 ===
        self.auto_start_cb = QCheckBox("开机自启")
        layout.addWidget(self.auto_start_cb)

        layout.addStretch()

        # === 按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("保存")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # 主题切换联动
        self.theme_group.buttonClicked.connect(self._on_theme_changed)

    def _load_settings(self):
        s = self.settings
        theme = s.get("theme", "light")
        if theme == "light":
            self.radio_light.setChecked(True)
        elif theme == "dark":
            self.radio_dark.setChecked(True)
        else:
            self.radio_custom.setChecked(True)

        colors = s.get("colors", {})
        self.color_bg.edit.setText(colors.get("bg", "#FFFFFF"))
        self.color_text.edit.setText(colors.get("text", "#333333"))
        self.color_border.edit.setText(colors.get("border", "#CCCCCC"))

        self.transp_slider.setValue(s.get("transparency", 60))
        self.font_spin.setValue(s.get("font_size", 12))
        self.auto_start_cb.setChecked(s.get("auto_start", False))

        self._on_theme_changed()

    def _on_theme_changed(self):
        is_custom = self.radio_custom.isChecked()
        self.color_group_widget.setEnabled(is_custom)

    def _on_save(self):
        theme = "light"
        if self.radio_dark.isChecked():
            theme = "dark"
        elif self.radio_custom.isChecked():
            theme = "custom"

        colors = {
            "bg": self.color_bg.get_color(),
            "text": self.color_text.get_color(),
            "border": self.color_border.get_color(),
        }

        self.settings["theme"] = theme
        self.settings["colors"] = colors
        self.settings["transparency"] = self.transp_slider.value()
        self.settings["font_size"] = self.font_spin.value()
        self.settings["auto_start"] = self.auto_start_cb.isChecked()

        self.data_manager.save_settings(self.settings)
        self.accept()