"""插件管理器 — 负责发现、加载、卸载插件
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from .base_plugin import BasePlugin, LibraryPlugin, PluginAPI, PluginMeta, PluginType
from app.constants import PLUGINS_DIR
from qfluentwidgets import FluentIcon as FIF
from loguru import logger


class PluginEntry:
    """插件运行时记录"""

    def __init__(self, plugin: BasePlugin, api: PluginAPI):
        self.plugin = plugin
        self.api = api
        self.enabled = True
        self.error: str | None = None
        # 记录哪些插件依赖了本插件（用于卷载驱逐检查）
        self.dependents: set[str] = set()

    @property
    def meta(self) -> PluginMeta:
        return self.plugin.meta

    @property
    def is_library(self) -> bool:
        return self.meta.plugin_type == PluginType.LIBRARY


class PluginManager:
    """插件管理器。

    外部插件目录结构::

        plugins_ext/
            my_lib/
                plugin.json       ← plugin_type: "library"
                __init__.py       ← Plugin(LibraryPlugin)
            my_plugin/
                plugin.json       ← plugin_type: "feature", requires: ["my_lib"]
                __init__.py       ← Plugin(BasePlugin)
            simple_plugin.py      ← 单文件插件（无清单文件）

    加载顺序：管理器根据 ``requires`` 对所有插件做拓扑排序，
    确保依赖插件在依赖方之前完成加载。
    """

    def __init__(
        self,
        shared_api: PluginAPI | None = None,
        services: dict[str, Any] | None = None,
        toast_callback: Callable | None = None,
        permission_check_callback: Callable | None = None,
        main_window: Any | None = None,
    ):
        self._shared_api = shared_api or PluginAPI()
        self._services = services or {}
        self._toast_cb = toast_callback
        self._permission_check_cb = permission_check_callback
        self._always_allowed_plugins: set[str] = set()
        self._entries: dict[str, PluginEntry] = {}
        self._main_window = main_window  # 主窗口引用

        # 事件回调列表（替代 Qt Signal）
        self._on_loaded: list[Callable[[str], None]] = []
        self._on_unloaded: list[Callable[[str], None]] = []
        self._on_error: list[Callable[[str, str], None]] = []
        self._on_enabled_changed: list[Callable[[str, bool], None]] = []

    def set_main_window(self, window: Any) -> None:
        """设置主窗口引用（在窗口就绪后调用）"""
        self._main_window = window

    def on(self, event: str, callback: Callable):
        """注册事件回调。

        Parameters
        ----------
        event : str
            "loaded" | "unloaded" | "error" | "enabled_changed"
        callback : Callable
            回调函数
        """
        targets = {
            "loaded": self._on_loaded,
            "unloaded": self._on_unloaded,
            "error": self._on_error,
            "enabled_changed": self._on_enabled_changed,
        }
        if event in targets:
            targets[event].append(callback)

    def off(self, event: str, callback: Callable):
        """移除事件回调。"""
        targets = {
            "loaded": self._on_loaded,
            "unloaded": self._on_unloaded,
            "error": self._on_error,
            "enabled_changed": self._on_enabled_changed,
        }
        if event in targets:
            targets[event] = [cb for cb in targets[event] if cb is not callback]

    def _emit(self, event: str, *args):
        """触发事件回调。"""
        targets = {
            "loaded": self._on_loaded,
            "unloaded": self._on_unloaded,
            "error": self._on_error,
            "enabled_changed": self._on_enabled_changed,
        }
        for cb in targets.get(event, []):
            try:
                cb(*args)
            except Exception:
                logger.exception("PluginManager 事件回调异常: {}", event)

    # ------------------------------------------------------------------ #
    # 属性
    # ------------------------------------------------------------------ #

    @property
    def api(self) -> PluginAPI:
        return self._shared_api

    def all_entries(self) -> list[PluginEntry]:
        return list(self._entries.values())

    def get_entry(self, plugin_id: str) -> PluginEntry | None:
        return self._entries.get(plugin_id)

    def get_navigation_entries(self) -> list[PluginEntry]:
        """获取提供侧边栏导航项的插件列表（仅返回已启用的）"""
        entries = []
        for entry in self._entries.values():
            if entry.enabled and entry.plugin and entry.plugin.get_navigation_info():
                entries.append(entry)
        return entries

    # ------------------------------------------------------------------ #
    # 加载
    # ------------------------------------------------------------------ #

    def discover_and_load(self) -> None:
        """扫描外部插件目录并尝试加载所有插件。"""
        base = Path(PLUGINS_DIR)
        if not base.exists():
            base.mkdir(parents=True, exist_ok=True)
            return

        # 第一阶段：收集所有插件信息
        plugin_infos: dict[str, dict] = {}
        for path in sorted(base.iterdir()):
            # 跳过隐藏目录和 .gitkeep 等文件
            if path.name.startswith(".") or path.name.startswith("_"):
                continue
            if path.is_dir() and (path / "__init__.py").exists():
                info = self._collect_plugin_info(path)
                if info:
                    plugin_infos[info["id"]] = info
            elif path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
                info = self._collect_plugin_info(path)
                if info:
                    plugin_infos[info["id"]] = info

        # 第二阶段：拓扑排序
        dep_graph = {pid: info["requires"] for pid, info in plugin_infos.items()}
        sorted_ids = _topo_sort(dep_graph)

        # 第三阶段：按排序顺序加载插件
        for pid in sorted_ids:
            info = plugin_infos[pid]
            self._load_from_info(info)

    def _collect_plugin_info(self, path: Path) -> dict | None:
        """收集插件信息，不实际加载。"""
        is_pkg = path.is_dir()
        entry_file = (path / "__init__.py") if is_pkg else path

        # 读取 plugin.json（包形式才有）
        manifest: PluginMeta | None = None
        if is_pkg:
            manifest = _load_manifest(path)

        # 如果无清单文件，尝试从代码中获取 meta
        if manifest is None:
            try:
                module_name = f"_plugin_info_{path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, entry_file)
                if spec is None or spec.loader is None:
                    return None
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)

                plugin_cls = getattr(mod, "Plugin", None)
                if plugin_cls is None:
                    return None
                manifest = plugin_cls.meta
            except Exception:
                logger.exception("插件 {} 信息收集失败", path.name)
                return None

        # 每个包插件拥有独立的数据目录
        data_dir: Path
        if is_pkg:
            data_dir = path
        else:
            data_dir = Path(PLUGINS_DIR) / "._data" / path.stem

        return {
            "id": manifest.id,
            "path": path,
            "is_pkg": is_pkg,
            "manifest": manifest,
            "data_dir": data_dir,
            "requires": manifest.requires,
        }

    def _load_from_info(self, info: dict) -> None:
        """根据收集的信息加载插件。"""
        path = info["path"]
        is_pkg = info["is_pkg"]
        manifest = info["manifest"]
        data_dir = info["data_dir"]

        module_name = f"_plugin_{path.stem}"
        entry_file = (path / "__init__.py") if is_pkg else path

        try:
            spec = importlib.util.spec_from_file_location(module_name, entry_file)
            if spec is None or spec.loader is None:
                return
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            plugin_cls = getattr(mod, "Plugin", None)
            if plugin_cls is None:
                logger.warning("插件 {} 未找到 Plugin 类，跳过", path.name)
                return

            # plugin.json 中的 meta 优先于代码中的 meta 属性
            plugin_cls.meta = manifest

            self._instantiate_and_register(plugin_cls, data_dir=data_dir)
        except Exception:
            self._emit("error", path.stem, "加载异常，查看日志")
            logger.exception("插件 {} 加载失败", path.name)

    def load_builtin(self, plugin_cls: type[BasePlugin]) -> None:
        """直接注册内置插件类（无需文件扫描）。"""
        self._instantiate_and_register(plugin_cls)

    def _instantiate_and_register(
        self,
        plugin_cls: type[BasePlugin],
        data_dir: Path | None = None,
    ) -> None:
        plugin = plugin_cls()
        pid = plugin.meta.id

        if pid in self._entries:
            logger.debug("插件 {} 已加载，跳过", pid)
            return

        # 检查依赖是否已加载（对于库插件）
        for dep_id in plugin.meta.requires:
            dep_entry = self._entries.get(dep_id)
            if dep_entry is None:
                logger.error("插件 {} 依赖的插件 {} 未加载，跳过", pid, dep_id)
                self._emit("error", pid, f"依赖插件 {dep_id} 未加载")
                return
            if not dep_entry.is_library:
                logger.warning("插件 {} 依赖的 {} 不是库插件，可能无法正常工作", pid, dep_id)
            # 记录依赖关系
            dep_entry.dependents.add(pid)

        # 检查并请求插件权限
        permissions = plugin.meta.permissions or []
        if permissions and pid not in self._always_allowed_plugins:
            if self._permission_check_cb:
                accepted, always_allow = self._permission_check_cb(plugin.meta.name, permissions)
                if not accepted:
                    logger.warning("插件 {} 用户拒绝权限，停止加载", pid)
                    self._emit("error", pid, "用户拒绝权限")
                    return
                if always_allow:
                    self._always_allowed_plugins.add(pid)
                    logger.info("插件 {} 已添加到始终允许列表", pid)

        api = PluginAPI(plugin_data_dir=data_dir, plugin_id=pid)

        # 注入宿主服务与通知能力
        for svc_name, svc_obj in self._services.items():
            api._register_service(svc_name, svc_obj)
        if self._toast_cb:
            api._set_toast_callback(self._toast_cb)

        # 注入依赖插件解析器
        api._set_plugin_resolver(self._resolve_plugin_for_api)

        # 注入主窗口能力
        if self._main_window:
            api._set_main_window(self._main_window)

        entry = PluginEntry(plugin, api)
        try:
            # 使用适配器，让插件通过自己的局部 API 注册钩子/触发器/动作
            adapter = _SharedAPIAdapter(api, self._shared_api)
            plugin.on_load(adapter)
            self._entries[pid] = entry
            self._emit("loaded", pid)
            logger.success("插件 '{}' v{} 已加载", plugin.meta.name, plugin.meta.version)
        except Exception:
            # 即使 on_load 失败，也将插件添加到列表（仅标记错误）
            self._entries[pid] = entry
            entry.error = "on_load 异常，查看日志"
            self._emit("error", pid, entry.error or "")
            logger.exception("插件 {} on_load 异常", pid)

    def _resolve_plugin_for_api(self, plugin_id: str) -> Any | None:
        """为 PluginAPI.get_plugin() 提供依赖插件解析。"""
        entry = self._entries.get(plugin_id)
        if entry is None or not entry.enabled:
            return None
        if not entry.is_library:
            return None
        if isinstance(entry.plugin, LibraryPlugin):
            return entry.plugin.export()
        return None

    # ------------------------------------------------------------------ #
    # 卸载
    # ------------------------------------------------------------------ #

    def unload(self, plugin_id: str) -> None:
        entry = self._entries.pop(plugin_id, None)
        if entry is None:
            return
        try:
            entry.plugin.on_unload()
        except Exception:
            logger.exception("插件 {} on_unload 异常", plugin_id)
        self._emit("unloaded", plugin_id)

    def unload_all(self) -> None:
        for pid in list(self._entries.keys()):
            self.unload(pid)

    def uninstall(self, plugin_id: str) -> tuple[bool, str]:
        """卸载插件并从磁盘删除。

        Returns
        -------
        tuple[bool, str]
            (成功与否, 消息)
        """
        entry = self._entries.get(plugin_id)
        if entry is None:
            return False, f"插件 {plugin_id} 未加载"

        # 检查是否有其他插件依赖此插件
        if entry.dependents:
            names = []
            for dep_id in entry.dependents:
                dep_entry = self._entries.get(dep_id)
                if dep_entry:
                    names.append(dep_entry.meta.name)
            if names:
                return False, (
                    f"无法卸载：以下插件依赖「{entry.meta.name}」\n"
                    f"{', '.join(names)}\n"
                    f"请先卸载这些依赖插件"
                )

        plugin_name = entry.meta.name

        # 1. 调用 on_unload
        self.unload(plugin_id)

        # 2. 清理 sys.modules 中的模块缓存
        module_prefix = f"_plugin_{plugin_id}"
        info_prefix = f"_plugin_info_{plugin_id}"
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith(module_prefix) or mod_name.startswith(info_prefix):
                del sys.modules[mod_name]
                logger.debug("已清理模块缓存: {}", mod_name)

        # 3. 从磁盘删除插件文件
        plugin_dir = PLUGINS_DIR / plugin_id
        plugin_file = PLUGINS_DIR / f"{plugin_id}.py"

        deleted = False
        if plugin_dir.exists():
            try:
                shutil.rmtree(plugin_dir)
                deleted = True
                logger.info("已删除插件目录: {}", plugin_dir)
            except Exception as e:
                return False, f"删除插件目录失败: {e}"
        elif plugin_file.exists():
            try:
                plugin_file.unlink()
                deleted = True
                logger.info("已删除插件文件: {}", plugin_file)
            except Exception as e:
                return False, f"删除插件文件失败: {e}"
        else:
            return False, f"插件文件不存在（{plugin_dir} 或 {plugin_file}）"

        # 4. 清理单文件插件的数据目录
        data_dir = PLUGINS_DIR / "._data" / plugin_id
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)

        logger.success("插件「{}」已卸载并删除", plugin_name)
        return True, f"插件「{plugin_name}」已卸载"

    # ------------------------------------------------------------------ #
    # 启用 / 禁用
    # ------------------------------------------------------------------ #

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        entry = self.get_entry(plugin_id)
        if entry:
            entry.enabled = enabled
            self._emit("enabled_changed", plugin_id, enabled)
            logger.info("插件 {} 状态已更新: {}", plugin_id, "启用" if enabled else "禁用")

    def enable_plugin(self, plugin_id: str) -> None:
        self.set_enabled(plugin_id, True)

    def disable_plugin(self, plugin_id: str) -> None:
        self.set_enabled(plugin_id, False)

    def is_enabled(self, plugin_id: str) -> bool:
        """检查插件是否启用。"""
        entry = self.get_entry(plugin_id)
        return entry.enabled if entry else False

    # ------------------------------------------------------------------ #
    # 前端数据查询
    # ------------------------------------------------------------------ #

    def get_plugin_navigation_items(self) -> list[dict[str, Any]]:
        """获取所有插件的侧边栏导航项（供前端渲染）。

        Returns
        -------
        list[dict]
            导航项列表，每项包含 plugin_id, title, icon, position。
        """
        items = []
        for entry in self._entries.values():
            if not entry.enabled or not entry.plugin:
                continue
            nav_info = entry.plugin.get_navigation_info()
            if nav_info:
                items.append({
                    "plugin_id": entry.meta.id,
                    "title": nav_info.get("title", entry.meta.name),
                    "icon": nav_info.get("icon", FIF.PLUGIN),
                    "position": nav_info.get("position"),
                })
        return items

    def get_plugin_settings_panels(self) -> list[dict[str, Any]]:
        """获取所有插件的设置面板配置（供前端渲染）。

        Returns
        -------
        list[dict]
            设置面板列表，每项包含 plugin_id, name, config。
        """
        panels = []
        for entry in self._entries.values():
            if not entry.enabled or not entry.plugin:
                continue
            settings_config = entry.plugin.create_settings_widget()
            if settings_config:
                panels.append({
                    "plugin_id": entry.meta.id,
                    "name": entry.meta.name,
                    "config": settings_config,
                })
        return panels

    def get_plugin_detail(self, plugin_id: str) -> dict[str, Any] | None:
        """获取插件的详细信息（供前端渲染详情页）。

        Returns
        -------
        dict | None
            插件详情，包含元数据、导航项、设置面板、侧边栏面板。
        """
        entry = self.get_entry(plugin_id)
        if not entry:
            return None

        result = {
            **entry.meta.to_dict(),
            "enabled": entry.enabled,
            "error": entry.error,
            "navigation_info": entry.plugin.get_navigation_info() if entry.plugin else None,
            "settings_panel": entry.plugin.create_settings_widget() if entry.plugin else None,
            "sidebar_panel": entry.plugin.create_sidebar_widget() if entry.plugin else None,
            "sidebar_icon": entry.plugin.get_sidebar_icon() if entry.plugin else None,
            "sidebar_label": entry.plugin.get_sidebar_label() if entry.plugin else None,
        }
        return result


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #

def _load_manifest(plugin_dir: Path) -> PluginMeta | None:
    """从 plugin_dir/plugin.json 加载插件清单，失败返回 None。"""
    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "id" not in data or "name" not in data:
            logger.warning("plugin.json 缺少必填字段 id/name: {}", manifest_path)
            return None
        return PluginMeta.from_dict(data)
    except Exception:
        logger.exception("plugin.json 解析失败: {}", manifest_path)
        return None


def _topo_sort(dep_graph: dict[str, list[str]]) -> list[str]:
    """对插件 ID 进行拓扑排序，返回加载顺序。"""
    in_degree: dict[str, int] = {pid: 0 for pid in dep_graph}
    adj: dict[str, list[str]] = {pid: [] for pid in dep_graph}

    for pid, deps in dep_graph.items():
        for dep in deps:
            if dep not in dep_graph:
                logger.warning("插件 {} 声明依赖 '{}'，但该依赖未安装", pid, dep)
                continue
            adj[dep].append(pid)
            in_degree[pid] += 1

    queue = [pid for pid, deg in in_degree.items() if deg == 0]
    queue.sort()
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in sorted(adj.get(node, [])):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(dep_graph):
        remaining = set(dep_graph) - set(result)
        logger.warning("插件依赖存在循环，受影响的插件: {}，将按原始顺序加载", remaining)
        result.extend(sorted(remaining))

    return result


class _SharedAPIAdapter(PluginAPI):
    """透传适配器：让插件通过自己的局部 API 对象注册，
    但触发器/动作同步写入全局 shared_api。
    """

    def __init__(self, local_api: PluginAPI, shared_api: PluginAPI):
        self.__dict__ = local_api.__dict__
        self._local = local_api
        self._shared = shared_api

    def __getattr__(self, name: str):
        return getattr(self._local, name)

    def register_hook(self, hook_type, callback):
        self._local.register_hook(hook_type, callback)
        self._shared.register_hook(hook_type, callback)

    def register_trigger(self, trigger_id: str, handler=None, **kwargs):
        self._local.register_trigger(trigger_id, handler, **kwargs)
        self._shared.register_trigger(trigger_id, handler, **kwargs)

    def register_action(self, action_id: str, executor=None, **kwargs):
        self._local.register_action(action_id, executor, **kwargs)
        self._shared.register_action(action_id, executor, **kwargs)

    def register_canvas_service(self, name: str, service: Any) -> None:
        self._local.register_canvas_service(name, service)
        self._shared.register_canvas_service(name, service)

    def register_canvas_topbar_btn_factory(self, factory: Any) -> None:
        self._local.register_canvas_topbar_btn_factory(factory)
        self._shared.register_canvas_topbar_btn_factory(factory)
