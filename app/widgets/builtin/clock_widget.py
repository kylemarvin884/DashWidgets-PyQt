"""时钟小组件 — 纯时间数字（Win11 主题适配）"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class ClockWidget(WidgetBase):
    WIDGET_TYPE = "clock"
    WIDGET_NAME = "时钟"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._setup_ui()
        self._start_timers()

    def _setup_ui(self) -> None:
        self.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._time_label = QLabel("00:00")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Segoe UI Variable", 52, QFont.Weight.ExtraLight)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
        self._time_label.setFont(font)
        c = Win11Style.widget_colors()
        self._time_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(self._time_label)

    def _start_timers(self) -> None:
        timer = QTimer(self)
        timer.timeout.connect(self._update_time)
        timer.start(1000)
        self._update_time()

    def _update_time(self) -> None:
        self._time_label.setText(QDateTime.currentDateTime().toString("HH:mm"))

    def update_theme(self) -> None:
        if hasattr(self, '_time_label'):
            c = Win11Style.widget_colors()
            self._time_label.setStyleSheet(f"color: {c['text']}; background: transparent;")

    def apply_settings(self, settings: dict) -> None:
        if not hasattr(self, '_time_label'):
            return
        font_size = settings.get("font_size")
        if font_size is not None:
            font = self._time_label.font()
            font.setPointSize(int(font_size))
            self._time_label.setFont(font)
        text_color = settings.get("text_color")
        if text_color is not None:
            qc = QColor(text_color)
            if qc.isValid():
                self._time_label.setStyleSheet(f"color: {text_color}; background: transparent;")

    def on_settings_changed(self, settings: dict) -> None:
        self.apply_settings(settings)
