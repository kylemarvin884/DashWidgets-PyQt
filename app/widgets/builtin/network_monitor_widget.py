"""网络监控小组件 — Win11 风格"""
from __future__ import annotations
import psutil

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QLinearGradient, QPainterPath, QRadialGradient, QFontMetrics
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class SpeedIndicator(QWidget):
    """速度指示器（主题感知）"""
    def __init__(self, direction: str, parent=None):
        super().__init__(parent)
        self._dir = direction
        self._speed = 0.0
        self._speed_text = "0 KB/s"
        self.setFixedHeight(40)
        self.setStyleSheet("background: transparent;")

    def set_speed(self, bytes_per_sec: float) -> None:
        self._speed = bytes_per_sec
        if bytes_per_sec < 1024:
            self._speed_text = f"{int(bytes_per_sec)} B/s"
        elif bytes_per_sec < 1024 * 1024:
            self._speed_text = f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            self._speed_text = f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = Win11Style.widget_colors()
        w, h = self.width(), self.height()

        # 箭头图标区域（左侧）
        icon_cx, icon_cy = 16, h // 2

        arrow_color = QColor(c["accent"]) if self._dir == "up" else QColor(100, 220, 150)

        grad = QRadialGradient(icon_cx, icon_cy, 12)
        grad.setColorAt(0.0, QColor(arrow_color.red(), arrow_color.green(), arrow_color.blue(), 35))
        grad.setColorAt(1.0, QColor(arrow_color.red(), arrow_color.green(), arrow_color.blue(), 8))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(icon_cx, icon_cy), 12, 12)

        p.setBrush(QBrush(arrow_color))
        if self._dir == "up":
            tri = QPainterPath()
            tri.moveTo(icon_cx - 4, icon_cy + 3)
            tri.lineTo(icon_cx + 4, icon_cy + 3)
            tri.lineTo(icon_cx, icon_cy - 5)
            tri.closeSubpath()
            p.drawPath(tri)
            p.drawRect(int(icon_cx - 2), int(icon_cy + 3), 3, 5)
        else:
            tri = QPainterPath()
            tri.moveTo(icon_cx - 4, icon_cy - 3)
            tri.lineTo(icon_cx + 4, icon_cy - 3)
            tri.lineTo(icon_cx, icon_cy + 5)
            tri.closeSubpath()
            p.drawPath(tri)
            p.drawRect(int(icon_cx - 2), int(icon_cy - 8), 3, 5)

        # 文字区域（从 x=36 开始）
        tx = 36

        # 标签行：UP / DN
        label_str = "UP" if self._dir == "up" else "DN"
        label_font = QFont("Segoe UI Variable", 10, QFont.Weight.Normal)
        p.setFont(label_font)
        p.setPen(QColor(c["text_secondary"]))
        p.drawText(QPointF(tx, h // 2 - 6), label_str)

        # 数值行：大号数字 + 单位
        if self._speed < 1024 * 1024:
            num_str = f"{self._speed / 1024:.0f}"
            unit_str = "KB/s"
        else:
            num_str = f"{self._speed / (1024 * 1024):.1f}"
            unit_str = "MB/s"

        speed_font = QFont("Segoe UI Variable", 17, QFont.Weight.Light)
        p.setFont(speed_font)
        p.setPen(QColor(c["text"]))
        p.drawText(QPointF(tx, h // 2 + 14), num_str)

        unit_font = QFont("Segoe UI Variable", 9, QFont.Weight.Light)
        p.setFont(unit_font)
        p.setPen(QColor(c["text_dim"]))
        num_width = QFontMetrics(speed_font).horizontalAdvance(num_str)
        p.drawText(QPointF(tx + num_width + 3, h // 2 + 12), unit_str)

        p.end()


class NetworkMonitorWidget(WidgetBase):
    WIDGET_TYPE = "network_monitor"
    WIDGET_NAME = "网络监控"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._last_bytes_sent = 0
        self._last_bytes_recv = 0
        self._setup_ui()
        self._start_monitoring()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 10)
        main_layout.setSpacing(8)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(20)
        self._upload_indicator = SpeedIndicator("up", self)
        self._download_indicator = SpeedIndicator("down", self)
        speed_row.addWidget(self._upload_indicator, stretch=1)
        speed_row.addWidget(self._download_indicator, stretch=1)
        main_layout.addLayout(speed_row)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {c['separator']};")
        main_layout.addWidget(sep)

        total_font = QFont("Segoe UI Variable", 10, QFont.Weight.ExtraLight)
        up_total_row = QHBoxLayout()
        self._up_total_label = QLabel("↑ 总计: --")
        self._up_total_label.setFont(total_font)
        self._up_total_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        up_total_row.addWidget(self._up_total_label)
        up_total_row.addStretch()
        main_layout.addLayout(up_total_row)

        dn_total_row = QHBoxLayout()
        self._dn_total_label = QLabel("↓ 总计: --")
        self._dn_total_label.setFont(total_font)
        self._dn_total_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        dn_total_row.addWidget(self._dn_total_label)
        dn_total_row.addStretch()
        main_layout.addLayout(dn_total_row)
        main_layout.addStretch()

    def _start_monitoring(self) -> None:
        try:
            net = psutil.net_io_counters()
            self._last_bytes_sent = net.bytes_sent
            self._last_bytes_recv = net.bytes_recv
        except Exception:
            pass
        timer = QTimer(self)
        timer.timeout.connect(self._update_network)
        timer.start(1500)
        self._update_network()

    def _update_network(self) -> None:
        try:
            net = psutil.net_io_counters()
            upload_speed = max(0, net.bytes_sent - self._last_bytes_sent) / 1.5
            download_speed = max(0, net.bytes_recv - self._last_bytes_recv) / 1.5
            self._upload_indicator.set_speed(upload_speed)
            self._download_indicator.set_speed(download_speed)
            sent_gb = net.bytes_sent / (1024 ** 3)
            recv_gb = net.bytes_recv / (1024 ** 3)
            self._up_total_label.setText(f"↑ 总计: {sent_gb:.2f} GB" if sent_gb >= 1 else f"↑ 总计: {net.bytes_sent / (1024**2):.0f} MB")
            self._dn_total_label.setText(f"↓ 总计: {recv_gb:.2f} GB" if recv_gb >= 1 else f"↓ 总计: {net.bytes_recv / (1024**2):.0f} MB")
            self._last_bytes_sent = net.bytes_sent
            self._last_bytes_recv = net.bytes_recv
        except Exception:
            pass
