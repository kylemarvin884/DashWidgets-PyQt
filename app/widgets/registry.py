"""小组件注册表 —— 全局单例，内置 + 插件均向此处注册"""
from __future__ import annotations

from typing import Type, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.widgets.base_widget import WidgetBase, WidgetConfig


class WidgetRegistry:
    """全局小组件注册表（单例）"""

    _instance: "WidgetRegistry | None" = None

    def __init__(self):
        self._registry: dict[str, Type] = {}
        self._widget_plugin_map: dict[str, str] = {}
        self._all_types: list[tuple[str, str]] = []
        self._services: dict[str, Any] = {}
        self._register_builtins()

    @classmethod
    def instance(cls) -> "WidgetRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, widget_cls: Type, plugin_id: str | None = None) -> None:
        widget_type = getattr(widget_cls, 'WIDGET_TYPE', None)
        if not widget_type:
            widget_type = widget_cls.__name__.replace('Widget', '').lower()

        self._registry[widget_type] = widget_cls
        if plugin_id:
            self._widget_plugin_map[widget_type] = plugin_id

        display_name = getattr(widget_cls, 'WIDGET_NAME', widget_type)
        if not any(t == widget_type for t, _ in self._all_types):
            self._all_types.append((widget_type, display_name))

    def get_plugin_id(self, widget_type: str) -> str | None:
        return self._widget_plugin_map.get(widget_type)

    def get(self, widget_type: str) -> Type | None:
        return self._registry.get(widget_type)

    def all_types(self) -> list[tuple[str, str]]:
        return list(self._all_types)

    def create(self, config: Any, services: dict[str, Any], parent=None) -> Any | None:
        widget_type = config.widget_type if hasattr(config, 'widget_type') else str(config)
        cls = self._registry.get(widget_type)
        if cls is None:
            return None
        try:
            import inspect
            sig = inspect.signature(cls.__init__)
            param_count = len([p for p in sig.parameters.values() if p.name != 'self'])

            if param_count <= 2:
                inst = cls(parent=parent)
            else:
                inst = cls(config, services, parent)

            if hasattr(inst, 'refresh'):
                inst.refresh()
            return inst
        except Exception as e:
            from loguru import logger
            logger.warning("小组件创建失败: {} - {}", widget_type, e)
            return None

    def set_services(self, services: dict[str, Any]) -> None:
        self._services = services

    def _register_builtins(self) -> None:
        try:
            from app.widgets.builtin.clock_widget import ClockWidget
            from app.widgets.builtin.stopwatch_widget import StopwatchWidget
            from app.widgets.builtin.timer_widget import TimerWidget
            from app.widgets.builtin.pomodoro_widget import PomodoroWidget
            from app.widgets.builtin.system_monitor_widget import SystemMonitorWidget
            from app.widgets.builtin.network_monitor_widget import NetworkMonitorWidget
            from app.widgets.builtin.weather_widget import WeatherWidget
            from app.widgets.builtin.calendar_widget import CalendarWidget
            from app.widgets.builtin.todo_widget import TodoWidget
            from app.widgets.builtin.music_widget import MusicWidget
            from app.widgets.builtin.note_widget import NoteWidget
            from app.widgets.builtin.exchange_widget import ExchangeWidget
            from app.widgets.builtin.rss_widget import RssWidget
            from app.widgets.builtin.automation_widget import AutomationWidget
            from app.widgets.builtin.image_widget import ImageWidget
            from app.widgets.builtin.document_viewer_widget import DocumentViewerWidget

            for cls in [
                ClockWidget, StopwatchWidget, TimerWidget, PomodoroWidget,
                SystemMonitorWidget, NetworkMonitorWidget,
                WeatherWidget, CalendarWidget, TodoWidget, MusicWidget,
                NoteWidget, ExchangeWidget, RssWidget,
                AutomationWidget, ImageWidget, DocumentViewerWidget,
            ]:
                self.register(cls)

            from loguru import logger
            logger.info("已注册所有内置小组件 ({}个)", len(self._registry))
        except Exception as e:
            from loguru import logger
            logger.warning(f"注册内置小组件失败: {e}")
