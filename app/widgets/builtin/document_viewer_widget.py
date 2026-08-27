"""文档查看器小组件 — 支持选择/更换/清除文档"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea,
    QTextEdit, QFileDialog,
)

from qfluentwidgets import FluentIcon as FIF

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style

_SUPPORTED = (
    "文档文件 (*.txt *.md *.py *.json *.xml *.html *.css *.js "
    "*.csv *.log *.ini *.cfg *.yaml *.toml *.rst);;"
    "所有文件 (*)"
)


class DocumentViewerWidget(WidgetBase):
    WIDGET_TYPE = "document_viewer"
    WIDGET_NAME = "文档查看器"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._doc_path = config.settings.get("doc_path", "")
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(4)

        # 标题
        title = QLabel("文档查看器")
        title.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(title)

        # 文本显示区
        self._text_edit = QTextEdit(self)
        self._text_edit.setReadOnly(True)
        # 内建右键菜单会继承窗口透明样式渲染成黑底；禁用后右键
        # 传播到窗口统一菜单（全选/复制作为组件动作贡献）
        self._text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._text_edit.setFont(QFont("Segoe UI Variable", 11))
        self._text_edit.setStyleSheet(
            f"QTextEdit {{"
            f"  color: {c['text']};"
            f"  background: {c['bg_input']};"
            f"  border: 1px solid {c['border_input']};"
            f"  border-radius: 6px;"
            f"  padding: 8px;"
            f"}}"
            f"QScrollBar:vertical {{ background: transparent; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: rgba(128,128,128,0.2); border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        main_layout.addWidget(self._text_edit, stretch=1)

        self._load_document()

    def _choose_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文档", str(Path.home() / "Documents"),
            _SUPPORTED,
        )
        if path:
            self._doc_path = path
            self._load_document()
            self._save_config()

    def _load_document(self) -> None:
        c = Win11Style.widget_colors()

        if not self._doc_path or not Path(self._doc_path).is_file():
            self._text_edit.setPlainText("")
            self._text_edit.setPlaceholderText("点击选择文档")
            return

        try:
            with open(self._doc_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # 截断过大文件
            if len(content) > 50000:
                content = content[:50000] + "\n\n... (内容已截断，仅显示前 50000 字符)"
            self._text_edit.setPlainText(content)
        except Exception:
            self._text_edit.setPlainText("无法读取该文件")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._doc_path:
            self._choose_document()
        super().mousePressEvent(event)

    def get_context_menu_actions(self) -> list[tuple]:
        """组件专属右键动作（由窗口统一菜单渲染，避免自建 QMenu 黑底）"""
        actions = [(FIF.DOCUMENT, "更换文档", self._choose_document)]
        if self._doc_path:
            actions.append((FIF.DELETE, "清除文档", self._clear_document))
            actions.append((None, "全选", self._text_edit.selectAll))
            actions.append((None, "复制选中", self._text_edit.copy))
        return actions

    def _clear_document(self) -> None:
        self._doc_path = ""
        self._text_edit.clear()
        self._text_edit.setPlaceholderText("点击选择文档")
        self._save_config()

    def _save_config(self) -> None:
        self.config.settings["doc_path"] = self._doc_path
        try:
            from app.models.widget_model import WidgetModel
            model = WidgetModel()
            w = model.get_widget(self.config.id)
            if w:
                w.custom_settings = dict(self.config.settings)
                model.save()
        except Exception:
            pass
