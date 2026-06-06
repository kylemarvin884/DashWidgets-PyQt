"""
小组件卡片组件 - Windows 11 Fluent 风格
"""
from typing import Optional

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget
from PySide6.QtCore import Qt, Signal

from qfluentwidgets import (
    CardWidget, CaptionLabel, StrongBodyLabel,
    PushButton, ToolButton, FluentIcon as FIF, IconWidget,
)

from app.models.widget_model import WidgetInfo
from app.services.desktop_widget_service import Win11Style


class WidgetCard(CardWidget):
    """小组件卡片 - 管理页面使用"""

    activated = Signal(str)
    deactivated = Signal(str)
    settings_clicked = Signal(str)

    def __init__(self, widget_info: WidgetInfo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.widget_info = widget_info
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.c()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 顶部：图标 + 名称 + 描述
        top = QHBoxLayout()
        top.setSpacing(12)

        icon_w = IconWidget(getattr(FIF, self.widget_info.icon_name, FIF.APPLICATION), self)
        icon_w.setFixedSize(36, 36)
        top.addWidget(icon_w)

        info = QVBoxLayout()
        info.setSpacing(3)

        name = StrongBodyLabel(self.widget_info.name)
        name.setStyleSheet(
            f"font-family:{Win11Style.FONT_FAMILY};font-size:15px;"
            f"font-weight:600;color:{c['text_primary']};background:transparent;"
        )
        info.addWidget(name)

        desc = CaptionLabel(self.widget_info.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        info.addWidget(desc)

        top.addLayout(info)
        top.addStretch()
        layout.addLayout(top)

        # 底部按钮
        self._btn_lay = QHBoxLayout()
        self._btn_lay.setSpacing(8)
        self._setup_buttons()
        layout.addLayout(self._btn_lay)

    def _setup_buttons(self) -> None:
        while self._btn_lay.count():
            item = self._btn_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self.widget_info.is_active:
            btn = ToolButton(FIF.CANCEL, parent=self)
            btn.setToolTip("停用")
            btn.clicked.connect(lambda: self.deactivated.emit(self.widget_info.id))
            self._btn_lay.addWidget(btn)

            btn2 = ToolButton(FIF.SETTING, parent=self)
            btn2.setToolTip("设置")
            btn2.clicked.connect(lambda: self.settings_clicked.emit(self.widget_info.id))
            self._btn_lay.addWidget(btn2)
            self._btn_lay.addStretch()
        else:
            btn = PushButton(
                getattr(FIF, self.widget_info.icon_name, FIF.APPLICATION),
                "添加到桌面", parent=self
            )
            btn.clicked.connect(lambda: self.activated.emit(self.widget_info.id))
            self._btn_lay.addWidget(btn)

    def update_status(self, is_active: bool) -> None:
        self.widget_info.is_active = is_active
        self._setup_buttons()
        self.update()

    def update_theme(self) -> None:
        """更新主题颜色"""
        c = Win11Style.c()
        self.setAutoFillBackground(False)
        # 更新 StrongBodyLabel 文字颜色
        for child in self.findChildren(StrongBodyLabel):
            child.setStyleSheet(
                f"font-family:{Win11Style.FONT_FAMILY};font-size:15px;"
                f"font-weight:600;color:{c['text_primary']};background:transparent;"
            )
        # 更新 CaptionLabel 文字颜色
        for child in self.findChildren(CaptionLabel):
            child.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")