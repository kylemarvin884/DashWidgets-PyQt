"""天气小组件 — Win11 风格，自动获取真实天气（网络请求在工作线程执行）"""
from __future__ import annotations
import math

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QRadialGradient, QPainterPath,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style
from app.utils.async_fetch import run_in_background

# 服务 icon → 图标组件类型 映射
_ICON_MAP = {
    "SUNNY": "sunny",
    "PARTLY_SUNNY": "sunny",
    "CLOUD": "cloudy",
    "RAIN": "rainy",
    "SNOW": "cloudy",
    "FOG": "cloudy",
    "THUNDER": "rainy",
}


class WeatherIconWidget(QWidget):
    """手绘天气图标（保持彩色，不依赖主题）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self.setStyleSheet("background: transparent;")
        self._weather_type = "sunny"

    def set_weather(self, weather_type: str) -> None:
        self._weather_type = weather_type
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._weather_type == "sunny":
            self._draw_sunny(p)
        elif self._weather_type == "cloudy":
            self._draw_cloudy(p)
        elif self._weather_type == "rainy":
            self._draw_rainy(p)
        else:
            self._draw_sunny(p)
        p.end()

    def _draw_sunny(self, p: QPainter):
        cx, cy = 28, 30
        grad = QRadialGradient(cx, cy - 2, 16)
        grad.setColorAt(0.0, QColor(255, 230, 120))
        grad.setColorAt(0.7, QColor(255, 190, 60))
        grad.setColorAt(1.0, QColor(255, 170, 40, 100))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy - 2), 15, 15)
        pen = QPen(QColor(255, 200, 60, 200), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for angle in range(45, 360, 45):
            rad = math.radians(angle)
            x1 = cx + 19 * math.cos(rad)
            y1 = (cy - 2) + 19 * math.sin(rad)
            x2 = cx + 25 * math.cos(rad)
            y2 = (cy - 2) + 25 * math.sin(rad)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_cloudy(self, p: QPainter):
        cx, cy = 28, 32
        grad = QRadialGradient(cx + 10, cy - 8, 12)
        grad.setColorAt(0.0, QColor(255, 230, 120))
        grad.setColorAt(1.0, QColor(255, 190, 60, 80))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx + 10, cy - 8), 11, 11)
        cloud_path = QPainterPath()
        cloud_path.addEllipse(QPointF(cx - 12, cy + 2), 12, 9)
        cloud_path.addEllipse(QPointF(cx + 2, cy - 2), 14, 11)
        cloud_path.addEllipse(QPointF(cx + 14, cy + 3), 10, 8)
        c_grad = QRadialGradient(cx, cy - 2, 22)
        c_grad.setColorAt(0.0, QColor(240, 245, 250, 245))
        c_grad.setColorAt(1.0, QColor(210, 220, 235, 200))
        p.setBrush(QBrush(c_grad))
        p.drawPath(cloud_path)

    def _draw_rainy(self, p: QPainter):
        cx, cy = 28, 26
        cloud_path = QPainterPath()
        cloud_path.addEllipse(QPointF(cx - 12, cy), 12, 9)
        cloud_path.addEllipse(QPointF(cx + 2, cy - 4), 14, 11)
        cloud_path.addEllipse(QPointF(cx + 14, cy + 1), 10, 8)
        c_grad = QRadialGradient(cx, cy - 4, 22)
        c_grad.setColorAt(0.0, QColor(200, 210, 225, 245))
        c_grad.setColorAt(1.0, QColor(170, 180, 200, 200))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c_grad))
        p.drawPath(cloud_path)
        rain_pen = QPen(QColor(140, 180, 220, 180), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(rain_pen)
        for dx, dy in [(-10, 16), (-3, 20), (5, 17), (12, 21)]:
            p.drawLine(QPointF(cx + dx, cy + dy), QPointF(cx + dx - 2, cy + dy + 6))


class WeatherWidget(WidgetBase):
    WIDGET_TYPE = "weather"
    WIDGET_NAME = "天气"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._fetching = False
        self._task = None  # 持有后台任务信号对象，防止被 GC
        self._show_detail = bool(config.settings.get("show_detail", True))
        self._setup_ui()
        self._apply_detail_visibility()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30 * 60 * 1000)  # 30分钟
        self._refresh_timer.timeout.connect(self._fetch_weather)
        self._fetch_weather()
        self._refresh_timer.start()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(14)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = WeatherIconWidget(self)
        main_layout.addWidget(self._icon)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._desc_label = QLabel("晴")
        self._desc_label.setFont(QFont("Segoe UI Variable", 16, QFont.Weight.Light))
        self._desc_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        info_col.addWidget(self._desc_label)

        self._temp_label = QLabel("22℃")
        self._temp_label.setFont(QFont("Segoe UI Variable", 13, QFont.Weight.ExtraLight))
        self._temp_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        info_col.addWidget(self._temp_label)

        self._detail_label = QLabel("湿度 -- · 风 --")
        self._detail_label.setFont(QFont("Segoe UI Variable", 9, QFont.Weight.Light))
        self._detail_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        info_col.addWidget(self._detail_label)

        main_layout.addLayout(info_col)
        main_layout.addStretch()

    def _apply_detail_visibility(self) -> None:
        self._detail_label.setVisible(self._show_detail)

    def _fetch_weather(self) -> None:
        """在工作线程获取天气数据（服务内部有缓存与并发去重）"""
        if self._fetching:
            return
        self._fetching = True

        def _work():
            from app.services.weather_service import get_weather_service
            try:
                return get_weather_service().get_weather()
            except Exception:
                return None

        self._task = run_in_background(_work, self._on_weather)

    def _on_weather(self, data) -> None:
        """工作线程结果回传（UI 线程执行）"""
        self._fetching = False
        if data:
            wtype = _ICON_MAP.get(data.icon, "sunny")
            self._icon.set_weather(wtype)
            self._desc_label.setText(data.condition)
            self._temp_label.setText(f"{data.temperature:.0f}℃")
            self._detail_label.setText(
                f"湿度 {data.humidity}% · 风 {data.wind_speed:.0f} km/h"
            )
        else:
            self._desc_label.setText("获取失败")
            self._temp_label.setText("--℃")

    def on_settings_changed(self, settings: dict) -> None:
        if "show_detail" in settings:
            self._show_detail = bool(settings["show_detail"])
            self._apply_detail_visibility()

    def apply_settings(self, settings: dict) -> None:
        if "weather" in settings:
            self._icon.set_weather(settings["weather"])
            self._desc_label.setText(settings.get("desc", ""))
            self._temp_label.setText(settings.get("temp", ""))
