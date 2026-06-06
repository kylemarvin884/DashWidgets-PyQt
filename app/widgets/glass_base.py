"""
液态玻璃窗口基类 - Windows 11 亚克力/毛玻璃效果

提供原生级别的 Win11 液态玻璃质感：
- 高斯模糊背景
- 冷调半透明蒙版
- 超大圆角
- 微弱弥散阴影
"""
from __future__ import annotations

import platform
from typing import Optional

from PySide6.QtCore import (
    Qt, QRect, QRectF, QPoint, QSize, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QBrush, QPen, QLinearGradient,
    QFont,
)
from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import QTimer

from qfluentwidgets import isDarkTheme

from app.widgets.glass_surface import SHADOW_NONE, SHADOW_SOFT, SHADOW_HARD, SHADOW_GLOW, SHADOW_STYLES


# ── 配色方案 ──────────────────────────────────────────────── #

class GlassTheme:
    """Win11 液态玻璃配色"""

    # 浅色主题
    LIGHT = {
        # 玻璃基底：冷调灰蓝半透明
        "glass_bg": QColor(243, 243, 243, 200),
        "glass_tint": QColor(255, 255, 255, 180),
        "glass_border": QColor(255, 255, 255, 120),
        # 文字
        "text_primary": QColor(30, 30, 30, 230),
        "text_secondary": QColor(80, 80, 80, 160),
        # 阴影
        "shadow_color": QColor(0, 0, 0, 25),
    }

    # 深色主题
    DARK = {
        "glass_bg": QColor(32, 32, 32, 200),
        "glass_tint": QColor(50, 50, 50, 160),
        "glass_border": QColor(255, 255, 255, 40),
        # 文字
        "text_primary": QColor(255, 255, 255, 240),
        "text_secondary": QColor(180, 180, 180, 150),
        # 阴影
        "shadow_color": QColor(0, 0, 0, 60),
    }

    @classmethod
    def current(cls) -> dict:
        return cls.DARK if isDarkTheme() else cls.LIGHT




class GlassButton(QPushButton):
    """迷你玻璃按钮 — 共享组件，供所有 GlassWindow 子类使用"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._theme = GlassTheme.current()
        self.setFixedSize(64, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self) -> None:
        theme = self._theme
        is_dark = theme == GlassTheme.DARK
        if is_dark:
            bg = "rgba(255, 255, 255, 12)"
            bg_hover = "rgba(255, 255, 255, 20)"
            border = "rgba(255, 255, 255, 25)"
            text_color = "rgba(255, 255, 255, 200)"
            text_hover = "rgba(255, 255, 255, 240)"
        else:
            bg = "rgba(0, 0, 0, 6)"
            bg_hover = "rgba(0, 0, 0, 12)"
            border = "rgba(0, 0, 0, 10)"
            text_color = "rgba(30, 30, 30, 180)"
            text_hover = "rgba(30, 30, 30, 220)"

        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg}; color: {text_color};
                border: 1px solid {border}; border-radius: 8px;
                font-size: 12px; font-family: "Segoe UI Variable";
                padding: 4px 8px;
            }}
            QPushButton:hover {{ background: {bg_hover}; color: {text_hover};
                border: 1px solid rgba(255, 255, 255, 40); }}
            QPushButton:pressed {{ background: rgba(255, 255, 255, 15); }}
            QPushButton:disabled {{
                background: rgba(128, 128, 128, 20); color: rgba(128, 128, 128, 80);
                border: 1px solid rgba(128, 128, 128, 15); }}
        """)


