"""
DashWidgets - Windows桌面小组件管理器
PyQt版本

@author: Little Tree Studio
@license: GPL-3.0
"""

import sys
import json
import ctypes
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any

from loguru import logger
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSystemTrayIcon, QMenu,
    QListWidget, QListWidgetItem, QProgressBar, QTextEdit, QGridLayout,
    QSlider, QCheckBox, QDialog, QFileDialog, QLineEdit, QComboBox, QSpinBox
)
from PyQt6.QtCore import (
    Qt, QTimer, QRect, QPoint, QPointF, QPropertyAnimation, QEasingCurve, pyqtSignal, pyqtProperty,
    QByteArray
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QScreen, QPixmap, QFont, QIcon, QPolygonF
from PyQt6.QtSvg import QSvgRenderer

# 网页组件支持（可选）
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError as e:
    print(f"WebEngine 导入失败: {e}")
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False
except Exception as e:
    print(f"WebEngine 初始化错误: {e}")
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False

import psutil
import ctypes

# Windows API 常量
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

# Windows API 函数
user32 = ctypes.windll.user32

# 配置目录
DATA_DIR = Path.home() / ".dashwidgets_pyqt"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 资源目录
ASSETS_DIR = Path(__file__).parent / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"

# 配置日志
logger.add(
    LOG_DIR / "dashwidgets_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    level="INFO",
    encoding="utf-8"
)


class ThemeColors:
    """主题颜色配置 - Windows 11 风格"""
    # 配色方案
    COLOR_SCHEMES = {
        "blue": {
            "accent": "#0078D4", "accent_hover": "#106EBE", "accent_pressed": "#005A9E", "accent_light": "#60CDFF"
        },
        "green": {
            "accent": "#107C10", "accent_hover": "#0B5C0B", "accent_pressed": "#084008", "accent_light": "#6BBF6B"
        },
        "purple": {
            "accent": "#8764B8", "accent_hover": "#6D4F96", "accent_pressed": "#533A74", "accent_light": "#B8A4D4"
        },
        "orange": {
            "accent": "#FF8C00", "accent_hover": "#E67E00", "accent_pressed": "#CC7000", "accent_light": "#FFB84D"
        },
        "red": {
            "accent": "#D13438", "accent_hover": "#A82828", "accent_pressed": "#7E1E1E", "accent_light": "#E87A7A"
        },
        "teal": {
            "accent": "#00B7C3", "accent_hover": "#00909A", "accent_pressed": "#006D73", "accent_light": "#66D9E0"
        }
    }

    def __init__(self, light_mode: bool = True, color_scheme: str = "blue"):
        self.light_mode = light_mode
        self.color_scheme = color_scheme
        self._update_colors()

    def _update_colors(self):
        scheme = self.COLOR_SCHEMES.get(self.color_scheme, self.COLOR_SCHEMES["blue"])

        if self.light_mode:
            # 浅色主题 - Windows 11 风格
            self.bg_main = "#F3F3F3"           # 页面背景
            self.bg_sidebar = "#F9F9F9"        # 侧边栏背景
            self.bg_card = "#FFFFFF"           # 卡片背景
            self.bg_widget = "#FFFFFF"         # 小组件背景
            self.bg_input = "#FFFFFF"          # 输入框背景
            self.bg_hover = "#E9E9E9"          # 悬停背景
            self.bg_pressed = "#D9D9D9"        # 按下背景
            self.text_primary = "#1A1A1A"      # 主要文字
            self.text_secondary = "#5C5C5C"    # 次要文字
            self.text_tertiary = "#8A8A8A"     # 三级文字
            self.accent = scheme["accent"]
            self.accent_light = scheme["accent_light"]
            self.accent_hover = scheme["accent_hover"]
            self.accent_pressed = scheme["accent_pressed"]
            self.border = "#E5E5E5"            # 边框
            self.subtle = "#0000000F"          # 微妙背景
            self.success = "#0F7B0F"           # 成功
            self.warning = "#9D5D00"           # 警告
            self.error = "#C42B1C"             # 错误
            self.shadow = QColor(0, 0, 0, 15)
        else:
            # 深色主题 - Windows 11 风格
            self.bg_main = "#202020"           # 页面背景
            self.bg_sidebar = "#282828"        # 侧边栏背景
            self.bg_card = "#2D2D2D"           # 卡片背景
            self.bg_widget = "#2D2D2D"         # 小组件背景
            self.bg_input = "#1A1A1A"          # 输入框背景
            self.bg_hover = "#383838"          # 悬停背景
            self.bg_pressed = "#484848"        # 按下背景
            self.text_primary = "#FFFFFF"      # 主要文字
            self.text_secondary = "#C5C5C5"    # 次要文字
            self.text_tertiary = "#8A8A8A"     # 三级文字
            self.accent = scheme["accent_light"]
            self.accent_light = scheme["accent_light"]
            self.accent_hover = scheme["accent"]
            self.accent_pressed = scheme["accent_hover"]
            self.border = "#3D3D3D"            # 边框
            self.subtle = "#FFFFFF0F"          # 微妙背景
            self.success = "#6CCB6C"           # 成功
            self.warning = "#FCE100"           # 警告
            self.error = "#FF99A4"             # 错误
            self.shadow = QColor(0, 0, 0, 40)


# 全局主题
theme = ThemeColors(light_mode=True)


class WidgetConfig:
    """小组件配置"""
    def __init__(self):
        self.widgets: list = []
        self.light_mode: bool = True
        self.widget_opacity: float = 0.95
        self.snap_enabled: bool = True
        self.snap_threshold: int = 20
        self.color_scheme: str = "blue"
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                self.widgets = data.get("widgets", [])
                self.light_mode = data.get("light_mode", True)
                self.widget_opacity = data.get("widget_opacity", 0.95)
                self.snap_enabled = data.get("snap_enabled", True)
                self.snap_threshold = data.get("snap_threshold", 20)
                self.color_scheme = data.get("color_scheme", "blue")
            except Exception as e:
                logger.error(f"加载配置失败: {e}")

    def save(self):
        try:
            data = {
                "widgets": self.widgets,
                "light_mode": self.light_mode,
                "widget_opacity": self.widget_opacity,
                "snap_enabled": self.snap_enabled,
                "snap_threshold": self.snap_threshold,
                "color_scheme": self.color_scheme
            }
            CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")


config = WidgetConfig()


class AnimatedNavButton(QPushButton):
    """带动画效果的导航按钮"""
    def __init__(self, text: str, icon_path: str = None, parent=None):
        super().__init__(text, parent)
        self._hover_progress = 0.0
        self._active = False
        self._indicator_width = 0.0
        self._icon_path = icon_path
        self._icon_pixmap = None
        self._collapsed = False  # 抽屉收起状态
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 加载图标
        if icon_path and Path(icon_path).exists():
            self._load_icon(icon_path)

        # 悬停动画
        self._hover_anim = QPropertyAnimation(self, b"hover_progress")
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 指示器动画
        self._indicator_anim = QPropertyAnimation(self, b"indicator_width")
        self._indicator_anim.setDuration(200)
        self._indicator_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setFixedHeight(40)
        
    def set_collapsed(self, collapsed: bool):
        """设置收起状态"""
        self._collapsed = collapsed
        self.update()

    def _load_icon(self, icon_path: str):
        """加载并着色图标"""
        from PyQt6.QtGui import QPixmap, QIcon

        # 读取SVG文件并替换currentColor为实际颜色
        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()

            # 获取当前主题的文字颜色
            icon_color = theme.text_primary

            # 替换currentColor为实际颜色
            svg_content = svg_content.replace('currentColor', icon_color)

            # 从修改后的SVG创建图标 - 使用2倍尺寸确保清晰
            renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
            if renderer.isValid():
                icon_size = 40  # 2倍尺寸，确保清晰
                pixmap = QPixmap(icon_size, icon_size)
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                renderer.render(painter)
                painter.end()
                self._icon_pixmap = pixmap
                return
        except Exception as e:
            logger.warning(f"加载SVG图标失败: {e}")

        # 回退到普通加载方式
        icon = QIcon(str(icon_path))
        self._icon_pixmap = icon.pixmap(20, 20)

    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress

    @hover_progress.setter
    def hover_progress(self, value):
        self._hover_progress = value
        self.update()

    @pyqtProperty(float)
    def indicator_width(self):
        return self._indicator_width

    @indicator_width.setter
    def indicator_width(self, value):
        self._indicator_width = value
        self.update()

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value: bool):
        if self._active != value:
            self._active = value
            # 指示器动画
            self._indicator_anim.stop()
            self._indicator_anim.setStartValue(self._indicator_width)
            self._indicator_anim.setEndValue(3.0 if value else 0.0)
            self._indicator_anim.start()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_progress)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_progress)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 悬停背景
        if self._hover_progress > 0:
            hover_color = QColor(theme.bg_hover)
            hover_color.setAlpha(int(hover_color.alpha() * self._hover_progress))
            painter.fillRect(self.rect(), hover_color)

        # 选中指示器
        if self._indicator_width > 0:
            indicator_color = QColor(theme.accent)
            indicator_rect = QRect(0, 8, int(self._indicator_width), self.height() - 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(indicator_color))
            painter.drawRoundedRect(indicator_rect, 1, 1)

        # 绘制图标
        icon_size = 20
        if self._icon_pixmap:
            if self._collapsed:
                # 收起状态：图标居中
                icon_x = (self.width() - icon_size) // 2
            else:
                icon_x = 16
            icon_y = (self.height() - icon_size) // 2
            painter.drawPixmap(icon_x, icon_y, icon_size, icon_size, self._icon_pixmap)

        # 文字（仅展开状态显示）
        if not self._collapsed:
            text_offset = 44 if self._icon_pixmap else 16
            text_color = theme.accent if self._active else theme.text_primary
            painter.setPen(QColor(text_color))
            font = self.font()
            font.setBold(self._active)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(text_offset, 0, 0, 0),
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            self.text())

    def update_style(self):
        """更新样式（主题切换时调用）"""
        # 重新加载图标以匹配新主题颜色
        if self._icon_path and Path(self._icon_path).exists():
            self._load_icon(self._icon_path)
        self.update()


