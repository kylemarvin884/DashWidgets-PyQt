"""时钟小组件 — 时间 + 日期（Win11 主题适配，支持秒数显示）"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style

_WEEKDAYS_CN = ["一", "二", "三", "四", "五", "六", "日"]


class ClockWidget(WidgetBase):
    WIDGET_TYPE = "clock"
    WIDGET_NAME = "时钟"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._show_seconds = bool(config.settings.get("show_seconds", False))
        self._show_date = bool(config.settings.get("show_date", True))
        self._hour_12 = bool(config.settings.get("hour_12", False))
        self._custom_color: str | None = None
        self._setup_ui()
        self._start_timers()

    def _setup_ui(self) -> None:
        self.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._time_label = QLabel("00:00")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = Win11Style.widget_font(69, QFont.Weight.ExtraLight)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
        self._time_label.setFont(font)

        self._date_label = QLabel("")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_font = Win11Style.widget_font(15, QFont.Weight.Light)
        date_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        self._date_label.setFont(date_font)

        self._apply_colors()
        main_layout.addWidget(self._time_label)
        main_layout.addWidget(self._date_label)

    def _apply_colors(self) -> None:
        c = Win11Style.widget_colors()
        text = self._custom_color or c["text"]
        self._time_label.setStyleSheet(f"color: {text}; background: transparent;")
        # 日期行跟随时间颜色但更柔和；自定义颜色时直接使用
        date_color = self._custom_color or c["text_secondary"]
        self._date_label.setStyleSheet(f"color: {date_color}; background: transparent;")

    def _start_timers(self) -> None:
        timer = QTimer(self)
        timer.timeout.connect(self._update_time)
        timer.start(1000)
        self._update_time()

    def _update_time(self) -> None:
        now = QDateTime.currentDateTime()
        if self._hour_12:
            fmt = "h:mm:ss AP" if self._show_seconds else "h:mm AP"
        else:
            fmt = "HH:mm:ss" if self._show_seconds else "HH:mm"
        self._time_label.setText(now.toString(fmt))
        self._date_label.setVisible(self._show_date)
        self._date_label.setText(
            f"{now.date().month()}月{now.date().day()}日 周{_WEEKDAYS_CN[now.date().dayOfWeek() - 1]}"
        )

    def refresh(self) -> None:
        self._update_time()

    def update_theme(self) -> None:
        if hasattr(self, '_time_label'):
            self._apply_colors()

    def apply_settings(self, settings: dict) -> None:
        if not hasattr(self, '_time_label'):
            return

        show_seconds = settings.get("show_seconds")
        if show_seconds is not None:
            self._show_seconds = bool(show_seconds)

        show_date = settings.get("show_date")
        if show_date is not None:
            self._show_date = bool(show_date)
            self._date_label.setVisible(self._show_date)

        hour_12 = settings.get("hour_12")
        if hour_12 is not None:
            self._hour_12 = bool(hour_12)

        font_size = settings.get("font_size")
        if font_size is not None:
            font = self._time_label.font()
            font.setPointSize(int(font_size))
            self._time_label.setFont(font)

        text_color = settings.get("text_color")
        if text_color is not None:
            qc = QColor(text_color)
            if qc.isValid():
                self._custom_color = text_color
            else:
                self._custom_color = None
        elif "text_color" in settings:
            self._custom_color = None

        self._apply_colors()
        self._update_time()

    def on_settings_changed(self, settings: dict) -> None:
        self.apply_settings(settings)
