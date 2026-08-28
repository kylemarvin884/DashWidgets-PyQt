"""
组件自定义选项 — 声明式 schema

每个组件可声明一组「信息显示」选项，由组件设置窗口自动渲染成
开关/下拉/数字控件，值保存在 widget.custom_settings 并通过
on_settings_changed 推送给组件实例。

选项描述符格式::

    {
        "key": "show_date",          # settings 键名
        "label": "显示日期行",         # 界面文案
        "type": "bool",              # bool | choice | int | currency_pair
        "default": True,
        # type=choice 时：
        "choices": [("a", "选项甲"), ("b", "选项乙")],   # (值, 显示名)
        # type=int 时：
        "min": 1, "max": 10, "suffix": " 条",
        # type=currency_pair 时（每行显示哪两种货币的汇率）：
        "currencies": ["USD", "EUR", ...],   # 可选货币
    }

组件还可通过 :func:`register_settings_pages`（widget_options 模块级
注册表）在组件设置窗口注册自定义页面（可多个），页面为
SettingCard 卡片的垂直列表。
"""
from __future__ import annotations

from typing import Any, Callable

_WIDGET_OPTIONS: dict[str, list[dict[str, Any]]] = {
    "clock": [
        {"key": "show_date", "label": "显示日期行", "type": "bool", "default": True},
        # show_seconds 已在外观区块提供，这里不重复声明
        {"key": "hour_12", "label": "12 小时制", "type": "bool", "default": False},
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
        {"key": "unit", "label": "温度单位", "type": "choice",
         "default": "°C", "choices": [("°C", "摄氏度 °C"), ("°F", "华氏度 °F"), ("K", "开尔文 K")]},
    ],
    "music": [
        {"key": "show_artist", "label": "显示歌手", "type": "bool", "default": True},
    ],
    "battery": [
        {"key": "show_time", "label": "显示剩余时间", "type": "bool", "default": True},
    ],
    "todo": [
        {"key": "show_done_count", "label": "显示完成计数", "type": "bool", "default": True},
    ],
    "rss": [
        {"key": "max_items", "label": "显示条数", "type": "int",
         "default": 6, "min": 1, "max": 10, "suffix": " 条"},
        {"key": "show_source", "label": "显示来源", "type": "bool", "default": True},
    ],
    "exchange": [
        {"key": "pair_1", "label": "第 1 行", "type": "currency_pair",
         "default": ["USD", "CNY"],
         "currencies": ["USD", "EUR", "GBP", "JPY", "HKD", "CNY", "KRW", "AUD", "CAD", "CHF"]},
        {"key": "pair_2", "label": "第 2 行", "type": "currency_pair",
         "default": ["EUR", "CNY"],
         "currencies": ["USD", "EUR", "GBP", "JPY", "HKD", "CNY", "KRW", "AUD", "CAD", "CHF"]},
        {"key": "pair_3", "label": "第 3 行", "type": "currency_pair",
         "default": ["GBP", "CNY"],
         "currencies": ["USD", "EUR", "GBP", "JPY", "HKD", "CNY", "KRW", "AUD", "CAD", "CHF"]},
        {"key": "pair_4", "label": "第 4 行", "type": "currency_pair",
         "default": ["JPY", "CNY"],
         "currencies": ["USD", "EUR", "GBP", "JPY", "HKD", "CNY", "KRW", "AUD", "CAD", "CHF"]},
        {"key": "pair_5", "label": "第 5 行", "type": "currency_pair",
         "default": ["HKD", "CNY"],
         "currencies": ["USD", "EUR", "GBP", "JPY", "HKD", "CNY", "KRW", "AUD", "CAD", "CHF"]},
        {"key": "pair_6", "label": "第 6 行", "type": "currency_pair",
         "default": ["AUD", "CNY"],
         "currencies": ["USD", "EUR", "GBP", "JPY", "HKD", "CNY", "KRW", "AUD", "CAD", "CHF"]},
    ],
}


def get_widget_options(widget_id: str) -> list[dict[str, Any]]:
    """获取组件的自定义选项声明（无则返回空列表）"""
    return _WIDGET_OPTIONS.get(widget_id, [])


def get_option_defaults(widget_id: str) -> dict[str, Any]:
    """获取组件选项的默认值字典（未声明选项的组件返回空）"""
    return {opt["key"]: opt.get("default") for opt in _WIDGET_OPTIONS.get(widget_id, [])}


# --------------------------------------------------------------------------- #
# 组件自定义设置页面注册表（组件/插件可注册多个页面）
# --------------------------------------------------------------------------- #

# {widget_id: [(page_id, icon, title, factory), ...]}
# factory: () -> QWidget（页面内容，SettingCard 卡片列表或任意控件）
_CUSTOM_SETTINGS_PAGES: dict[str, list[dict[str, Any]]] = {}


def register_settings_page(widget_id: str, page_id: str, title: str,
                           factory: Callable[[], QWidget],
                           icon: Any = None) -> bool:
    """为组件的设置窗口注册一个自定义页面（可多次调用注册多页）。

    Parameters
    ----------
    widget_id : str
        目标组件的 WIDGET_TYPE。
    page_id : str
        页面唯一标识（同组件内不可重复，重复注册返回 False）。
    title : str
        导航栏显示的页面标题。
    factory : Callable[[], QWidget]
        页面内容工厂，返回一个 QWidget（通常为 SettingCard 列表容器）。
        工厂在设置窗口打开时才被调用，可安全捕获组件实例。
    icon : FluentIconBase, optional
        导航图标，默认信息图标。

    Returns
    -------
    bool
        注册是否成功（page_id 重复时返回 False）。
    """
    pages = _CUSTOM_SETTINGS_PAGES.setdefault(widget_id, [])
    if any(p["page_id"] == page_id for p in pages):
        return False
    pages.append({
        "page_id": page_id,
        "title": title,
        "factory": factory,
        "icon": icon,
    })
    return True


def unregister_settings_pages(widget_id: str, page_ids: list[str]) -> None:
    """注销组件的自定义设置页面（组件关闭/插件卸载时调用）"""
    pages = _CUSTOM_SETTINGS_PAGES.get(widget_id)
    if not pages:
        return
    _CUSTOM_SETTINGS_PAGES[widget_id] = [
        p for p in pages if p["page_id"] not in page_ids
    ]


def get_settings_pages(widget_id: str) -> list[dict[str, Any]]:
    """获取组件注册的自定义设置页面列表"""
    return list(_CUSTOM_SETTINGS_PAGES.get(widget_id, []))
