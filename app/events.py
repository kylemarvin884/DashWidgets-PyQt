"""
事件系统 - 提供全局事件总线和事件类型
"""
from __future__ import annotations

from typing import Callable, Any
from enum import Enum, auto
from loguru import logger


class EventType(Enum):
    """事件类型枚举"""
    # 应用事件
    APP_STARTED = auto()
    APP_CLOSED = auto()
    
    # 小组件事件
    WIDGET_ADDED = auto()
    WIDGET_REMOVED = auto()
    WIDGET_SHOWN = auto()
    WIDGET_HIDDEN = auto()
    
    # 全屏事件
    FULLSCREEN_OPENED = auto()
    FULLSCREEN_CLOSED = auto()
    
    # 主题事件
    THEME_CHANGED = auto()
    
    # 自动化事件
    AUTOMATION_TRIGGERED = auto()
    
    # 自定义事件
    CUSTOM = auto()


class EventBus:
    """全局事件总线（单例）"""
    _instance: "EventBus | None" = None
    
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}
    
    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug("事件订阅: {} -> {}", event_type.name, callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb is not callback
            ]
    
    def emit(self, event_type: EventType, *args: Any, **kwargs: Any) -> list[Any]:
        """发布事件"""
        results = []
        for callback in self._subscribers.get(event_type, []):
            try:
                results.append(callback(*args, **kwargs))
            except Exception:
                logger.exception("事件处理异常: {} -> {}", event_type.name, callback)
        return results


# 便捷函数
def emit_event(event_type: EventType, *args: Any, **kwargs: Any) -> list[Any]:
    """发布事件"""
    return EventBus.instance().emit(event_type, *args, **kwargs)


def subscribe_event(event_type: EventType, callback: Callable) -> None:
    """订阅事件"""
    EventBus.instance().subscribe(event_type, callback)


def unsubscribe_event(event_type: EventType, callback: Callable) -> None:
    """取消订阅事件"""
    EventBus.instance().unsubscribe(event_type, callback)
