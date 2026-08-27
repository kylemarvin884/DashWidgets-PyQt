"""系统监控小组件 — 现代进度条风格（指标由后台采样服务推送）"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QLinearGradient, QBrush,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class _StatBar(QWidget):
    """带进度条的系统指标"""

    def __init__(self, label: str, color: QColor, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0
        self._sub_text = ""
        self.setFixedHeight(48)
        self.setStyleSheet("background: transparent;")
        # 字体只创建一次（paint 每次触发都新建 QFont 是无谓分配）
        self._label_font = QFont("Segoe UI Variable", 10, QFont.Weight.Normal)
        self._pct_font = QFont("Segoe UI Variable", 14, QFont.Weight.DemiBold)
        self._sub_font = QFont("Segoe UI Variable", 8, QFont.Weight.Light)

    def set_value(self, value: float, sub_text: str = "") -> None:
        self._value = max(0.0, min(1.0, value))
        self._sub_text = sub_text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = Win11Style.widget_colors()

        w = self.width()
        bar_h = 6
        bar_y = 26

        # 标签
        p.setFont(self._label_font)
        p.setPen(QColor(c["text"]))
        p.drawText(QRectF(12, 0, 50, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._label)

        # 百分比
        p.setFont(self._pct_font)
        pct = f"{int(self._value * 100)}%"
        pct_w = 50
        p.drawText(QRectF(w - 12 - pct_w, -2, pct_w, 22),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pct)

        # 副文本
        if self._sub_text:
            p.setFont(self._sub_font)
            p.setPen(QColor(c["accent"]))
            p.drawText(QRectF(w - 12 - pct_w, 20, pct_w, 12),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._sub_text)

        # 进度条背景
        bar_x = 60
        bar_w = w - bar_x - 72
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(c["track"])))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        # 进度条前景
        if self._value > 0.001:
            fill_w = int(bar_w * self._value)
            grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            grad.setColorAt(0.0, self._color)
            grad.setColorAt(1.0, QColor(
                min(255, self._color.red() + 40),
                min(255, self._color.green() + 40),
                min(255, self._color.blue() + 40),
            ))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)

        p.end()


class SystemMonitorWidget(WidgetBase):
    WIDGET_TYPE = "system_monitor"
    WIDGET_NAME = "系统监控"

    CPU_COLOR = QColor(80, 200, 255)
    MEM_COLOR = QColor(255, 180, 80)
    DISK_COLOR = QColor(120, 220, 160)

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._setup_ui()
        self._connect_stats_service()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 8, 14, 8)
        main_layout.setSpacing(2)

        # 标题
        title = QLabel("系统监控")
        title.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {c['text']}; background: transparent; padding-bottom: 2px;")
        main_layout.addWidget(title)

        # CPU
        self._cpu_bar = _StatBar("CPU", self.CPU_COLOR, self)
        main_layout.addWidget(self._cpu_bar)

        # 内存
        self._mem_bar = _StatBar("内存", self.MEM_COLOR, self)
        main_layout.addWidget(self._mem_bar)

        # 磁盘
        self._disk_bar = _StatBar("磁盘", self.DISK_COLOR, self)
        main_layout.addWidget(self._disk_bar)

    def _connect_stats_service(self) -> None:
        """订阅后台采样服务（psutil 不再占用 UI 线程）"""
        from app.services.system_stats_service import get_system_stats_service
        self._stats_svc = get_system_stats_service()
        self._stats_svc.system_stats.connect(self._on_stats)
        self._stats_svc.acquire_system()

    def _on_stats(self, s: dict) -> None:
        freq_str = f"{s['cpu_ghz']:.1f} GHz" if s["cpu_ghz"] > 0 else ""
        self._cpu_bar.set_value(s["cpu"] / 100, sub_text=freq_str)
        self._mem_bar.set_value(s["mem_percent"] / 100,
                                f"{s['mem_used_gb']:.1f}/{s['mem_total_gb']:.0f} GB")
        self._disk_bar.set_value(s["disk_percent"] / 100,
                                 f"{s['disk_used_gb']:.0f}/{s['disk_total_gb']:.0f} GB")

    def on_close(self) -> None:
        try:
            self._stats_svc.system_stats.disconnect(self._on_stats)
            self._stats_svc.release_system()
        except Exception:
            pass
