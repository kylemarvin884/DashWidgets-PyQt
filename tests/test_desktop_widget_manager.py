"""测试桌面小组件管理器"""
from __future__ import annotations

import pytest
from pathlib import Path

from app.models.widget_model import WidgetModel, WidgetInfo
from app.services.desktop_widget_service import DesktopWidgetManager


class TestDesktopWidgetManager:
    """DesktopWidgetManager 单元测试"""

    @pytest.fixture(autouse=True)
    def _reset_singletons(self, tmp_path: Path, monkeypatch):
        """重置所有单例并使用临时配置"""
        # 重置 WidgetModel
        WidgetModel._instance = None
        if hasattr(WidgetModel, "_initialized"):
            delattr(WidgetModel, "_initialized")

        # 重置 DesktopWidgetManager
        DesktopWidgetManager._instance = None
        if hasattr(DesktopWidgetManager, "_initialized"):
            delattr(DesktopWidgetManager, "_initialized")

        # 使用临时配置文件
        widget_config = tmp_path / "widgets.json"
        monkeypatch.setattr("app.models.widget_model.WIDGET_CONFIG", widget_config)

        yield

        WidgetModel._instance = None
        if hasattr(WidgetModel, "_initialized"):
            delattr(WidgetModel, "_initialized")

        DesktopWidgetManager._instance = None
        if hasattr(DesktopWidgetManager, "_initialized"):
            delattr(DesktopWidgetManager, "_initialized")

    def test_singleton(self):
        """单例模式测试"""
        mgr1 = DesktopWidgetManager.instance()
        mgr2 = DesktopWidgetManager.instance()
        assert mgr1 is mgr2

    def test_get_widget_colors_default(self):
        """默认配色测试"""
        mgr = DesktopWidgetManager.instance()
        colors = mgr.get_widget_colors("clock")
        assert "primary" in colors
        assert "secondary" in colors
        assert "background" in colors
        assert "text" in colors

    def test_get_widget_colors_blue_preset(self, tmp_path: Path, monkeypatch):
        """清新蓝配色测试"""
        from app.services.settings_service import SettingsService

        # 重置 SettingsService
        SettingsService._instance = None
        if hasattr(SettingsService, "_initialized"):
            delattr(SettingsService, "_initialized")
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr("app.services.settings_service.SETTINGS_CONFIG", settings_file)

        svc = SettingsService.instance()
        svc.set_color_preset("清新蓝")

        mgr = DesktopWidgetManager.instance()
        colors = mgr.get_widget_colors("clock")
        # 清新蓝的时钟主色应为蓝色系
        assert colors["primary"].startswith("#0")

    def test_show_hide_widget_state(self):
        """激活状态应在模型中正确反映"""
        # 注意：这里不实际创建 Qt 窗口，只测试模型状态
        model = WidgetModel()
        model.activate_widget("clock")
        assert model.get_widget("clock").is_active is True

        model.deactivate_widget("clock")
        assert model.get_widget("clock").is_active is False

    def test_widget_position_update(self):
        """位置更新应正确持久化"""
        model = WidgetModel()
        model.update_widget_position("clock", (100, 200))
        assert model.get_widget("clock").position == (100, 200)

    def test_widget_size_update(self):
        """尺寸更新应正确持久化"""
        model = WidgetModel()
        model.update_widget_size("clock", (400, 300))
        assert model.get_widget("clock").size_override == (400, 300)

    def test_available_widgets_count(self):
        """可用组件数量测试"""
        model = WidgetModel()
        all_widgets = model.get_all_widgets()
        assert len(all_widgets) >= 10  # 至少有10个内置组件

    def test_categories(self):
        """分类测试"""
        model = WidgetModel()
        categories = model.get_categories()
        assert "时间" in categories
        assert "系统" in categories
        assert "信息" in categories
