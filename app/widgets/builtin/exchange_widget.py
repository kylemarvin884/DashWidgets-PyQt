"""汇率小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class ExchangeWidget(WidgetBase):
    WIDGET_TYPE = "exchange"
    WIDGET_NAME = "汇率"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(4)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rates = [("USD/CNY", "7.2450"), ("EUR/CNY", "7.8920"), ("GBP/CNY", "9.1820"), ("JPY/CNY", "0.0483")]
        for pair, rate in rates:
            row = QHBoxLayout()
            row.setSpacing(0)
            pair_lbl = QLabel(pair)
            pair_lbl.setFont(QFont("Segoe UI Variable", 12, QFont.Weight.Light))
            pair_lbl.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
            row.addWidget(pair_lbl)
            row.addStretch()
            rate_lbl = QLabel(rate)
            rate_lbl.setFont(QFont("Segoe UI Variable", 13, QFont.Weight.ExtraLight))
            rate_lbl.setStyleSheet(f"color: {c['text']}; background: transparent;")
            row.addWidget(rate_lbl)
            main_layout.addLayout(row)