class GlassWindow(QWidget):
    """
    液态玻璃窗口基类

    特性：
    - 无边框、置顶、工具窗口
    - Win11 超大圆角 (16px)
    - 亚克力毛玻璃背景效果
    - 微弱弥散阴影
    - 支持拖拽移动
    """

    # 圆角半径（可运行时覆盖）
    CORNER_RADIUS = 18

    # 边框宽度
    BORDER_WIDTH = 1

    # ── 可配置外观参数 ──
    _custom_color: QColor | None = None
    _custom_opacity: float | None = None  # None = 未手动设置

    def __init__(
        self,
        size: tuple[int, int] = (280, 160),
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._size = size
        self._drag_pos: Optional[QPoint] = None
        self._theme = GlassTheme.current()

        # 阴影参数
        self._shadow_style = SHADOW_SOFT
        self._shadow_intensity = 40

        # ── 窗口属性 ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        # 固定尺寸
        self.setFixedSize(size[0], size[1])

        # 启用鼠标追踪（用于悬停效果）
        self.setMouseTracking(True)

        # 定时器管理
        self._timers: list[QTimer] = []

    # ── 绘制 ──────────────────────────────────────────────── #

    def paintEvent(self, event):
        """绘制液态玻璃背景"""
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )

        w, h = self.width(), self.height()
        r = self.CORNER_RADIUS

        # ── 阴影层（在主路径外部）──
        if self._shadow_style != SHADOW_NONE:
            self._paint_shadow(painter, w, h, r)

        # 创建圆角裁剪路径
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        painter.setClipPath(path)

        # ── 1. 绘制玻璃背景（线性渐变模拟亚克力）──
        bg = self._resolve_glass_bg()
        tint = self._resolve_glass_tint()

        glass_gradient = QLinearGradient(0, 0, 0, h)
        glass_gradient.setColorAt(0.0, tint)
        glass_gradient.setColorAt(0.5, bg)
        glass_gradient.setColorAt(1.0, QColor(bg.red(), bg.green(), bg.blue(), int(bg.alpha() * 0.85)))

        painter.fillPath(path, QBrush(glass_gradient))

        # ── 2. 绘制顶部高光（同一路径，仅限上半区）──
        highlight = QLinearGradient(0, 0, 0, h * 0.4)
        highlight.setColorAt(0.0, QColor(255, 255, 255, 25 if isDarkTheme() else 40))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.45), QBrush(highlight))

        # 取消裁剪，准备绘制边框
        painter.setClipPath(QPainterPath())

        # ── 3. 绘制边框（沿原始圆角路径描边）──
        border_pen = QPen(self._theme["glass_border"])
        border_pen.setWidthF(self.BORDER_WIDTH)
        painter.strokePath(path, border_pen)

        painter.end()

    def _resolve_glass_bg(self) -> QColor:
        """解析实际玻璃背景色"""
        if self._custom_color:
            c = self._custom_color
            opacity = self._custom_opacity if self._custom_opacity is not None else (c.alpha() / 255.0)
            return QColor(c.red(), c.green(), c.blue(), int(c.alpha() * opacity))
        return self._theme["glass_bg"]

    def _resolve_glass_tint(self) -> QColor:
        """解析玻璃色调"""
        if self._custom_color:
            c = self._custom_color
            return QColor(
                min(255, c.red() + 20),
                min(255, c.green() + 20),
                min(255, c.blue() + 20),
                int(c.alpha() * 0.8),
            )
        return self._theme["glass_tint"]

    def _paint_shadow(self, painter: QPainter, w: int, h: int, r: int) -> None:
        """手绘阴影（与 GlassCard 同风格）"""
        intensity = self._shadow_intensity / 100.0

        if self._shadow_style == SHADOW_SOFT:
            layers = 4
            for i in range(layers, 0, -1):
                t = i / layers
                alpha = int(intensity * 22 * t)
                offset = int((layers - i + 1) * 3 * intensity)
                s_path = QPainterPath()
                s_path.addRoundedRect(
                    QRectF(offset, offset, w + offset, h + offset).adjusted(-0.5, -0.5, 0.5, 0.5),
                    max(r, r + i), max(r, r + i),
                )
                painter.fillPath(s_path, QBrush(QColor(0, 0, 0, alpha)))
        elif self._shadow_style == SHADOW_HARD:
            alpha = int(intensity * 60)
            off = int(3 + 4 * intensity)
            s_path = QPainterPath()
            s_path.addRoundedRect(QRectF(off, off, w, h), r, r)
            painter.fillPath(s_path, QBrush(QColor(0, 0, 0, alpha)))
        elif self._shadow_style == SHADOW_GLOW:
            glow_layers = 5
            for i in range(glow_layers, 0, -1):
                t = i / glow_layers
                alpha = int(intensity * 18 * (1 - t * 0.5))
                margin = int(i * 4 * intensity)
                s_path = QPainterPath()
                s_path.addRoundedRect(
                    QRectF(-margin, -margin, w + margin * 2, h + margin * 2),
                    max(r, r + i * 2), max(r, r + i * 2),
                )
                painter.fillPath(s_path, QBrush(QColor(100, 140, 200, alpha)))

    # ── 鼠标事件（支持拖拽）───────────────────────────────── #

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── 主题更新 ──────────────────────────────────────────── #

    def update_theme(self):
        """更新主题配色"""
        self._theme = GlassTheme.current()
        self.update()

    # ── 设置应用 ──────────────────────────────────────────── #

    def apply_settings(self, settings: dict) -> None:
        """应用设置变更（子类可重写以处理特定设置项）

        支持的键：
          - opacity: 0.0-1.0 或 0-100
          - border_radius: int (px)
          - color: QColor / "#RRGGBB" / tuple(r,g,b,a)
          - shadow_style: "none" | "soft" | "hard" | "glow"
          - shadow_intensity: 0-100
        """
        if not settings:
            return

        # 透明度
        opacity = settings.get("opacity")
        if opacity is not None:
            v = float(opacity)
            if v <= 1.5:  # 支持 0.0-1.0 和百分比两种写法
                self._custom_opacity = v if v <= 1.0 else v / 100.0
                self.setWindowOpacity(self._custom_opacity)
            else:
                self._custom_opacity = v / 100.0
                self.setWindowOpacity(self._custom_opacity)

        # 圆角
        border_radius = settings.get("border_radius")
        if border_radius is not None:
            self.CORNER_RADIUS = int(border_radius)
            self.update()

        # 自定义颜色
        color_val = settings.get("color")
        if color_val is not None:
            if isinstance(color_val, str):
                c = QColor(color_val)
                if c.isValid():
                    self._custom_color = c
            elif isinstance(color_val, (tuple, list)):
                a = int(color_val[3]) if len(color_val) > 3 else 255
                self._custom_color = QColor(int(color_val[0]), int(color_val[1]), int(color_val[2]), a)
            elif isinstance(color_val, QColor):
                self._custom_color = color_val

        # 阴影样式
        ss = settings.get("shadow_style")
        if ss in SHADOW_STYLES:
            self._shadow_style = ss

        si = settings.get("shadow_intensity")
        if si is not None:
            self._shadow_intensity = max(0, min(100, int(si)))

        self.update()

    def on_settings_changed(self, settings: dict) -> None:
        """设置变更回调（别名，与 WidgetBase 接口对齐）"""
        self.apply_settings(settings)

    # ── 定时器管理 ──────────────────────────────────────────── #

    def start_timer(self, interval_ms: int, callback) -> None:
        """注册一个定时器（统一接口，子类无需各自实现）"""
        t = QTimer(self)
        t.timeout.connect(callback)
        t.start(interval_ms)
        self._timers.append(t)

    def stop_all_timers(self) -> None:
        """停止所有通过 start_timer 注册的定时器"""
        for t in self._timers:
            t.stop()
        self._timers.clear()

    # ── 动画效果 ──────────────────────────────────────────── #

    def fade_in(self, duration: int = 300):
        """淡入动画"""
        self.setWindowOpacity(0)
        self.show()

        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

    def fade_out(self, duration: int = 200):
        """淡出动画"""
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self.close)
        anim.start()




