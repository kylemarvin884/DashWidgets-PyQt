"""画布服务注册表 (LTC 兼容)"""
from typing import Any, Callable


class CanvasServiceRegistry:
    """全局画布服务注册表，管理 LTC 插件系统中的画布服务和顶栏按钮工厂。"""

    _instance = None

    def __init__(self):
        self._services: dict[str, tuple[Any, str | None]] = {}
        self._topbar_btn_factories: list[tuple[Callable, str | None]] = []

    @classmethod
    def instance(cls) -> "CanvasServiceRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, service: Any, plugin_id: str | None = None) -> None:
        """注册画布服务。"""
        self._services[name] = (service, plugin_id)

    def get(self, name: str) -> Any | None:
        """获取画布服务。"""
        entry = self._services.get(name)
        return entry[0] if entry else None

    def get_plugin_id(self, name: str) -> str | None:
        """获取服务来源插件 ID。"""
        entry = self._services.get(name)
        return entry[1] if entry else None

    def list_services(self) -> dict[str, Any]:
        """列出所有已注册的服务。"""
        return {name: entry[0] for name, entry in self._services.items()}

    def register_topbar_btn_factory(self, factory: Callable, plugin_id: str | None = None) -> None:
        """注册画布顶栏按钮工厂函数。"""
        self._topbar_btn_factories.append((factory, plugin_id))

    def get_topbar_btn_factories(self) -> list[Callable]:
        """获取所有顶栏按钮工厂函数。"""
        return [factory for factory, _ in self._topbar_btn_factories]
