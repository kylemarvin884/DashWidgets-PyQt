"""秒表小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QElapsedTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import ToolButton, FluentIcon as FIF

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class StopwatchWidget(WidgetBase):
    WIDGET_TYPE = "stopwatch"
    WIDGET_NAME = "秒表"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._running = False
        self._elapsed_ms = 0
        self._timer = QElapsedTimer()
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._time_label = QLabel("00:00.00")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setFont(QFont("Segoe UI Variable", 28, QFont.Weight.ExtraLight))
        self._time_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(self._time_label)

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

        self._update_tick = QTimer(self)
        self._update_tick.timeout.connect(self._update_display)
        self._update_display()

    def _toggle(self) -> None:
        if self._running:
            self._elapsed_ms += self._timer.elapsed()
            self._timer.invalidate()
            self._update_tick.stop()
        else:
            self._timer.start()
            self._update_tick.start(100)
        self._running = not self._running
        self._start_btn.setIcon(FIF.PAUSE if self._running else FIF.PLAY)

    def _reset(self) -> None:
        self._running = False
        self._elapsed_ms = 0
        self._timer.invalidate()
        self._update_tick.stop()
        self._start_btn.setIcon(FIF.PLAY)
        self._update_display()

    def _update_display(self) -> None:
        total = self._elapsed_ms
        if self._running and self._timer.isValid():
            total += self._timer.elapsed()
        mins = (total // 60000) % 60
        secs = (total // 1000) % 60
        cs = (total // 10) % 100
        self._time_label.setText(f"{mins:02d}:{secs:02d}.{cs:02d}")
