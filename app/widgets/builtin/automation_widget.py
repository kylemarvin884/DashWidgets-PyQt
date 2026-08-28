"""自动化点击小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class AutomationWidget(WidgetBase):
    WIDGET_TYPE = "automation"
    WIDGET_NAME = "自动化点击"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._click_count = 0
        self._auto_running = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._count_label = QLabel("0")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_label.setFont(Win11Style.widget_font(48, QFont.Weight.ExtraLight))
        self._count_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(self._count_label)

        self._status_label = QLabel("就绪")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(Win11Style.widget_font(15, QFont.Weight.Light))
        self._status_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        main_layout.addWidget(self._status_label)

        btn_qss = (f"QPushButton {{ color: {c['text']}; background: {c['bg_input']};"
                   f" border: 1px solid {c['border_input']}; border-radius: 6px;"
                   f" padding: 4px 20px; font-size: 12px; }}"
                   f"QPushButton:hover {{ background: {c['track']}; }}"
                   f"QPushButton:pressed {{ background: {c['accent']}; color: #ffffff; }}")
        self._toggle_btn = QPushButton("启动")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(btn_qss)
        self._toggle_btn.clicked.connect(self._toggle)
        main_layout.addWidget(self._toggle_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _toggle(self) -> None:
        c = Win11Style.widget_colors()
        self._auto_running = not self._auto_running
        if self._auto_running:
            self._status_label.setText("运行中")
            self._status_label.setStyleSheet(f"color: {c['accent']}; background: transparent;")
            self._toggle_btn.setText("停止")
            self._auto_timer = QTimer(self)
            self._auto_timer.timeout.connect(self._auto_click)
            self._auto_timer.start(1000)
        else:
            self._status_label.setText("已停止")
            self._status_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
            self._toggle_btn.setText("启动")
            self._auto_timer.stop()

    def _auto_click(self) -> None:
        self._click_count += 1
        self._count_label.setText(str(self._click_count))
