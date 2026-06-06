"""DashWidgets 插件系统"""

from .base_plugin import BasePlugin, PluginAPI, PluginMeta, HookType, LibraryPlugin, PluginType, PluginPermission
from .plugin_manager import PluginManager

__all__ = [
    "BasePlugin",
    "PluginAPI",
    "PluginMeta",
    "HookType",
    "LibraryPlugin",
    "PluginType",
    "PluginPermission",
    "PluginManager",
]