class BaseWidget(QFrame):
    """小组件基类"""
    closed = pyqtSignal(str)

    # 组件尺寸映射
    SIZE_MAP = {
        "small": (160, 160),
        "medium": (220, 220),
        "large": (320, 280),
        "xlarge": (480, 360)
    }

    # 阴影边距
    SHADOW_MARGIN = 10
    # 所有小组件实例
    _all_widgets: list = []

    def __init__(self, widget_id: str, name: str, size: str = "medium", parent=None):
        super().__init__(parent)
        self.widget_id = widget_id
        self.widget_name = name
        self.size_key = size
        self.opacity = config.widget_opacity
        self.drag_pos = None
        self._snap_indicator_rect = None
        self._snap_indicator_type = None  # 'left', 'right', 'top', 'bottom'
        self.click_through = False  # 鼠标穿透模式
        self.always_on_top = False  # 默认不置顶，只显示在桌面

        # 拖拽调整大小相关
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None
        self._resize_handle_size = 16  # 调整大小手柄区域大小

        # 添加到全局列表
        BaseWidget._all_widgets.append(self)

        self._init_window()
        self._setup_ui()
        self._setup_animations()

        # 加载置顶配置
        self._load_top_state()

        # 定时器
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_content)
        self.update_timer.start(1000)

        self.update_content()

    def _init_window(self):
        """初始化窗口属性"""
        w, h = self.SIZE_MAP.get(self.size_key, (220, 220))
        self._content_width = w
        self._content_height = h

        # 默认不置顶，只显示在桌面层
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # 窗口大小增加阴影边距
        self.setFixedSize(w + self.SHADOW_MARGIN * 2, h + self.SHADOW_MARGIN * 2)

    def _load_top_state(self):
        """加载置顶状态配置"""
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                self.always_on_top = widget_config.get("always_on_top", False)
                break

        # 应用置顶状态
        self._apply_top_state()

    def _apply_top_state(self):
        """应用置顶状态"""
        if self.always_on_top:
            # 设置置顶窗口标志
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
        else:
            # 普通窗口标志
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.Tool
            )
        self.show()

        hwnd = int(self.winId())
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002

        if self.always_on_top:
            HWND_TOPMOST = -1
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE
            )
        else:
            HWND_NOTOPMOST = -2
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE
            )

    def _is_on_resize_handle(self, pos):
        """检查鼠标是否在调整大小手柄区域"""
        m = self.SHADOW_MARGIN
        handle_rect = QRect(
            self.width() - m - self._resize_handle_size,
            self.height() - m - self._resize_handle_size,
            self._resize_handle_size,
            self._resize_handle_size
        )
        return handle_rect.contains(pos)

    def _update_widget_size(self, new_width, new_height):
        """更新组件大小"""
        # 限制最小和最大尺寸
        min_w, min_h = 200, 150
        max_w, max_h = 800, 600

        new_width = max(min_w, min(max_w, new_width))
        new_height = max(min_h, min(max_h, new_height))

        self._content_width = new_width
        self._content_height = new_height

        # 更新窗口大小（包含阴影边距）
        total_w = new_width + self.SHADOW_MARGIN * 2
        total_h = new_height + self.SHADOW_MARGIN * 2
        self.setFixedSize(total_w, total_h)

        # 保存到配置
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["custom_width"] = new_width
                widget_config["custom_height"] = new_height
                break
        config.save()

    def _setup_ui(self):
        """设置UI（子类实现）"""
        self._main_layout = QVBoxLayout(self)
        # 布局边距需要包含阴影边距
        m = self.SHADOW_MARGIN
        self._main_layout.setContentsMargins(m + 12, m + 12, m + 12, m + 12)

        # 标题栏
        self.header = QHBoxLayout()
        self.title_label = QLabel(self.widget_name)
        self.title_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 12px;
            font-weight: 500;
        """)
        self.header.addWidget(self.title_label)
        self.header.addStretch()

        # 关闭按钮
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.text_secondary};
                border: none;
                font-size: 16px;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: {theme.error};
                color: white;
            }}
        """)
        self.close_btn.clicked.connect(self._on_close)
        self.header.addWidget(self.close_btn)

        self._main_layout.addLayout(self.header)

    def _setup_animations(self):
        """设置动画"""
        # 进入动画
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(self.opacity)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def update_style(self):
        """更新样式（切换主题时调用）"""
        self.title_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 12px;
            font-weight: 500;
        """)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.text_secondary};
                border: none;
                font-size: 16px;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: {theme.error};
                color: white;
            }}
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self.opacity_animation.start()

    def update_content(self):
        """更新内容（子类实现）"""
        pass

    def _on_close(self):
        # 保存当前位置（仅在配置中存在时）
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["position"] = [self.x(), self.y()]
                widget_config["size"] = self.size_key
                widget_config["click_through"] = self.click_through
                break
        config.save()

        # 从全局列表中移除
        if self in BaseWidget._all_widgets:
            BaseWidget._all_widgets.remove(self)

        # 淡出动画后关闭
        self.close_animation = QPropertyAnimation(self, b"windowOpacity")
        self.close_animation.setDuration(150)
        self.close_animation.setStartValue(self.windowOpacity())
        self.close_animation.setEndValue(0)
        self.close_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.close_animation.finished.connect(lambda: self._finish_close())
        self.close_animation.start()

    def _finish_close(self):
        """完成关闭"""
        self.closed.emit(self.widget_id)
        self.close()

    def paintEvent(self, event):
        """绘制圆角背景和阴影"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 计算内容区域（减去阴影边距）
        m = self.SHADOW_MARGIN
        content_rect = QRect(m, m, self.width() - m * 2, self.height() - m * 2)

        # 绘制阴影
        shadow_color = QColor(0, 0, 0, 40)
        for i in range(5, 0, -1):
            offset = i * 2
            shadow_rect = content_rect.adjusted(-offset, -offset, offset, offset)
            shadow_color.setAlpha(40 - i * 6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(shadow_color))
            painter.drawRoundedRect(shadow_rect, 16 + offset, 16 + offset)

        # 绘制背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(theme.bg_widget)))
        painter.setOpacity(self.opacity)
        painter.drawRoundedRect(content_rect, 16, 16)

        # 绘制边框
        painter.setPen(QPen(QColor(theme.border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(1)
        painter.drawRoundedRect(content_rect, 16, 16)

        # 绘制吸附指示器
        if self._snap_indicator_rect:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(theme.accent)))
            painter.setOpacity(0.5)
            painter.drawRect(self._snap_indicator_rect)

        # 绘制调整大小手柄（右下角三角形）
        handle_size = self._resize_handle_size
        handle_margin = 4
        painter.setOpacity(0.4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(theme.text_secondary)))
        # 绘制三角形手柄
        triangle = QPolygonF([
            QPointF(self.width() - m - handle_margin, self.height() - m - handle_margin),
            QPointF(self.width() - m - handle_margin - handle_size, self.height() - m - handle_margin),
            QPointF(self.width() - m - handle_margin, self.height() - m - handle_margin - handle_size)
        ])
        painter.drawPolygon(triangle)

        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()
            # 检查是否在调整大小手柄区域
            if self._is_on_resize_handle(local_pos):
                self._resizing = True
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_size = (self._content_width, self._content_height)
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _check_y_overlap(self, my_y, other_rect):
        """检查Y轴是否有重叠"""
        my_bottom = my_y + self.height()
        other_bottom = other_rect.bottom()
        return not (my_bottom < other_rect.top() or my_y > other_bottom)

    def _check_x_overlap(self, my_x, other_rect):
        """检查X轴是否有重叠"""
        my_right = my_x + self.width()
        other_right = other_rect.right()
        return not (my_right < other_rect.left() or my_x > other_right)

    def mouseReleaseEvent(self, event):
        """鼠标释放时清除吸附指示器并保存位置"""
        # 结束调整大小
        if self._resizing:
            self._resizing = False
            self._resize_start_pos = None
            self._resize_start_size = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

        self._snap_indicator_rect = None
        self.update()

        # 保存位置
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["position"] = [self.x(), self.y()]
                widget_config["size"] = self.size_key
                widget_config["click_through"] = self.click_through
                break
        config.save()

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 处理拖拽、调整大小和光标更新"""
        # 处理调整大小
        if self._resizing and self._resize_start_pos and self._resize_start_size:
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self._resize_start_pos
            new_width = self._resize_start_size[0] + delta.x()
            new_height = self._resize_start_size[1] + delta.y()
            self._update_widget_size(new_width, new_height)
            return

        # 更新光标
        local_pos = event.position().toPoint()
        if self._is_on_resize_handle(local_pos):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # 处理拖拽移动
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_pos:
            new_pos = event.globalPosition().toPoint() - self.drag_pos

            # 如果吸附功能启用
            if config.snap_enabled:
                threshold = config.snap_threshold

                # 获取屏幕边界
                screen = QApplication.screenAt(event.globalPosition().toPoint())
                if not screen:
                    screen = QApplication.primaryScreen()
                screen_rect = screen.availableGeometry()

                # 计算屏幕边缘吸附位置
                snap_x, snap_y = None, None
                snap_type_x, snap_type_y = None, None

                # 左边缘吸附
                if abs(new_pos.x() - screen_rect.left()) < threshold:
                    snap_x = screen_rect.left()
                    snap_type_x = 'screen_left'
                # 右边缘吸附
                elif abs(new_pos.x() + self.width() - screen_rect.right()) < threshold:
                    snap_x = screen_rect.right() - self.width()
                    snap_type_x = 'screen_right'

                # 上边缘吸附
                if abs(new_pos.y() - screen_rect.top()) < threshold:
                    snap_y = screen_rect.top()
                    snap_type_y = 'screen_top'
                # 下边缘吸附
                elif abs(new_pos.y() + self.height() - screen_rect.bottom()) < threshold:
                    snap_y = screen_rect.bottom() - self.height()
                    snap_type_y = 'screen_bottom'

                # 组件间吸附
                for other in BaseWidget._all_widgets:
                    if other is self or not other.isVisible():
                        continue

                    other_rect = other.geometry()

                    # 我的右边吸附到其他左边
                    if abs(new_pos.x() + self.width() - other_rect.left()) < threshold:
                        # Y轴对齐检查
                        if self._check_y_overlap(new_pos.y(), other_rect):
                            snap_x = other_rect.left() - self.width()
                            snap_type_x = 'widget_right'

                    # 我的左边吸附到其他右边
                    elif abs(new_pos.x() - other_rect.right()) < threshold:
                        if self._check_y_overlap(new_pos.y(), other_rect):
                            snap_x = other_rect.right()
                            snap_type_x = 'widget_left'

                    # 我的下边吸附到其他上边
                    if abs(new_pos.y() + self.height() - other_rect.top()) < threshold:
                        if self._check_x_overlap(new_pos.x(), other_rect):
                            snap_y = other_rect.top() - self.height()
                            snap_type_y = 'widget_bottom'

                    # 我的上边吸附到其他下边
                    elif abs(new_pos.y() - other_rect.bottom()) < threshold:
                        if self._check_x_overlap(new_pos.x(), other_rect):
                            snap_y = other_rect.bottom()
                            snap_type_y = 'widget_top'

                # 应用吸附
                if snap_x is not None:
                    new_pos.setX(snap_x)
                if snap_y is not None:
                    new_pos.setY(snap_y)

                # 更新吸附指示器
                self._snap_indicator_type = snap_type_x or snap_type_y
                if snap_x is not None or snap_y is not None:
                    self._snap_indicator_rect = self._calculate_snap_indicator(snap_x, snap_y, screen_rect)
                else:
                    self._snap_indicator_rect = None
            else:
                self._snap_indicator_rect = None

            self.move(new_pos)
            self.update()

    def _calculate_snap_indicator(self, snap_x, snap_y, screen_rect):
        """计算吸附指示器的位置"""
        m = self.SHADOW_MARGIN
        if snap_x == screen_rect.left():
            return QRect(0, 0, 3, self.height())
        elif snap_x == screen_rect.right() - self.width():
            return QRect(self.width() - 3, 0, 3, self.height())
        elif snap_y == screen_rect.top():
            return QRect(0, 0, self.width(), 3)
        elif snap_y == screen_rect.bottom() - self.height():
            return QRect(0, self.height() - 3, self.width(), 3)
        return None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 6px 4px;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 8px 28px 8px 16px;
                border-radius: 4px;
                background: transparent;
                color: {theme.text_primary};
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.bg_hover};
            }}
            QMenu::item:pressed {{
                background-color: {theme.bg_pressed};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {theme.border};
                margin: 4px 12px;
            }}
            QMenu::indicator {{
                width: 16px;
                height: 16px;
                margin-left: 8px;
            }}
            QMenu::indicator:checked {{
                background-color: {theme.accent};
                border: none;
                border-radius: 3px;
            }}
            QMenu::indicator:unchecked {{
                background-color: transparent;
                border: 2px solid {theme.text_tertiary};
                border-radius: 3px;
            }}
        """)

        # 鼠标穿透选项
        click_through_action = menu.addAction("鼠标穿透")
        click_through_action.setCheckable(True)
        click_through_action.setChecked(self.click_through)
        click_through_action.triggered.connect(self._toggle_click_through)

        menu.addSeparator()

        # 窗口层级选项
        top_action = menu.addAction("置顶显示")
        top_action.triggered.connect(self._bring_to_top)

        bottom_action = menu.addAction("置底显示")
        bottom_action.triggered.connect(self._send_to_bottom)

        menu.addSeparator()

        close_action = menu.addAction("关闭小组件")
        close_action.triggered.connect(self._on_close)

        menu.exec(event.globalPos())

    def _bring_to_top(self):
        """置顶显示 - 使用Windows API实现持久置顶"""
        self.always_on_top = True

        # 更新窗口标志，添加置顶属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.show()

        hwnd = int(self.winId())

        # 设置窗口为始终置顶
        HWND_TOPMOST = -1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002

        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE
        )

        # 保存配置
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["always_on_top"] = True
                break
        config.save()

    def _send_to_bottom(self):
        """置底显示 - 取消置顶并移到底层"""
        self.always_on_top = False

        # 更新窗口标志，移除置顶属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.show()

        hwnd = int(self.winId())

        # 取消置顶
        HWND_NOTOPMOST = -2
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002

        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_NOTOPMOST,
            0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE
        )

        # 移到最底层
        self.lower()

        # 保存配置
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["always_on_top"] = False
                break
        config.save()

    def _toggle_click_through(self):
        """切换鼠标穿透模式 - 使用Windows API"""
        self.click_through = not self.click_through

        # 获取窗口句柄
        hwnd = int(self.winId())

        # 获取当前扩展窗口样式
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        if self.click_through:
            # 添加透明和分层样式
            ex_style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            # 移除透明样式，保留分层
            ex_style &= ~WS_EX_TRANSPARENT

        # 设置新的扩展窗口样式
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

        # 保存配置
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["click_through"] = self.click_through
                break
        config.save()

    def _on_size_changed(self):
        """大小改变时的回调，子类可覆盖"""
        pass


class ClockWidget(BaseWidget):
    """时钟小组件"""
    # 尺寸对应的字体大小
    FONT_SIZES = {
        "small": 28,
        "medium": 42,
        "large": 56
    }

    def __init__(self, widget_id: str, size: str = "medium"):
        self.show_seconds = False  # 默认关闭秒数显示
        super().__init__(widget_id, "时钟", size)

    def _setup_ui(self):
        super()._setup_ui()

        # 时间显示
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 秒数显示
        self.seconds_label = QLabel()
        self.seconds_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 日期显示
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._apply_styles()

        self._main_layout.addStretch()
        self._main_layout.addWidget(self.time_label)
        self._main_layout.addWidget(self.seconds_label)
        self._main_layout.addSpacing(4)
        self._main_layout.addWidget(self.date_label)
        self._main_layout.addStretch()

    def _apply_styles(self):
        font_size = self.FONT_SIZES.get(self.size_key, 42)
        self.time_label.setStyleSheet(f"""
            font-size: {font_size}px;
            font-weight: 300;
            color: {theme.text_primary};
        """)
        self.seconds_label.setStyleSheet(f"""
            font-size: {font_size // 2}px;
            font-weight: 300;
            color: {theme.accent};
        """)
        self.date_label.setStyleSheet(f"""
            font-size: 13px;
            color: {theme.text_secondary};
        """)

    def update_style(self):
        """更新样式"""
        super().update_style()
        self._apply_styles()

    def _on_size_changed(self):
        self._apply_styles()

    def update_content(self):
        now = datetime.now()
        if self.show_seconds:
            self.time_label.setText(now.strftime("%H:%M"))
            self.seconds_label.setText(f":{now.strftime('%S')}")
            self.seconds_label.show()
        else:
            self.time_label.setText(now.strftime("%H:%M:%S"))
            self.seconds_label.hide()
        self.date_label.setText(now.strftime("%Y年%m月%d日 %A"))

    def contextMenuEvent(self, event):
        """右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 6px 4px;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 8px 28px 8px 16px;
                border-radius: 4px;
                background: transparent;
                color: {theme.text_primary};
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.bg_hover};
            }}
        """)

        # 秒数显示选项
        seconds_action = menu.addAction("显示秒数")
        seconds_action.setCheckable(True)
        seconds_action.setChecked(self.show_seconds)
        seconds_action.triggered.connect(self._toggle_seconds)

        menu.addSeparator()

        # 窗口层级选项
        top_action = menu.addAction("置顶显示")
        top_action.triggered.connect(self._bring_to_top)

        bottom_action = menu.addAction("置底显示")
        bottom_action.triggered.connect(self._send_to_bottom)

        menu.addSeparator()

        # 鼠标穿透选项
        click_through_action = menu.addAction("鼠标穿透")
        click_through_action.setCheckable(True)
        click_through_action.setChecked(self.click_through)
        click_through_action.triggered.connect(self._toggle_click_through)

        menu.addSeparator()
        close_action = menu.addAction("关闭小组件")
        close_action.triggered.connect(self._on_close)

        menu.exec(event.globalPos())

    def _toggle_seconds(self):
        """切换秒数显示"""
        self.show_seconds = not self.show_seconds
        self.update_content()


