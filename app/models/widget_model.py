"""
小组件数据模型
"""
from __future__ import annotations
from typing import Any
from dataclasses import dataclass, field, asdict

from PySide6.QtCore import QObject, Signal

from app.constants import WIDGET_CONFIG
from loguru import logger


@dataclass
class WidgetInfo:
    """小组件信息"""
    id: str                      # 唯一标识符
    name: str                    # 显示名称
    description: str = ""         # 描述
    icon_name: str = "APPLICATION"  # 图标名称 (FluentIcon)
    size: str = "medium"         # 尺寸: small, medium, large
    category: str = "默认"        # 分类
    is_active: bool = False      # 是否已激活
    position: tuple[int, int] | None = None  # 位置 (x, y) on desktop
    size_override: tuple[int, int] | None = None  # 自定义尺寸 (width, height)
    custom_settings: dict[str, Any] = field(default_factory=dict)  # pyright: ignore[reportExplicitAny]
    plugin_id: str | None = None  # 插件来源标识 (如果是插件提供的组件)

    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WidgetInfo":  # pyright: ignore[reportExplicitAny]
        """从字典创建"""
        # 确保 position 和 size_override 是 tuple 类型（JSON 反序列化后会变成 list）
        if isinstance(data.get("position"), list):
            data["position"] = tuple(data["position"])  # pyright: ignore[reportAny]
        if isinstance(data.get("size_override"), list):
            data["size_override"] = tuple(data["size_override"])  # pyright: ignore[reportAny]
        return cls(**data)  # pyright: ignore[reportAny]


# 所有可用的小组件模板
AVAILABLE_WIDGETS: list[WidgetInfo] = [
    WidgetInfo(
        id="clock",
        name="时钟",
        description="显示当前时间和日期",
        icon_name="STOP_WATCH",
        category="时间",
    ),
    WidgetInfo(
        id="stopwatch",
        name="秒表",
        description="精确计时功能",
        icon_name="HISTORY",
        size="small",
        category="时间",
    ),
    WidgetInfo(
        id="timer",
        name="计时器",
        description="倒计时功能",
        icon_name="DATE_TIME",
        size="small",
        category="时间",
    ),
    WidgetInfo(
        id="pomodoro",
        name="番茄钟",
        description="25分钟专注工作",
        icon_name="CAFE",
        category="时间",
    ),
    WidgetInfo(
        id="system_monitor",
        name="系统监控",
        description="CPU、内存使用率",
        icon_name="SETTING",
        size="small",
        category="系统",
    ),
    WidgetInfo(
        id="network_monitor",
        name="网络监控",
        description="网速、磁盘使用率",
        icon_name="SPEED_HIGH",
        category="系统",
    ),
    WidgetInfo(
        id="calendar",
        name="日历",
        description="显示当前日期",
        icon_name="CALENDAR",
        category="信息",
    ),
    WidgetInfo(
        id="todo",
        name="待办事项",
        description="管理每日任务",
        icon_name="CHECKBOX",
        size="large",
        category="信息",
    ),
    WidgetInfo(
        id="note",
        name="笔记",
        description="快速记录想法",
        icon_name="EDIT",
        category="信息",
    ),
    WidgetInfo(
        id="weather",
        name="天气",
        description="实时天气信息",
        icon_name="CLOUD",
        category="信息",
    ),
    WidgetInfo(
        id="music",
        name="音乐播放器",
        description="控制媒体播放",
        icon_name="MUSIC",
        category="娱乐",
    ),
    WidgetInfo(
        id="exchange",
        name="汇率",
        description="汇率查询",
        icon_name="UNIT",
        category="信息",
    ),
    WidgetInfo(
        id="rss",
        name="RSS订阅",
        description="新闻资讯订阅",
        icon_name="MESSAGE",
        size="large",
        category="信息",
    ),
    WidgetInfo(
        id="automation",
        name="自动化点击",
        description="自动执行点击操作",
        icon_name="ROBOT",
        category="工具",
    ),
    WidgetInfo(
        id="image",
        name="图片",
        description="显示本地图片，支持裁剪区域",
        icon_name="PICTURE",
        category="信息",
    ),
    WidgetInfo(
        id="document_viewer",
        name="文档查看器",
        description="查看 PDF、Word、Markdown、TXT 文档",
        icon_name="DOCUMENT",
        size="large",
        category="工具",
    ),
]


