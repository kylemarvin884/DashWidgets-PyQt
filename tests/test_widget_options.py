"""组件自定义选项（信息显示）测试"""
from __future__ import annotations

import pytest

from app.widgets.widget_options import get_option_defaults, get_widget_options


class TestWidgetOptionsSchema:
    def test_schema_validity(self):
        """所有选项声明必须含 key/label/type，且 type 受支持"""
        supported = {"bool", "choice", "int", "currency_pair"}
        for widget_id, options in get_widget_options.__globals__["_WIDGET_OPTIONS"].items():
            assert options, f"{widget_id} 声明了空选项列表"
            for opt in options:
                assert "key" in opt and "label" in opt and "type" in opt, opt
                assert opt["type"] in supported, opt
                assert "default" in opt, f"{widget_id}.{opt['key']} 缺少 default"
                if opt["type"] == "choice":
                    assert opt.get("choices"), f"{widget_id}.{opt['key']} choice 缺少选项"
                if opt["type"] == "int":
                    assert "min" in opt and "max" in opt, f"{widget_id}.{opt['key']} int 缺少范围"
                if opt["type"] == "currency_pair":
                    assert opt.get("currencies"), f"{widget_id}.{opt['key']} 缺少可选货币"

    def test_defaults_consistent(self):
        for widget_id in ("clock", "system_monitor", "network_monitor", "weather",
                          "music", "battery", "rss", "exchange"):
            options = get_widget_options(widget_id)
            defaults = get_option_defaults(widget_id)
            assert set(defaults) == {o["key"] for o in options}

    def test_unknown_widget_empty(self):
        assert get_widget_options("no_such_widget") == []
        assert get_option_defaults("no_such_widget") == {}