class SystemMonitorWidget(BaseWidget):
    """系统监控小组件"""
    def __init__(self, widget_id: str, size: str = "medium"):
        super().__init__(widget_id, "系统监控", size)

    def _setup_ui(self):
        super()._setup_ui()

        # CPU
        self.cpu_label = QLabel("CPU: ---%")
        self.cpu_label.setStyleSheet(f"color: {theme.text_primary}; font-size: 14px;")

        # 内存
        self.mem_label = QLabel("内存: ---%")
        self.mem_label.setStyleSheet(f"color: {theme.text_primary}; font-size: 14px;")

        self.cpu_bar = QProgressBar()
        self.mem_bar = QProgressBar()
        self._apply_progress_style()

        self.cpu_bar.setMaximumHeight(8)
        self.cpu_bar.setTextVisible(False)
        self.mem_bar.setMaximumHeight(8)
        self.mem_bar.setTextVisible(False)

        self._main_layout.addWidget(self.cpu_label)
        self._main_layout.addWidget(self.cpu_bar)
        self._main_layout.addSpacing(8)
        self._main_layout.addWidget(self.mem_label)
        self._main_layout.addWidget(self.mem_bar)
        self._main_layout.addStretch()

    def _apply_progress_style(self):
        """应用进度条样式"""
        style = f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background: {theme.border};
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background: {theme.accent};
            }}
        """
        self.cpu_bar.setStyleSheet(style)
        self.mem_bar.setStyleSheet(style)

    def update_style(self):
        """更新样式"""
        super().update_style()
        self.cpu_label.setStyleSheet(f"color: {theme.text_primary}; font-size: 14px;")
        self.mem_label.setStyleSheet(f"color: {theme.text_primary}; font-size: 14px;")
        self._apply_progress_style()

    def update_content(self):
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()

        self.cpu_label.setText(f"CPU: {cpu_percent:.1f}%")
        self.cpu_bar.setValue(int(cpu_percent))

        self.mem_label.setText(f"内存: {mem.percent:.1f}%")
        self.mem_bar.setValue(int(mem.percent))


class TimerWidget(BaseWidget):
    """计时器小组件"""
    # 尺寸对应的字体大小
    FONT_SIZES = {
        "small": 24,
        "medium": 36,
        "large": 48
    }

    def __init__(self, widget_id: str, size: str = "medium"):
        self.timer_seconds = 0
        self.is_running = False
        super().__init__(widget_id, "计时器", size)

    def _setup_ui(self):
        super()._setup_ui()

        self.display = QLabel("00:00:00")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.start_btn = QPushButton("开始")
        self.start_btn.setFixedHeight(36)
        self.start_btn.clicked.connect(self._toggle_timer)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.setFixedHeight(36)
        self.reset_btn.clicked.connect(self._reset_timer)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addWidget(self.start_btn, 1)
        btn_layout.addWidget(self.reset_btn, 1)

        self._main_layout.addStretch()
        self._main_layout.addWidget(self.display)
        self._main_layout.addSpacing(12)
        self._main_layout.addLayout(btn_layout)
        self._main_layout.addStretch()

        self._apply_styles()

    def _apply_styles(self):
        """应用样式"""
        font_size = self.FONT_SIZES.get(self.size_key, 36)
        self.display.setStyleSheet(f"""
            font-size: {font_size}px;
            font-weight: 300;
            color: {theme.text_primary};
        """)
        btn_style = f"""
            QPushButton {{
                background: {theme.accent};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {theme.accent_hover};
            }}
            QPushButton:pressed {{
                background: {theme.text_primary};
            }}
        """
        self.start_btn.setStyleSheet(btn_style)
        self.reset_btn.setStyleSheet(btn_style)

    def update_style(self):
        """更新样式"""
        super().update_style()
        self._apply_styles()

    def _on_size_changed(self):
        self._apply_styles()

    def _toggle_timer(self):
        self.is_running = not self.is_running
        self.start_btn.setText("暂停" if self.is_running else "开始")

    def _reset_timer(self):
        self.is_running = False
        self.timer_seconds = 0
        self.start_btn.setText("开始")
        self.display.setText("00:00:00")

    def update_content(self):
        if self.is_running:
            self.timer_seconds += 1
        hours = self.timer_seconds // 3600
        minutes = (self.timer_seconds % 3600) // 60
        seconds = self.timer_seconds % 60
        self.display.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")


class NotesWidget(BaseWidget):
    """笔记小组件"""
    def __init__(self, widget_id: str, size: str = "medium"):
        self.note_text = ""
        super().__init__(widget_id, "笔记", size)

    def _setup_ui(self):
        super()._setup_ui()

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("在这里输入笔记...")
        self._apply_style()
        self.text_edit.textChanged.connect(self._save_note)

        self._main_layout.addWidget(self.text_edit)

    def _apply_style(self):
        """应用样式"""
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                color: {theme.text_primary};
                font-size: 14px;
            }}
        """)

    def update_style(self):
        """更新样式"""
        super().update_style()
        self._apply_style()

    def _on_size_changed(self):
        self._apply_style()

    def _save_note(self):
        self.note_text = self.text_edit.toPlainText()

    def update_content(self):
        pass


