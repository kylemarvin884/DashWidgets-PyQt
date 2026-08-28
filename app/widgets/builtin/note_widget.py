"""笔记小组件 — Win11 风格"""
from __future__ import annotations
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QVBoxLayout, QTextEdit, QWidget

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class NoteWidget(WidgetBase):
    WIDGET_TYPE: str = "note"
    WIDGET_NAME: str = "笔记"

    _SAVE_DEBOUNCE_MS = 600

    def __init__(self, config: WidgetConfig, services: dict[str, Any], parent: Any = None):
        super().__init__(config, services, parent)
        self._setup_ui()
        self._load_note()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(4)

        self._editor = QTextEdit(self)
        self._editor.setFont(Win11Style.widget_font(16, QFont.Weight.Light))
        self._editor.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._editor.setStyleSheet(
            f"color: {c['text']}; background: {c['bg_input']};"
            f" border: 1px solid {c['border_input']}; border-radius: 8px; padding: 8px;"
        )
        self._editor.setPlaceholderText("在这里写点什么...")
        self._editor.textChanged.connect(self._on_text_changed)
        main_layout.addWidget(self._editor)

        # 防抖保存：连续输入只在停顿后写一次盘
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(self._SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._save_note)

    def _note_path(self):
        from app.constants import DATA_DIR
        return DATA_DIR / "note.txt"

    def _load_note(self) -> None:
        try:
            p = self._note_path()
            if p.exists():
                self._editor.setPlainText(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _on_text_changed(self) -> None:
        self._save_timer.start()

    def _save_note(self) -> None:
        try:
            from app.constants import DATA_DIR
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self._note_path().write_text(self._editor.toPlainText(), encoding="utf-8")
        except Exception:
            pass

    def on_close(self) -> None:
        # 关闭前把未落盘的输入补写
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_note()
