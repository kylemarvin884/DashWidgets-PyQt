"""待办事项小组件 — Win11 风格（支持持久化）"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QLineEdit,
)
from qfluentwidgets import CheckBox

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TODO_FILE = DATA_DIR / "todo_items.json"


class TodoWidget(WidgetBase):
    WIDGET_TYPE = "todo"
    WIDGET_NAME = "待办"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._items = []
        self._setup_ui()
        self._load_items()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 8)
        main_layout.setSpacing(2)

        self._title_label = QLabel("待办事项")
        self._title_label.setFont(Win11Style.widget_font(15, QFont.Weight.Light))
        self._title_label.setStyleSheet(f"color: {c['title']}; background: transparent;")
        main_layout.addWidget(self._title_label)

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 4, 0, 0)
        self._list_layout.setSpacing(2)

        scroll = QScrollArea()
        scroll.setWidget(self._list_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            "QScrollBar::handle:vertical { background: rgba(128,128,128,0.2); border-radius: 2px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        main_layout.addWidget(scroll, stretch=1)

        self._input = QLineEdit()
        self._input.setPlaceholderText("添加任务...")
        self._input.setFont(Win11Style.widget_font(13))
        self._input.setStyleSheet(
            f"color: {c['text']}; background: {c['bg_input']};"
            f" border: 1px solid {c['border_input']}; border-radius: 6px; padding: 4px 8px;"
        )
        self._input.returnPressed.connect(self._add_item)
        main_layout.addWidget(self._input)

    # ── 持久化 ────────────────────────────────────────────── #

    @staticmethod
    def _ensure_data_dir() -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _save_items(self) -> None:
        try:
            self._ensure_data_dir()
            data = []
            for cb, lbl in self._items:
                data.append({"text": lbl.text(), "checked": cb.isChecked()})
            TODO_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_items(self) -> None:
        try:
            if TODO_FILE.exists():
                raw = json.loads(TODO_FILE.read_text(encoding="utf-8"))
                for item in raw:
                    if item.get("text"):
                        self._add_todo_row(item["text"], item.get("checked", False))
        except Exception:
            pass

    # ── 行操作 ────────────────────────────────────────────── #

    def _add_todo_row(self, text: str, checked: bool) -> None:
        c = Win11Style.widget_colors()
        row = QHBoxLayout()
        row.setSpacing(8)

        cb = CheckBox()
        cb.setChecked(checked)
        row.addWidget(cb)

        label = QLabel(text)
        label.setFont(Win11Style.widget_font(15))
        label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        row.addWidget(label)
        row.addStretch()

        def on_toggle(state, lbl=label):
            if state == Qt.CheckState.Checked:
                lbl.setStyleSheet(f"color: {c['text_dim']}; background: transparent; text-decoration: line-through;")
            else:
                lbl.setStyleSheet(f"color: {c['text']}; background: transparent;")
            self._save_items()

        cb.checkStateChanged.connect(on_toggle)
        on_toggle(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._list_layout.addLayout(row)
        self._items.append((cb, label))

    def _add_item(self) -> None:
        text = self._input.text().strip()
        if text:
            self._add_todo_row(text, False)
            self._input.clear()
            self._save_items()

    def hideEvent(self, event):
        self._save_items()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._save_items()
        super().closeEvent(event)

    def event(self, e):
        # 父窗口销毁时也会触发 Type.None (cleanup)
        if e.type() == e.Type.Close:
            self._save_items()
        return super().event(e)