class ImageCropDialog(QDialog):
    """图片裁剪对话框 - 用于选择图片显示区域"""
    
    def __init__(self, image_path: str, target_ratio: float, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.target_ratio = target_ratio  # 目标宽高比 (width / height)
        self.original_pixmap = QPixmap(image_path)
        
        # 裁剪偏移量（相对于图片）
        self.crop_offset_x = 0
        self.crop_offset_y = 0
        self.crop_w = 0
        self.crop_h = 0
        
        # 拖动状态
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_start_offset = None
        
        # 显示比例（图片缩放比例）
        self.display_scale = 1.0
        
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("调整图片显示区域")
        self.setModal(True)
        self.setMinimumSize(500, 450)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 提示文字
        hint_label = QLabel("拖动图片以选择要显示的区域")
        hint_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 13px;")
        layout.addWidget(hint_label)
        
        # 裁剪预览区域 - 使用自定义widget
        self.preview_widget = CropPreviewWidget(self)
        self.preview_widget.setMinimumHeight(300)
        layout.addWidget(self.preview_widget, 1)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(100, 32)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.bg_card};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {theme.bg_hover};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("确认")
        confirm_btn.setFixedSize(100, 32)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {theme.accent_hover};
            }}
        """)
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)
        
        layout.addLayout(btn_layout)
        
        # 计算初始裁剪位置（居中）
        self._calculate_initial_crop()
        
    def _calculate_initial_crop(self):
        """计算初始裁剪位置"""
        if self.original_pixmap.isNull():
            return
            
        img_w = self.original_pixmap.width()
        img_h = self.original_pixmap.height()
        img_ratio = img_w / img_h
        
        # 计算裁剪区域（保持目标比例，覆盖整个图片）
        if img_ratio > self.target_ratio:
            # 图片更宽，以高度为准
            crop_h = img_h
            crop_w = int(crop_h * self.target_ratio)
        else:
            # 图片更高，以宽度为准
            crop_w = img_w
            crop_h = int(crop_w / self.target_ratio)
            
        self.crop_w = crop_w
        self.crop_h = crop_h
        
        # 初始居中
        self.crop_offset_x = (img_w - crop_w) // 2
        self.crop_offset_y = (img_h - crop_h) // 2
        
    def get_crop_rect(self) -> QRect:
        """获取裁剪区域"""
        return QRect(self.crop_offset_x, self.crop_offset_y, self.crop_w, self.crop_h)


class CropPreviewWidget(QFrame):
    """裁剪预览控件"""
    
    def __init__(self, dialog: ImageCropDialog):
        super().__init__()
        self.dialog = dialog
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
            }}
        """)
        self.setMouseTracking(True)
        
        # 拖动状态
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_start_offset = None
        
    def paintEvent(self, event):
        """绘制裁剪预览"""
        super().paintEvent(event)
        
        if self.dialog.original_pixmap.isNull():
            return
            
        preview_rect = self.rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 设置圆角裁剪
        painter.setClipRect(preview_rect)
        
        img_w = self.dialog.original_pixmap.width()
        img_h = self.dialog.original_pixmap.height()
        
        # 计算图片适应预览区域的缩放比例
        scale_x = preview_rect.width() / img_w
        scale_y = preview_rect.height() / img_h
        self.dialog.display_scale = min(scale_x, scale_y)
        
        display_w = int(img_w * self.dialog.display_scale)
        display_h = int(img_h * self.dialog.display_scale)
        
        # 图片显示位置（居中）
        display_x = (preview_rect.width() - display_w) // 2
        display_y = (preview_rect.height() - display_h) // 2
        
        # 绘制图片
        painter.drawPixmap(
            QRect(display_x, display_y, display_w, display_h),
            self.dialog.original_pixmap
        )
        
        # 计算裁剪框位置
        crop_display_x = display_x + int(self.dialog.crop_offset_x * self.dialog.display_scale)
        crop_display_y = display_y + int(self.dialog.crop_offset_y * self.dialog.display_scale)
        crop_display_w = int(self.dialog.crop_w * self.dialog.display_scale)
        crop_display_h = int(self.dialog.crop_h * self.dialog.display_scale)
        
        # 绘制半透明遮罩
        overlay_color = QColor(0, 0, 0, 150)
        painter.fillRect(preview_rect, overlay_color)
        
        # 清除裁剪区域的遮罩，显示原图
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(QRect(crop_display_x, crop_display_y, crop_display_w, crop_display_h), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        
        # 重新绘制裁剪区域的图片
        painter.drawPixmap(
            QRect(crop_display_x, crop_display_y, crop_display_w, crop_display_h),
            self.dialog.original_pixmap,
            QRect(self.dialog.crop_offset_x, self.dialog.crop_offset_y, self.dialog.crop_w, self.dialog.crop_h)
        )
        
        # 绘制裁剪框边框
        painter.setPen(QPen(QColor(theme.accent), 2))
        painter.drawRect(crop_display_x, crop_display_y, crop_display_w, crop_display_h)
        
        # 绘制网格线（三分法）
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
        third_w = crop_display_w // 3
        painter.drawLine(crop_display_x + third_w, crop_display_y,
                        crop_display_x + third_w, crop_display_y + crop_display_h)
        painter.drawLine(crop_display_x + third_w * 2, crop_display_y,
                        crop_display_x + third_w * 2, crop_display_y + crop_display_h)
        third_h = crop_display_h // 3
        painter.drawLine(crop_display_x, crop_display_y + third_h,
                        crop_display_x + crop_display_w, crop_display_y + third_h)
        painter.drawLine(crop_display_x, crop_display_y + third_h * 2,
                        crop_display_x + crop_display_w, crop_display_y + third_h * 2)
        
        painter.end()
        
    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_start_pos = event.pos()
            self.drag_start_offset = (self.dialog.crop_offset_x, self.dialog.crop_offset_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
                
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        if self.is_dragging and self.drag_start_pos:
            delta = event.pos() - self.drag_start_pos
            
            # 转换为图片坐标偏移
            delta_img_x = int(-delta.x() / self.dialog.display_scale)
            delta_img_y = int(-delta.y() / self.dialog.display_scale)
            
            # 计算新偏移量
            new_x = self.drag_start_offset[0] + delta_img_x
            new_y = self.drag_start_offset[1] + delta_img_y
            
            # 限制在图片范围内
            img_w = self.dialog.original_pixmap.width()
            img_h = self.dialog.original_pixmap.height()
            
            new_x = max(0, min(new_x, img_w - self.dialog.crop_w))
            new_y = max(0, min(new_y, img_h - self.dialog.crop_h))
            
            self.dialog.crop_offset_x = new_x
            self.dialog.crop_offset_y = new_y
            
            self.update()
            
        elif not self.is_dragging:
            # 鼠标悬停时显示手型光标
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            
    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            
    def leaveEvent(self, event):
        """鼠标离开"""
        if not self.is_dragging:
            self.setCursor(Qt.CursorShape.ArrowCursor)


class MusicWidget(BaseWidget):
    """音乐控制小组件 - 控制系统媒体播放"""
    def __init__(self, widget_id: str, size: str = "medium"):
        self.current_app = ""
        self.track_title = ""
        self.track_artist = ""
        self.is_playing = False
        super().__init__(widget_id, "音乐", size)

    def _setup_ui(self):
        super()._setup_ui()

        # 应用信息显示
        self.app_label = QLabel("无媒体播放")
        self.app_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 11px;
            background: transparent;
        """)
        self.app_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 歌曲信息
        self.track_label = QLabel("")
        self.track_label.setStyleSheet(f"""
            color: {theme.text_primary};
            font-size: 13px;
            font-weight: 500;
            background: transparent;
        """)
        self.track_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_label.setWordWrap(True)

        # 艺术家信息
        self.artist_label = QLabel("")
        self.artist_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 12px;
            background: transparent;
        """)
        self.artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 控制按钮容器
        controls = QHBoxLayout()
        controls.setSpacing(12)

        # 上一首按钮
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(40, 32)
        self.prev_btn.clicked.connect(self._prev_track)
        self.prev_btn.setToolTip("上一首")
        controls.addStretch()
        controls.addWidget(self.prev_btn)

        # 播放/暂停按钮
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(48, 32)
        self.play_btn.clicked.connect(self._toggle_play)
        self.play_btn.setToolTip("播放/暂停")
        controls.addWidget(self.play_btn)

        # 下一首按钮
        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(40, 32)
        self.next_btn.clicked.connect(self._next_track)
        self.next_btn.setToolTip("下一首")
        controls.addWidget(self.next_btn)
        controls.addStretch()

        # 添加到布局
        self._main_layout.addWidget(self.app_label)
        self._main_layout.addSpacing(4)
        self._main_layout.addWidget(self.track_label)
        self._main_layout.addWidget(self.artist_label)
        self._main_layout.addSpacing(10)
        self._main_layout.addLayout(controls)
        self._main_layout.addStretch()

        # 应用按钮样式
        self._style_button(self.prev_btn)
        self._style_button(self.play_btn, primary=True)
        self._style_button(self.next_btn)

        # 定时器获取媒体信息
        self.media_timer = QTimer(self)
        self.media_timer.timeout.connect(self._update_media_info)
        self.media_timer.start(1000)  # 每秒更新

    def _style_button(self, btn, primary=False):
        """设置按钮样式 - 优雅简约风格"""
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {theme.bg_hover};
                    color: {theme.text_primary};
                    border: 1px solid {theme.border};
                    border-radius: 20px;
                    font-size: 14px;
                    padding: 8px;
                }}
                QPushButton:hover {{
                    background: {theme.bg_pressed};
                    border-color: {theme.text_tertiary};
                }}
                QPushButton:pressed {{
                    background: {theme.bg_card};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {theme.text_secondary};
                    border: 1px solid {theme.border};
                    border-radius: 20px;
                    font-size: 14px;
                    padding: 8px;
                }}
                QPushButton:hover {{
                    background: {theme.bg_hover};
                    color: {theme.text_primary};
                }}
                QPushButton:pressed {{
                    background: {theme.bg_pressed};
                }}
            """)

    def _send_media_key(self, key_code):
        """发送媒体键 - 使用 keybd_event"""
        import ctypes

        KEYEVENTF_EXTENDEDKEY = 0x0001
        KEYEVENTF_KEYUP = 0x0002

        # 发送按键按下
        ctypes.windll.user32.keybd_event(key_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
        # 发送按键释放
        ctypes.windll.user32.keybd_event(key_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

    def _toggle_play(self):
        """播放/暂停"""
        VK_MEDIA_PLAY_PAUSE = 0xB3
        self._send_media_key(VK_MEDIA_PLAY_PAUSE)
        # 切换播放状态并更新按钮图标
        self.is_playing = not self.is_playing
        self._update_play_button()

    def _update_play_button(self):
        """更新播放按钮图标"""
        if self.is_playing:
            self.play_btn.setText("⏸")
            self.play_btn.setToolTip("暂停")
        else:
            self.play_btn.setText("▶")
            self.play_btn.setToolTip("播放")

    def _prev_track(self):
        """上一首"""
        VK_MEDIA_PREV_TRACK = 0xB1
        self._send_media_key(VK_MEDIA_PREV_TRACK)

    def _next_track(self):
        """下一首"""
        VK_MEDIA_NEXT_TRACK = 0xB0
        self._send_media_key(VK_MEDIA_NEXT_TRACK)

    def _update_media_info(self):
        """更新媒体信息"""
        try:
            # 尝试获取当前播放的媒体信息
            from pycaw.pycaw import AudioUtilities
            sessions = AudioUtilities.GetAllSessions()

            found_media = False
            was_playing = self.is_playing
            self.is_playing = False

            for session in sessions:
                if session.Process:
                    process_name = session.Process.name()
                    # 检查常见的媒体播放器
                    media_players = [
                        'Spotify.exe', 'Music.UI.exe', 'AIMP.exe', 'foobar2000.exe',
                        'Winamp.exe', 'vlc.exe', 'MusicBee.exe', 'AppleMusic.exe',
                        'YouTube Music.exe', 'NeteaseCloudMusic.exe', 'cloudmusic.exe',
                        'QQMusic.exe', 'KuGou.exe', 'KwMusic.exe'
                    ]
                    if process_name in media_players or 'music' in process_name.lower():
                        # 检查音频会话状态
                        try:
                            volume = session.SimpleAudioVolume
                            if volume and volume.GetMasterVolume() > 0:
                                # 获取音频会话状态
                                state = session.State
                                # State: 0 = Inactive, 1 = Active, 2 = Expired
                                if state == 1:  # Active
                                    self.is_playing = True
                        except:
                            self.is_playing = True  # 默认认为在播放

                        app_name = process_name.replace('.exe', '')
                        self.current_app = app_name
                        self.app_label.setText(app_name)
                        found_media = True
                        break

            if not found_media:
                self.app_label.setText("无媒体播放")
                self.track_label.setText("")
                self.artist_label.setText("")
                self.is_playing = False

            # 更新按钮图标
            if was_playing != self.is_playing:
                self._update_play_button()

        except Exception:
            pass

    def update_style(self):
        """更新样式"""
        super().update_style()
        self._style_button(self.prev_btn)
        self._style_button(self.play_btn, primary=True)
        self._style_button(self.next_btn)

    def update_content(self):
        pass


class WeatherWidget(BaseWidget):
    """天气小组件 - 显示实时天气信息"""
    def __init__(self, widget_id: str, size: str = "medium"):
        self.weather_data = {}
        self.location = "北京"
        self._fetch_thread = None
        super().__init__(widget_id, "天气", size)

    def _setup_ui(self):
        super()._setup_ui()

        # 天气图标和温度
        header_layout = QHBoxLayout()

        self.weather_icon = QLabel("N/A")
        self.weather_icon.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 500;
            color: {theme.accent};
            background: transparent;
        """)
        header_layout.addWidget(self.weather_icon)

        self.temp_label = QLabel("--°")
        self.temp_label.setStyleSheet(f"""
            color: {theme.text_primary};
            font-size: 28px;
            font-weight: 300;
            background: transparent;
        """)
        header_layout.addWidget(self.temp_label)
        header_layout.addStretch()

        self._main_layout.addLayout(header_layout)

        # 天气描述
        self.desc_label = QLabel("加载中...")
        self.desc_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 13px;
            background: transparent;
        """)
        self._main_layout.addWidget(self.desc_label)

        # 位置
        self.location_label = QLabel(self.location)
        self.location_label.setStyleSheet(f"""
            color: {theme.text_tertiary};
            font-size: 11px;
            background: transparent;
        """)
        self._main_layout.addWidget(self.location_label)

        # 详细信息
        details_layout = QHBoxLayout()
        details_layout.setSpacing(16)

        self.humidity_label = QLabel("湿度 --%")
        self.humidity_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 11px;
            background: transparent;
        """)
        details_layout.addWidget(self.humidity_label)

        self.wind_label = QLabel("风速 --km/h")
        self.wind_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 11px;
            background: transparent;
        """)
        details_layout.addWidget(self.wind_label)

        details_layout.addStretch()
        self._main_layout.addLayout(details_layout)
        self._main_layout.addStretch()

        # 定时更新天气
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self._start_fetch)
        self.weather_timer.start(300000)  # 每5分钟更新

        # 初始获取（异步）
        QTimer.singleShot(500, self._start_fetch)

    def _start_fetch(self):
        """异步获取天气数据"""
        from threading import Thread

        def fetch():
            try:
                import urllib.request
                import json

                url = f"https://wttr.in/{urllib.parse.quote(self.location)}?format=j1"
                req = urllib.request.Request(url, headers={'User-Agent': 'curl'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))

                current = data.get('current_condition', [{}])[0]
                self.weather_data = {
                    'temp': current.get('temp_C', '--'),
                    'desc': current.get('weatherDesc', [{}])[0].get('value', '未知'),
                    'humidity': current.get('humidity', '--'),
                    'wind': current.get('windspeedKmph', '--'),
                    'code': current.get('weatherCode', '113')
                }

                # 在主线程更新UI
                QTimer.singleShot(0, self._update_display)
            except Exception as e:
                QTimer.singleShot(0, lambda: self.desc_label.setText("获取失败"))
                logger.error(f"获取天气失败: {e}")

        thread = Thread(target=fetch, daemon=True)
        thread.start()

    def _get_weather_text(self, code):
        """根据天气代码获取文字描述"""
        code = int(code) if str(code).isdigit() else 113
        texts = {
            113: "晴",
            116: "多云",
            119: "阴",
            122: "阴",
            143: "雾",
            176: "小雨",
            179: "小雪",
            182: "雨夹雪",
            185: "雨夹雪",
            200: "雷雨",
            227: "暴风雪",
            230: "暴风雪",
            248: "雾",
            260: "雾",
            263: "小雨",
            266: "小雨",
            281: "雨夹雪",
            284: "雨夹雪",
            293: "小雨",
            296: "小雨",
            299: "中雨",
            302: "中雨",
            305: "大雨",
            308: "大雨",
            311: "大雨",
            314: "大雨",
            317: "中雪",
            320: "中雪",
            323: "小雪",
            326: "小雪",
            329: "中雪",
            332: "中雪",
            335: "大雪",
            338: "大雪",
            350: "冰雹",
            353: "中雨",
            356: "大雨",
            359: "暴雨",
            362: "中雪",
            365: "大雪",
            368: "小雪",
            371: "大雪",
            374: "冰雹",
            377: "冰雹",
            386: "雷雨",
            389: "雷雨",
            392: "雷雪",
            395: "雷雪",
        }
        return texts.get(code, "未知")

    def _update_display(self):
        """更新显示"""
        data = self.weather_data
        weather_text = self._get_weather_text(data.get('code', '113'))
        self.weather_icon.setText(weather_text)
        self.temp_label.setText(f"{data.get('temp', '--')}°")
        self.desc_label.setText(data.get('desc', '未知'))
        self.humidity_label.setText(f"湿度 {data.get('humidity', '--')}%")
        self.wind_label.setText(f"风速 {data.get('wind', '--')}km/h")

    def update_style(self):
        """更新样式"""
        super().update_style()

    def update_content(self):
        pass


class TodoWidget(BaseWidget):
    """待办清单小组件"""
    def __init__(self, widget_id: str, size: str = "medium"):
        self.todos = []
        self._load_todos()
        super().__init__(widget_id, "待办", size)

    def _load_todos(self):
        """从配置加载待办"""
        for w in config.widgets:
            if w.get("id") == self.widget_id:
                self.todos = w.get("todos", [])
                break

    def _setup_ui(self):
        super()._setup_ui()

        # 输入框
        self.input = QLineEdit()
        self.input.setPlaceholderText("添加新任务...")
        self.input.returnPressed.connect(self._add_todo)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                color: {theme.text_primary};
            }}
            QLineEdit:focus {{
                border-color: {theme.accent};
            }}
        """)
        self._main_layout.addWidget(self.input)

        # 待办列表
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._toggle_todo)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 6px;
                border-bottom: 1px solid {theme.border};
            }}
            QListWidget::item:selected {{
                background: {theme.bg_hover};
            }}
        """)
        self._main_layout.addWidget(self.list_widget)
        self._update_list()

        # 清除已完成按钮
        self.clear_btn = QPushButton("清除已完成")
        self.clear_btn.clicked.connect(self._clear_completed)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.text_secondary};
                border: none;
                font-size: 11px;
                padding: 4px;
            }}
            QPushButton:hover {{
                color: {theme.accent};
            }}
        """)
        self._main_layout.addWidget(self.clear_btn)

    def _add_todo(self):
        """添加待办"""
        text = self.input.text().strip()
        if text:
            self.todos.append({"text": text, "done": False})
            self.input.clear()
            self._update_list()
            self._save_todos()

    def _update_list(self):
        """更新列表显示"""
        self.list_widget.clear()
        for i, todo in enumerate(self.todos):
            item = QListWidgetItem(f"{'✓ ' if todo['done'] else '○ '}{todo['text']}")
            if todo['done']:
                item.setForeground(QColor(theme.text_tertiary))
            self.list_widget.addItem(item)

    def _toggle_todo(self, item):
        """切换待办状态"""
        idx = self.list_widget.row(item)
        if 0 <= idx < len(self.todos):
            self.todos[idx]['done'] = not self.todos[idx]['done']
            self._update_list()
            self._save_todos()

    def _clear_completed(self):
        """清除已完成"""
        self.todos = [t for t in self.todos if not t['done']]
        self._update_list()
        self._save_todos()

    def _save_todos(self):
        """保存待办"""
        # 保存到配置
        for w in config.widgets:
            if w.get("id") == self.widget_id:
                w["todos"] = self.todos
                break
        config.save()

    def update_style(self):
        """更新样式"""
        super().update_style()

    def update_content(self):
        pass


