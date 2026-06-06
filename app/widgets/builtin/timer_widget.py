"""计时器小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import ToolButton, FluentIcon as FIF

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class TimerWidget(WidgetBase):
    WIDGET_TYPE = "timer"
    WIDGET_NAME = "计时器"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._remaining_ms = 5 * 60 * 1000
        self._running = False
        self._finished = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._time_label = QLabel("05:00")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setFont(QFont("Segoe UI Variable", 28, QFont.Weight.ExtraLight))
        self._time_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(self._time_label)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
        self._status_label.setStyleSheet(f"color: {c['accent']}; background: transparent;")
        main_layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._start_btn = ToolButton(FIF.PLAY)
        self._start_btn.setFixedSize(36, 36)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self._start_btn)

        self._reset_btn = ToolButton(FIF.SYNC)
        self._reset_btn.setFixedSize(36, 36)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self._reset_btn)
        main_layout.addLayout(btn_row)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._update_display()

    def _toggle(self) -> None:
        if self._finished:
            self._reset()
            return
        self._running = not self._running
        if self._running:
            self._tick.start(100)
        else:
            self._tick.stop()
        self._start_btn.setIcon(FIF.PAUSE if self._running else FIF.PLAY)

    def _reset(self) -> None:
        self._running = False
        self._finished = False
        self._remaining_ms = 5 * 60 * 1000
        self._tick.stop()
        self._start_btn.setIcon(FIF.PLAY)
        self._status_label.setText("")
        self._update_display()

    def _on_tick(self) -> None:
        self._remaining_ms -= 100
        if self._remaining_ms <= 0:
            self._remaining_ms = 0
            self._running = False
            self._finished = True
            self._tick.stop()
            self._start_btn.setIcon(FIF.PLAY)
            self._status_label.setText("时间到!")
        self._update_display()

    def _update_display(self) -> None:
        total = max(0, self._remaining_ms)
        mins = total // 60000
        secs = (total // 1000) % 60
        self._time_label.setText(f"{mins:02d}:{secs:02d}")
        if self._finished:
            self._time_label.setStyleSheet("color: #e74856; background: transparent;")
        else:
            c = Win11Style.widget_colors()
            self._time_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
