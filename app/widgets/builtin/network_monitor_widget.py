"""网络监控小组件 — Win11 风格（指标由后台采样服务推送）"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QRadialGradient, QFontMetrics,
)
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
        # 字体/路径只建一次，避免每次 paint 重复分配
        self._label_font = QFont("Segoe UI Variable", 9, QFont.Weight.Normal)
        self._speed_font = QFont("Segoe UI Variable", 14, QFont.Weight.Light)
        self._unit_font = QFont("Segoe UI Variable", 9, QFont.Weight.Light)

        self._up_tri = QPainterPath()
        self._up_tri.moveTo(-4, 3)
        self._up_tri.lineTo(4, 3)
        self._up_tri.lineTo(0, -5)
        self._up_tri.closeSubpath()
        self._dn_tri = QPainterPath()
        self._dn_tri.moveTo(-4, -3)
        self._dn_tri.lineTo(4, -3)
        self._dn_tri.lineTo(0, 5)
        self._dn_tri.closeSubpath()

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
        p.save()
        p.translate(icon_cx, icon_cy)
        if self._dir == "up":
            p.drawPath(self._up_tri)
            p.drawRect(-2, 3, 3, 5)
        else:
            p.drawPath(self._dn_tri)
            p.drawRect(-2, -8, 3, 5)
        p.restore()

        # 文字区域（从 x=30 开始，留更多右侧空间）
        tx = 30

        # 标签行：UP / DN
        p.setFont(self._label_font)
        p.setPen(QColor(c["text_secondary"]))
        p.drawText(QPointF(tx, h // 2 - 6), "UP" if self._dir == "up" else "DN")

        # 数值行：数字 + 单位（缩小字体避免小数部分被裁剪）
        if self._speed < 1024 * 1024:
            num_str = f"{self._speed / 1024:.0f}"
            unit_str = "KB/s"
        else:
            num_str = f"{self._speed / (1024 * 1024):.1f}"
            unit_str = "MB/s"

        p.setFont(self._speed_font)
        p.setPen(QColor(c["text"]))
        num_width = QFontMetrics(self._speed_font).horizontalAdvance(num_str)
        p.drawText(QPointF(tx, h // 2 + 12), num_str)

        p.setFont(self._unit_font)
        p.setPen(QColor(c["text_dim"]))
        p.drawText(QPointF(tx + num_width + 3, h // 2 + 11), unit_str)

        p.end()


class NetworkMonitorWidget(WidgetBase):
    WIDGET_TYPE = "network_monitor"
    WIDGET_NAME = "网络监控"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._setup_ui()
        self._apply_visibility(bool(config.settings.get("show_totals", True)))
        self._connect_stats_service()

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
        self._separator = sep

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

    def _apply_visibility(self, show_totals: bool) -> None:
        """按设置显示/隐藏累计流量区"""
        self._separator.setVisible(show_totals)
        self._up_total_label.setVisible(show_totals)
        self._dn_total_label.setVisible(show_totals)

    def _connect_stats_service(self) -> None:
        """订阅后台采样服务（psutil 不再占用 UI 线程）"""
        from app.services.system_stats_service import get_system_stats_service
        self._stats_svc = get_system_stats_service()
        self._stats_svc.network_stats.connect(self._on_stats)
        self._stats_svc.acquire_network()

    def _on_stats(self, s: dict) -> None:
        self._upload_indicator.set_speed(s["up_bps"])
        self._download_indicator.set_speed(s["down_bps"])

        sent_gb = s["sent_bytes"] / (1024 ** 3)
        recv_gb = s["recv_bytes"] / (1024 ** 3)
        self._up_total_label.setText(
            f"↑ 总计: {sent_gb:.2f} GB" if sent_gb >= 1
            else f"↑ 总计: {s['sent_bytes'] / (1024 ** 2):.0f} MB"
        )
        self._dn_total_label.setText(
            f"↓ 总计: {recv_gb:.2f} GB" if recv_gb >= 1
            else f"↓ 总计: {s['recv_bytes'] / (1024 ** 2):.0f} MB"
        )

    def on_settings_changed(self, settings: dict) -> None:
        if "show_totals" in settings:
            self._apply_visibility(bool(settings["show_totals"]))

    def on_close(self) -> None:
        try:
            self._stats_svc.network_stats.disconnect(self._on_stats)
            self._stats_svc.release_network()
        except Exception:
            pass
