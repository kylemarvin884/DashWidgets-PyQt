"""自定义 Toast 通知系统

提供可替代系统通知的悬浮 Toast 窗口，支持：
- 六种出现位置（左上/左下/右上/右下/上中/下中）
- 可配置停留时间（0 = 常驻）
- 单个关闭按钮
- 进入/退出动画
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, Signal, QObject, QRect,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QBrush, QPen,
)
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QApplication, QPushButton, QSizePolicy,
)

from qfluentwidgets import isDarkTheme, qconfig, FluentIcon as FIF, IconWidget

from loguru import logger

# ── 常量 ────────────────────────────────────────────────── #
TOAST_WIDTH  = 340        # 固定宽度（px）
TOAST_MIN_H  = 64         # 最小高度
TOAST_MARGIN = 16         # 距屏幕边缘距离
TOAST_GAP    = 10         # 相邻 Toast 之间间距
TOAST_ANIM_MS = 280       # 动画时长（ms）
TOAST_RADIUS = 12         # 圆角半径

# 位置常量
POS_TOP_LEFT      = "top_left"
POS_TOP_CENTER    = "top_center"
POS_TOP_RIGHT     = "top_right"
POS_BOTTOM_LEFT   = "bottom_left"
POS_BOTTOM_CENTER = "bottom_center"
POS_BOTTOM_RIGHT  = "bottom_right"

POSITION_LABELS = {
    POS_TOP_LEFT:      "左上",
    POS_TOP_CENTER:    "上中",
    POS_TOP_RIGHT:     "右上",
    POS_BOTTOM_LEFT:   "左下",
    POS_BOTTOM_CENTER: "下中",
    POS_BOTTOM_RIGHT:  "右下",
}

ALL_POSITIONS = list(POSITION_LABELS.keys())


def _is_bottom(position: str) -> bool:
    return position.startswith("bottom")


# ── Toast 单体 ──────────────────────────────────────────── #

class ToastItem(QWidget):
    """单条 Toast 通知窗口（纯 paintEvent 绘制，无 QGraphicsDropShadowEffect）"""

    request_close = Signal(object)

    def __init__(
        self,
        title: str,
        message: str,
        duration_ms: int = 5000,
        parent: QWidget | None = None,
        level: str = "info",
    ):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._duration_ms = duration_ms
        self._closing = False
        self._level = level
        self._is_dark = isDarkTheme()

        # ── 直接构建 UI（无外层透明容器、无阴影 margin）──
        self.setFixedWidth(TOAST_WIDTH)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 10, 12)
        h.setSpacing(10)

        # 图标
        icon_map = {
            "info": (FIF.INFO, "#60CDFF"),
            "success": (FIF.COMPLETED, "#4CAF50"),
            "warning": (FIF.IOT, "#FFB74D"),
            "error": (FIF.CLOSE, "#F44336"),
        }
        fif, tint = icon_map.get(self._level, (FIF.INFO, "#60CDFF"))
        icon_widget = IconWidget(fif)
        icon_widget.setFixedSize(24, 24)
        self._icon_widget = icon_widget
        h.addWidget(icon_widget)

        # 文字区
        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        self._title_lbl = QLabel(title)
        self._title_lbl.setWordWrap(True)
        self._msg_lbl = QLabel(message)
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        text_col.addWidget(self._title_lbl)
        if message:
            text_col.addWidget(self._msg_lbl)

        h.addLayout(text_col, 1)

        # 关闭按钮
        self._close_btn = QPushButton("\u2715")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._request_close)
        h.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignTop)

        # 样式
        self._update_theme()

        # 主题变化
        qconfig.themeChanged.connect(self._on_theme_changed)

        if duration_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(duration_ms)
            self._timer.timeout.connect(self._request_close)
        else:
            self._timer = None

    def paintEvent(self, event) -> None:
        """绘制圆角背景（替代 QGraphicsDropShadowEffect，彻底消除半透明边框伪影）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = TOAST_RADIUS

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)

        # 背景
        if self._is_dark:
            bg_color = QColor(40, 40, 40, 240)
            border_color = QColor(80, 80, 80, 80)
        else:
            bg_color = QColor(255, 255, 255, 245)
            border_color = QColor(0, 0, 0, 12)

        painter.fillPath(path, QBrush(bg_color))

        # 边框
        pen = QPen(border_color)
        pen.setWidthF(1)
        painter.strokePath(path, pen)

        painter.end()

    def _on_theme_changed(self) -> None:
        self._update_theme()

    def _update_theme(self) -> None:
        self._is_dark = isDarkTheme()

        if self._is_dark:
            title_color = "#E5E5E5"
            msg_color = "#A0A0A0"
            close_btn_color = "#808080"
            close_btn_hover = "#505050"
        else:
            title_color = "#1a1a1a"
            msg_color = "#555555"
            close_btn_color = "#999999"
            close_btn_hover = "#e0e0e0"

        # 图标跟随主题
        if hasattr(self, '_icon_widget'):
            if self._is_dark:
                self._icon_widget.setStyleSheet("background: transparent;")
            else:
                self._icon_widget.setStyleSheet("background: transparent;")

        self._title_lbl.setStyleSheet(
            f"color: {title_color}; font-size: 10pt; font-weight: bold;"
        )
        self._msg_lbl.setStyleSheet(f"color: {msg_color}; font-size: 9pt;")
        self._close_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; "
            f"color: {close_btn_color}; font-size: 13px; font-weight: bold; border-radius: 11px; }}"
            f"QPushButton:hover {{ background: {close_btn_hover}; color: {title_color}; }}"
        )
        self.update()

    def start_timer(self) -> None:
        if self._timer:
            self._timer.start()

    def _request_close(self) -> None:
        if not self._closing:
            self._closing = True
            self.request_close.emit(self)


