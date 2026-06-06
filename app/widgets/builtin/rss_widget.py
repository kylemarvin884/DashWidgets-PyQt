"""RSS 订阅小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class RssWidget(WidgetBase):
    WIDGET_TYPE = "rss"
    WIDGET_NAME = "RSS订阅"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(4)

        title = QLabel("RSS 订阅")
        title.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
        title.setStyleSheet(f"color: {c['title']}; background: transparent;")
        main_layout.addWidget(title)

        items = ["DashWidgets v2.0 发布", "PySide6 新特性速览", "Fluent Design 更新日志"]
        for item in items:
            lbl = QLabel(f"  {item}")
            lbl.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
            lbl.setStyleSheet(f"color: {c['text']}; background: transparent;")
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            main_layout.addWidget(lbl)
        main_layout.addStretch()
