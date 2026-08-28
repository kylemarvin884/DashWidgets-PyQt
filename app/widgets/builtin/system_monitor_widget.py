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
        self._label_font = Win11Style.widget_font(13, QFont.Weight.Normal)
        self._pct_font = Win11Style.widget_font(19, QFont.Weight.DemiBold)
        self._sub_font = Win11Style.widget_font(11, QFont.Weight.Light)

    def set_value(self, value: float, sub_text: str = "") -> None:
        self._value = max(0.0, min(1.0, value))
        self._sub_text = sub_text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = Win11Style.widget_colors()

        w = self.width()
        h = self.height()
        m = 14          # 左右统一边距
        pct_w = 52      # 右侧数值列固定宽

        # ── 第一行：标签（左）+ 百分比/副文本（右）──
        row_h = 22
        p.setFont(self._label_font)
        p.setPen(QColor(c["text"]))
        p.drawText(QRectF(m, 0, 80, row_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        pct = f"{int(self._value * 100)}%"
        p.setFont(self._pct_font)
        p.drawText(QRectF(w - m - pct_w, 0, pct_w, row_h),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pct)

        # ── 第二行：进度条（与上下文本对齐，占满行宽）──
        bar_y = h - 14
        bar_x = m
        bar_w = w - m * 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(c["track"])))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, 5), 2.5, 2.5)

        if self._value > 0.001:
            fill_w = max(5, int(bar_w * self._value))
            grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            grad.setColorAt(0.0, self._color)
            grad.setColorAt(1.0, QColor(
                min(255, self._color.red() + 40),
                min(255, self._color.green() + 40),
                min(255, self._color.blue() + 40),
            ))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, 5), 2.5, 2.5)

        p.end()


class SystemMonitorWidget(WidgetBase):
    WIDGET_TYPE = "system_monitor"
    WIDGET_NAME = "系统监控"

    CPU_COLOR = QColor(80, 200, 255)
    MEM_COLOR = QColor(255, 180, 80)
    DISK_COLOR = QColor(120, 220, 160)

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._show_cpu_freq = bool(config.settings.get("show_cpu_freq", True))
        self._setup_ui()
        self._apply_visibility(
            show_cpu=config.settings.get("show_cpu", True),
            show_mem=config.settings.get("show_mem", True),
            show_disk=config.settings.get("show_disk", True),
        )
        self._connect_stats_service()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 8, 14, 8)
        main_layout.setSpacing(2)

        # 标题（Fluent Caption Semibold）
        main_layout.addWidget(Win11Style.widget_title("系统监控"))

        # CPU
        self._cpu_bar = _StatBar("CPU", self.CPU_COLOR, self)
        main_layout.addWidget(self._cpu_bar)

        # 内存
        self._mem_bar = _StatBar("内存", self.MEM_COLOR, self)
        main_layout.addWidget(self._mem_bar)

        # 磁盘
        self._disk_bar = _StatBar("磁盘", self.DISK_COLOR, self)
        main_layout.addWidget(self._disk_bar)

    def _apply_visibility(self, show_cpu: bool, show_mem: bool, show_disk: bool) -> None:
        """按设置显示/隐藏各指标行"""
        self._cpu_bar.setVisible(show_cpu)
        self._mem_bar.setVisible(show_mem)
        self._disk_bar.setVisible(show_disk)

    def _connect_stats_service(self) -> None:
        """订阅后台采样服务（psutil 不再占用 UI 线程）"""
        from app.services.system_stats_service import get_system_stats_service
        self._stats_svc = get_system_stats_service()
        self._stats_svc.system_stats.connect(self._on_stats)
        self._stats_svc.acquire_system()

    def _on_stats(self, s: dict) -> None:
        freq_str = (f"{s['cpu_ghz']:.1f} GHz" if s["cpu_ghz"] > 0 else "") \
            if self._show_cpu_freq else ""
        self._cpu_bar.set_value(s["cpu"] / 100, sub_text=freq_str)
        self._mem_bar.set_value(s["mem_percent"] / 100,
                                f"{s['mem_used_gb']:.1f}/{s['mem_total_gb']:.0f} GB")
        self._disk_bar.set_value(s["disk_percent"] / 100,
                                 f"{s['disk_used_gb']:.0f}/{s['disk_total_gb']:.0f} GB")

    def on_settings_changed(self, settings: dict) -> None:
        if "show_cpu_freq" in settings:
            self._show_cpu_freq = bool(settings["show_cpu_freq"])
        self._apply_visibility(
            show_cpu=settings.get("show_cpu", True),
            show_mem=settings.get("show_mem", True),
            show_disk=settings.get("show_disk", True),
        )

    def on_close(self) -> None:
        try:
            self._stats_svc.system_stats.disconnect(self._on_stats)
            self._stats_svc.release_system()
        except Exception:
            pass