# ── Toast 管理器 ────────────────────────────────────────── #

class ToastManager(QObject):
    """管理所有 ToastItem 的生命周期、堆叠与动画"""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._toasts: list[ToastItem] = []
        self._position: str = POS_BOTTOM_RIGHT
        self._duration_ms: int = 5000
        self._anim_group: QParallelAnimationGroup | None = None

    def set_position(self, position: str) -> None:
        if position in ALL_POSITIONS:
            self._position = position

    def set_duration(self, duration_ms: int) -> None:
        self._duration_ms = max(0, duration_ms)

    def show_toast(
        self,
        title: str,
        message: str,
        duration_ms: int | None = None,
        level: str = "info",
    ) -> None:
        dur = self._duration_ms if duration_ms is None else duration_ms
        toast = ToastItem(title, message, dur, level=level)
        self.add_item(toast)
        logger.debug("Toast 显示：{} | {}", title, message)

    def add_item(self, toast: ToastItem) -> None:
        toast.request_close.connect(self._on_toast_close)
        self._toasts.append(toast)

        start_pos = self._off_screen_pos(toast)
        toast.move(start_pos)
        toast.show()
        toast.adjustSize()

        self._animate_all()
        toast.start_timer()

    def _on_toast_close(self, toast: ToastItem) -> None:
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)

        end_pos = self._off_screen_pos(toast)
        anim = QPropertyAnimation(toast, b"pos", self)
        anim.setDuration(TOAST_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.setEndValue(end_pos)
        anim.finished.connect(toast.close)
        anim.finished.connect(anim.deleteLater)
        anim.start()

        QTimer.singleShot(0, self._animate_all)

    def clear(self) -> None:
        for t in list(self._toasts):
            self._on_toast_close(t)

    def _screen_rect(self) -> QRect:
        screen = QApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    def _toast_height(self, toast: ToastItem) -> int:
        h = toast.sizeHint().height()
        return max(h, TOAST_MIN_H)

    @staticmethod
    def _window_width() -> int:
        return TOAST_WIDTH

    def _target_pos(self, index: int, toast: ToastItem) -> QPoint:
        rect = self._screen_rect()
        pos = self._position
        is_bot = _is_bottom(pos)

        vis_offset = TOAST_MARGIN
        for i in range(index):
            vis_offset += self._toast_height(self._toasts[i]) + TOAST_GAP

        ww = self._window_width()
        vh = self._toast_height(toast)

        if pos in (POS_TOP_LEFT, POS_BOTTOM_LEFT):
            x = rect.left() + TOAST_MARGIN
        elif pos in (POS_TOP_CENTER, POS_BOTTOM_CENTER):
            x = rect.left() + (rect.width() - ww) // 2
        else:
            x = rect.right() - TOAST_MARGIN - ww

        if is_bot:
            y = rect.bottom() - vis_offset - vh
        else:
            y = rect.top() + vis_offset

        return QPoint(x, y)

    def _off_screen_pos(self, toast: ToastItem) -> QPoint:
        rect = self._screen_rect()
        is_bot = _is_bottom(self._position)
        pos = self._position
        ww = self._window_width()
        wh = self._toast_height(toast)

        if pos in (POS_TOP_LEFT, POS_BOTTOM_LEFT):
            x = rect.left() + TOAST_MARGIN
        elif pos in (POS_TOP_CENTER, POS_BOTTOM_CENTER):
            x = rect.left() + (rect.width() - ww) // 2
        else:
            x = rect.right() - TOAST_MARGIN - ww

        if is_bot:
            y = rect.bottom() + TOAST_MARGIN
        else:
            y = rect.top() - wh - TOAST_MARGIN

        return QPoint(x, y)

    def _animate_all(self) -> None:
        if not self._toasts:
            return

        if self._anim_group is not None:
            try:
                if self._anim_group.state() == QParallelAnimationGroup.State.Running:
                    self._anim_group.stop()
            except RuntimeError:
                pass
            self._anim_group = None

        group = QParallelAnimationGroup(self)

        for i, toast in enumerate(self._toasts):
            target = self._target_pos(i, toast)
            anim = QPropertyAnimation(toast, b"pos", group)
            anim.setDuration(TOAST_ANIM_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(toast.pos())
            anim.setEndValue(target)
            group.addAnimation(anim)

        self._anim_group = group
        group.finished.connect(self._on_anim_group_finished)
        group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    def _on_anim_group_finished(self) -> None:
        self._anim_group = None


# ── 全局单例 ─────────────────────────────────────────────── #

_manager: ToastManager | None = None


def get_manager() -> ToastManager:
    global _manager
    if _manager is None:
        _manager = ToastManager()
    return _manager


def show_toast(title: str, message: str = "", level: str = "info", duration: int = 5000) -> None:
    get_manager().show_toast(title, message, duration, level)


def show_success(title: str, message: str = "", duration: int = 3000) -> None:
    show_toast(title, message, "success", duration)


def show_error(title: str, message: str = "", duration: int = 5000) -> None:
    show_toast(title, message, "error", duration)


def show_warning(title: str, message: str = "", duration: int = 4000) -> None:
    show_toast(title, message, "warning", duration)


def show_info(title: str, message: str = "", duration: int = 3000) -> None:
    show_toast(title, message, "info", duration)