class TestWidgetOptionConsumption:
    """组件实际消费选项（离屏 GUI 验证）"""

    @pytest.fixture(scope="class", autouse=True)
    def _qapp(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        yield app

    def _create(self, widget_type: str, settings: dict):
        from app.widgets.registry import WidgetRegistry
        from app.widgets.base_widget import WidgetConfig
        cfg = WidgetConfig(
            widget_type=widget_type, id=widget_type,
            width=320, height=220, settings=settings,
        )
        w = WidgetRegistry.instance().create(cfg, {})
        assert w is not None, f"{widget_type} 创建失败"
        return w

    def test_clock_show_date(self):
        w = self._create("clock", {"show_date": False})
        assert not w._date_label.isVisibleTo(w)
        w.on_settings_changed({"show_date": True})
        assert w._date_label.isVisibleTo(w)

    def test_system_monitor_rows(self):
        w = self._create("system_monitor", {"show_disk": False})
        assert not w._disk_bar.isVisibleTo(w)
        w.on_settings_changed({"show_mem": False, "show_disk": True})
        assert not w._mem_bar.isVisibleTo(w)
        assert w._disk_bar.isVisibleTo(w)

    def test_network_monitor_totals(self):
        w = self._create("network_monitor", {"show_totals": False})
        assert not w._up_total_label.isVisibleTo(w)
        w.on_settings_changed({"show_totals": True})
        assert w._up_total_label.isVisibleTo(w)

    def test_music_artist(self):
        w = self._create("music", {"show_artist": False})
        assert not w._artist_label.isVisibleTo(w)
        w.on_settings_changed({"show_artist": True})
        assert w._artist_label.isVisibleTo(w)

    def test_exchange_pairs_configurable(self):
        """汇率组件按 pair_N 设置渲染任意货币对，配置变化时重建行"""
        w = self._create("exchange", {"pair_1": ["JPY", "USD"]})
        assert ("JPY", "USD") in w._rate_labels
        assert ("EUR", "CNY") in w._rate_labels  # 未配置的行用默认值

        # 配置变化 → 行重建
        w.on_settings_changed({"pair_1": ["GBP", "JPY"]})
        assert ("GBP", "JPY") in w._rate_labels
        assert ("JPY", "USD") not in w._rate_labels

    def test_exchange_cross_rate(self):
        """任意货币对换算（EUR 中转）"""
        from app.services.exchange_service import ExchangeService, ExchangeData
        data = ExchangeData(rates={"EUR": 1.0, "USD": 1.1, "CNY": 7.8}, last_updated=0)
        assert abs(ExchangeService.cross_rate(data, "USD", "CNY") - 7.8 / 1.1) < 1e-9
        assert ExchangeService.cross_rate(data, "EUR", "EUR") == 1.0
        assert ExchangeService.cross_rate(data, "XXX", "CNY") is None

    def test_rss_max_items(self):
        w = self._create("rss", {"max_items": 3})
        assert w._max_items == 3
        w._last_rows = [(f"标题{i}", "来源", f"https://x/{i}") for i in range(8)]
        w._rebuild_rows()
        visible = [i for i in range(w._list_lay.count())
                   if w._list_lay.itemAt(i).widget() and w._list_lay.itemAt(i).widget().isVisibleTo(w)]
        assert len(visible) == 3
        w.on_settings_changed({"max_items": 5})
        visible = [i for i in range(w._list_lay.count())
                   if w._list_lay.itemAt(i).widget() and w._list_lay.itemAt(i).widget().isVisibleTo(w)]
        assert len(visible) == 5


class TestSettingsDialogOptions:
    """设置对话框渲染信息显示区块并正确收集/回填（SettingCard 版）"""

    @pytest.fixture(scope="class", autouse=True)
    def _qapp(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        yield app

    @pytest.fixture
    def _isolated_model(self, tmp_path, monkeypatch):
        """用临时 widgets.json，避免污染真实配置"""
        import json
        cfg = tmp_path / "widgets.json"

        def _save_defaults():
            from app.models.widget_model import WidgetModel, AVAILABLE_WIDGETS
            data = {"widgets": [w.to_dict() for w in AVAILABLE_WIDGETS]}
            cfg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        _save_defaults()
        from app.models import widget_model
        monkeypatch.setattr(widget_model, "WIDGET_CONFIG", cfg)
        widget_model.WidgetModel._instance = None
        yield
        widget_model.WidgetModel._instance = None

    def test_dialog_renders_and_collects(self, _isolated_model):
        from app.widgets.widget_settings_dialog import WidgetSettingsWindow as WidgetSettingsDialog

        dlg = WidgetSettingsDialog("system_monitor")
        # 渲染出了 schema 声明的 4 个开关
        assert set(dlg._option_controls) == {"show_cpu", "show_mem", "show_disk", "show_cpu_freq"}

        # 切换开关 → 立即写入 settings（实时生效；未动过的键不写入，
        # 由组件侧默认值兜底）
        dlg._option_controls["show_disk"][1].setChecked(False)
        assert dlg.widget_info.custom_settings.get("show_disk") is False
        assert "show_cpu" not in dlg.widget_info.custom_settings

        # 回填：再次打开能恢复
        dlg2 = WidgetSettingsDialog("system_monitor")
        assert dlg2._option_controls["show_disk"][1].isChecked() is False

    def test_dialog_no_options_widget(self, _isolated_model):
        from app.widgets.widget_settings_dialog import WidgetSettingsWindow as WidgetSettingsDialog
        dlg = WidgetSettingsDialog("note")
        assert not dlg._option_controls

    def test_dialog_range_and_reset(self, _isolated_model):
        from app.widgets.widget_settings_dialog import WidgetSettingsWindow as WidgetSettingsDialog

        dlg = WidgetSettingsDialog("rss")
        dlg._option_controls["max_items"][1].setValue(9)
        assert dlg.widget_info.custom_settings.get("max_items") == 9

        # 恢复默认
        dlg._reset_defaults()
        assert dlg.widget_info.custom_settings.get("max_items") == 6
        assert dlg.widget_info.custom_settings.get("show_source") is True

    def test_dialog_clock_opacity_conversion(self, _isolated_model):
        """时钟透明度卡片（百分比）→ 存储 0-1 小数"""
        from app.widgets.widget_settings_dialog import WidgetSettingsWindow as WidgetSettingsDialog
        dlg = WidgetSettingsDialog("clock")
        dlg._opacity_card.setValue(70)
        assert abs(dlg.widget_info.custom_settings.get("opacity") - 0.70) < 0.001
