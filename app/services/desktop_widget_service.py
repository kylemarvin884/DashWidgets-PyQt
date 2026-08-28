"""
桌面小组件服务 — PySide6 版本

每个桌面小组件是一个独立的 QWidget 窗口（无边框、可拖拽、可缩放），
内部嵌入一个 WidgetBase 子类作为内容。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QApplication, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QEvent, QPoint, QSize, QObject, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QAction, QCursor, QPainter, QPen, QBrush, QLinearGradient, QPainterPath, QTransform

from loguru import logger
from qfluentwidgets import isDarkTheme

from app.constants import BASE_DIR, WIDGET_CONFIG
from app.models.widget_model import WidgetModel, WidgetInfo

# ── Win32 辅助函数 ─────────────────────────────────────────────── #

if __import__("sys").platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _dwmapi = ctypes.windll.dwmapi

    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_BORDER = 0x00800000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000

    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    HWND_BOTTOM = 1

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    SWP_SHOWWINDOW = 0x0040
    SWP_NOOWNERZORDER = 0x0200

    DWMNCRP_DISABLED = 1
    DWMWA_NCRENDERING_POLICY = 2
    DWMWA_BORDER_COLOR = 34
    DWMWA_CAPTION_COLOR = 35
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWCP_DONOTROUND = 1
    DWMSBT_NONE = 1

    def _get_window_handle(widget: QWidget) -> int:
        return int(widget.winId())

    def _set_click_through(hwnd: int, enable: bool) -> None:
        ex_style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enable:
            ex_style |= WS_EX_TRANSPARENT
        else:
            ex_style &= ~WS_EX_TRANSPARENT
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

    def _set_window_zorder(hwnd: int, zorder: int) -> None:
        _user32.SetWindowPos(
            hwnd, zorder, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )

    def _remove_window_border(hwnd: int) -> None:
        """移除 Windows DWM 边框"""
        style = _user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~(WS_BORDER | WS_CAPTION | WS_THICKFRAME)
        _user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        _user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )

    def _make_fully_transparent(hwnd: int) -> None:
        """使窗口完全透明（用于 frameless 纯文字组件如时钟）"""
        # 1. 分层窗口
        ex_style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

        # 2. 移除所有标准窗口样式
        style = _user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~(WS_BORDER | WS_CAPTION | WS_THICKFRAME | 0x00400000)
        _user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        _user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_NOOWNERZORDER,
        )

        # 3. DWM: 禁用非客户区渲染
        try:
            _dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_NCRENDERING_POLICY,
                ctypes.byref(ctypes.c_int(DWMNCRP_DISABLED)), 4
            )
        except Exception:
            pass

        # 4. 边框/标题颜色完全透明
        for attr in (DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR):
            try:
                _dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(ctypes.c_int(0x00000000)), 4
                )
            except Exception:
                pass

        # 5. 关闭 Mica / 系统背景效果
        try:
            _dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(ctypes.c_int(DWMSBT_NONE)), 4
            )
        except Exception:
            pass

        # 6. 禁止圆角
        try:
            _dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)), 4
            )
        except Exception:
            pass

        # 7. DwmExtendFrameIntoClientArea
        try:
            class MARGINS(ctypes.Structure):
                _fields_ = [
                    ("cxLeftWidth", ctypes.c_int),
                    ("cxRightWidth", ctypes.c_int),
                    ("cyTopHeight", ctypes.c_int),
                    ("cyBottomHeight", ctypes.c_int),
                ]
            m = MARGINS(-1, -1, -1, -1)
            _dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
        except Exception:
            pass

else:
    def _get_window_handle(widget: QWidget) -> int:
        return 0

    def _set_click_through(hwnd: int, enable: bool) -> None:
        pass

    def _set_window_zorder(hwnd: int, zorder: int) -> None:
        pass

    def _remove_window_border(hwnd: int) -> None:
        pass

    def _make_fully_transparent(hwnd: int) -> None:
        pass


# ── 全局信号桥 ───────────────────────────────────────────────────── #

class _WidgetSignals(QObject):
    widget_closed = Signal(str)
    widget_shown = Signal(str)
    widget_hidden = Signal(str)


widget_signals = _WidgetSignals()


# ── Win11 风格工具类 ─────────────────────────────────────────────── #

class Win11Style:
    """Fluent Design 配色 — WinUI 3 官方 token（浅色层叠 / 深色层叠）"""

    # 字体：Fluent 用 Segoe UI Variable（Display 用于大标题）
    FONT_SERIF = '"Segoe UI Variable Display", "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", sans-serif'
    FONT_SANS = '"Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", sans-serif'
    FONT_FAMILY = FONT_SANS  # 兼容旧引用

    # ── 浅色（WinUI 3 Light，Layer/Mica 底 + 白卡片 + 系统蓝）── #
    _LIGHT = {
        "bg": "#f9f9f9",              # SolidBackgroundFillColorBase
        "card_bg": "#ffffff",         # LayerFillColorDefault（卡片白）
        "card_border": "#ebebeb",     # CardStrokeColorDefault
        "text_primary": "#1a1a1a",    # TextFillColorPrimary 近似
        "text_secondary": "#5f5f5f",  # TextFillColorSecondary 近似
        "accent": "#0078d4",          # SystemAccentColor
        "accent_hover": "#106ebe",    # InteractionColorHover
        "danger": "#c42b1c",          # SystemFillColorCritical
        "success": "#0f7b0f",         # SystemFillColorSuccess
        "warning": "#9d5d00",         # SystemFillColorCaution
        "divider": "#ebebeb",         # DividerStrokeColorDefault
        "surface_soft": "#f5f5f5",    # ControlFillColorDefault 近似
        "surface_dark": "#202020",    # 深色底（弹层用）
        "on_dark": "#ffffff",
    }

    # ── 深色（WinUI 3 Dark，#202020 底 + 灰层卡片 + 浅蓝强调）── #
    _DARK = {
        "bg": "#202020",              # SolidBackgroundFillColorBase
        "card_bg": "#2b2b2b",         # LayerFillColorDefault
        "card_border": "#383838",     # CardStrokeColorDefault
        "text_primary": "#ffffff",    # TextFillColorPrimary
        "text_secondary": "#c8c8c8",  # TextFillColorSecondary 近似
        "accent": "#4cc2ff",          # SystemAccentColorLight2
        "accent_hover": "#99ebff",    # InteractionColorHover 近似
        "danger": "#ff99a4",          # SystemFillColorCritical
        "success": "#6ccb5f",         # SystemFillColorSuccess
        "warning": "#fce100",         # SystemFillColorCaution
        "divider": "#2d2d2d",         # DividerStrokeColorDefault
        "surface_soft": "#272727",    # ControlFillColorDefault 近似
        "surface_dark": "#202020",
        "on_dark": "#ffffff",
    }

    @classmethod
    def c(cls) -> dict[str, str]:
        return cls._DARK if cls.is_dark() else cls._LIGHT

    @classmethod
    def is_dark(cls) -> bool:
        return isDarkTheme()

    @classmethod
    def widget_colors(cls) -> dict[str, str]:
        """桌面小组件内文字/标签颜色（中性 Fluent 文本色）"""
        if cls.is_dark():
            return {
                "title": "rgba(255,255,255,0.50)",
                "text": "rgba(255,255,255,0.89)",
                "text_secondary": "rgba(255,255,255,0.60)",
                "text_dim": "rgba(255,255,255,0.35)",
                "accent": "#4cc2ff",
                "bg_input": "rgba(255,255,255,0.05)",
                "border_input": "rgba(255,255,255,0.07)",
                "separator": "rgba(255,255,255,0.08)",
                "track": "rgba(255,255,255,0.12)",
            }
        return {
            "title": "rgba(0,0,0,0.45)",
            "text": "rgba(0,0,0,0.90)",
            "text_secondary": "rgba(0,0,0,0.55)",
            "text_dim": "rgba(0,0,0,0.35)",
            "accent": "#0078d4",
            "bg_input": "rgba(0,0,0,0.04)",
            "border_input": "#e5e5e5",
            "separator": "#ebebeb",
            "track": "rgba(0,0,0,0.08)",
        }

    @classmethod
    def menu_qss(cls) -> str:
        """WinUI MenuFlyout 规格的菜单样式（托盘菜单/右键菜单共用）

        规格：8px 外圆角、1px 卡片描边、条目 14px 正文 + 4px 选中圆角、
        悬停为 subtle 叠层色，分隔线 1px。
        """
        c = cls.c()
        dark = cls.is_dark()
        hover = "rgba(255,255,255,0.06)" if dark else "rgba(0,0,0,0.05)"
        return f"""
            QMenu {{
                background-color: {c['card_bg']};
                border: 1px solid {c['card_border']};
                border-radius: 8px;
                padding: 3px;
            }}
            QMenu::item {{
                padding: 6px 14px 6px 10px;
                border-radius: 4px;
                color: {c['text_primary']};
                font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI";
                font-size: 14px;
            }}
            QMenu::item:selected {{
                background: {hover};
            }}
            QMenu::item:disabled {{
                color: {c['text_secondary']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {c['divider']};
                margin: 4px 6px;
                border: none;
            }}
            QMenu::icon {{
                padding-left: 8px;
                padding-right: 4px;
            }}
        """

    @classmethod
    def label_title(cls, text: str) -> QLabel:
        """设置页分区标题 — Fluent Body Strong（14px Semibold）"""
        c = cls.c()
        label = QLabel(text)
        label.setStyleSheet(
            f"font-family:{cls.FONT_SANS};font-size:14px;"
            f"font-weight:600;color:{c['text_primary']};"
            f"background:transparent;padding:8px 0 4px 0;"
        )
        return label

    @classmethod
    def widget_title(cls, text: str) -> QLabel:
        """桌面小组件标题 — Fluent Caption Semibold（12px，次要色）"""
        c = cls.widget_colors()
        label = QLabel(text)
        label.setStyleSheet(
            f"font-family:{cls.FONT_SANS};font-size:12px;"
            f"font-weight:600;color:{c['text_secondary']};"
            f"background:transparent;letter-spacing:0.2px;"
        )
        return label


# ── 桌面小组件窗口 ──────────────────────────────────────────────── #

class DesktopWidgetWindow(QWidget):
    """单个桌面小组件的窗口（无边框、可拖拽、可缩放、右键菜单、毛玻璃效果）"""

    CORNER_RADIUS = 8   # Fluent 卡片圆角
    BORDER_WIDTH = 1

    def __init__(self, widget_info: WidgetInfo, widget_instance: QWidget | None = None, parent=None):
        super().__init__(parent)
        self._info = widget_info
        self._widget_instance = widget_instance
        self._timers: list[QTimer] = []

        # 交互状态
        self._dragging = False
        self._drag_offset: QPoint = QPoint()
        self._resizing = False
        self._resize_start: QPoint = QPoint()
        self._resize_start_size: QPoint = QPoint()

        # 窗口状态
        self._click_through = False
        self._window_level = "top"
        self._custom_color: QColor | None = None
        self._custom_opacity: float | None = None

        self._setup_window()
        self._build_ui()
        self._load_widget_content()

    def _setup_window(self):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        if self._window_level == "top":
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        # 判断是否为无边框纯文字组件
        self._is_frameless = getattr(self._info, 'id', '') in ('clock',)

        if self._is_frameless:
            self.setStyleSheet("background: transparent;")
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        else:
            # 不在 stylesheet 设背景 — 由 paintEvent 统一绘制奶油色卡片
            self.setStyleSheet("background: transparent;")

        # 默认尺寸
        if self._info.size_override:
            w, h = self._info.size_override
        elif self._info.id == "clock":
            w, h = 170, 88  # 时间 + 日期两行
        else:
            w, h = 320, 220
        self.resize(w, h)

        if self._info.position:
            self.move(self._info.position[0], self._info.position[1])

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 内容区域
        self._content = QWidget(self)
        self._content.setObjectName("dwContent")
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if self._is_frameless:
            self._content.setStyleSheet("background: transparent;")
        else:
            self._content.setStyleSheet("#dwContent { background: transparent; }")
        margin = (0, 0, 0, 0) if self._is_frameless else (10, 10, 10, 10)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(*margin)
        self._content_layout.setSpacing(0)
        main_layout.addWidget(self._content, 1)

        # 拖拽光标：无边框组件整体可拖，默认手形；其余默认箭头，悬停时动态调整
        if self._is_frameless:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setMouseTracking(True)

        # Resize Handle
        self._resize_handle = QWidget(self)
        self._resize_handle.setFixedSize(16, 16)
        self._resize_handle.setStyleSheet("background: transparent;")
        self._resize_handle.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        self._resize_handle.installEventFilter(self)

    # ------------------------------------------------------------------ #
    # 绘制
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        if self._is_frameless:
            # 分层窗口对 alpha=0 的像素做鼠标穿透命中，
            # 补一层 alpha=1 的隐形底色让整个窗口区域都可以拖拽
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = self.CORNER_RADIUS
        c = Win11Style.c()

        # ── 主卡片：奶油色卡片 + 细线边框 ──
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)

        if self._custom_color:
            bg = self._custom_color
        else:
            bg = QColor(c["card_bg"])

        painter.setClipPath(path)
        painter.fillPath(path, QBrush(bg))

        # ── 细线边框（hairline）──
        painter.setClipPath(QPainterPath())
        border_color = QColor(c["card_border"])
        border_pen = QPen(border_color)
        border_pen.setWidthF(self.BORDER_WIDTH)
        painter.strokePath(path, border_pen)

        painter.end()

    # ------------------------------------------------------------------ #
    # 事件处理
    # ------------------------------------------------------------------ #

    def eventFilter(self, watched: Any, event: QEvent) -> bool:
        # Resize handle
        if watched == self._resize_handle:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._resizing = True
                    self._resize_start = event.globalPos()
                    self._resize_start_size = self.size()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                if self._resizing and event.buttons() == Qt.MouseButton.LeftButton:
                    delta = event.globalPos() - self._resize_start
                    new_w = max(180, self._resize_start_size.width() + delta.x())
                    new_h = max(80, self._resize_start_size.height() + delta.y())
                    self.resize(new_w, new_h)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._resizing = False
                    self._save_size()
                    return True

        # 无边框模式：子组件鼠标事件转发（实现拖拽）
        # 注意：子组件事件的 position() 是其局部坐标，需换算到窗口坐标
        if self._is_frameless and watched is not self and watched is not self._resize_handle:
            etype = event.type()
            if etype == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    local = watched.mapTo(self, event.position().toPoint())
                    self._begin_drag(event.globalPos(), local)
                    return True
            elif etype == QEvent.Type.MouseMove:
                if self._dragging:
                    self._update_drag(event.globalPos())
                    return True
            elif etype == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton and self._dragging:
                    self._end_drag()
                    return True

        return super().eventFilter(watched, event)

    def _install_drag_filter(self, widget: QWidget) -> None:
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def _is_interactive_widget(self, widget) -> bool:
        """检查组件是否为可交互控件（按钮、输入框等）"""
        if not widget:
            return False
        from PySide6.QtWidgets import (
            QAbstractButton, QLineEdit, QTextEdit,
            QAbstractSlider, QComboBox, QSpinBox,
            QDoubleSpinBox, QCheckBox, QRadioButton,
        )
        return isinstance(widget, (
            QAbstractButton, QLineEdit, QTextEdit,
            QAbstractSlider, QComboBox, QSpinBox,
            QDoubleSpinBox, QCheckBox, QRadioButton,
        ))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._resizing:
            # 如果点击在可交互控件上，不启动拖拽
            target = self.childAt(event.position().toPoint())
            if self._is_interactive_widget(target):
                return
            self._begin_drag(event.globalPos(), event.position().toPoint())

    def mouseMoveEvent(self, event):
        # 动态光标：交互控件上显示箭头，其他区域显示手形
        target = self.childAt(event.position().toPoint())
        if self._is_interactive_widget(target):
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self._update_drag(event.globalPos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging:
                self._end_drag()
            else:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    # ------------------------------------------------------------------ #
    # 拖拽（窗口本体与子组件事件转发共用）
    # ------------------------------------------------------------------ #

    def _begin_drag(self, global_pos: QPoint, local_pos: QPoint) -> None:
        """local_pos 为窗口坐标，用于避开可交互子控件（保留扩展点）"""
        self._dragging = True
        self._drag_offset = global_pos - self.frameGeometry().topLeft()
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def _update_drag(self, global_pos: QPoint) -> None:
        self.move(global_pos - self._drag_offset)

    def _end_drag(self) -> None:
        self._dragging = False
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self._save_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_resize_handle"):
            self._resize_handle.move(
                self.width() - self._resize_handle.width() - 2,
                self.height() - self._resize_handle.height() - 2,
            )
        if self._is_frameless:
            return

    def showEvent(self, event):
        super().showEvent(event)
        hwnd = _get_window_handle(self)
        if hwnd:
            _remove_window_border(hwnd)
            if self._is_frameless:
                _make_fully_transparent(hwnd)
                QTimer.singleShot(50, lambda: _make_fully_transparent(_get_window_handle(self)))

    def _build_context_menu(self) -> tuple:
        """构建统一右键菜单（组件专属动作 + 系统项），返回 (menu, actions)"""
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        # WinUI MenuFlyout 规格（浅深色自动跟随）
        menu.setStyleSheet(Win11Style.menu_qss())

        act_settings = menu.addAction("组件设置...")

        # 组件贡献的专属动作（合并进统一菜单，避免组件自建 QMenu 出现黑底）
        widget_actions: list[tuple] = []
        if self._widget_instance and hasattr(self._widget_instance, "get_context_menu_actions"):
            try:
                widget_actions = self._widget_instance.get_context_menu_actions() or []
            except Exception:
                logger.exception("获取组件右键动作异常: {}", self._info.id)

        for entry in widget_actions:
            try:
                icon, text, callback = entry
                if icon is not None:
                    # FluentIcon / QIcon 均可：先转 QIcon 走原生重载
                    qicon = icon.icon() if hasattr(icon, "icon") else icon
                    menu.addAction(qicon, text, callback)
                else:
                    menu.addAction(text, callback)
            except Exception:
                logger.exception("注册组件右键动作异常: {}", entry)
        if widget_actions:
            menu.addSeparator()

        level_menu = menu.addMenu("窗口层级")
        act_top = level_menu.addAction("置顶显示")
        act_top.setCheckable(True)
        act_top.setChecked(self._window_level == "top")
        act_normal = level_menu.addAction("正常")
        act_normal.setCheckable(True)
        act_normal.setChecked(self._window_level == "normal")
        act_bottom = level_menu.addAction("置底显示")
        act_bottom.setCheckable(True)
        act_bottom.setChecked(self._window_level == "bottom")

        menu.addSeparator()
        act_click = menu.addAction("鼠标穿透")
        act_click.setCheckable(True)
        act_click.setChecked(self._click_through)

        menu.addSeparator()
        act_close = menu.addAction("关闭小组件")

        actions = {
            "settings": act_settings,
            "top": act_top,
            "normal": act_normal,
            "bottom": act_bottom,
            "click_through": act_click,
            "close": act_close,
        }
        return menu, actions

    def contextMenuEvent(self, event):
        menu, actions = self._build_context_menu()
        selected = menu.exec(event.globalPos())

        if selected == actions["settings"]:
            self._open_appearance_dialog()
        elif selected == actions["top"]:
            self.set_window_level("top")
        elif selected == actions["normal"]:
            self.set_window_level("normal")
        elif selected == actions["bottom"]:
            self.set_window_level("bottom")
        elif selected == actions["click_through"]:
            self.set_click_through(not self._click_through)
        elif selected == actions["close"]:
            self._on_close()

    # ------------------------------------------------------------------ #
    # 功能
    # ------------------------------------------------------------------ #

    def set_window_level(self, level: str) -> None:
        if level not in ("top", "normal", "bottom"):
            return
        self._window_level = level
        hwnd = _get_window_handle(self)
        if not hwnd:
            return
        if level == "top":
            _set_window_zorder(hwnd, HWND_TOPMOST)
        else:
            # bottom / normal: 取消置顶，但不压到 HWND_BOTTOM（会被桌面遮挡）
            _set_window_zorder(hwnd, HWND_NOTOPMOST)

    def set_click_through(self, enable: bool) -> None:
        self._click_through = enable
        hwnd = _get_window_handle(self)
        if hwnd:
            _set_click_through(hwnd, enable)

    def _teardown_widget(self) -> None:
        """统一的组件关闭清理（幂等，可安全重复调用）"""
        if getattr(self, "_widget_closed", False):
            return
        self._widget_closed = True
        self.stop_all_timers()
        if self._widget_instance and hasattr(self._widget_instance, "on_close"):
            try:
                self._widget_instance.on_close()
            except Exception:
                logger.exception("组件 {} on_close 异常", self._info.id)

    def _on_close(self):
        self._teardown_widget()
        self.close()
        from app.services.desktop_widget_service import DesktopWidgetManager
        mgr = DesktopWidgetManager.instance()
        if self._info.id in mgr._active_widgets:
            mgr._on_widget_closed(self._info.id)

    def _save_position(self):
        pos = self.pos()
        self._info.position = (pos.x(), pos.y())
        WidgetModel().update_widget_position(self._info.id, (pos.x(), pos.y()))

    def _save_size(self):
        size = self.size()
        self._info.size_override = (size.width(), size.height())
        WidgetModel().update_widget_size(self._info.id, (size.width(), size.height()))

    def update_settings(self, settings: dict) -> None:
        """应用设置变更到小组件实例"""
        if not settings:
            return
        if self._info:
            self._info.custom_settings = settings
        if self._widget_instance and hasattr(self._widget_instance, "on_settings_changed"):
            self._widget_instance.on_settings_changed(settings)
        elif self._widget_instance and hasattr(self._widget_instance, "apply_settings"):
            self._widget_instance.apply_settings(settings)
        self._apply_window_settings(settings)

    def _open_appearance_dialog(self) -> None:
        """打开外观设置对话框"""
        from app.widgets.widget_settings_dialog import WidgetSettingsDialog

        dialog = WidgetSettingsDialog(widget_id=self._info.id, parent=self)
        dialog.exec()

    def _apply_window_settings(self, settings: dict) -> None:
        """应用窗口级别的设置"""
        # 尺寸变更
        size_key = settings.get("size")
        if size_key:
            from app.constants import WIDGET_SIZES
            new_size = WIDGET_SIZES.get(size_key)
            if new_size and self._info.size_override != new_size:
                self.resize(*new_size)
                self._info.size_override = new_size

        # 透明度
        opacity_val = settings.get("opacity")
        if opacity_val is not None:
            v = float(opacity_val)
            op = v if v <= 1.0 else v / 100.0
            self.setWindowOpacity(op)

        # 颜色（支持 "color" 和 "text_color" 两种 key）
        color_val = settings.get("color") or settings.get("text_color")
        if color_val is not None:
            c = None
            if isinstance(color_val, str):
                qc = QColor(color_val)
                c = qc if qc.isValid() else None
            elif isinstance(color_val, (tuple, list)):
                a = int(color_val[3]) if len(color_val) > 3 else 255
                c = QColor(int(color_val[0]), int(color_val[1]), int(color_val[2]), a)
            elif isinstance(color_val, QColor):
                c = color_val
            if c:
                self._custom_color = c
                self.update()

        # 圆角（支持 "corner_radius" 和 "border_radius" 两种 key）
        corner_radius = settings.get("corner_radius") or settings.get("border_radius")
        if corner_radius is not None:
            self.CORNER_RADIUS = int(corner_radius)
            self.setStyleSheet(
                f"background: transparent; border-radius: {self.CORNER_RADIUS}px;"
            )
            self.update()

        # 阴影样式
        shadow_style = settings.get("shadow_style") or settings.get("shadow")
        if shadow_style:
            # 目前 Win11 风格无手绘阴影，仅记录设置
            pass

        click_through = settings.get("click_through")
        if click_through is not None:
            self.set_click_through(bool(click_through))

    # ------------------------------------------------------------------ #
    # 内容加载
    # ------------------------------------------------------------------ #

    def _load_widget_content(self) -> None:
        try:
            if self._widget_instance:
                self._content_layout.addWidget(self._widget_instance)
                if hasattr(self._widget_instance, "refresh"):
                    self._widget_instance.refresh()
            else:
                from app.widgets.registry import WidgetRegistry
                from app.widgets.base_widget import WidgetConfig

                config = WidgetConfig(
                    widget_type=self._info.id,
                    id=self._info.id,
                    width=self._info.size_override[0] if self._info.size_override else 280,
                    height=self._info.size_override[1] if self._info.size_override else 160,
                    settings=dict(self._info.custom_settings or {}),
                )

                widget = WidgetRegistry.instance().create(config, {}, parent=self._content)
                if widget:
                    # 记录实例：统一右键菜单的组件动作、on_close 清理都依赖它
                    self._widget_instance = widget
                    self._content_layout.addWidget(widget)
                    if hasattr(widget, "refresh"):
                        widget.refresh()
                else:
                    label = QLabel(f"小组件: {self._info.name}\nID: {self._info.id}")
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    label.setStyleSheet("background:transparent;color:rgba(20,20,19,220);"
                                        f"font-family:{Win11Style.FONT_SANS};")
                    self._content_layout.addWidget(label)

            if self._is_frameless:
                self._install_drag_filter(self._content)
        except Exception as e:
            logger.warning("加载小组件内容失败: {}", e)
            label = QLabel(f"加载失败: {e}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color:#c64545;background:transparent;")
            self._content_layout.addWidget(label)

    # ------------------------------------------------------------------ #
    # 公共接口
    # ------------------------------------------------------------------ #

    @property
    def widget_info(self) -> WidgetInfo:
        return self._info

    def start_timer(self, interval_ms: int, callback):
        timer = QTimer(self)
        timer.timeout.connect(callback)
        timer.start(interval_ms)
        self._timers.append(timer)

    def stop_all_timers(self):
        for timer in self._timers:
            timer.stop()
        self._timers.clear()

    def closeEvent(self, event):
        # 隐藏（hide_widget → close）路径也要触发组件 on_close，
        # 释放组件持有的服务订阅（媒体轮询、统计采样等）
        self._teardown_widget()
        super().closeEvent(event)


# ── 桌面小组件管理器 ─────────────────────────────────────────────── #

class DesktopWidgetManager:
    """桌面小组件管理器 — 单例"""

    _instance: Optional["DesktopWidgetManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._active_widgets: dict[str, DesktopWidgetWindow] = {}
        self._model = WidgetModel()
        from app.services.usage_tracker import UsageTracker
        self._usage = UsageTracker()

    def show_widget(self, widget_id: str):
        if widget_id in self._active_widgets:
            self._active_widgets[widget_id].show()
            self._usage.start_session(widget_id)
            return

        info = self._model.get_widget(widget_id)
        if not info:
            logger.warning("小组件不存在: {}", widget_id)
            return

        if not info.is_active:
            info.is_active = True
            self._model.save()

        window = DesktopWidgetWindow(info)
        window.show()
        self._active_widgets[widget_id] = window
        self._usage.start_session(widget_id)
        widget_signals.widget_shown.emit(widget_id)
        logger.info("桌面小组件已显示: {}", info.name)

    def hide_widget(self, widget_id: str):
        if widget_id not in self._active_widgets:
            return
        window = self._active_widgets[widget_id]
        window.stop_all_timers()
        window.close()
        window.deleteLater()  # 释放窗口及其子组件，防止隐藏后仍驻留内存
        del self._active_widgets[widget_id]
        self._usage.end_session(widget_id)
        widget_signals.widget_hidden.emit(widget_id)
        logger.info("桌面小组件已隐藏: {}", widget_id)

    def hide_all(self):
        for widget_id in list(self._active_widgets.keys()):
            self.hide_widget(widget_id)

    def show_all(self):
        self.show_all_active_widgets()

    def show_all_active_widgets(self):
        widgets = self._model.get_all_widgets()
        for w in widgets:
            if w.is_active:
                self.show_widget(w.id)

    def toggle_all(self):
        if self._active_widgets:
            self.hide_all()
        else:
            self.show_all_active_widgets()

    def _on_widget_closed(self, widget_id: str):
        if widget_id in self._active_widgets:
            del self._active_widgets[widget_id]
        self._usage.end_session(widget_id)
        info = self._model.get_widget(widget_id)
        if info and info.is_active:
            info.is_active = False
            info.position = None
            self._model.save()
            logger.info("小组件已停用: {}", widget_id)
        widget_signals.widget_closed.emit(widget_id)

    def set_widget_level(self, widget_id: str, level: str) -> None:
        window = self._active_widgets.get(widget_id)
        if window:
            window.set_window_level(level)

    def set_widget_click_through(self, widget_id: str, enable: bool) -> None:
        window = self._active_widgets.get(widget_id)
        if window:
            window.set_click_through(enable)

    def get_widget_colors(self, widget_id: str) -> dict[str, str]:
        from app.services.settings_service import SettingsService
        settings = SettingsService.instance()
        color_preset = settings.color_preset

        color_presets = {
            "默认": {"default": ("#6B7280", "#4B5563", "#E5E7EB", "#374151")},
            "清新蓝": {"clock": ("#0EA5E9", "#0284C7", "#E0F2FE", "#0369A1"), "default": ("#0EA5E9", "#0284C7", "#E0F2FE", "#0369A1")},
            "活力橙": {"clock": ("#F97316", "#EA580C", "#FFF7ED", "#C2410C"), "default": ("#F97316", "#EA580C", "#FFF7ED", "#C2410C")},
            "优雅紫": {"clock": ("#6366F1", "#4F46E5", "#EEF2FF", "#4338CA"), "default": ("#6366F1", "#4F46E5", "#EEF2FF", "#4338CA")},
            "自然绿": {"clock": ("#059669", "#047857", "#ECFDF5", "#065F46"), "default": ("#059669", "#047857", "#ECFDF5", "#065F46")},
        }

        scheme = color_presets.get(color_preset, color_presets["默认"])
        colors = scheme.get(widget_id, scheme.get("default", ("#6B7280", "#4B5563", "#E5E7EB", "#374151")))

        return {
            "primary": colors[0],
            "secondary": colors[1],
            "background": colors[2],
            "text": colors[3],
        }

    @classmethod
    def instance(cls) -> "DesktopWidgetManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
