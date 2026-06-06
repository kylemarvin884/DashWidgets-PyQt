"""日历小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class CalendarWidget(WidgetBase):
    WIDGET_TYPE = "calendar"
    WIDGET_NAME = "日历"
    WEEKDAYS_CN = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._day_labels = []
        self._setup_ui()
        self._start_timers()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 8)
        main_layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label = QLabel("")
        self._title_label.setFont(QFont("Segoe UI Variable", 13, QFont.Weight.Light))
        self._title_label.setStyleSheet(f"color: {c['title']}; background: transparent;")
        title_row.addWidget(self._title_label)
        main_layout.addLayout(title_row)

        header_grid = QGridLayout()
        header_grid.setSpacing(2)
        hdr_font = QFont("Segoe UI Variable", 9, QFont.Weight.Normal)
        for col, wd in enumerate(self.WEEKDAYS_CN):
            lbl = QLabel(wd)
            lbl.setFont(hdr_font)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {c['text_dim']}; background: transparent;")
            header_grid.addWidget(lbl, 0, col)
        main_layout.addLayout(header_grid)

        self._date_grid = QGridLayout()
        self._date_grid.setSpacing(3)
        day_font = QFont("Segoe UI Variable", 11, QFont.Weight.ExtraLight)
        for row in range(6):
            for col in range(7):
                lbl = QLabel("")
                lbl.setFont(day_font)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet(f"color: {c['text']}; background: transparent; padding: 1px;")
                lbl.setMinimumSize(22, 18)
                self._date_grid.addWidget(lbl, row, col)
                self._day_labels.append(lbl)
        main_layout.addLayout(self._date_grid)
        main_layout.addStretch()

    def _start_timers(self) -> None:
        timer = QTimer(self)
        timer.timeout.connect(self._update_calendar)
        timer.start(60000)
        self._update_calendar()

    def _update_calendar(self) -> None:
        c = Win11Style.widget_colors()
        today = QDate.currentDate()
        year, month = today.year(), today.month()
        self._title_label.setText(f"{year}年 {month}月")
        first_day = QDate(year, month, 1)
        start_dow = first_day.dayOfWeek()
        days_in_month = first_day.daysInMonth()
        idx = 0
        for row in range(6):
            for col in range(7):
                lbl = self._day_labels[idx]
                day_num = idx - start_dow + 2
                if 1 <= day_num <= days_in_month:
                    lbl.setText(str(day_num))
                    if day_num == today.day():
                        lbl.setStyleSheet(
                            f"color: #ffffff; background: {c['accent']};"
                            " border-radius: 9px; padding: 2px 4px;"
                        )
                    else:
                        lbl.setStyleSheet(f"color: {c['text']}; background: transparent;")
                else:
                    lbl.setText("")
                    lbl.setStyleSheet("background: transparent;")
                idx += 1

    def update_theme(self) -> None:
        self._update_calendar()

    def apply_settings(self, settings: dict) -> None:
        pass
