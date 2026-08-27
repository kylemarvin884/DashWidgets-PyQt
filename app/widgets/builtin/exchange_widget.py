"""汇率小组件 — Win11 风格，接入 frankfurter.app 真实汇率（工作线程获取）"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from app.widgets.base_widget import WidgetConfig, WidgetBase
from app.services.desktop_widget_service import Win11Style
from app.utils.async_fetch import run_in_background

_PAIRS = ["USD", "EUR", "GBP", "JPY", "HKD"]  # 显示 1 外币 = X CNY
_REFRESH_MS = 60 * 60 * 1000  # 参考汇率每小时刷新一次


class ExchangeWidget(WidgetBase):
    WIDGET_TYPE = "exchange"
    WIDGET_NAME = "汇率"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._fetching = False
        self._task = None  # 持有后台任务信号对象，防止被 GC
        self._rate_labels: dict[str, QLabel] = {}
        self._setup_ui()
        self._refresh()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(_REFRESH_MS)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

    def _setup_ui(self):
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for code in _PAIRS:
            row = QHBoxLayout()
            row.setSpacing(0)
            pair_lbl = QLabel(f"{code}/CNY")
            pair_lbl.setFont(QFont("Segoe UI Variable", 12, QFont.Weight.Light))
            pair_lbl.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
            row.addWidget(pair_lbl)
            row.addStretch()
            rate_lbl = QLabel("--")
            rate_lbl.setFont(QFont("Segoe UI Variable", 13, QFont.Weight.ExtraLight))
            rate_lbl.setStyleSheet(f"color: {c['text']}; background: transparent;")
            row.addWidget(rate_lbl)
            self._rate_labels[code] = rate_lbl
            main_layout.addLayout(row)

    def _refresh(self):
        """在后台线程获取汇率（网络请求阻塞，不能放 UI 线程）"""
        if self._fetching:
            return
        self._fetching = True

        def _work():
            from app.services.exchange_service import get_exchange_service
            return get_exchange_service().get_rates()

        self._task = run_in_background(_work, self._on_rates)

    def _on_rates(self, result):
        self._fetching = False
        if isinstance(result, Exception) or result is None:
            for lbl in self._rate_labels.values():
                lbl.setText("--")
            return

        for code, lbl in self._rate_labels.items():
            rate = result.rates.get(code)
            if rate is None:
                lbl.setText("--")
            elif rate >= 1:
                lbl.setText(f"{rate:.4f}")
            else:
                lbl.setText(f"{rate:.6f}")  # JPY 等小汇率多给两位精度

    def on_close(self):
        self._refresh_timer.stop()
