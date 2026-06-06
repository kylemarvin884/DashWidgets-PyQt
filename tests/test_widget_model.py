"""测试小组件数据模型"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from app.models.widget_model import WidgetInfo, WidgetModel, AVAILABLE_WIDGETS


class TestWidgetInfo:
    """WidgetInfo 单元测试"""

    def test_to_dict_roundtrip(self):
        """to_dict / from_dict 往返应保持数据一致"""
        original = WidgetInfo(
            id="test_widget",
            name="测试组件",
            description="一个测试用组件",
            icon_name="HOME",
            size="medium",
            category="测试",
            is_active=True,
            position=(100, 200),
            size_override=(300, 400),
            custom_settings={"key": "value"},
            plugin_id="test_plugin",
        )
        data = original.to_dict()
        restored = WidgetInfo.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.icon_name == original.icon_name
        assert restored.size == original.size
        assert restored.category == original.category
        assert restored.is_active == original.is_active
        assert restored.position == original.position
        assert restored.size_override == original.size_override
        assert restored.custom_settings == original.custom_settings
        assert restored.plugin_id == original.plugin_id

    def test_from_dict_list_to_tuple(self):
        """JSON 反序列化后的 list 应被正确转为 tuple"""
        data = {
            "id": "test",
            "name": "Test",
            "icon_name": "HOME",
            "position": [10, 20],
            "size_override": [100, 200],
        }
        info = WidgetInfo.from_dict(data)
        assert isinstance(info.position, tuple)
        assert info.position == (10, 20)
        assert isinstance(info.size_override, tuple)
        assert info.size_override == (100, 200)

    def test_default_values(self):
        """默认值测试"""
        info = WidgetInfo(id="test", name="Test", icon_name="HOME")
        assert info.size == "medium"
        assert info.category == "默认"
        assert info.is_active is False
        assert info.position is None
        assert info.size_override is None
        assert info.custom_settings == {}
        assert info.plugin_id is None


class TestWidgetModel:
    """WidgetModel 单元测试"""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self, tmp_path: Path, monkeypatch):
        """每个测试前重置单例并使用临时配置目录"""
        # 清理单例状态
        WidgetModel._instance = None
        if hasattr(WidgetModel, "_initialized"):
            delattr(WidgetModel, "_initialized")

        # Monkeypatch 配置文件路径到临时目录
        config_file = tmp_path / "widgets.json"
        monkeypatch.setattr("app.models.widget_model.WIDGET_CONFIG", config_file)
        yield
        # 测试后再次清理
        WidgetModel._instance = None
        if hasattr(WidgetModel, "_initialized"):
            delattr(WidgetModel, "_initialized")

    def test_load_defaults_when_no_config(self):
        """无配置文件时应加载默认组件列表"""
        model = WidgetModel()
        all_widgets = model.get_all_widgets()
        assert len(all_widgets) == len(AVAILABLE_WIDGETS)
        assert model.get_widget("clock") is not None
        assert model.get_widget("weather") is not None

    def test_save_and_load(self, tmp_path: Path):
        """保存后应能正确加载"""
        model = WidgetModel()
        model.activate_widget("clock")
        model.update_widget_position("clock", (100, 200))

        # 重新加载
        WidgetModel._instance = None
        if hasattr(WidgetModel, "_initialized"):
            delattr(WidgetModel, "_initialized")
        model2 = WidgetModel()

        clock = model2.get_widget("clock")
        assert clock is not None
        assert clock.is_active is True
        assert clock.position == (100, 200)

    def test_activate_deactivate(self):
        """激活/停用测试"""
        model = WidgetModel()
        model.activate_widget("clock")
        assert model.get_widget("clock").is_active is True

        model.deactivate_widget("clock")
        assert model.get_widget("clock").is_active is False
        assert model.get_widget("clock").position is None

    def test_get_by_category(self):
        """按分类获取测试"""
        model = WidgetModel()
        time_widgets = model.get_widgets_by_category("时间")
        assert len(time_widgets) >= 4  # clock, stopwatch, timer, pomodoro
        assert all(w.category == "时间" for w in time_widgets)

    def test_update_position(self):
        """更新位置测试"""
        model = WidgetModel()
        model.update_widget_position("clock", (50, 100))
        assert model.get_widget("clock").position == (50, 100)

    def test_update_size(self):
        """更新尺寸测试"""
        model = WidgetModel()
        model.update_widget_size("clock", (400, 300))
        assert model.get_widget("clock").size_override == (400, 300)
