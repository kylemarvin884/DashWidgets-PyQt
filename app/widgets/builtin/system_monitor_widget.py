"""系统监控小组件 — Win11 风格（主题感知颜色）"""
from __future__ import annotations

import psutil

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QConicalGradient, QBrush,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import FluentIcon as FIF, IconWidget

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class RingIndicator(QWidget):
    """圆环进度指示器"""

    def __init__(self, label: str, color: QColor, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0
        self._sub_text = ""
        self.setFixedSize(100, 120)
        self.setStyleSheet("background: transparent;")

    def set_value(self, value: float, sub_text: str = "") -> None:
        self._value = max(0.0, min(1.0, value))
        self._sub_text = sub_text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        c = Win11Style.widget_colors()
        cx = 50
        cy = 42
        r = 34

        # 背景环（淡色细线）
        track_color = QColor(c["border_input"])
        track_color.setAlpha(50)
        bg_pen = QPen(track_color, 3)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(bg_pen)
        p.drawEllipse(QPointF(cx, cy), float(r), float(r))

        # 进度弧
        if self._value > 0.001:
            span_angle = int(-self._value * 360 * 16)
            grad = QConicalGradient(cx, cy, 90)
            grad.setColorAt(0.0, self._color)
            grad.setColorAt(1.0, QColor(self._color.red(), self._color.green(), self._color.blue(), 120))
            fg_pen = QPen(QBrush(grad), 4)
            fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(fg_pen)
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            p.drawArc(rect, 90 * 16, span_angle)

        # 百分比数字
        text_color = QColor(c["text"])
        num_font = QFont("Segoe UI Variable", 15, QFont.Weight.DemiBold)
        p.setFont(num_font)
        p.setPen(text_color)
        pct_str = f"{int(self._value * 100)}%"
        p.drawText(QRectF(cx - 32, cy - 11, 64, 22), Qt.AlignmentFlag.AlignCenter, pct_str)

        # 标签
        label_color = QColor(c["text_secondary"])
        label_font = QFont("Segoe UI Variable", 9, QFont.Weight.Normal)
        p.setFont(label_font)
        p.setPen(label_color)
        p.drawText(QRectF(cx - 26, cy + 12, 52, 14), Qt.AlignmentFlag.AlignCenter, self._label)

        # 副文本
        if self._sub_text:
            sub_color = QColor(c["accent"])
            sub_font = QFont("Segoe UI Variable", 8, QFont.Weight.Light)
            p.setFont(sub_font)
            p.setPen(sub_color)
            p.drawText(QRectF(cx - 40, cy + 28, 80, 14), Qt.AlignmentFlag.AlignCenter, self._sub_text)

        p.end()


class SystemMonitorWidget(WidgetBase):
    WIDGET_TYPE = "system_monitor"
    WIDGET_NAME = "系统监控"
    CPU_COLOR = QColor(80, 200, 255)
    MEM_COLOR = QColor(120, 220, 160)

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._setup_ui()
        self._start_timers()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 8, 14, 6)
        main_layout.setSpacing(4)

        # 标题栏
        header = QHBoxLayout()
        header.setSpacing(8)
        icon = IconWidget(FIF.APPLICATION, self)
        icon.setFixedSize(18, 18)
        header.addWidget(icon)
        title_label = QLabel("系统监控")
        title_label.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Medium))
        title_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        header.addWidget(title_label)
        header.addStretch()
        main_layout.addLayout(header)

        # 圆环区域
        ring_row = QHBoxLayout()
        ring_row.setSpacing(20)
        ring_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cpu_ring = RingIndicator("CPU", self.CPU_COLOR, self)
        self._mem_ring = RingIndicator("MEM", self.MEM_COLOR, self)
        ring_row.addWidget(self._cpu_ring)
        ring_row.addWidget(self._mem_ring)
        main_layout.addLayout(ring_row)

    def _start_timers(self) -> None:
        timer = QTimer(self)
        timer.timeout.connect(self._update_stats)
        timer.start(2000)
        self._update_stats()

    def _update_stats(self) -> None:
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()

            cpu_freq = psutil.cpu_freq()
            freq_str = f"{cpu_freq.current:.1f}GHz" if cpu_freq else ""
            mem_str = f"{mem.used / 1024**3:.1f}G/{mem.total / 1024**3:.0f}G"

            self._cpu_ring.set_value(cpu_pct / 100.0, sub_text=freq_str)
            self._mem_ring.set_value(mem.percent / 100.0, sub_text=mem_str)
        except Exception:
            pass
