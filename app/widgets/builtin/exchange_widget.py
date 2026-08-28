"""汇率小组件 — 每行货币对可自定义（设置中选任意两种货币）"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from app.widgets.base_widget import WidgetConfig, WidgetBase
from app.services.desktop_widget_service import Win11Style
from app.utils.async_fetch import run_in_background

_DEFAULT_PAIRS = [
    ("USD", "CNY"), ("EUR", "CNY"), ("GBP", "CNY"), ("JPY", "CNY"), ("HKD", "CNY"),
    ("AUD", "CNY"),
]
_MAX_PAIRS = 6  # 行数上限
_REFRESH_MS = 60 * 60 * 1000  # 参考汇率每小时刷新一次


def _configured_pairs(settings: dict) -> list[tuple[str, str]]:
    """从设置读取每行的货币对（pair_1..pair_5），缺省回落到默认值"""
    pairs: list[tuple[str, str]] = []
    for i in range(1, _MAX_PAIRS + 1):
        val = settings.get(f"pair_{i}")
        if isinstance(val, (list, tuple)) and len(val) == 2:
            base, quote = str(val[0]).upper(), str(val[1]).upper()
            if base and quote:
                pairs.append((base, quote))
                continue
        pairs.append(_DEFAULT_PAIRS[i - 1])
    return pairs


def _configured_count(settings: dict) -> int:
    """用户实际配置的行数（settings 中存在的 pair_N 键数）"""
    return sum(1 for i in range(1, _MAX_PAIRS + 1)
               if isinstance(settings.get(f"pair_{i}"), (list, tuple)))


class ExchangeWidget(WidgetBase):
    WIDGET_TYPE = "exchange"
    WIDGET_NAME = "汇率"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._fetching = False
        self._task = None  # 持有后台任务信号对象，防止被 GC
        self._rate_labels: dict[tuple[str, str], QLabel] = {}
        self._pair_rows: dict[tuple[str, str], QWidget] = {}
        self._build_rows()
        self._refresh()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(_REFRESH_MS)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

    def _build_rows(self):
        """按当前配置的货币对重建全部行"""
        # 移除旧布局及其子控件
        old_lay = self.layout()
        if old_lay is not None:
            QWidget().setLayout(old_lay)

        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._rate_labels.clear()
        self._pair_rows.clear()

        for pair in _configured_pairs(self.config.settings):
            base, quote = pair
            row_w = QWidget(self)
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(0)
            pair_lbl = QLabel(f"{base}/{quote}")
            pair_lbl.setFont(Win11Style.widget_font(16, QFont.Weight.Light))
            pair_lbl.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
            row.addWidget(pair_lbl)
            row.addStretch()
            rate_lbl = QLabel("--")
            rate_lbl.setFont(Win11Style.widget_font(17, QFont.Weight.ExtraLight))
            rate_lbl.setStyleSheet(f"color: {c['text']}; background: transparent;")
            row.addWidget(rate_lbl)
            self._rate_labels[pair] = rate_lbl
            self._pair_rows[pair] = row_w
            main_layout.addWidget(row_w)

        # ── 底部操作行：添加/删除（已配置行数上限 _MAX_PAIRS）──
        count = _configured_count(self.config.settings)
        op_row = QHBoxLayout()
        op_row.setSpacing(12)

        from qfluentwidgets import ToolButton, FluentIcon as FIF
        self._add_btn = ToolButton(FIF.ADD)
        self._add_btn.setFixedSize(26, 26)
        self._add_btn.setToolTip(f"添加货币对（最多 {_MAX_PAIRS} 行）")
        self._add_btn.setEnabled(count < _MAX_PAIRS)
        self._add_btn.clicked.connect(self._add_pair)
        op_row.addWidget(self._add_btn)

        self._remove_btn = ToolButton(FIF.REMOVE)
        self._remove_btn.setFixedSize(26, 26)
        self._remove_btn.setToolTip("删除最后一行")
        self._remove_btn.setEnabled(count > 1)
        self._remove_btn.clicked.connect(self._remove_last_pair)
        op_row.addWidget(self._remove_btn)

        op_row.addStretch()
        main_layout.addLayout(op_row)

    def _add_pair(self) -> None:
        """追加一行（默认 USD/CNY；超过上限忽略）"""
        settings = dict(self.config.settings)
        count = _configured_count(settings)
        if count >= _MAX_PAIRS:
            return
        next_idx = count + 1
        settings[f"pair_{next_idx}"] = ["USD", "CNY"]
        self._save_and_apply(settings)

    def _remove_last_pair(self) -> None:
        """删除最后一行（至少保留 1 行）"""
        settings = dict(self.config.settings)
        count = _configured_count(settings)
        if count <= 1:
            return
        # 删除后：把被删槽位之后的配置前移，保持行连续
        for i in range(count, _MAX_PAIRS):
            nxt = settings.get(f"pair_{i + 1}")
            if nxt is not None:
                settings[f"pair_{i}"] = nxt
            else:
                settings.pop(f"pair_{i}", None)
        settings.pop(f"pair_{count}", None)
        settings.pop(f"pair_{count}", None)
        self._save_and_apply(settings)

    def _save_and_apply(self, settings: dict) -> None:
        """持久化配置并重建行"""
        self.config.settings = settings
        try:
            from app.models.widget_model import WidgetModel
            model = WidgetModel()
            w = model.get_widget(self.config.id)
            if w:
                w.custom_settings = dict(settings)
                model.save()
        except Exception:
            pass
        self._build_rows()
        self._refresh()

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

        from app.services.exchange_service import get_exchange_service
        svc = get_exchange_service()
        for (base, quote), lbl in self._rate_labels.items():
            rate = svc.cross_rate(result, base, quote)
            if rate is None:
                lbl.setText("--")
            elif rate >= 1:
                lbl.setText(f"{rate:.4f}")
            else:
                lbl.setText(f"{rate:.6f}")  # 小汇率多给两位精度

    def on_settings_changed(self, settings: dict) -> None:
        """货币对配置变化时重建行并刷新数据

        settings 可能是增量（设置窗口只传改动的键），与现有配置合并后判断。
        """
        merged = dict(self.config.settings)
        merged.update(settings)
        if _configured_pairs(merged) != list(self._rate_labels.keys()):
            self.config.settings = merged
            self._build_rows()
        self._refresh()

    def on_close(self):
        self._refresh_timer.stop()
