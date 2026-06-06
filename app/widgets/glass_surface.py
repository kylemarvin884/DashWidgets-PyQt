"""液态玻璃表面渲染组件"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QLinearGradient, QPen, QBrush,
)


# 阴影样式常量
SHADOW_NONE = "none"
SHADOW_SOFT = "soft"
SHADOW_HARD = "hard"
SHADOW_GLOW = "glow"

SHADOW_STYLES = [SHADOW_NONE, SHADOW_SOFT, SHADOW_HARD, SHADOW_GLOW]


class GlassCard(QWidget):
    """
    液态玻璃卡片 — 圆角背景 + 可配置阴影（paintEvent 手绘，无 DWM 伪影）

    可配置属性：
    - color: 背景颜色
    - opacity: 整体不透明度 (0-100)
    - corner_radius: 圆角半径 (px)
    - shadow_style: 阴影样式 none/soft/hard/glow
    - shadow_intensity: 阴影强度 (0-100)
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        radius: int = 20,
        border_width: float = 1.0,
        base_alpha: int = 35,
        highlight_alpha: int = 40,
        border_alpha: int = 50,
    ):
        super().__init__(parent)

        # ── 视觉参数 ──
        self._radius = radius
        self._border_width = border_width
        self._base_alpha = base_alpha
        self._highlight_alpha = highlight_alpha
        self._border_alpha = border_alpha

        # ── 可配置外观参数（默认值）──
        self._color: QColor | None = None          # None = 使用默认深色玻璃
        self._opacity: float = 1.0                  # 窗口级不透明度
        self._corner_radius: int | None = None      # None = 用 _radius
        self._shadow_style: str = SHADOW_SOFT       # none / soft / hard / glow
        self._shadow_intensity: int = 50            # 0-100

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    # ── 公共设置接口 ────────────────────────────────────────── #

    def set_card_color(self, color: QColor) -> None:
        """设置卡片背景颜色"""
        self._color = color
        self.update()

    def set_card_opacity(self, value: float) -> None:
        """设置整体不透明度 0.0~1.0"""
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    def set_corner_radius(self, r: int) -> None:
        """设置圆角半径"""
        self._corner_radius = max(0, r)
        self.update()

    def set_shadow(self, style: str, intensity: int = 50) -> None:
        """设置阴影样式和强度

        style: "none" / "soft" / "hard" / "glow"
        intensity: 0-100
        """
        if style not in SHADOW_STYLES:
            style = SHADOW_SOFT
        self._shadow_style = style
        self._shadow_intensity = max(0, min(100, intensity))
        self.update()

    def apply_appearance(self, settings: dict) -> None:
        """一次性应用所有外观设置

        settings 键：
          - color: "#RRGGBB" 或 QColor 或 tuple(r,g,b,a)
          - opacity: 0.0-1.0 或 0-100
          - corner_radius: int
          - shadow_style: str
          - shadow_intensity: 0-100
        """
        if "color" in settings:
            c = settings["color"]
            if isinstance(c, str):
                self._color = QColor(c) if c else None
            elif isinstance(c, (tuple, list)):
                a = int(c[3]) if len(c) > 3 else 255
                self._color = QColor(int(c[0]), int(c[1]), int(c[2]), a)
            elif isinstance(c, QColor):
                self._color = c

        if "opacity" in settings:
            v = settings["opacity"]
            if v <= 1.0:
                self._opacity = float(v)
            else:
                self._opacity = float(v) / 100.0

        if "corner_radius" in settings:
            self._corner_radius = int(settings["corner_radius"])

        if "shadow_style" in settings:
            s = settings["shadow_style"]
            if s in SHADOW_STYLES:
                self._shadow_style = s

        if "shadow_intensity" in settings:
            self._shadow_intensity = max(0, min(100, int(settings["shadow_intensity"])))

        self.update()

    # ── 绘制 ────────────────────────────────────────────────── #

    @property
    def _effective_radius(self) -> int:
        return self._corner_radius if self._corner_radius is not None else self._radius

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = self._effective_radius
        margin = self._shadow_margin()

        # ── 1. 绘制阴影（在主矩形外部区域）──
        if self._shadow_style != SHADOW_NONE and margin > 0:
            self._draw_shadow(painter, w, h, r, margin)

        # ── 2. 主圆角矩形路径 ──
        rect = QRectF(margin, margin, w - margin * 2, h - margin * 2).adjusted(
            0.5, 0.5, -0.5, -0.5
        )
        path = QPainterPath()
        path.addRoundedRect(rect, r, r)

        # ── 3. 底层填充 ──
        bg_color = self._resolve_bg_color()
        painter.fillPath(path, QBrush(bg_color))

        # ── 4. 顶部折射高光 ──
        if self._highlight_alpha > 0:
            self._draw_highlight(painter, rect, path, r)

        # ── 5. 边缘轮廓 ──
        if self._border_alpha > 0 and self._border_width > 0:
            border_pen = QPen(QColor(255, 255, 255, self._border_alpha))
            border_pen.setWidthF(self._border_width)
            painter.setPen(border_pen)
            painter.drawPath(path)

        # ── 6. 底部暗边（增加厚度感）──
        bottom_grad = QLinearGradient(0, rect.center().y(), 0, rect.bottom())
        bottom_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        bottom_grad.setColorAt(1.0, QColor(0, 0, 0, 20))
        painter.fillPath(path, bottom_grad)

        painter.end()

    # ── 内部绘制方法 ──────────────────────────────────────── #

    def _resolve_bg_color(self) -> QColor:
        """解析实际背景颜色"""
        if self._color is not None:
            c = self._color
            alpha = int(c.alpha() * self._opacity)
            return QColor(c.red(), c.green(), c.blue(), alpha)

        # 默认深色玻璃基底，受透明度影响
        base_a = int(self._base_alpha * self._opacity)
        return QColor(12, 12, 18, base_a)

    def _shadow_margin(self) -> int:
        """根据阴影样式和强度计算外边距"""
        if self._shadow_style == SHADOW_NONE:
            return 0
        intensity = self._shadow_intensity / 100.0

        if self._shadow_style == SHADOW_GLOW:
            return int(8 + 16 * intensity)
        elif self._shadow_style == SHADOW_HARD:
            return int(4 + 8 * intensity)
        else:  # SOFT
            return int(6 + 18 * intensity)

    def _draw_shadow(
        self, painter: QPainter, w: int, h: int, r: int, margin: int
    ) -> None:
        """手绘投影效果"""
        intensity = self._shadow_intensity / 100.0

        if self._shadow_style == SHADOW_SOFT:
            # 柔和扩散阴影 — 多层半透明叠加模拟高斯模糊
            layers = 5
            for i in range(layers, 0, -1):
                layer_margin = margin - (margin * i // (layers + 1))
                layer_alpha = int((intensity * 30) * ((layers - i + 1) / layers))
                layer_r = max(r, r + (i * 2))
                s_rect = QRectF(
                    margin - layer_margin,
                    margin - layer_margin,
                    w - 2 * (margin - layer_margin),
                    h - 2 * (margin - layer_margin),
                )
                s_path = QPainterPath()
                s_path.addRoundedRect(s_rect, layer_r, layer_r)
                painter.fillPath(s_path, QBrush(QColor(0, 0, 0, layer_alpha)))

        elif self._shadow_style == SHADOW_HARD:
            # 硬边缘偏移阴影
            hard_alpha = int(intensity * 80)
            offset = int(3 + 4 * intensity)
            s_rect = QRectF(
                margin + offset,
                margin + offset,
                w - 2 * margin,
                h - 2 * margin,
            )
            s_path = QPainterPath()
            s_path.addRoundedRect(s_rect, r, r)
            painter.fillPath(s_path, QBrush(QColor(0, 0, 0, hard_alpha)))

        elif self._shadow_style == SHADOW_GLOW:
            # 发光效果（向外扩散的柔和光晕）
            glow_layers = 6
            for i in range(glow_layers, 0, -1):
                t = i / glow_layers
                layer_margin = int(margin * t * 0.7)
                layer_alpha = int(intensity * 25 * (1 - t * 0.6))
                layer_r = max(r, r + int(i * 3))
                s_rect = QRectF(
                    margin - layer_margin,
                    margin - layer_margin,
                    w - 2 * (margin - layer_margin),
                    h - 2 * (margin - layer_margin),
                )
                s_path = QPainterPath()
                s_path.addRoundedRect(s_rect, layer_r, layer_r)
                # 发光色使用微蓝色调
                painter.fillPath(
                    s_path, QBrush(QColor(100, 140, 200, layer_alpha))
                )

    def _draw_highlight(
        self, painter: QPainter, rect: QRectF, path: QPainterPath, r: int
    ) -> None:
        """顶部折射高光"""
        highlight_rect = QRectF(rect)
        highlight_rect.setHeight(rect.height() * 0.55)
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(highlight_rect, r, r)
        highlight_path = highlight_path.intersected(path)

        ha = int(self._highlight_alpha * self._opacity)
        grad = QLinearGradient(0, rect.top(), 0, highlight_rect.bottom())
        grad.setColorAt(0.0, QColor(255, 255, 255, ha))
        grad.setColorAt(0.6, QColor(255, 255, 255, int(ha * 0.3)))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(highlight_path, grad)


class GlassPanel(QWidget):
    """内部玻璃面板 — 比 GlassCard 更轻量，用于内容分区"""

    def __init__(self, parent: QWidget | None = None, radius: int = 12):
        super().__init__(parent)
        self._radius = radius

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        # 极淡填充
        painter.fillPath(path, QColor(255, 255, 255, 8))

        # 微边框
        pen = QPen(QColor(255, 255, 255, 20))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.end()
