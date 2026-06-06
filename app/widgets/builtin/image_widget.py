"""图片小组件 — 整组件即图片"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QFileDialog, QMenu,
)

from qfluentwidgets import FluentIcon as FIF

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style

_SUPPORTED = "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.avif *.svg)"


class ImageWidget(WidgetBase):
    WIDGET_TYPE = "image"
    WIDGET_NAME = "图片"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._image_path = config.settings.get("image_path", "")
        self._original_pixmap: QPixmap | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()

        # 无 margin，图片撑满整个组件
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label.setStyleSheet(
            f"color: {c['text_dim']}; background: {c['bg_input']};"
            f" border: 2px dashed {c['border_input']}; border-radius: 8px;"
        )
        layout.addWidget(self._label)

        self._load_image()

    def mousePressEvent(self, event):
        # 仅未设置图片时左键才打开选择
        if event.button() == Qt.MouseButton.LeftButton and not self._image_path:
            self._choose_image()
        super().mousePressEvent(event)

    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", str(Path.home() / "Pictures"),
            _SUPPORTED,
        )
        if path:
            self._image_path = path
            self._load_image()
            self._save_config()

    def _load_image(self) -> None:
        c = Win11Style.widget_colors()

        if not self._image_path or not Path(self._image_path).is_file():
            self._label.clear()
            self._label.setText("点击选择图片")
            self._label.setFont(QFont("Segoe UI Variable", 12, QFont.Weight.Light))
            self._original_pixmap = None
            return

        pm = QPixmap(self._image_path)
        if pm.isNull():
            self._label.clear()
            self._label.setText("加载失败")
            self._label.setFont(QFont("Segoe UI Variable", 12, QFont.Weight.Light))
            self._original_pixmap = None
            return

        self._original_pixmap = pm
        self._label.setStyleSheet("background: transparent; border: none;")
        self._label.setCursor(Qt.CursorShape.ArrowCursor)
        self._fit_image()

    def _fit_image(self) -> None:
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return
        s = self.size()
        if s.width() < 4 or s.height() < 4:
            return
        scaled = self._original_pixmap.scaled(
            s, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_image()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction(FIF.PHOTO.icon(), "更换图片", self._choose_image)
        if self._image_path:
            menu.addAction(FIF.DELETE.icon(), "清除图片", self._clear_image)
        menu.exec(event.globalPos())

    def _clear_image(self) -> None:
        c = Win11Style.widget_colors()
        self._image_path = ""
        self._original_pixmap = None
        self._label.clear()
        self._label.setText("点击选择图片")
        self._label.setFont(QFont("Segoe UI Variable", 12, QFont.Weight.Light))
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label.setStyleSheet(
            f"color: {c['text_dim']}; background: {c['bg_input']};"
            f" border: 2px dashed {c['border_input']}; border-radius: 8px;"
        )
        self._save_config()

    def _save_config(self) -> None:
        self.config.settings["image_path"] = self._image_path
        try:
            from app.models.widget_model import WidgetModel
            model = WidgetModel()
            w = model.get_widget(self.config.id)
            if w:
                w.custom_settings = dict(self.config.settings)
                model.save()
        except Exception:
            pass
