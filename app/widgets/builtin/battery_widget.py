"""电池小组件 — Win11 风格，环形电量指示（笔记本）"""
from __future__ import annotations
import math

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style

_POLL_MS = 30_000  # 电量变化缓慢，30 秒轮询足够


class _BatteryRing(QWidget):
    """手绘环形电量指示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(72, 72)
        self.setStyleSheet("background: transparent;")
        self._percent: float | None = None
        self._plugged = False

    def set_battery(self, percent: float | None, plugged: bool):
        self._percent = percent
        self._plugged = plugged
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = Win11Style.widget_colors()

        rect = QRectF(10, 10, 52, 52)
        # 背景轨道
        track_pen = QPen(QColor(c["track"]), 6)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.drawArc(rect, 0, 360 * 16)

        if self._percent is not None:
            # 电量弧：低电量红色 / 充电黄色 / 正常绿色
            pct = max(0.0, min(100.0, self._percent))
            if pct <= 20 and not self._plugged:
                color = QColor("#e74856")
            elif self._plugged:
                color = QColor("#d4a017")
            else:
                color = QColor("#5db872")
            arc_pen = QPen(color, 6)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(arc_pen)
            span = int(-360 * 16 * pct / 100)
            p.drawArc(rect, 90 * 16, span)

            # 中心数字
            p.setPen(QColor(c["text"]))
            p.setFont(QFont("Segoe UI Variable", 15, QFont.Weight.Light))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{int(pct)}%")
        else:
            p.setPen(QColor(c["text_secondary"]))
            p.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Light))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "无电池")

        # 充电闪电标记
        if self._plugged and self._percent is not None:
            bolt = QPainterPath(QPointF(58, 16))
            bolt.lineTo(53, 26)
            bolt.lineTo(57, 26)
            bolt.lineTo(52, 36)
            bolt.lineTo(60, 24)
            bolt.lineTo(56, 24)
            bolt.lineTo(61, 16)
            bolt.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#d4a017"))
            p.drawPath(bolt)
        p.end()


class BatteryWidget(WidgetBase):
    WIDGET_TYPE = "battery"
    WIDGET_NAME = "电池"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._show_time = bool(config.settings.get("show_time", True))
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._refresh)
        self._refresh()
        self._timer.start()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 10)
        main_layout.setSpacing(4)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._ring = _BatteryRing(self)
        main_layout.addWidget(self._ring, alignment=Qt.AlignmentFlag.AlignCenter)

        row = QHBoxLayout()
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label = QLabel("读取中…")
        self._status_label.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Light))
        self._status_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        row.addWidget(self._status_label)
        main_layout.addLayout(row)
        main_layout.addStretch()

    def _refresh(self) -> None:
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                self._ring.set_battery(None, False)
                self._status_label.setText("未检测到电池")
                self._timer.stop()  # 台式机：不必继续轮询
                return
            plugged = bool(getattr(battery, "power_plugged", False))
            self._ring.set_battery(float(battery.percent), plugged)
            if plugged:
                self._status_label.setText("充电中")
            elif not self._show_time:
                self._status_label.setText("使用电池")
            else:
                # 估算剩余时间
                secs = getattr(battery, "secsleft", None)
                if secs and 0 < secs < 86400 * 7:
                    hours = secs // 3600
                    mins = (secs % 3600) // 60
                    self._status_label.setText(f"剩余 {hours}:{mins:02d}")
                else:
                    self._status_label.setText("使用电池")
        except Exception:
            self._ring.set_battery(None, False)
            self._status_label.setText("读取失败")

    def on_close(self) -> None:
        self._timer.stop()

    def on_settings_changed(self, settings: dict) -> None:
        if "show_time" in settings:
            self._show_time = bool(settings["show_time"])
            self._refresh()

    def apply_settings(self, settings: dict) -> None:
        pass
