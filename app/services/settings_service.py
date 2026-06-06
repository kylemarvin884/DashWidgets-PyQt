"""
应用通用设置服务（持久化到 settings.json）
"""
from __future__ import annotations

from typing import Any, Callable
import json

from app.constants import SETTINGS_CONFIG, DEFAULT_GROUPS, DEFAULT_UPDATE_FREQUENCY


class SettingsService:
    """
    单例设置服务。

    使用回调列表监听设置变更。
    """

    _instance: "SettingsService | None" = None
    _initialized: bool
    _data: dict[str, Any]
    _listeners: list[Callable]

    @classmethod
    def instance(cls) -> "SettingsService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._data = self._load()
        self._listeners = []

    def on_changed(self, callback: Callable) -> None:
        """注册设置变更监听器"""
        self._listeners.append(callback)

    def off_changed(self, callback: Callable) -> None:
        """移除设置变更监听器"""
        self._listeners = [cb for cb in self._listeners if cb is not callback]

    def _notify(self):
        """通知所有监听器"""
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass

    def _load(self) -> dict[str, Any]:
        """加载配置"""
        if SETTINGS_CONFIG.exists():
            try:
                with open(SETTINGS_CONFIG, 'r', encoding='utf-8') as f:
                    data: dict[str, Any] = json.load(f)
                    if "colorPreset" not in data:
                        data["colorPreset"] = "默认"
                    return data
            except Exception as e:
                from loguru import logger
                logger.warning(f"加载设置失败: {e}")
        return {"colorPreset": "默认"}

    def _save(self):
        """保存配置"""
        SETTINGS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)
        self._notify()

    # ------------------------------------------------------------------ #
    # 主题设置
    # ------------------------------------------------------------------ #

    @property
    def light_mode(self) -> bool:
        return self._data.get("lightMode", True)

    def set_light_mode(self, value: bool) -> None:
        self._data["lightMode"] = bool(value)
        self._save()

    @property
    def color_scheme(self) -> str:
        return self._data.get("colorScheme", "blue")

    def set_color_scheme(self, value: str) -> None:
        self._data["colorScheme"] = str(value)
        self._save()

    @property
    def color_preset(self) -> str:
        return self._data.get("colorPreset", "默认")

    def set_color_preset(self, value: str) -> None:
        self._data["colorPreset"] = str(value)
        self._save()

    # ------------------------------------------------------------------ #
    # 字体设置
    # ------------------------------------------------------------------ #

    @property
    def font_family(self) -> str:
        return self._data.get("fontFamily", "Microsoft YaHei")

    def set_font_family(self, value: str) -> None:
        self._data["fontFamily"] = str(value)
        self._save()

    @property
    def font_size(self) -> int:
        return self._data.get("fontSize", 12)

    def set_font_size(self, value: int) -> None:
        self._data["fontSize"] = int(value)
        self._save()

    # ------------------------------------------------------------------ #
    # 小组件设置
    # ------------------------------------------------------------------ #

    @property
    def widget_opacity(self) -> int:
        return self._data.get("widgetOpacity", 0)

    def set_widget_opacity(self, value: int) -> None:
        self._data["widgetOpacity"] = max(0, min(100, int(value)))
        self._save()

    @property
    def click_through(self) -> bool:
        return self._data.get("clickThrough", False)

    def set_click_through(self, value: bool) -> None:
        self._data["clickThrough"] = bool(value)
        self._save()

    @property
    def widget_customization(self) -> dict[str, Any]:
        return self._data.get("widgetCustomization", {})

    def set_widget_customization(self, value: dict[str, Any]) -> None:
        self._data["widgetCustomization"] = dict(value)
        self._save()

    # ------------------------------------------------------------------ #
    # 拖拽和布局设置
    # ------------------------------------------------------------------ #

    @property
    def snap_to_grid(self) -> bool:
        return self._data.get("snapToGrid", True)

    def set_snap_to_grid(self, value: bool) -> None:
        self._data["snapToGrid"] = bool(value)
        self._save()

    @property
    def grid_size(self) -> int:
        return self._data.get("gridSize", 20)

    def set_grid_size(self, value: int) -> None:
        self._data["gridSize"] = int(value)
        self._save()

    @property
    def prevent_overlap(self) -> bool:
        return self._data.get("preventOverlap", True)

    def set_prevent_overlap(self, value: bool) -> None:
        self._data["preventOverlap"] = bool(value)
        self._save()

    @property
    def snap_to_edge(self) -> bool:
        return self._data.get("snapToEdge", True)

    def set_snap_to_edge(self, value: bool) -> None:
        self._data["snapToEdge"] = bool(value)
        self._save()

    @property
    def drag_animation_enabled(self) -> bool:
        return self._data.get("dragAnimationEnabled", True)

    def set_drag_animation_enabled(self, value: bool) -> None:
        self._data["dragAnimationEnabled"] = bool(value)
        self._save()

    # ------------------------------------------------------------------ #
    # 性能设置
    # ------------------------------------------------------------------ #

    @property
    def low_power_mode(self) -> bool:
        return self._data.get("lowPowerMode", False)

    def set_low_power_mode(self, value: bool) -> None:
        self._data["lowPowerMode"] = bool(value)
        self._save()

    @property
    def update_frequency(self) -> int:
        return self._data.get("updateFrequency", DEFAULT_UPDATE_FREQUENCY)

    def set_update_frequency(self, value: int) -> None:
        self._data["updateFrequency"] = int(value)
        self._save()

    # ------------------------------------------------------------------ #
    # 分组设置
    # ------------------------------------------------------------------ #

    @property
    def widget_groups(self) -> list[str]:
        return self._data.get("widgetGroups", DEFAULT_GROUPS.copy())

    def set_widget_groups(self, value: list[str]) -> None:
        self._data["widgetGroups"] = list(value)
        self._save()

    @property
    def group_visibility(self) -> dict[str, bool]:
        groups = self.widget_groups
        return self._data.get("groupVisibility", {g: True for g in groups})

    def set_group_visibility(self, value: dict[str, bool]) -> None:
        self._data["groupVisibility"] = dict(value)
        self._save()

    @property
    def widget_assignments(self) -> dict[str, str]:
        return self._data.get("widgetAssignments", {})

    def set_widget_assignments(self, value: dict[str, str]) -> None:
        self._data["widgetAssignments"] = dict(value)
        self._save()

    @property
    def widget_order(self) -> list[str]:
        return self._data.get("widgetOrder", [])

    def set_widget_order(self, value: list[str]) -> None:
        self._data["widgetOrder"] = list(value)
        self._save()

    # ------------------------------------------------------------------ #
    # 系统设置
    # ------------------------------------------------------------------ #

    @property
    def autostart(self) -> bool:
        return self._data.get("autostart", False)

    def set_autostart(self, value: bool) -> None:
        self._data["autostart"] = bool(value)
        self._save()

    # ------------------------------------------------------------------ #
    # 主题和外观设置
    # ------------------------------------------------------------------ #

    @property
    def theme(self) -> str:
        return self._data.get("theme", "light")

    def set_theme(self, value: str) -> None:
        self._data["theme"] = str(value)
        self._save()

    @property
    def mica_enabled(self) -> bool:
        return self._data.get("micaEnabled", False)

    def set_mica_enabled(self, value: bool) -> None:
        self._data["micaEnabled"] = bool(value)
        self._save()

    def get_theme(self) -> str:
        return self.theme

    def get_mica_enabled(self) -> bool:
        return self.mica_enabled

    # ------------------------------------------------------------------ #
    # 开发者选项
    # ------------------------------------------------------------------ #

    @property
    def developer_mode(self) -> bool:
        return self._data.get("developerMode", False)

    def set_developer_mode(self, value: bool) -> None:
        self._data["developerMode"] = bool(value)
        self._save()
