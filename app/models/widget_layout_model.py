"""
小组件自定义布局模型
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from app.constants import CONFIG_DIR
from loguru import logger


@dataclass
class LayoutItem:
    """布局中的单个小组件"""

    widget_id: str
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1


@dataclass
class WidgetLayout:
    """小组件自定义布局"""

    name: str = "默认布局"
    grid_cols: int = 4
    grid_rows: int = 6
    items: list[LayoutItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "grid_cols": self.grid_cols,
            "grid_rows": self.grid_rows,
            "items": [asdict(i) for i in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WidgetLayout":
        items = [LayoutItem(**i) for i in data.get("items", [])]
        return cls(
            name=data.get("name", "默认布局"),
            grid_cols=data.get("grid_cols", 4),
            grid_rows=data.get("grid_rows", 6),
            items=items,
        )


class WidgetLayoutModel:
    """小组件自定义布局管理器"""

    _instance: "WidgetLayoutModel | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._config_path = CONFIG_DIR / "widget_layouts.json"
        self._layouts: dict[str, WidgetLayout] = {}
        self._active_layout_id: str = "default"
        self._load()

    def _load(self):
        """从配置文件加载布局"""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for lid, ldata in data.get("layouts", {}).items():
                    self._layouts[lid] = WidgetLayout.from_dict(ldata)
                self._active_layout_id = data.get("active_layout", "default")
                logger.info(f"加载了 {len(self._layouts)} 个自定义布局")
            except Exception as e:
                logger.warning(f"加载布局配置失败: {e}")
        # 确保至少有一个默认布局
        if "default" not in self._layouts:
            self._layouts["default"] = WidgetLayout(name="默认布局")
            self._active_layout_id = "default"

    def save(self):
        """保存布局到配置文件"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "layouts": {lid: l.to_dict() for lid, l in self._layouts.items()},
                "active_layout": self._active_layout_id,
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info("自定义布局已保存")
        except Exception as e:
            logger.error(f"保存布局配置失败: {e}")

    def get_layout(self, layout_id: str) -> WidgetLayout | None:
        return self._layouts.get(layout_id)

    def get_active_layout(self) -> WidgetLayout:
        return self._layouts.get(self._active_layout_id, WidgetLayout())

    def get_all_layouts(self) -> list[tuple[str, WidgetLayout]]:
        return list(self._layouts.items())

    def create_layout(self, name: str, grid_cols: int = 4, grid_rows: int = 6) -> str:
        """创建新布局，返回 layout_id"""
        import time

        layout_id = f"layout_{int(time.time())}"
        self._layouts[layout_id] = WidgetLayout(
            name=name, grid_cols=grid_cols, grid_rows=grid_rows
        )
        self.save()
        return layout_id

    def delete_layout(self, layout_id: str):
        if layout_id == "default":
            return
        self._layouts.pop(layout_id, None)
        if self._active_layout_id == layout_id:
            self._active_layout_id = "default"
        self.save()

    def set_active_layout(self, layout_id: str):
        if layout_id in self._layouts:
            self._active_layout_id = layout_id
            self.save()

    def update_layout(self, layout_id: str, layout: WidgetLayout):
        self._layouts[layout_id] = layout
        self.save()

    def get_widget_position(self, widget_id: str) -> tuple[int, int] | None:
        """获取小组件在当前激活布局中的位置"""
        active = self.get_active_layout()
        for item in active.items:
            if item.widget_id == widget_id:
                return (item.row, item.col)
        return None

    def set_widget_position(self, widget_id: str, row: int, col: int):
        """设置小组件位置"""
        active = self.get_active_layout()
        for item in active.items:
            if item.widget_id == widget_id:
                item.row = row
                item.col = col
                self.save()
                return
        # 如果不存在，添加
        active.items.append(LayoutItem(widget_id=widget_id, row=row, col=col))
        self.save()

    def remove_widget(self, widget_id: str):
        """从布局中移除小组件"""
        active = self.get_active_layout()
        active.items = [i for i in active.items if i.widget_id != widget_id]
        self.save()

    def reorder_items(self, items: list[LayoutItem]):
        """批量更新布局项"""
        active = self.get_active_layout()
        active.items = items
        self.save()
