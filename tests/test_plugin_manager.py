"""插件管理器测试：加载/热重载/卸载/权限/版本检查"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.plugins.base_plugin import BasePlugin, HookType, PluginAPI, PluginMeta
from app.plugins.plugin_manager import PluginManager, _topo_sort, _version_tuple


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #

class TestTopoSort:
    def test_no_deps_preserves_stable_order(self):
        assert _topo_sort({"b": [], "a": [], "c": []}) == ["a", "b", "c"]

    def test_dependency_order(self):
        # c 依赖 b，b 依赖 a → a, b, c
        order = _topo_sort({"c": ["b"], "b": ["a"], "a": []})
        assert order.index("a") < order.index("b") < order.index("c")

    def test_missing_dependency_not_fatal(self):
        order = _topo_sort({"a": ["ghost"], "b": []})
        assert set(order) == {"a", "b"}

    def test_cycle_falls_back_to_all(self):
        order = _topo_sort({"a": ["b"], "b": ["a"]})
        assert sorted(order) == ["a", "b"]


class TestVersionTuple:
    def test_basic(self):
        assert _version_tuple("1.2.3") == (1, 2, 3)

    def test_with_suffix(self):
        assert _version_tuple("1.2.3-beta.1") == (1, 2, 3)

    def test_comparison(self):
        assert _version_tuple("1.10.0") > _version_tuple("1.9.9")
        assert _version_tuple("2.0") > _version_tuple("1.99.99")


# --------------------------------------------------------------------------- #
# 插件加载生命周期
# --------------------------------------------------------------------------- #

_SIMPLE_PLUGIN = '''
from app.plugins.base_plugin import BasePlugin, PluginMeta, HookType


class Plugin(BasePlugin):
    meta = PluginMeta(id="demo_plugin", name="演示插件", version="1.0.0")
    loaded_marker = []

    def on_load(self, api):
        self.api = api
        api.register_hook(HookType.ON_WIDGET_SHOWN, self._on_shown)
        Plugin.loaded_marker.append("load")

    def on_unload(self):
        Plugin.loaded_marker.append("unload")

    def _on_shown(self, widget_id):
        Plugin.loaded_marker.append(f"shown:{widget_id}")
'''


class TestPluginLifecycle:
    @pytest.fixture
    def plugins_dir(self, tmp_path: Path, monkeypatch) -> Path:
        base = tmp_path / "plugins_ext"
        base.mkdir()
        monkeypatch.setattr("app.plugins.plugin_manager.PLUGINS_DIR", base)
        monkeypatch.setattr("app.constants.PLUGINS_DIR", base)
        return base

    @pytest.fixture
    def perm_file(self, tmp_path: Path, monkeypatch) -> Path:
        f = tmp_path / "config" / "plugin_permissions.json"
        monkeypatch.setattr(
            "app.plugins.plugin_manager._PERMISSION_STATE_FILE", f
        )
        return f

    def _write_plugin(self, base: Path, code: str, manifest: dict | None = None):
        pdir = base / "demo_plugin"
        pdir.mkdir(exist_ok=True)
        (pdir / "__init__.py").write_text(code, encoding="utf-8")
        if manifest is not None:
            (pdir / "plugin.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
        return pdir

    def test_discover_and_load(self, plugins_dir, perm_file):
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN)
        mgr = PluginManager()
        mgr.discover_and_load()

        entry = mgr.get_entry("demo_plugin")
        assert entry is not None
        assert entry.meta.name == "演示插件"
        assert entry.enabled is True

    def test_hook_fired(self, plugins_dir, perm_file):
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN)
        mgr = PluginManager()
        mgr.discover_and_load()

        mgr.emit_hook(HookType.ON_WIDGET_SHOWN, "clock")
        # 钩子在共享 API 上生效
        assert mgr.api.emit_hook(HookType.ON_WIDGET_SHOWN, "clock") is not None

    def test_hot_reload(self, plugins_dir, perm_file):
        pdir = self._write_plugin(plugins_dir, _SIMPLE_PLUGIN)
        mgr = PluginManager()
        mgr.discover_and_load()
        assert mgr.get_entry("demo_plugin") is not None

        # 修改插件代码（版本号变化）
        new_code = _SIMPLE_PLUGIN.replace('version="1.0.0"', 'version="2.0.0"')
        (pdir / "__init__.py").write_text(new_code, encoding="utf-8")

        ok, msg = mgr.reload_plugin("demo_plugin")
        assert ok, msg
        entry = mgr.get_entry("demo_plugin")
        assert entry is not None
        assert entry.meta.version == "2.0.0"

        # 模块缓存已刷新（重新执行的模块对象）
        mod = sys.modules.get("_plugin_demo_plugin")
        assert mod is not None

    def test_uninstall_removes_files_and_cache(self, plugins_dir, perm_file):
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN)
        mgr = PluginManager()
        mgr.discover_and_load()

        ok, msg = mgr.uninstall("demo_plugin")
        assert ok, msg
        assert mgr.get_entry("demo_plugin") is None
        assert not (plugins_dir / "demo_plugin").exists()
        assert "_plugin_demo_plugin" not in sys.modules
        assert "_plugin_info_demo_plugin" not in sys.modules

    def test_uninstall_not_loaded_but_files_exist(self, plugins_dir, perm_file):
        """加载失败的插件也应能从磁盘卸载"""
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN)
        mgr = PluginManager()  # 未调用 discover_and_load

        ok, _msg = mgr.uninstall("demo_plugin")
        assert ok
        assert not (plugins_dir / "demo_plugin").exists()

    def test_disable_detaches_hooks(self, plugins_dir, perm_file):
        from app.plugins.base_plugin import BasePlugin as BP

        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN)
        mgr = PluginManager()
        mgr.discover_and_load()

        shared = mgr.api
        before = len(shared._hooks.get(HookType.ON_WIDGET_SHOWN, []))
        assert before > 0

        mgr.disable_plugin("demo_plugin")
        assert shared._hooks.get(HookType.ON_WIDGET_SHOWN, []) == []

        mgr.enable_plugin("demo_plugin")
        assert len(shared._hooks.get(HookType.ON_WIDGET_SHOWN, [])) == before

    def test_always_allow_persisted(self, plugins_dir, perm_file):
        manifest = {
            "id": "demo_plugin", "name": "演示插件",
            "permissions": ["network"],
        }
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN, manifest)

        # 首次加载：模拟用户"始终允许"
        decisions = []
        mgr = PluginManager(
            permission_check_callback=lambda name, perms: (
                decisions.append(name) or (True, True)
            )
        )
        mgr.discover_and_load()
        assert decisions == ["演示插件"]
        assert perm_file.exists()
        assert "demo_plugin" in json.loads(perm_file.read_text(encoding="utf-8"))["always_allowed"]

        # 第二个管理器实例（模拟重启）：不再弹权限询问
        decisions2 = []
        mgr2 = PluginManager(
            permission_check_callback=lambda name, perms: (
                decisions2.append(name) or (True, False)
            )
        )
        mgr2.discover_and_load()
        assert decisions2 == []

    def test_permission_denied_blocks_load(self, plugins_dir, perm_file):
        manifest = {
            "id": "demo_plugin", "name": "演示插件",
            "permissions": ["network"],
        }
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN, manifest)

        errors = []
        mgr = PluginManager(
            permission_check_callback=lambda name, perms: (False, False),
        )
        mgr.on("error", lambda pid, msg: errors.append((pid, msg)))
        mgr.discover_and_load()

        assert mgr.get_entry("demo_plugin") is None
        assert errors and errors[0][0] == "demo_plugin"

    def test_has_permission_reflects_grant(self, plugins_dir, perm_file):
        from app.plugins.base_plugin import PluginPermission

        manifest = {
            "id": "demo_plugin", "name": "演示插件",
            "permissions": ["network"],
        }
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN, manifest)
        mgr = PluginManager(
            permission_check_callback=lambda name, perms: (True, True)
        )
        mgr.discover_and_load()

        api = mgr.get_entry("demo_plugin").api
        assert api.has_permission(PluginPermission.NETWORK) is True
        assert api.has_permission(PluginPermission.FS_READ) is False

    def test_min_host_version_blocks_load(self, plugins_dir, perm_file):
        manifest = {
            "id": "demo_plugin", "name": "演示插件",
            "min_host_version": "999.0.0",
        }
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN, manifest)
        mgr = PluginManager()
        mgr.discover_and_load()

        assert mgr.get_entry("demo_plugin") is None

    def test_min_host_version_satisfied(self, plugins_dir, perm_file):
        manifest = {
            "id": "demo_plugin", "name": "演示插件",
            "min_host_version": "0.1.0",
        }
        self._write_plugin(plugins_dir, _SIMPLE_PLUGIN, manifest)
        mgr = PluginManager()
        mgr.discover_and_load()

        assert mgr.get_entry("demo_plugin") is not None


class TestFireTrigger:
    def test_fire_trigger_emits_event(self):
        from app.events import EventBus, EventType

        api = PluginAPI(plugin_id="test_plugin")
        received = []

        def _on_event(**kwargs):
            received.append(kwargs)

        EventBus.instance().subscribe(EventType.AUTOMATION_TRIGGERED, _on_event)
        try:
            api.fire_trigger("my.trigger", value=1)
        finally:
            EventBus.instance().unsubscribe(EventType.AUTOMATION_TRIGGERED, _on_event)

        assert received and received[0]["trigger_id"] == "my.trigger"
        assert received[0]["source_plugin"] == "test_plugin"
