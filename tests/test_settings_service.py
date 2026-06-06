"""测试设置服务"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from app.services.settings_service import SettingsService


class TestSettingsService:
    """SettingsService 单元测试"""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self, tmp_path: Path, monkeypatch):
        """每个测试前重置单例并使用临时配置目录"""
        SettingsService._instance = None
        if hasattr(SettingsService, "_initialized"):
            delattr(SettingsService, "_initialized")

        config_file = tmp_path / "settings.json"
        monkeypatch.setattr("app.services.settings_service.SETTINGS_CONFIG", config_file)
        yield

        SettingsService._instance = None
        if hasattr(SettingsService, "_initialized"):
            delattr(SettingsService, "_initialized")

    def test_default_values(self):
        """默认值测试"""
        svc = SettingsService.instance()
        assert svc.light_mode is True
        assert svc.color_scheme == "blue"
        assert svc.color_preset == "默认"
        assert svc.font_family == "Microsoft YaHei"
        assert svc.font_size == 12
        assert svc.widget_opacity == 0
        assert svc.click_through is False
        assert svc.snap_to_grid is True
        assert svc.grid_size == 20
        assert svc.prevent_overlap is True
        assert svc.snap_to_edge is True
        assert svc.drag_animation_enabled is True
        assert svc.low_power_mode is False
        assert svc.update_frequency == 1000
        assert svc.widget_groups == ["工作", "娱乐", "学习"]
        assert svc.autostart is False
        assert svc.theme == "light"
        assert svc.mica_enabled is False

    def test_setters_and_persistence(self, tmp_path: Path):
        """设置值后应持久化到文件"""
        svc = SettingsService.instance()
        svc.set_color_scheme("green")
        svc.set_font_size(14)
        svc.set_widget_opacity(80)
        svc.set_click_through(True)
        svc.set_snap_to_grid(False)
        svc.set_grid_size(40)
        svc.set_low_power_mode(True)
        svc.set_autostart(True)
        svc.set_mica_enabled(True)

        # 验证内存值
        assert svc.color_scheme == "green"
        assert svc.font_size == 14
        assert svc.widget_opacity == 80
        assert svc.click_through is True
        assert svc.snap_to_grid is False
        assert svc.grid_size == 40
        assert svc.low_power_mode is True
        assert svc.autostart is True
        assert svc.mica_enabled is True

        # 验证文件内容
        config_file = tmp_path / "settings.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["colorScheme"] == "green"
        assert data["fontSize"] == 14
        assert data["widgetOpacity"] == 80
        assert data["clickThrough"] is True
        assert data["snapToGrid"] is False
        assert data["gridSize"] == 40
        assert data["lowPowerMode"] is True
        assert data["autostart"] is True
        assert data["micaEnabled"] is True

    def test_load_existing_config(self, tmp_path: Path, monkeypatch):
        """应能正确加载已有配置文件"""
        config_file = tmp_path / "settings.json"
        config_file.write_text(
            json.dumps({
                "colorScheme": "purple",
                "fontSize": 16,
                "widgetOpacity": 50,
                "lightMode": False,
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        SettingsService._instance = None
        if hasattr(SettingsService, "_initialized"):
            delattr(SettingsService, "_initialized")

        svc = SettingsService.instance()
        assert svc.color_scheme == "purple"
        assert svc.font_size == 16
        assert svc.widget_opacity == 50
        assert svc.light_mode is False

    def test_widget_opacity_clamping(self):
        """透明度应在 0-100 范围内被截断"""
        svc = SettingsService.instance()
        svc.set_widget_opacity(150)
        assert svc.widget_opacity == 100
        svc.set_widget_opacity(-10)
        assert svc.widget_opacity == 0

    def test_widget_groups_management(self):
        """分组管理测试"""
        svc = SettingsService.instance()
        svc.set_widget_groups(["工作", "生活", "娱乐", "学习"])
        assert svc.widget_groups == ["工作", "生活", "娱乐", "学习"]
        assert svc.group_visibility == {
            "工作": True,
            "生活": True,
            "娱乐": True,
            "学习": True,
        }

    def test_color_preset_fallback(self, tmp_path: Path, monkeypatch):
        """旧配置缺少 colorPreset 时应回退到默认值"""
        config_file = tmp_path / "settings.json"
        config_file.write_text(
            json.dumps({"colorScheme": "red"}, ensure_ascii=False),
            encoding="utf-8",
        )

        SettingsService._instance = None
        if hasattr(SettingsService, "_initialized"):
            delattr(SettingsService, "_initialized")

        svc = SettingsService.instance()
        assert svc.color_preset == "默认"

    def test_change_callback(self):
        """变更监听器测试"""
        svc = SettingsService.instance()
        called = [False]

        def callback():
            called[0] = True

        svc.on_changed(callback)
        svc.set_theme("dark")
        assert called[0] is True

        # 移除监听器
        svc.off_changed(callback)
        called[0] = False
        svc.set_theme("light")
        assert called[0] is False