class WidgetModel(QObject):
    """小组件数据模型 — 支持实时信号通知"""

    widgets_changed = Signal()  # 组件状态（激活/停用）发生变化时发射

    _instance: "WidgetModel | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized: bool = True

        self._widgets: dict[str, WidgetInfo] = {}
        self._load()

    def _load(self):
        """从配置文件加载"""
        if WIDGET_CONFIG.exists():
            try:
                import json
                with open(WIDGET_CONFIG, 'r', encoding='utf-8') as f:
                    data: dict[str, Any] = json.load(f)  # pyright: ignore[reportAny,reportExplicitAny]
                    for widget_data in data.get("widgets", []):  # pyright: ignore[reportAny]
                        widget = WidgetInfo.from_dict(widget_data)  # pyright: ignore[reportAny]
                        self._widgets[widget.id] = widget
                logger.info(f"加载了 {len(self._widgets)} 个小组件配置")
                
                # 合并新组件（配置文件中可能缺少新添加的组件）
                self._merge_new_widgets()
            except Exception as e:
                logger.warning(f"加载小组件配置失败: {e}")
                # 初始化所有小组件
                for widget in AVAILABLE_WIDGETS:
                    self._widgets[widget.id] = widget
        else:
            # 初始化所有小组件为未激活状态
            for widget in AVAILABLE_WIDGETS:
                self._widgets[widget.id] = widget
            logger.info("初始化小组件配置")

    def _merge_new_widgets(self):
        """合并新添加的小组件模板和插件组件"""
        merged = False
        
        # 合并内置组件
        for widget in AVAILABLE_WIDGETS:
            if widget.id not in self._widgets:
                self._widgets[widget.id] = widget
                logger.info(f"添加新组件: {widget.name}")
                merged = True
        
        # 合并插件注册的组件
        try:
            from app.widgets.registry import WidgetRegistry
            registry = WidgetRegistry.instance()
            for widget_type, display_name in registry.all_types():
                if widget_type not in self._widgets:
                    # 从 WidgetRegistry 获取插件来源
                    plugin_id = registry.get_plugin_id(widget_type)
                    # 创建新的 WidgetInfo
                    widget_info = WidgetInfo(
                        id=widget_type,
                        name=display_name,
                        description=f"来自插件: {plugin_id or '未知'}",
                        icon_name="APPLICATION",
                        category="插件",
                        plugin_id=plugin_id,
                    )
                    self._widgets[widget_type] = widget_info
                    logger.info(f"添加插件组件: {display_name} (来自: {plugin_id})")
                    merged = True
        except Exception as e:
            logger.warning(f"合并插件组件失败: {e}")
        
        if merged:
            self.save()

    def save(self):
        """保存到配置文件"""
        try:
            import json
            WIDGET_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "widgets": [widget.to_dict() for widget in self._widgets.values()]
            }
            with open(WIDGET_CONFIG, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info("小组件配置已保存")
        except Exception as e:
            logger.error(f"保存小组件配置失败: {e}")

    def get_widget(self, widget_id: str) -> WidgetInfo | None:
        """获取指定小组件"""
        return self._widgets.get(widget_id)

    def get_all_widgets(self) -> list[WidgetInfo]:
        """获取所有小组件（包括动态加载的插件组件）"""
        # 每次获取时合并插件组件，确保新加载的插件组件能显示
        self._merge_plugin_widgets()
        return list(self._widgets.values())

    def _merge_plugin_widgets(self):
        """合并插件注册的小组件（动态）"""
        try:
            from app.widgets.registry import WidgetRegistry
            registry = WidgetRegistry.instance()
            merged = False
            for widget_type, display_name in registry.all_types():
                if widget_type not in self._widgets:
                    # 从 WidgetRegistry 获取插件来源
                    plugin_id = registry.get_plugin_id(widget_type)
                    # 创建新的 WidgetInfo
                    widget_info = WidgetInfo(
                        id=widget_type,
                        name=display_name,
                        description=f"来自插件: {plugin_id or '未知'}",
                        icon_name="APPLICATION",
                        category="插件",
                        plugin_id=plugin_id,
                    )
                    self._widgets[widget_type] = widget_info
                    logger.info(f"动态添加插件组件: {display_name} (来自: {plugin_id})")
                    merged = True
            if merged:
                self.save()
        except Exception as e:
            logger.debug(f"合并插件组件失败: {e}")

    def get_active_widgets(self) -> list[WidgetInfo]:
        """获取所有激活的小组件"""
        return [w for w in self._widgets.values() if w.is_active]

    def get_widgets_by_category(self, category: str) -> list[WidgetInfo]:
        """按分类获取小组件"""
        return [w for w in self._widgets.values() if w.category == category]

    def get_categories(self) -> list[str]:
        """获取所有分类"""
        categories = set(w.category for w in self._widgets.values())
        return sorted(categories)

    def activate_widget(self, widget_id: str):
        """激活小组件"""
        if widget_id in self._widgets:
            self._widgets[widget_id].is_active = True
            self.save()
            self.widgets_changed.emit()
            logger.info(f"激活小组件: {widget_id}")

    def deactivate_widget(self, widget_id: str):
        """停用小组件"""
        if widget_id in self._widgets:
            self._widgets[widget_id].is_active = False
            self._widgets[widget_id].position = None
            self.save()
            self.widgets_changed.emit()
            logger.info(f"停用小组件: {widget_id}")

    def update_widget_position(self, widget_id: str, position: tuple[int, int]):
        """更新小组件位置"""
        if widget_id in self._widgets:
            self._widgets[widget_id].position = position
            self.save()

    def update_widget_size(self, widget_id: str, size_override: tuple[int, int]):
        """更新小组件尺寸"""
        if widget_id in self._widgets:
            self._widgets[widget_id].size_override = size_override
            self.save()
