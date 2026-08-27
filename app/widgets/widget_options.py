"""
组件自定义选项 — 声明式 schema

每个组件可声明一组「信息显示」选项，由组件设置对话框自动渲染成
开关/下拉/数字控件，值保存在 widget.custom_settings 并通过
on_settings_changed 推送给组件实例。

选项描述符格式::

    {
        "key": "show_date",          # settings 键名
        "label": "显示日期行",         # 界面文案
        "type": "bool",              # bool | choice | int
        "default": True,
        # type=choice 时：
        "choices": [("a", "选项甲"), ("b", "选项乙")],   # (值, 显示名)
        # type=int 时：
        "min": 1, "max": 10, "suffix": " 条",
    }
"""
from __future__ import annotations

from typing import Any

_WIDGET_OPTIONS: dict[str, list[dict[str, Any]]] = {
    "clock": [
        {"key": "show_date", "label": "显示日期行", "type": "bool", "default": True},
        # show_seconds 已在外观区块提供，这里不重复声明
    ],
    "system_monitor": [
        {"key": "show_cpu", "label": "显示 CPU", "type": "bool", "default": True},
        {"key": "show_mem", "label": "显示内存", "type": "bool", "default": True},
        {"key": "show_disk", "label": "显示磁盘", "type": "bool", "default": True},
        {"key": "show_cpu_freq", "label": "显示 CPU 频率", "type": "bool", "default": True},
    ],
    "network_monitor": [
        {"key": "show_totals", "label": "显示累计流量", "type": "bool", "default": True},
    ],
    "weather": [
        {"key": "show_detail", "label": "显示湿度/风速", "type": "bool", "default": True},
    ],
    "music": [
        {"key": "show_artist", "label": "显示歌手", "type": "bool", "default": True},
    ],
    "battery": [
        {"key": "show_time", "label": "显示剩余时间", "type": "bool", "default": True},
    ],
    "rss": [
        {"key": "max_items", "label": "显示条数", "type": "int",
         "default": 6, "min": 1, "max": 10, "suffix": " 条"},
        {"key": "show_source", "label": "显示来源", "type": "bool", "default": True},
    ],
    "exchange": [
        {"key": "show_usd", "label": "美元 USD", "type": "bool", "default": True},
        {"key": "show_eur", "label": "欧元 EUR", "type": "bool", "default": True},
        {"key": "show_gbp", "label": "英镑 GBP", "type": "bool", "default": True},
        {"key": "show_jpy", "label": "日元 JPY", "type": "bool", "default": True},
        {"key": "show_hkd", "label": "港币 HKD", "type": "bool", "default": True},
    ],
}


def get_widget_options(widget_id: str) -> list[dict[str, Any]]:
    """获取组件的自定义选项声明（无则返回空列表）"""
    return _WIDGET_OPTIONS.get(widget_id, [])


def get_option_defaults(widget_id: str) -> dict[str, Any]:
    """获取组件选项的默认值字典（未声明选项的组件返回空）"""
    return {opt["key"]: opt.get("default") for opt in _WIDGET_OPTIONS.get(widget_id, [])}
