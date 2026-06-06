"""
可拖拽小组件卡片 - 点击交换方案（最可靠）
"""
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QColor

from qfluentwidgets import (
    CardWidget, CaptionLabel, StrongBodyLabel, IconWidget, FluentIcon as FIF,
)

from app.models.widget_model import WidgetInfo
from app.services.desktop_widget_service import Win11Style


class DraggableWidgetCard(CardWidget):
    """可交换的小组件卡片 - 点击选择 + 点击交换"""

    # 点击卡片：widget_id
    clicked = Signal(str)
    # 双击卡片：widget_id
    double_clicked = Signal(str)
    
    activated = Signal(str)
    deactivated = Signal(str)

    def __init__(self, widget_info: WidgetInfo, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.widget_info = widget_info
        self._is_selected = False
        self._set_ui()

    def _set_ui(self):
        c = Win11Style.c()
        self.setFixedHeight(100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 30 if not Win11Style.is_dark() else 60))
        self.setGraphicsEffect(shadow)

        self._update_style()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        icon_w = IconWidget(getattr(FIF, self.widget_info.icon_name, FIF.APPLICATION), self)
        icon_w.setFixedSize(28, 28)
        lay.addWidget(icon_w)

        name = StrongBodyLabel(self.widget_info.name)
        name.setStyleSheet(
            f"font-family:{Win11Style.FONT_FAMILY};font-size:13px;font-weight:600;"
            f"color:{c['text_primary']};background:transparent;"
        )
        lay.addWidget(name)
        lay.addStretch()

        desc = CaptionLabel(self.widget_info.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        lay.addWidget(desc)

        status = "已激活" if self.widget_info.is_active else "未激活"
        sc = c["success"] if self.widget_info.is_active else c["text_secondary"]
        self._status_lbl = CaptionLabel(status)
        self._status_lbl.setStyleSheet(f"color:{sc};background:transparent;font-weight:600;")
        lay.addWidget(self._status_lbl)

    def _update_style(self):
        """更新样式（选中状态）"""
        c = Win11Style.c()
        if self._is_selected:
            border = c["accent"]
            bg = c["bg"]
        else:
            border = c["card_border"]
            bg = c["card_bg"]
        
        self.setStyleSheet(
            f"CardWidget{{background:{bg};border:2px solid {border};border-radius:12px;}}"
        )

    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        self._update_style()

    def is_selected(self) -> bool:
        return self._is_selected

    def update_status(self, is_active: bool):
        self.widget_info.is_active = is_active
        c = Win11Style.c()
        status = "已激活" if is_active else "未激活"
        sc = c["success"] if is_active else c["text_secondary"]
        if hasattr(self, "_status_lbl"):
            self._status_lbl.setText(status)
            self._status_lbl.setStyleSheet(f"color:{sc};background:transparent;font-weight:600;")

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.widget_info.id)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.widget_info.id)
        super().mouseDoubleClickEvent(e)