class AlarmWidget(BaseWidget):
    """倒计时小组件"""
    def __init__(self, widget_id: str, size: str = "medium"):
        self.target_time = None
        self.remaining_seconds = 0
        self.is_running = False
        super().__init__(widget_id, "倒计时", size)

    def _setup_ui(self):
        super()._setup_ui()

        # 倒计时显示
        self._main_layout.addStretch()
        self.display = QLabel("00:00:00")
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"""
            font-size: 36px;
            font-weight: 200;
            color: {theme.text_primary};
            background: transparent;
            letter-spacing: 2px;
        """)
        self._main_layout.addWidget(self.display)
        self._main_layout.addSpacing(12)

        # 时间设置容器
        time_container = QWidget()
        time_layout = QHBoxLayout(time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(8)

        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setValue(0)
        self.hour_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_layout.addWidget(self.hour_spin)

        colon1 = QLabel(":")
        colon1.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px; background: transparent;")
        time_layout.addWidget(colon1)

        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 59)
        self.min_spin.setValue(5)
        self.min_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_layout.addWidget(self.min_spin)

        colon2 = QLabel(":")
        colon2.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px; background: transparent;")
        time_layout.addWidget(colon2)

        self.sec_spin = QSpinBox()
        self.sec_spin.setRange(0, 59)
        self.sec_spin.setValue(0)
        self.sec_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_layout.addWidget(self.sec_spin)

        self._main_layout.addWidget(time_container)
        self._main_layout.addSpacing(16)

        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.start_btn = QPushButton("开始")
        self.start_btn.clicked.connect(self._toggle)
        btn_layout.addWidget(self.start_btn, 1)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self._reset)
        btn_layout.addWidget(self.reset_btn, 1)

        self._main_layout.addLayout(btn_layout)
        self._main_layout.addStretch()

        # 定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self._apply_styles()

    def _apply_styles(self):
        """应用样式 - 优雅简约风格"""
        spin_style = f"""
            QSpinBox {{
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 6px 4px;
                font-size: 13px;
                color: {theme.text_primary};
                min-width: 36px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 16px;
                background: transparent;
            }}
            QSpinBox:hover {{
                border-color: {theme.text_tertiary};
            }}
        """
        # 优雅的按钮样式 - 使用边框而非填充色
        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {theme.bg_hover};
                border-color: {theme.text_tertiary};
            }}
            QPushButton:pressed {{
                background: {theme.bg_pressed};
            }}
        """
        # 主按钮样式 - 稍微突出但不刺眼
        start_btn_style = f"""
            QPushButton {{
                background: {theme.bg_hover};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {theme.bg_pressed};
                border-color: {theme.text_tertiary};
            }}
            QPushButton:pressed {{
                background: {theme.bg_card};
            }}
        """
        self.hour_spin.setStyleSheet(spin_style)
        self.min_spin.setStyleSheet(spin_style)
        self.sec_spin.setStyleSheet(spin_style)
        self.start_btn.setStyleSheet(start_btn_style)
        self.reset_btn.setStyleSheet(btn_style)

    def _toggle(self):
        """开始/暂停"""
        if self.is_running:
            self.timer.stop()
            self.is_running = False
            self.start_btn.setText("继续")
        else:
            if self.remaining_seconds == 0:
                self.remaining_seconds = (self.hour_spin.value() * 3600 +
                                         self.min_spin.value() * 60 +
                                         self.sec_spin.value())
            if self.remaining_seconds > 0:
                self.timer.start(1000)
                self.is_running = True
                self.start_btn.setText("暂停")

    def _reset(self):
        """重置"""
        self.timer.stop()
        self.is_running = False
        self.remaining_seconds = 0
        self.start_btn.setText("开始")
        self.display.setText("00:00:00")

    def _tick(self):
        """计时"""
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            h = self.remaining_seconds // 3600
            m = (self.remaining_seconds % 3600) // 60
            s = self.remaining_seconds % 60
            self.display.setText(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self.timer.stop()
            self.is_running = False
            self.start_btn.setText("开始")
            # 播放提示音和弹窗
            self._on_timer_end()

    def _on_timer_end(self):
        """倒计时结束处理"""
        # 播放系统提示音
        try:
            import winsound
            # 播放系统默认通知音
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except:
            pass

        # 显示弹窗提示
        self._show_notification()

    def _show_notification(self):
        """显示倒计时结束通知"""
        from PyQt6.QtWidgets import QMessageBox

        # 创建自定义消息框
        msg = QMessageBox(self)
        msg.setWindowTitle("倒计时结束")
        msg.setText("时间到！")
        msg.setInformativeText("您的倒计时已完成。")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStyleSheet(f"""
            QMessageBox {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 12px;
            }}
            QMessageBox QLabel {{
                color: {theme.text_primary};
                font-size: 14px;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
            }}
            QPushButton {{
                background-color: {theme.bg_card};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {theme.bg_hover};
                border-color: {theme.text_tertiary};
            }}
            QPushButton:pressed {{
                background-color: {theme.bg_pressed};
            }}
        """)
        msg.exec()

        # 让窗口闪烁提醒
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.FlashWindow(hwnd, True)
        except:
            pass

    def update_style(self):
        """更新样式"""
        super().update_style()
        self._apply_styles()

    def update_content(self):
        pass


class WorldClockWidget(BaseWidget):
    """世界时钟小组件"""
    TIMEZONES = {
        "北京": 8, "东京": 9, "纽约": -5, "伦敦": 0, "巴黎": 1,
        "悉尼": 11, "迪拜": 4, "莫斯科": 3, "新加坡": 8, "洛杉矶": -8
    }

    def __init__(self, widget_id: str, size: str = "medium"):
        self.selected_city = "纽约"
        super().__init__(widget_id, "世界时钟", size)

    def _setup_ui(self):
        super()._setup_ui()

        # 城市选择
        self.city_combo = QComboBox()
        self.city_combo.addItems(list(self.TIMEZONES.keys()))
        self.city_combo.setCurrentText(self.selected_city)
        self.city_combo.currentTextChanged.connect(self._on_city_changed)
        self.city_combo.setStyleSheet(f"""
            QComboBox {{
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                color: {theme.text_primary};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """)
        self._main_layout.addWidget(self.city_combo)

        # 时间显示
        self.time_label = QLabel("--:--:--")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet(f"""
            font-size: 32px;
            font-weight: 300;
            color: {theme.text_primary};
            background: transparent;
        """)
        self._main_layout.addWidget(self.time_label)

        # 日期显示
        self.date_label = QLabel("")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setStyleSheet(f"""
            font-size: 12px;
            color: {theme.text_secondary};
            background: transparent;
        """)
        self._main_layout.addWidget(self.date_label)

        # 时差显示
        self.diff_label = QLabel("")
        self.diff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diff_label.setStyleSheet(f"""
            font-size: 11px;
            color: {theme.text_tertiary};
            background: transparent;
        """)
        self._main_layout.addWidget(self.diff_label)
        self._main_layout.addStretch()

        # 更新定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_time)
        self.timer.start(1000)
        self._update_time()

    def _on_city_changed(self, city):
        """城市改变"""
        self.selected_city = city
        self._update_time()

    def _update_time(self):
        """更新时间"""
        from datetime import datetime, timedelta
        import time

        utc_now = datetime.utcnow()
        target_offset = self.TIMEZONES.get(self.selected_city, 0)
        target_time = utc_now + timedelta(hours=target_offset)

        self.time_label.setText(target_time.strftime("%H:%M:%S"))
        self.date_label.setText(target_time.strftime("%Y年%m月%d日 %A"))

        # 计算时差
        local_offset = time.timezone // -3600  # 本地时区偏移
        diff = target_offset - local_offset
        if diff == 0:
            self.diff_label.setText("与本地时间相同")
        elif diff > 0:
            self.diff_label.setText(f"比本地快 {diff} 小时")
        else:
            self.diff_label.setText(f"比本地慢 {abs(diff)} 小时")

    def update_style(self):
        """更新样式"""
        super().update_style()

    def update_content(self):
        pass


class NetworkMonitorWidget(BaseWidget):
    """网络速度监控小组件"""
    def __init__(self, widget_id: str, size: str = "medium"):
        self.last_bytes_sent = 0
        self.last_bytes_recv = 0
        super().__init__(widget_id, "网络监控", size)

    def _setup_ui(self):
        super()._setup_ui()

        # 下载速度
        self.download_label = QLabel("↓ 0 KB/s")
        self.download_label.setStyleSheet(f"""
            color: {theme.accent};
            font-size: 14px;
            font-weight: 500;
            background: transparent;
        """)
        self._main_layout.addWidget(self.download_label)

        # 上传速度
        self.upload_label = QLabel("↑ 0 KB/s")
        self.upload_label.setStyleSheet(f"""
            color: {theme.success};
            font-size: 14px;
            font-weight: 500;
            background: transparent;
        """)
        self._main_layout.addWidget(self.upload_label)

        self._main_layout.addSpacing(8)

        # 磁盘使用率
        self.disk_label = QLabel("磁盘: --")
        self.disk_label.setStyleSheet(f"""
            color: {theme.text_secondary};
            font-size: 11px;
            background: transparent;
        """)
        self._main_layout.addWidget(self.disk_label)

        self._main_layout.addStretch()

        # 初始化网络计数
        net = psutil.net_io_counters()
        self.last_bytes_sent = net.bytes_sent
        self.last_bytes_recv = net.bytes_recv

        # 更新定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_stats)
        self.timer.start(1000)
        self._update_stats()

    def _format_speed(self, bytes_per_sec):
        """格式化速度"""
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec / 1024 / 1024:.1f} MB/s"

    def _update_stats(self):
        """更新统计"""
        # 网络速度
        net = psutil.net_io_counters()
        download_speed = net.bytes_recv - self.last_bytes_recv
        upload_speed = net.bytes_sent - self.last_bytes_sent
        self.last_bytes_recv = net.bytes_recv
        self.last_bytes_sent = net.bytes_sent

        self.download_label.setText(f"↓ {self._format_speed(download_speed)}")
        self.upload_label.setText(f"↑ {self._format_speed(upload_speed)}")

        # 磁盘使用率
        try:
            disk = psutil.disk_usage('C:')
            used_gb = disk.used / (1024 ** 3)
            total_gb = disk.total / (1024 ** 3)
            percent = disk.percent
            self.disk_label.setText(f"磁盘 C: {used_gb:.0f}/{total_gb:.0f} GB ({percent}%)")
        except:
            pass

    def update_style(self):
        """更新样式"""
        super().update_style()

    def update_content(self):
        pass


class ImageWidget(BaseWidget):
    """图片小组件 - 支持自定义背景图片"""
    def __init__(self, widget_id: str, size: str = "medium"):
        self.image_path = ""
        self.crop_rect = None  # 裁剪区域 (x, y, width, height)
        self.filter_type = "none"  # none, grayscale, sepia, blur
        super().__init__(widget_id, "图片", size)

    def _setup_ui(self):
        super()._setup_ui()
        # 不添加任何按钮，保持空白界面
        self._main_layout.addStretch()
        
    def _get_widget_ratio(self) -> float:
        """获取小组件的宽高比（使用实际窗口大小）"""
        # 使用实际内容区域大小（支持拖拽调整大小）
        if hasattr(self, '_content_width') and hasattr(self, '_content_height'):
            return self._content_width / self._content_height
        # 回退到 SIZE_MAP
        w, h = self.SIZE_MAP.get(self.size_key, (220, 220))
        return w / h

    def _select_image(self):
        """选择图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;所有文件 (*)"
        )

        if file_path:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                return
                
            # 计算图片和小组件的比例
            img_ratio = pixmap.width() / pixmap.height()
            widget_ratio = self._get_widget_ratio()
            
            # 判断比例是否匹配（允许5%误差）
            ratio_diff = abs(img_ratio - widget_ratio) / widget_ratio
            
            if ratio_diff > 0.05:
                # 比例不匹配，弹出裁剪对话框
                dialog = ImageCropDialog(file_path, widget_ratio, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.image_path = file_path
                    self.crop_rect = dialog.get_crop_rect()
                else:
                    return  # 用户取消
            else:
                # 比例匹配，直接使用
                self.image_path = file_path
                self.crop_rect = None
                
            self.update()

            # 保存配置
            for widget_config in config.widgets:
                if widget_config.get("id") == self.widget_id:
                    widget_config["image_path"] = self.image_path
                    if self.crop_rect:
                        widget_config["crop_rect"] = [
                            self.crop_rect.x(), self.crop_rect.y(),
                            self.crop_rect.width(), self.crop_rect.height()
                        ]
                    else:
                        widget_config["crop_rect"] = None
                    break
            config.save()

    def _clear_image(self):
        """清除图片"""
        self.image_path = ""
        self.crop_rect = None
        self.update()

        # 保存配置
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["image_path"] = ""
                widget_config["crop_rect"] = None
                break
        config.save()

    def paintEvent(self, event):
        """绘制背景图片或水印提示"""
        # 先调用父类的 paintEvent 绘制默认背景
        super().paintEvent(event)

        m = self.SHADOW_MARGIN
        content_rect = QRect(m, m, self.width() - m * 2, self.height() - m * 2)
        corner_radius = 16  # 圆角半径

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self.image_path:
            # 有图片，绘制图片背景（带圆角）
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                # 创建圆角矩形路径作为裁剪区域
                from PyQt6.QtGui import QPainterPath
                clip_path = QPainterPath()
                clip_path.addRoundedRect(content_rect.x(), content_rect.y(), 
                                          content_rect.width(), content_rect.height(),
                                          corner_radius, corner_radius)
                painter.setClipPath(clip_path)

                if self.crop_rect:
                    # 使用裁剪区域绘制
                    cropped = pixmap.copy(self.crop_rect)
                    scaled_pixmap = cropped.scaled(
                        content_rect.size(),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                else:
                    # 无裁剪区域，按比例缩放填充
                    scaled_pixmap = pixmap.scaled(
                        content_rect.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )

                # 应用滤镜
                if self.filter_type != "none":
                    scaled_pixmap = self._apply_filter(scaled_pixmap)

                painter.drawPixmap(content_rect, scaled_pixmap, scaled_pixmap.rect())
        else:
            # 没有图片，绘制水印提示
            painter.setClipRect(content_rect)

            # 计算整体布局（图标 + 文字）
            icon_size = 40
            text_height = 20
            total_height = icon_size + 10 + text_height

            # 计算起始位置（整体垂直居中）
            start_y = content_rect.center().y() - total_height // 2

            # 绘制图片图标
            icon_rect = QRect(
                content_rect.center().x() - icon_size // 2,
                start_y,
                icon_size,
                icon_size
            )

            painter.setPen(QPen(QColor(theme.text_tertiary), 2))
            painter.drawRect(icon_rect)
            # 绘制山形
            painter.drawLine(icon_rect.left() + 5, icon_rect.bottom() - 10,
                           icon_rect.center().x(), icon_rect.top() + 15)
            painter.drawLine(icon_rect.center().x(), icon_rect.top() + 15,
                           icon_rect.right() - 5, icon_rect.bottom() - 10)
            # 绘制太阳
            painter.drawEllipse(icon_rect.topLeft() + QPoint(8, 8), 5, 5)

            # 绘制提示文字（在图标下方）
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QColor(theme.text_tertiary))
            text_rect = QRect(
                content_rect.left(),
                start_y + icon_size + 10,
                content_rect.width(),
                text_height
            )
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                "右键添加图片"
            )

        painter.end()

    def contextMenuEvent(self, event):
        """右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 6px 4px;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 8px 28px 8px 16px;
                border-radius: 4px;
                background: transparent;
                color: {theme.text_primary};
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.bg_hover};
            }}
            QMenu::item:pressed {{
                background-color: {theme.bg_pressed};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {theme.border};
                margin: 4px 12px;
            }}
        """)

        # 选择图片
        select_action = menu.addAction("选择图片")
        select_action.triggered.connect(self._select_image)

        # 清除图片（仅在已有图片时显示）
        if self.image_path:
            clear_action = menu.addAction("清除图片")
            clear_action.triggered.connect(self._clear_image)

        menu.addSeparator()

        # 鼠标穿透选项
        click_through_action = menu.addAction("鼠标穿透")
        click_through_action.setCheckable(True)
        click_through_action.setChecked(self.click_through)
        click_through_action.triggered.connect(self._toggle_click_through)

        menu.addSeparator()

        # 窗口层级选项
        top_action = menu.addAction("置顶显示")
        top_action.triggered.connect(self._bring_to_top)

        bottom_action = menu.addAction("置底显示")
        bottom_action.triggered.connect(self._send_to_bottom)

        menu.addSeparator()

        close_action = menu.addAction("关闭小组件")
        close_action.triggered.connect(self._on_close)

        menu.exec(event.globalPos())

    def update_content(self):
        pass

    def resizeEvent(self, event):
        """窗口大小改变时重新计算裁剪区域"""
        super().resizeEvent(event)

        # 如果有图片且有裁剪区域，需要重新计算
        if hasattr(self, 'image_path') and self.image_path and self.crop_rect:
            # 获取新的宽高比
            new_ratio = self._get_widget_ratio()

            # 加载原始图片
            pixmap = QPixmap(self.image_path)
            if pixmap.isNull():
                return

            # 计算新的裁剪区域（保持居中）
            img_w = pixmap.width()
            img_h = pixmap.height()
            img_ratio = img_w / img_h

            if new_ratio > img_ratio:
                # 新窗口更宽，裁剪高度
                crop_h = int(img_w / new_ratio)
                crop_w = img_w
                crop_x = 0
                crop_y = (img_h - crop_h) // 2
            else:
                # 新窗口更高，裁剪宽度
                crop_w = int(img_h * new_ratio)
                crop_h = img_h
                crop_x = (img_w - crop_w) // 2
                crop_y = 0

            self.crop_rect = QRect(crop_x, crop_y, crop_w, crop_h)
            self.update()

            # 保存新的裁剪区域
            for widget_config in config.widgets:
                if widget_config.get("id") == self.widget_id:
                    widget_config["crop_rect"] = [
                        self.crop_rect.x(), self.crop_rect.y(),
                        self.crop_rect.width(), self.crop_rect.height()
                    ]
                    break
            config.save()

    def _apply_filter(self, pixmap):
        """应用滤镜效果"""
        from PyQt6.QtGui import QImage

        img = pixmap.toImage()
        result = QImage(img.size(), QImage.Format.Format_ARGB32)

        for y in range(img.height()):
            for x in range(img.width()):
                color = img.pixelColor(x, y)
                r, g, b = color.red(), color.green(), color.blue()

                if self.filter_type == "grayscale":
                    gray = int(0.299 * r + 0.587 * g + 0.114 * b)
                    color = QColor(gray, gray, gray, color.alpha())
                elif self.filter_type == "sepia":
                    nr = min(255, int(0.393 * r + 0.769 * g + 0.189 * b))
                    ng = min(255, int(0.349 * r + 0.686 * g + 0.168 * b))
                    nb = min(255, int(0.272 * r + 0.534 * g + 0.131 * b))
                    color = QColor(nr, ng, nb, color.alpha())
                elif self.filter_type == "invert":
                    color = QColor(255 - r, 255 - g, 255 - b, color.alpha())

                result.setPixelColor(x, y, color)

        return QPixmap.fromImage(result)

    def _set_filter(self, filter_type):
        """设置滤镜"""
        self.filter_type = filter_type
        self.update()

        # 保存配置
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                widget_config["filter_type"] = filter_type
                break
        config.save()

    def _get_context_menu(self):
        """获取右键菜单"""
        menu = super()._get_context_menu()
        menu.addSeparator()

        # 滤镜子菜单
        filter_menu = menu.addMenu("滤镜效果")
        filters = [("无", "none"), ("灰度", "grayscale"), ("复古", "sepia"), ("反色", "invert")]
        for name, ftype in filters:
            action = filter_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(self.filter_type == ftype)
            action.triggered.connect(lambda checked, f=ftype: self._set_filter(f))

        return menu

    def _load_config(self):
        """从配置加载"""
        for widget_config in config.widgets:
            if widget_config.get("id") == self.widget_id:
                self.image_path = widget_config.get("image_path", "")
                self.filter_type = widget_config.get("filter_type", "none")
                crop = widget_config.get("crop_rect")
                if crop:
                    self.crop_rect = QRect(crop[0], crop[1], crop[2], crop[3])
                break


