"""小组件基类

所有桌面小组件继承此基类。
"""
from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt


@dataclass
class WidgetConfig:
    """小组件配置"""
    widget_type: str = ""
    id: str = ""
    x: int = 0
    y: int = 0
    width: int = 200
    height: int = 100
    visible: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


class WidgetBase(QWidget):
    """小组件基类

    设计约束：
    - 背景保持 transparent，由外层 DesktopWidgetWindow 提供卡片背景
    - 使用 Win11Style.widget_colors() 获取主题感知颜色
    """

    WIDGET_TYPE: str = ""
    WIDGET_NAME: str = ""

    def __init__(self, config: WidgetConfig, services: dict[str, Any], parent: Any = None):
        super().__init__(parent=parent)
        self.config = config
        self.services = services
        self.parent_widget = parent

        if parent is None:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setFixedSize(config.width, config.height)
            if config.x or config.y:
                self.move(config.x, config.y)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def refresh(self) -> None:
        """刷新小组件内容（子类重写）"""

    def on_close(self) -> None:
        """小组件关闭时调用"""

    def on_settings_changed(self, settings: dict[str, Any]) -> None:
        """设置变更时调用"""

    def get_context_menu_actions(self) -> list[tuple]:
        """向窗口统一右键菜单贡献组件专属动作（子类可选重写）。

        返回 [(icon, label, callback), ...]；icon 为 FluentIcon 枚举或
        None（无图标）。动作会渲染在「组件设置 / 窗口层级 …」等系统
        菜单项之前，由窗口菜单统一提供主题样式——不要在组件里自建
        QMenu（会继承透明样式而渲染成黑底）。
        """
        return []
