"""图片小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class ImageWidget(WidgetBase):
    WIDGET_TYPE = "image"
    WIDGET_NAME = "图片"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._image_path = config.settings.get("image_path", "")
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        self._label = QLabel("点击设置图片")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFont(QFont("Segoe UI Variable", 12, QFont.Weight.Light))
        self._label.setStyleSheet(
            f"color: {c['text_dim']}; background: {c['bg_input']};"
            f" border: 1px solid {c['border_input']}; border-radius: 8px;"
        )
        layout.addWidget(self._label)

        if self._image_path:
            from PySide6.QtGui import QPixmap
            pm = QPixmap(self._image_path)
            if not pm.isNull():
                self._label.setPixmap(pm.scaled(
                    self._label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