if WEBENGINE_AVAILABLE:
    class WebWidget(BaseWidget):
        """网页小组件 - 显示网页内容"""
        def __init__(self, widget_id: str, size: str = "xlarge"):
            self.url = ""
            self.web_view = None
            self.url_input = None
            self.control_bar = None
            super().__init__(widget_id, "网页", size)

        def _setup_ui(self):
            super()._setup_ui()

            # 创建网页视图
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet(f"""
                QWebEngineView {{
                    background-color: transparent;
                    border: none;
                }}
            """)
            # 设置初始缩放因子（基于 1920px 宽度的网页设计）
            self._base_zoom = 1.0

            # 创建控制栏
            self.control_bar = QFrame()
            self.control_bar.setStyleSheet(f"""
                QFrame {{
                    background-color: {theme.bg_card};
                    border: none;
                    border-radius: 4px;
                }}
                QLineEdit {{
                    background-color: {theme.bg_input};
                    border: 1px solid {theme.border};
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: {theme.text_primary};
                    font-size: 12px;
                }}
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: {theme.text_primary};
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.bg_hover};
                }}
            """)

            control_layout = QHBoxLayout(self.control_bar)
            control_layout.setContentsMargins(8, 4, 8, 4)
            control_layout.setSpacing(4)

            # 后退按钮
            self.back_btn = QPushButton("←")
            self.back_btn.setFixedSize(28, 24)
            self.back_btn.clicked.connect(self._go_back)
            self.back_btn.setToolTip("后退")
            control_layout.addWidget(self.back_btn)

            # 前进按钮
            self.forward_btn = QPushButton("→")
            self.forward_btn.setFixedSize(28, 24)
            self.forward_btn.clicked.connect(self._go_forward)
            self.forward_btn.setToolTip("前进")
            control_layout.addWidget(self.forward_btn)

            # 刷新按钮
            self.refresh_btn = QPushButton("⟳")
            self.refresh_btn.setFixedSize(28, 24)
            self.refresh_btn.clicked.connect(self._refresh)
            self.refresh_btn.setToolTip("刷新")
            control_layout.addWidget(self.refresh_btn)

            # 网址输入框
            self.url_input = QLineEdit()
            self.url_input.setPlaceholderText("输入网址...")
            self.url_input.returnPressed.connect(self._load_url)
            control_layout.addWidget(self.url_input, 1)

            # 访问按钮
            self.go_btn = QPushButton("访问")
            self.go_btn.clicked.connect(self._load_url)
            control_layout.addWidget(self.go_btn)

            # 添加到布局
            self._main_layout.addWidget(self.control_bar)
            self._main_layout.addWidget(self.web_view, 1)

            # 默认显示提示页面
            self._show_placeholder()

        def _show_placeholder(self):
            """显示占位页面"""
            html = f"""
            <html>
            <head>
                <style>
                    body {{
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background-color: {theme.bg_card};
                        font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                        color: {theme.text_secondary};
                    }}
                    .hint {{
                        font-size: 14px;
                        opacity: 0.7;
                    }}
                </style>
            </head>
            <body>
                <div class="hint">在上方输入网址开始浏览</div>
            </body>
            </html>
            """
            self.web_view.setHtml(html)

        def _load_url(self):
            """加载网址"""
            url = self.url_input.text().strip()
            if not url:
                return

            # 自动添加协议
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            self.url = url
            from PyQt6.QtCore import QUrl
            self.web_view.setUrl(QUrl(url))

            # 保存配置
            for widget_config in config.widgets:
                if widget_config.get("id") == self.widget_id:
                    widget_config["url"] = self.url
                    break
            config.save()

        def _go_back(self):
            """后退"""
            if self.web_view:
                self.web_view.back()

        def _go_forward(self):
            """前进"""
            if self.web_view:
                self.web_view.forward()

        def _refresh(self):
            """刷新"""
            if self.web_view:
                self.web_view.reload()

        def load_config(self, widget_config: dict):
            """加载配置"""
            url = widget_config.get("url", "")
            if url:
                self.url = url
                self.url_input.setText(url)
                from PyQt6.QtCore import QUrl
                self.web_view.setUrl(QUrl(url))

        def _context_menu(self, event):
            """右键菜单"""
            from PyQt6.QtWidgets import QMenu

            menu = QMenu(self)
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {theme.bg_card};
                    border: 1px solid {theme.border};
                    border-radius: 8px;
                    padding: 6px 4px;
                    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                    font-size: 13px;
                }}
                QMenu::item {{
                    padding: 6px 24px;
                    border-radius: 4px;
                }}
                QMenu::item:selected {{
                    background-color: {theme.bg_hover};
                }}
            """)

            # 控制栏显示/隐藏
            control_action = menu.addAction("显示控制栏")
            control_action.setCheckable(True)
            control_action.setChecked(self.control_bar.isVisible())
            control_action.triggered.connect(self._toggle_control_bar)

            menu.addSeparator()

            # 鼠标穿透选项
            click_through_action = menu.addAction("鼠标穿透")
            click_through_action.setCheckable(True)
            click_through_action.setChecked(self.click_through)
            click_through_action.triggered.connect(self._toggle_click_through)

            menu.addSeparator()

            # 窗口层级选项
            top_action = menu.addAction("置顶显示")
            top_action.triggered.connect(self._bring_to_top)

            bottom_action = menu.addAction("置底显示")
            bottom_action.triggered.connect(self._send_to_bottom)

            menu.addSeparator()

            close_action = menu.addAction("关闭小组件")
            close_action.triggered.connect(self._on_close)

            menu.exec(event.globalPos())

        def _toggle_control_bar(self):
            """切换控制栏显示"""
            if self.control_bar:
                self.control_bar.setVisible(not self.control_bar.isVisible())

        def update_content(self):
            pass

        def resizeEvent(self, event):
            """组件大小变化时自动调整网页缩放"""
            super().resizeEvent(event)
            if self.web_view:
                # 基于组件宽度计算缩放比例（以 480px 为基准）
                base_width = 480
                current_width = self.width()
                zoom_factor = max(0.5, min(2.0, current_width / base_width))
                self.web_view.setZoomFactor(zoom_factor)


class WidgetManager(QMainWindow):
    """小组件管理器 - Windows 11 设置风格"""
    # 小组件类型映射
    WIDGET_CLASSES = {
        "ClockWidget": ClockWidget,
        "SystemMonitorWidget": SystemMonitorWidget,
        "TimerWidget": TimerWidget,
        "NotesWidget": NotesWidget,
        "ImageWidget": ImageWidget,
        "MusicWidget": MusicWidget,
        "WeatherWidget": WeatherWidget,
        "TodoWidget": TodoWidget,
        "AlarmWidget": AlarmWidget,
        "WorldClockWidget": WorldClockWidget,
        "NetworkMonitorWidget": NetworkMonitorWidget,
    }

    def __init__(self):
        super().__init__()
        self.widgets: Dict[str, BaseWidget] = {}

        # 可用小组件类型
        self.available_widgets = [
            ("时钟", "显示当前时间和日期", ClockWidget),
            ("系统监控", "CPU和内存使用率", SystemMonitorWidget),
            ("计时器", "简单计时器", TimerWidget),
            ("笔记", "快速记录笔记", NotesWidget),
            ("图片", "自定义背景图片", ImageWidget),
            ("音乐", "控制系统媒体播放", MusicWidget),
            ("天气", "显示实时天气信息", WeatherWidget),
            ("待办", "待办事项清单", TodoWidget),
            ("倒计时", "倒计时提醒", AlarmWidget),
            ("世界时钟", "显示世界各地时间", WorldClockWidget),
            ("网络监控", "网络速度和磁盘使用", NetworkMonitorWidget),
        ]

        # 网页组件（需要 PyQt6-WebEngine）
        if WEBENGINE_AVAILABLE:
            self.WIDGET_CLASSES["WebWidget"] = WebWidget
            self.available_widgets.append(("网页", "显示网页内容", WebWidget))

        # 抽屉状态
        self._sidebar_collapsed = False
        self._sidebar_expanded_width = 240
        self._sidebar_collapsed_width = 56

        # 全局快捷键
        self._hotkey_id = 1
        self._register_hotkey()

        self._init_ui()
        self._init_tray()
        self._restore_widgets()

    def _init_ui(self):
        """初始化UI - Windows 11 设置风格"""
        self.setWindowTitle("DashWidgets")
        self.setMinimumSize(800, 550)

        # 创建中心部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航栏
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        # 导航栏宽度动画
        from PyQt6.QtCore import QVariantAnimation
        self._sidebar_anim = QVariantAnimation(self)
        self._sidebar_anim.setDuration(200)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sidebar_anim.valueChanged.connect(self._on_sidebar_anim_changed)

        # 右侧内容区
        self.content_stack = QWidget()
        self.content_stack.setObjectName("content_stack")
        self.content_layout = QVBoxLayout(self.content_stack)
        self.content_layout.setContentsMargins(40, 32, 40, 32)
        self.content_layout.setSpacing(16)
        main_layout.addWidget(self.content_stack, 1)

        # 创建各页面
        self._create_widgets_page()
        self._create_settings_page()
        self._create_about_page()

        # 默认显示小组件页面
        self._show_page("widgets")

        # 应用主题
        self._apply_theme()

    def _create_sidebar(self):
        """创建左侧导航栏"""
        sidebar = QFrame()
        sidebar.setFixedWidth(self._sidebar_expanded_width)
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        # 顶部：切换按钮和标题
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # 抽屉切换按钮
        self.toggle_btn = QPushButton()
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_sidebar)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.bg_hover};
            }}
        """)
        header_layout.addWidget(self.toggle_btn)
        
        # 应用标题
        self.sidebar_title = QLabel("DashWidgets")
        self.sidebar_title.setObjectName("sidebar_title")
        header_layout.addWidget(self.sidebar_title)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        layout.addSpacing(16)

        # 导航项
        self.nav_buttons = {}
        nav_items = [
            ("widgets", "小组件", "浏览和管理桌面小组件", str(ICONS_DIR / "manage.svg")),
            ("settings", "设置", "应用主题和偏好设置", str(ICONS_DIR / "settings.svg")),
            ("about", "关于", "关于此应用程序", str(ICONS_DIR / "create.svg")),
        ]

        for key, label, tooltip, icon_path in nav_items:
            btn = AnimatedNavButton(label, icon_path)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, k=key: self._show_page(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn

        layout.addStretch()

        # 底部状态
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status_label")
        layout.addWidget(self.status_label)
        
        # 绘制切换按钮图标
        self._update_toggle_icon()

        return sidebar
        
    def _update_toggle_icon(self):
        """更新切换按钮图标"""
        # 绘制汉堡菜单/箭头图标
        icon_size = 20
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(theme.text_primary), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        
        if self._sidebar_collapsed:
            # 展开箭头 →
            painter.drawLine(8, 4, 14, 10)
            painter.drawLine(14, 10, 8, 16)
        else:
            # 收起箭头 ←
            painter.drawLine(12, 4, 6, 10)
            painter.drawLine(6, 10, 12, 16)
            
        painter.end()
        self.toggle_btn.setIcon(QIcon(pixmap))
        
    def _on_sidebar_anim_changed(self, value):
        """动画值变化时更新宽度"""
        self.sidebar.setFixedWidth(int(value))
        
    def _toggle_sidebar(self):
        """切换抽屉状态"""
        self._sidebar_collapsed = not self._sidebar_collapsed
        
        # 动画切换宽度
        self._sidebar_anim.stop()
        if self._sidebar_collapsed:
            self._sidebar_anim.setStartValue(self._sidebar_expanded_width)
            self._sidebar_anim.setEndValue(self._sidebar_collapsed_width)
        else:
            self._sidebar_anim.setStartValue(self._sidebar_collapsed_width)
            self._sidebar_anim.setEndValue(self._sidebar_expanded_width)
        self._sidebar_anim.start()
        
        # 更新UI元素（延迟到动画完成后）
        QTimer.singleShot(100, lambda: self._update_sidebar_elements())
            
        # 更新切换按钮图标
        self._update_toggle_icon()
        
    def _update_sidebar_elements(self):
        """更新侧边栏元素可见性"""
        self.sidebar_title.setVisible(not self._sidebar_collapsed)
        self.status_label.setVisible(not self._sidebar_collapsed)
        
        # 更新导航按钮状态
        for btn in self.nav_buttons.values():
            btn.set_collapsed(self._sidebar_collapsed)

    def _create_widgets_page(self):
        """创建小组件页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 页面标题
        header = QVBoxLayout()
        header.setSpacing(8)

        title = QLabel("小组件")
        title.setObjectName("page_title")
        header.addWidget(title)

        subtitle = QLabel("添加和管理桌面小组件")
        subtitle.setObjectName("page_subtitle")
        header.addWidget(subtitle)

        layout.addLayout(header)

        # 已添加的小组件卡片
        active_section = QVBoxLayout()
        active_section.setSpacing(12)

        active_title = QLabel("当前运行")
        active_title.setObjectName("section_title")
        active_section.addWidget(active_title)

        self.active_widgets_frame = QFrame()
        self.active_widgets_frame.setObjectName("card")
        active_layout = QVBoxLayout(self.active_widgets_frame)
        active_layout.setContentsMargins(16, 16, 16, 16)

        self.active_list = QListWidget()
        self.active_list.setObjectName("widget_list")
        self.active_list.setMaximumHeight(150)
        self.active_list.itemDoubleClicked.connect(self._on_active_item_double_clicked)
        active_layout.addWidget(self.active_list)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("移除选中")
        self.remove_btn.clicked.connect(self._remove_selected_widget)
        btn_row.addWidget(self.remove_btn)

        self.close_all_btn = QPushButton("关闭全部")
        self.close_all_btn.clicked.connect(self._close_all_widgets)
        btn_row.addWidget(self.close_all_btn)
        btn_row.addStretch()
        active_layout.addLayout(btn_row)

        active_section.addWidget(self.active_widgets_frame)
        layout.addLayout(active_section)

        # 可添加的小组件
        available_section = QVBoxLayout()
        available_section.setSpacing(12)

        available_title = QLabel("添加小组件")
        available_title.setObjectName("section_title")
        available_section.addWidget(available_title)

        # 搜索框
        self.widget_search = QLineEdit()
        self.widget_search.setPlaceholderText("🔍 搜索小组件...")
        self.widget_search.textChanged.connect(self._filter_available_widgets)
        self.widget_search.setStyleSheet(f"""
            QLineEdit {{
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: {theme.text_primary};
            }}
            QLineEdit:focus {{
                border-color: {theme.accent};
            }}
        """)
        available_section.addWidget(self.widget_search)

        self.available_frame = QFrame()
        self.available_frame.setObjectName("card")
        self.available_layout = QGridLayout(self.available_frame)
        self.available_layout.setContentsMargins(16, 16, 16, 16)
        self.available_layout.setSpacing(12)

        self._populate_available_widgets_grid()
        available_section.addWidget(self.available_frame)
        layout.addLayout(available_section)

        layout.addStretch()

        self.widgets_page = page
        self.content_layout.addWidget(page)

    def _populate_available_widgets_grid(self, filter_text=""):
        """填充可用小组件网格"""
        # 清除现有内容
        while self.available_layout.count():
            item = self.available_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        filtered_widgets = self.available_widgets
        if filter_text:
            filter_lower = filter_text.lower()
            filtered_widgets = [
                (name, desc, cls) for name, desc, cls in self.available_widgets
                if filter_lower in name.lower() or filter_lower in desc.lower()
            ]

        for idx, (name, desc, widget_class) in enumerate(filtered_widgets):
            card = QFrame()
            card.setObjectName("widget_card")
            card.setFixedSize(150, 90)
            card.setCursor(Qt.CursorShape.PointingHandCursor)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(4)

            name_label = QLabel(name)
            name_label.setObjectName("card_title")
            card_layout.addWidget(name_label)

            desc_label = QLabel(desc)
            desc_label.setObjectName("card_desc")
            desc_label.setWordWrap(True)
            card_layout.addWidget(desc_label)
            card_layout.addStretch()

            # 点击添加
            card.mousePressEvent = lambda e, w=widget_class, n=name: self._add_widget(w, n)
            self.available_layout.addWidget(card, idx // 3, idx % 3)

    def _filter_available_widgets(self, text):
        """过滤可用小组件"""
        self._populate_available_widgets_grid(text)

    def _create_settings_page(self):
        """创建设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 页面标题
        header = QVBoxLayout()
        header.setSpacing(8)

        title = QLabel("设置")
        title.setObjectName("page_title")
        header.addWidget(title)

        subtitle = QLabel("自定义应用外观和行为")
        subtitle.setObjectName("page_subtitle")
        header.addWidget(subtitle)

        layout.addLayout(header)

        # 外观设置卡片
        appearance_card = QFrame()
        appearance_card.setObjectName("card")
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(20, 16, 20, 16)
        appearance_layout.setSpacing(16)

        appearance_title = QLabel("外观")
        appearance_title.setObjectName("card_header")
        appearance_layout.addWidget(appearance_title)

        # 主题切换
        theme_row = QHBoxLayout()
        theme_info = QVBoxLayout()
        theme_label = QLabel("应用主题")
        theme_label.setObjectName("setting_label")
        theme_info.addWidget(theme_label)

        theme_desc = QLabel("选择浅色或深色主题")
        theme_desc.setObjectName("setting_desc")
        theme_info.addWidget(theme_desc)
        theme_row.addLayout(theme_info)
        theme_row.addStretch()

        self.theme_btn = QPushButton("切换主题")
        self.theme_btn.setObjectName("accent_button")
        self.theme_btn.clicked.connect(self._toggle_theme)
        theme_row.addWidget(self.theme_btn)
        appearance_layout.addLayout(theme_row)

        # 配色方案
        color_row = QHBoxLayout()
        color_info = QVBoxLayout()
        color_label = QLabel("配色方案")
        color_label.setObjectName("setting_label")
        color_info.addWidget(color_label)

        color_desc = QLabel("选择主题强调色")
        color_desc.setObjectName("setting_desc")
        color_info.addWidget(color_desc)
        color_row.addLayout(color_info)
        color_row.addStretch()

        self.color_combo = QComboBox()
        self.color_combo.addItems(["蓝色", "绿色", "紫色", "橙色", "红色", "青色"])
        color_map = {"blue": 0, "green": 1, "purple": 2, "orange": 3, "red": 4, "teal": 5}
        self.color_combo.setCurrentIndex(color_map.get(config.color_scheme, 0))
        self.color_combo.currentIndexChanged.connect(self._on_color_changed)
        self.color_combo.setStyleSheet(f"""
            QComboBox {{
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 100px;
            }}
        """)
        color_row.addWidget(self.color_combo)
        appearance_layout.addLayout(color_row)

        # 透明度设置
        opacity_row = QHBoxLayout()
        opacity_info = QVBoxLayout()
        opacity_label = QLabel("组件透明度")
        opacity_label.setObjectName("setting_label")
        opacity_info.addWidget(opacity_label)

        self.opacity_value_label = QLabel(f"{int(config.widget_opacity * 100)}%")
        self.opacity_value_label.setObjectName("setting_desc")
        opacity_info.addWidget(self.opacity_value_label)
        opacity_row.addLayout(opacity_info)
        opacity_row.addStretch()

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setFixedWidth(200)
        self.opacity_slider.setRange(50, 100)
        self.opacity_slider.setValue(int(config.widget_opacity * 100))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider)
        appearance_layout.addLayout(opacity_row)

        layout.addWidget(appearance_card)

        # 行为设置卡片
        behavior_card = QFrame()
        behavior_card.setObjectName("card")
        behavior_layout = QVBoxLayout(behavior_card)
        behavior_layout.setContentsMargins(20, 16, 20, 16)
        behavior_layout.setSpacing(16)

        behavior_title = QLabel("行为")
        behavior_title.setObjectName("card_header")
        behavior_layout.addWidget(behavior_title)

        # 吸附开关
        snap_row = QHBoxLayout()
        snap_info = QVBoxLayout()
        snap_label = QLabel("自动吸附")
        snap_label.setObjectName("setting_label")
        snap_info.addWidget(snap_label)

        snap_desc = QLabel("拖动组件时自动吸附到屏幕边缘和其他组件")
        snap_desc.setObjectName("setting_desc")
        snap_info.addWidget(snap_desc)
        snap_row.addLayout(snap_info)
        snap_row.addStretch()

        self.snap_checkbox = QCheckBox()
        self.snap_checkbox.setChecked(config.snap_enabled)
        self.snap_checkbox.stateChanged.connect(self._on_snap_changed)
        snap_row.addWidget(self.snap_checkbox)
        behavior_layout.addLayout(snap_row)

        # 吸附阈值
        threshold_row = QHBoxLayout()
        threshold_info = QVBoxLayout()
        threshold_label = QLabel("吸附距离")
        threshold_label.setObjectName("setting_label")
        threshold_info.addWidget(threshold_label)

        self.threshold_value_label = QLabel(f"{config.snap_threshold} 像素")
        self.threshold_value_label.setObjectName("setting_desc")
        threshold_info.addWidget(self.threshold_value_label)
        threshold_row.addLayout(threshold_info)
        threshold_row.addStretch()

        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setFixedWidth(200)
        self.threshold_slider.setRange(10, 50)
        self.threshold_slider.setValue(config.snap_threshold)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        threshold_row.addWidget(self.threshold_slider)
        behavior_layout.addLayout(threshold_row)

        layout.addWidget(behavior_card)
        layout.addStretch()

        self.settings_page = page
        self.content_layout.addWidget(page)

    def _on_opacity_changed(self, value):
        """透明度改变"""
        config.widget_opacity = value / 100
        self.opacity_value_label.setText(f"{value}%")
        config.save()

        # 更新所有小组件透明度
        for widget in self.widgets.values():
            widget.opacity = config.widget_opacity
            widget.update()

    def _on_color_changed(self, index):
        """配色方案改变"""
        colors = ["blue", "green", "purple", "orange", "red", "teal"]
        config.color_scheme = colors[index]
        config.save()

        # 更新主题颜色
        theme.color_scheme = config.color_scheme
        theme._update_colors()

        # 刷新所有小组件样式
        for widget in self.widgets.values():
            widget.update_style()
        self._apply_styles()

    def _on_snap_changed(self, state):
        """吸附开关改变"""
        config.snap_enabled = state == Qt.CheckState.Checked.value
        config.save()

    def _on_threshold_changed(self, value):
        """吸附阈值改变"""
        config.snap_threshold = value
        self.threshold_value_label.setText(f"{value} 像素")
        config.save()

    def _create_about_page(self):
        """创建关于页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 页面标题
        header = QVBoxLayout()
        header.setSpacing(8)

        title = QLabel("关于")
        title.setObjectName("page_title")
        header.addWidget(title)

        subtitle = QLabel("了解此应用程序")
        subtitle.setObjectName("page_subtitle")
        header.addWidget(subtitle)

        layout.addLayout(header)

        # 关于卡片
        about_card = QFrame()
        about_card.setObjectName("card")
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(20, 20, 20, 20)
        about_layout.setSpacing(12)

        app_name = QLabel("DashWidgets")
        app_name.setObjectName("about_title")
        about_layout.addWidget(app_name)

        version = QLabel("版本 0.1.0")
        version.setObjectName("setting_desc")
        about_layout.addWidget(version)

        about_layout.addSpacing(8)

        desc = QLabel("Windows 桌面小组件管理器\n基于 PyQt6 开发")
        desc.setObjectName("setting_desc")
        about_layout.addWidget(desc)

        about_layout.addSpacing(8)

        copyright_label = QLabel("© 2026 Little Tree Studio")
        copyright_label.setObjectName("setting_desc")
        about_layout.addWidget(copyright_label)

        layout.addWidget(about_card)
        layout.addStretch()

        self.about_page = page
        self.content_layout.addWidget(page)

    def _show_page(self, page_key):
        """显示指定页面"""
        self.widgets_page.setVisible(page_key == "widgets")
        self.settings_page.setVisible(page_key == "settings")
        self.about_page.setVisible(page_key == "about")

        # 更新导航按钮状态
        for key, btn in self.nav_buttons.items():
            btn.active = (key == page_key)

    def _on_active_item_double_clicked(self, item):
        """双击活动小组件项"""
        widget_id = item.data(Qt.ItemDataRole.UserRole)
        if widget_id in self.widgets:
            self.widgets[widget_id].raise_()
            self.widgets[widget_id].activateWindow()

    def _refresh_widget_list(self):
        """刷新已添加的小组件列表"""
        self.active_list.clear()
        for widget_id, widget in self.widgets.items():
            item = QListWidgetItem(f"{widget.widget_name} ({widget_id})")
            item.setData(Qt.ItemDataRole.UserRole, widget_id)
            self.active_list.addItem(item)
        self.status_label.setText(f"运行中: {len(self.widgets)} 个小组件")

    def _remove_selected_widget(self):
        """移除选中的小组件"""
        current_item = self.active_list.currentItem()
        if current_item:
            widget_id = current_item.data(Qt.ItemDataRole.UserRole)
            if widget_id in self.widgets:
                self.widgets[widget_id].close()

    def _apply_theme(self):
        """应用主题样式 - Windows 11 风格"""
        style_sheet = f"""
            /* 全局 */
            QMainWindow {{
                background-color: {theme.bg_main};
            }}
            QWidget {{
                color: {theme.text_primary};
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
                font-weight: normal;
            }}

            /* 侧边栏 */
            #sidebar {{
                background-color: {theme.bg_sidebar};
                border-right: 1px solid {theme.border};
            }}
            /* 内容区 */
            #content_stack {{
                background-color: {theme.bg_main};
            }}
            #sidebar_title {{
                font-size: 14px;
                font-weight: 600;
                color: {theme.text_primary};
                padding: 8px 12px;
            }}
            #nav_button {{
                background-color: transparent;
                color: {theme.text_primary};
                border: none;
                border-radius: 4px;
                padding: 10px 12px;
                text-align: left;
                font-size: 13px;
            }}
            #nav_button:hover {{
                background-color: {theme.bg_hover};
            }}
            #nav_button[active="true"] {{
                background-color: {theme.bg_pressed};
                font-weight: 500;
            }}
            #status_label {{
                color: {theme.text_tertiary};
                font-size: 12px;
                padding: 8px 12px;
            }}

            /* 页面标题 */
            #page_title {{
                font-size: 28px;
                font-weight: 600;
                color: {theme.text_primary};
            }}
            #page_subtitle {{
                font-size: 14px;
                color: {theme.text_secondary};
            }}
            #section_title {{
                font-size: 14px;
                font-weight: 600;
                color: {theme.text_primary};
            }}

            /* 卡片 */
            #card {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
            }}
            #card_header {{
                font-size: 14px;
                font-weight: 600;
                color: {theme.text_primary};
            }}
            #card_title {{
                font-size: 14px;
                font-weight: 600;
                color: {theme.text_primary};
            }}
            #card_desc {{
                font-size: 12px;
                color: {theme.text_secondary};
            }}

            /* 小组件卡片 */
            #widget_card {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
            }}
            #widget_card:hover {{
                border-color: {theme.accent};
                background-color: {theme.bg_hover};
            }}

            /* 设置项 */
            #setting_label {{
                font-size: 14px;
                color: {theme.text_primary};
            }}
            #setting_desc {{
                font-size: 12px;
                color: {theme.text_secondary};
            }}

            /* 关于 */
            #about_title {{
                font-size: 18px;
                font-weight: 600;
                color: {theme.text_primary};
            }}

            /* 按钮 */
            QPushButton {{
                background-color: {theme.bg_card};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {theme.bg_hover};
                border-color: {theme.border};
            }}
            QPushButton:pressed {{
                background-color: {theme.bg_pressed};
            }}
            #accent_button {{
                background-color: {theme.accent};
                color: white;
                border: none;
            }}
            #accent_button:hover {{
                background-color: {theme.accent_hover};
            }}

            /* 列表 */
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
                color: {theme.text_primary};
            }}
            QListWidget::item:selected {{
                background-color: {theme.accent};
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background-color: {theme.bg_hover};
            }}

            /* 菜单 */
            QMenu {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px 8px 12px;
                border-radius: 4px;
                background: transparent;
                color: {theme.text_primary};
            }}
            QMenu::item:selected {{
                background-color: {theme.bg_hover};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {theme.border};
                margin: 4px 8px;
            }}

            /* 滚动条 - Fluent 风格 */
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 0;
                padding: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.text_tertiary};
                min-height: 30px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {theme.text_secondary};
            }}
            QScrollBar::handle:vertical:pressed {{
                background: {theme.text_primary};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
                background: transparent;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}

            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 0;
                padding: 0;
            }}
            QScrollBar::handle:horizontal {{
                background: {theme.text_tertiary};
                min-width: 30px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {theme.text_secondary};
            }}
            QScrollBar::handle:horizontal:pressed {{
                background: {theme.text_primary};
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0;
                background: transparent;
            }}
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}

            /* 滚动区域 */
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """
        self.setStyleSheet(style_sheet)
        # 强制刷新所有子控件
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
            child.update()

    def _create_tray_icon(self):
        """创建托盘图标"""
        from PyQt6.QtGui import QIcon

        # 使用 assets 中的 logo.ico
        logo_path = IMAGES_DIR / "logo.ico"
        if logo_path.exists():
            return QIcon(str(logo_path))

        # 如果图标不存在，创建一个默认图标
        from PyQt6.QtGui import QPixmap, QFont

        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制圆角矩形背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(theme.accent)))
        painter.drawRoundedRect(2, 2, 28, 28, 6, 6)

        # 绘制D字母
        painter.setPen(QPen(QColor(255, 255, 255), 2.5))
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 32, 32), Qt.AlignmentFlag.AlignCenter, "D")

        painter.end()

        return QIcon(pixmap)

    def _init_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        # 使用自定义图标
        self.tray_icon.setIcon(self._create_tray_icon())
        self.tray_icon.setToolTip("DashWidgets")

        self.tray_menu = QMenu()
        self._apply_tray_menu_style()

        show_action = self.tray_menu.addAction("打开管理器")
        show_action.triggered.connect(self.show)

        theme_action = self.tray_menu.addAction("切换主题")
        theme_action.triggered.connect(self._toggle_theme)

        # 开机自启动
        self.autostart_action = self.tray_menu.addAction("开机自启动")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(self._is_autostart_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)

        # 一键解除鼠标穿透
        disable穿透_action = self.tray_menu.addAction("解除所有鼠标穿透")
        disable穿透_action.triggered.connect(self._disable_all_click_through)

        self.tray_menu.addSeparator()

        # 导出/导入配置
        export_action = self.tray_menu.addAction("导出配置")
        export_action.triggered.connect(self._export_config)
        import_action = self.tray_menu.addAction("导入配置")
        import_action.triggered.connect(self._import_config)

        self.tray_menu.addSeparator()

        quit_action = self.tray_menu.addAction("退出")
        quit_action.triggered.connect(self._quit_app)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _apply_tray_menu_style(self):
        """应用托盘菜单样式 - Fluent风格"""
        self.tray_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.bg_card};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 6px 4px;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 8px 28px 8px 16px;
                border-radius: 4px;
                background: transparent;
                color: {theme.text_primary};
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.bg_hover};
            }}
            QMenu::item:pressed {{
                background-color: {theme.bg_pressed};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {theme.border};
                margin: 4px 12px;
            }}
        """)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    def _add_widget(self, widget_class, name: str):
        """添加小组件"""
        import uuid
        widget_id = str(uuid.uuid4())[:8]

        widget = widget_class(widget_id, "medium")
        widget.closed.connect(self._remove_widget)
        widget.show()

        self.widgets[widget_id] = widget

        # 保存配置
        config.widgets.append({
            "id": widget_id,
            "type": widget_class.__name__,
            "name": name,
            "size": "medium",
            "position": [100, 100],
            "click_through": False
        })
        config.save()

        self._refresh_widget_list()
        self.status_label.setText(f"运行中: {len(self.widgets)} 个小组件")
        logger.info(f"添加小组件: {name} ({widget_id})")

    def _remove_widget(self, widget_id: str):
        """移除小组件"""
        if widget_id in self.widgets:
            del self.widgets[widget_id]

        config.widgets = [w for w in config.widgets if w.get("id") != widget_id]
        config.save()

        self._refresh_widget_list()
        logger.info(f"移除小组件: {widget_id}")

    def _close_all_widgets(self):
        """关闭所有小组件"""
        for widget in list(self.widgets.values()):
            widget.close()
        self.widgets.clear()
        config.widgets = []
        config.save()
        self._refresh_widget_list()
        self.status_label.setText("就绪")

    def _toggle_theme(self):
        """切换主题"""
        global theme
        theme.light_mode = not theme.light_mode
        theme._update_colors()
        config.light_mode = theme.light_mode
        config.save()

        self._apply_theme()
        self._apply_tray_menu_style()
        self._refresh_widget_list()

        # 更新导航按钮样式
        for btn in self.nav_buttons.values():
            btn.update_style()

        # 更新可用小组件网格
        available_layout = self.available_frame.layout()
        if available_layout:
            self._populate_available_widgets_grid(available_layout)

        # 更新所有小组件样式
        for widget in self.widgets.values():
            widget.update_style()
            widget.update()  # 强制重绘

        theme_name = "浅色" if theme.light_mode else "深色"
        self.status_label.setText(f"已切换到{theme_name}主题")
        logger.info(f"切换主题: {theme_name}")

    def _disable_all_click_through(self):
        """解除所有小组件的鼠标穿透模式"""
        count = 0
        for widget in self.widgets.values():
            if hasattr(widget, 'click_through') and widget.click_through:
                widget.click_through = False

                # 使用Windows API解除鼠标穿透
                hwnd = int(widget.winId())
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ex_style &= ~WS_EX_TRANSPARENT  # 移除透明样式
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

                # 保存配置
                for widget_config in config.widgets:
                    if widget_config.get("id") == widget.widget_id:
                        widget_config["click_through"] = False
                        break
                count += 1

        if count > 0:
            config.save()
            self.tray_icon.showMessage(
                "DashWidgets",
                f"已解除 {count} 个组件的鼠标穿透",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            self.tray_icon.showMessage(
                "DashWidgets",
                "没有启用了鼠标穿透的组件",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def _restore_widgets(self):
        """恢复已保存的小组件"""
        for widget_config in config.widgets:
            widget_id = widget_config.get("id")
            widget_type = widget_config.get("type")
            widget_name = widget_config.get("name", "未知")
            widget_size = widget_config.get("size", "medium")
            position = widget_config.get("position", [100, 100])
            click_through = widget_config.get("click_through", False)

            widget_class = self.WIDGET_CLASSES.get(widget_type)
            if widget_class and widget_id:
                try:
                    widget = widget_class(widget_id, widget_size)
                    widget.closed.connect(self._remove_widget)

                    # 恢复位置
                    if len(position) >= 2:
                        widget.move(position[0], position[1])

                    # 恢复图片小组件的图片路径
                    if widget_type == "ImageWidget":
                        image_path = widget_config.get("image_path", "")
                        if image_path:
                            widget.image_path = image_path
                        # 恢复裁剪区域
                        crop_rect_data = widget_config.get("crop_rect")
                        if crop_rect_data and len(crop_rect_data) == 4:
                            widget.crop_rect = QRect(
                                crop_rect_data[0], crop_rect_data[1],
                                crop_rect_data[2], crop_rect_data[3]
                            )

                    # 恢复网页小组件的网址
                    if widget_type == "WebWidget":
                        url = widget_config.get("url", "")
                        if url:
                            widget.url = url
                            widget.url_input.setText(url)
                            from PyQt6.QtCore import QUrl
                            widget.web_view.setUrl(QUrl(url))

                    widget.show()

                    # 恢复鼠标穿透状态（需要在show之后，因为需要窗口句柄）
                    if click_through:
                        widget.click_through = True
                        hwnd = int(widget.winId())
                        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                        ex_style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
                        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

                    self.widgets[widget_id] = widget
                    logger.info(f"恢复小组件: {widget_name} ({widget_id})")
                except Exception as e:
                    logger.error(f"恢复小组件失败 {widget_name}: {e}")

        self._refresh_widget_list()

    def _is_autostart_enabled(self) -> bool:
        """检查是否已启用开机自启动"""
        import sys
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "DashWidgets")
            winreg.CloseKey(key)
            return True
        except WindowsError:
            return False

    def _toggle_autostart(self):
        """切换开机自启动"""
        import sys
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        exe_path = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{__file__}"'

        if self.autostart_action.isChecked():
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
                winreg.SetValueEx(key, "DashWidgets", 0, winreg.REG_SZ, exe_path)
                winreg.CloseKey(key)
                self.tray_icon.showMessage("DashWidgets", "已启用开机自启动", QSystemTrayIcon.MessageIcon.Information, 2000)
            except Exception as e:
                self.autostart_action.setChecked(False)
                self.tray_icon.showMessage("DashWidgets", f"设置失败: {e}", QSystemTrayIcon.MessageIcon.Warning, 2000)
        else:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
                winreg.DeleteValue(key, "DashWidgets")
                winreg.CloseKey(key)
                self.tray_icon.showMessage("DashWidgets", "已关闭开机自启动", QSystemTrayIcon.MessageIcon.Information, 2000)
            except WindowsError:
                pass

    def _export_config(self):
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "dashwidgets_config.json", "JSON文件 (*.json)"
        )
        if file_path:
            try:
                # 保存当前配置
                config.save()
                # 复制到目标位置
                import shutil
                shutil.copy(CONFIG_FILE, file_path)
                self.tray_icon.showMessage("DashWidgets", f"配置已导出到: {file_path}", QSystemTrayIcon.MessageIcon.Information, 2000)
            except Exception as e:
                self.tray_icon.showMessage("DashWidgets", f"导出失败: {e}", QSystemTrayIcon.MessageIcon.Warning, 2000)

    def _import_config(self):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "JSON文件 (*.json)"
        )
        if file_path:
            try:
                # 读取配置文件
                data = json.loads(Path(file_path).read_text(encoding="utf-8"))
                # 应用配置
                config.widgets = data.get("widgets", [])
                config.light_mode = data.get("light_mode", True)
                config.widget_opacity = data.get("widget_opacity", 0.95)
                config.save()
                # 应用主题
                theme.light_mode = config.light_mode
                theme._update_colors()
                # 重新加载小组件
                self._restore_widgets()
                self.tray_icon.showMessage("DashWidgets", "配置已导入，请重启应用以完全生效", QSystemTrayIcon.MessageIcon.Information, 2000)
            except Exception as e:
                self.tray_icon.showMessage("DashWidgets", f"导入失败: {e}", QSystemTrayIcon.MessageIcon.Warning, 2000)

    def _quit_app(self):
        """退出应用"""
        self.tray_icon.hide()
        QApplication.quit()

    def _register_hotkey(self):
        """注册全局热键 (Win+Shift+D 显示/隐藏管理器)"""
        import ctypes
        # MOD_WIN = 0x0008, MOD_SHIFT = 0x0004, D = 0x44
        ctypes.windll.user32.RegisterHotKey(
            int(self.winId()), self._hotkey_id, 0x0008 | 0x0004, 0x44
        )

    def _unregister_hotkey(self):
        """注销热键"""
        import ctypes
        ctypes.windll.user32.UnregisterHotKey(int(self.winId()), self._hotkey_id)

    def nativeEvent(self, eventType, message):
        """处理Windows原生事件"""
        if eventType == b"windows_generic_MSG":
            import ctypes
            msg = ctypes.cast(int(message), ctypes.POINTER(ctypes.c_uint32 * 6)).contents
            if msg[0] == 0x0312:  # WM_HOTKEY
                if msg[1] == self._hotkey_id:
                    if self.isVisible():
                        self.hide()
                    else:
                        self.show()
                        self.activateWindow()
                    return True, 0
        return False, 0

    def closeEvent(self, event):
        """关闭时最小化到托盘"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "DashWidgets",
            "程序已最小化到系统托盘",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )


def main():
    # 启用高DPI缩放（PyQt6默认启用）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 设置应用信息
    app.setApplicationName("DashWidgets")
    app.setApplicationDisplayName("DashWidgets - 桌面小组件")

    # 设置默认字体，启用抗锯齿
    font = QFont("Segoe UI", 9)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # 加载主题
    global theme
    theme = ThemeColors(light_mode=config.light_mode)

    manager = WidgetManager()

    logger.info(f"WebEngine 可用: {WEBENGINE_AVAILABLE}")
    logger.info("DashWidgets 启动成功")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
