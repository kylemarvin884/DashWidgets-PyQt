"""文档查看器小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class DocumentViewerWidget(WidgetBase):
    WIDGET_TYPE = "document_viewer"
    WIDGET_NAME = "文档查看器"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(4)

        title = QLabel("文档查看器")
        title.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
        title.setStyleSheet(f"color: {c['title']}; background: transparent;")
        main_layout.addWidget(title)

        self._content = QLabel("暂无打开的文档")
        self._content.setWordWrap(True)
        self._content.setFont(QFont("Segoe UI Variable", 12))
        self._content.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        self._content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll = QScrollArea()
        scroll.setWidget(self._content)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            "QScrollBar::handle:vertical { background: rgba(128,128,128,0.2); border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        main_layout.addWidget(scroll)
