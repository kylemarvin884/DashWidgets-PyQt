"""
小组件模块

提供小组件基类、注册表和卡片组件。
"""
from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.widgets.registry import WidgetRegistry

__all__ = ["WidgetBase", "WidgetConfig", "WidgetRegistry"]
