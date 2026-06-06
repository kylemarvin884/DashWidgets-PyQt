"""
自定义网格布局组件 - 稳定版（修复黑边与布局混乱）
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent

from qfluentwidgets import (
    CardWidget,
    CaptionLabel,
    BodyLabel,
    ToolButton,
    FluentIcon as FIF,
    IconWidget,
)

from app.models.widget_layout_model import WidgetLayoutModel, LayoutItem
from app.widgets.draggable_widget_card import DraggableWidgetCard
from app.services.desktop_widget_service import Win11Style


class _WidgetPaletteItem(CardWidget):
    """右侧组件面板项"""

    clicked = Signal(str)

    def __init__(self, widget_info, parent=None):
        super().__init__(parent)
        self.widget_info = widget_info
        self.setFixedHeight(48)
        c = Win11Style.c()
        self.setStyleSheet(
            f"CardWidget{{background:{c['card_bg']};border:1px solid {c['card_border']};border-radius:8px;}}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(10)

        icon = IconWidget(getattr(FIF, widget_info.icon_name, FIF.APPLICATION), self)
        icon.setFixedSize(22, 22)
        lay.addWidget(icon)

        name = BodyLabel(widget_info.name)
        name.setStyleSheet(
            f"font-size:12px;color:{c['text_primary']};background:transparent;"
        )
        lay.addWidget(name)
        lay.addStretch()

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.widget_info.id)
        super().mousePressEvent(e)


class WidgetCustomLayout(QWidget):
    """自定义网格布局 - 稳定版"""

    layout_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout_model = WidgetLayoutModel()
        self._widget_model = None
        self._cards: dict[str, DraggableWidgetCard] = {}
        self._selected_id: str | None = None
        self._build_ui()

    def _build_ui(self):
        # 主布局
        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(16)

        # 左侧：网格区
        left = QVBoxLayout()
        left.setSpacing(10)

        # 工具栏
        toolbar = QHBoxLayout()
        self._layout_name = BodyLabel("默认布局")
        self._layout_name.setStyleSheet(
            f"font-size:14px;font-weight:600;color:{Win11Style.c()['text_primary']};background:transparent;"
        )
        toolbar.addWidget(self._layout_name)
        toolbar.addStretch()

        self._add_all_btn = ToolButton(FIF.ADD_TO, self)
        self._add_all_btn.setToolTip("添加所有组件")
        self._add_all_btn.clicked.connect(self._add_all_widgets)
        toolbar.addWidget(self._add_all_btn)

        self._reset_btn = ToolButton(FIF.SYNC, self)
        self._reset_btn.setToolTip("重置布局")
        self._reset_btn.clicked.connect(self._reset_layout)
        toolbar.addWidget(self._reset_btn)
        left.addLayout(toolbar)

        # 滚动区域 - 修复黑边关键
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # 关键修复：设置视口背景色，防止透明导致黑边
        vp_style = f"background: {Win11Style.c()['card_bg']};"
        self._scroll.viewport().setStyleSheet(vp_style)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # 网格容器 - 明确尺寸策略
        self._grid_frame = QFrame()
        self._grid_frame.setStyleSheet(
            f"QFrame{{background:{Win11Style.c()['card_bg']};border:1px solid {Win11Style.c()['card_border']};"
            f"border-radius:12px;}}"
        )
        self._grid_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._grid_lay = QGridLayout(self._grid_frame)
        self._grid_lay.setContentsMargins(12, 12, 12, 12)
        self._grid_lay.setSpacing(10)
        self._grid_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll.setWidget(self._grid_frame)
        left.addWidget(self._scroll)

        tip = CaptionLabel(
            "点击选中一个组件，再点击另一个即可交换位置 · 双击切换激活状态"
        )
        tip.setStyleSheet(f"color:{Win11Style.c()['text_secondary']};background:transparent;")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(tip)

        main_lay.addLayout(left, stretch=4)

        # 右侧：组件面板
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(BodyLabel("未添加的组件"))

        self._palette_scroll = QScrollArea()
        self._palette_scroll.setWidgetResizable(True)
        self._palette_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._palette_scroll.setFixedWidth(190)
        self._palette_scroll.viewport().setStyleSheet(
            f"background: {Win11Style.c()['card_bg']};"
        )
        self._palette_scroll.setStyleSheet(
            f"QScrollArea{{border:1px solid {Win11Style.c()['card_border']};border-radius:10px;}}"
        )
        self._palette_scroll.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        self._palette_content = QWidget()
        self._palette_lay = QVBoxLayout(self._palette_content)
        self._palette_lay.setContentsMargins(6, 6, 6, 6)
        self._palette_lay.setSpacing(6)
        self._palette_lay.addStretch()

        self._palette_scroll.setWidget(self._palette_content)
        right.addWidget(self._palette_scroll)
        main_lay.addLayout(right, stretch=1)

    def set_widget_model(self, model):
        self._widget_model = model
        self._refresh()

    def _refresh(self):
        """安全刷新布局"""
        # 1. 清除网格
        while self._grid_lay.count():
            item = self._grid_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        active = self._layout_model.get_active_layout()
        self._layout_name.setText(active.name)

        cols, rows = active.grid_cols, active.grid_rows
        pos_map = {(it.row, it.col): it.widget_id for it in active.items}

        # 2. 填充网格
        for r in range(rows):
            for c in range(cols):
                wid = pos_map.get((r, c))
                if wid and self._widget_model:
                    info = self._widget_model.get_widget(wid)
                    if info:
                        card = DraggableWidgetCard(info, self)
                        card.clicked.connect(self._on_card_clicked)
                        card.double_clicked.connect(self._on_card_double_clicked)
                        card.activated.connect(self._on_activated)
                        card.deactivated.connect(self._on_deactivated)
                        self._grid_lay.addWidget(card, r, c)
                        self._cards[wid] = card
                        if wid == self._selected_id:
                            card.set_selected(True)

        self._refresh_palette()

    def _refresh_palette(self):
        """刷新右侧面板"""
        while self._palette_lay.count():
            item = self._palette_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        if not self._widget_model:
            return

        active = self._layout_model.get_active_layout()
        layout_ids = {it.widget_id for it in active.items}
        for w in self._widget_model.get_all_widgets():
            if w.id not in layout_ids:
                item = _WidgetPaletteItem(w, self._palette_content)
                item.clicked.connect(self._on_palette_clicked)
                self._palette_lay.insertWidget(self._palette_lay.count() - 1, item)

    # ── 核心交互：点击交换 ───────────────────────────────────────── #
    def _on_card_clicked(self, widget_id: str):
        if self._selected_id and self._selected_id != widget_id:
            self._swap_widgets(self._selected_id, widget_id)
            self._selected_id = None
        elif self._selected_id == widget_id:
            self._selected_id = None
        else:
            self._selected_id = widget_id
        self._refresh()

    def _on_card_double_clicked(self, widget_id: str):
        if self._widget_model:
            if self._widget_model.get_widget(widget_id).is_active:
                self._widget_model.deactivate_widget(widget_id)
                from app.services.desktop_widget_service import DesktopWidgetManager

                DesktopWidgetManager.instance().hide_widget(widget_id)
            else:
                self._widget_model.activate_widget(widget_id)
                from app.services.desktop_widget_service import DesktopWidgetManager

                DesktopWidgetManager.instance().show_widget(widget_id)
            self._refresh()

    def _swap_widgets(self, id1: str, id2: str):
        active = self._layout_model.get_active_layout()
        item1 = next((i for i in active.items if i.widget_id == id1), None)
        item2 = next((i for i in active.items if i.widget_id == id2), None)
        if item1 and item2:
            item1.row, item2.row = item2.row, item1.row
            item1.col, item2.col = item2.col, item1.col
            self._layout_model.save()
            self.layout_changed.emit()

    def _on_palette_clicked(self, widget_id: str):
        active = self._layout_model.get_active_layout()
        cols, rows = active.grid_cols, active.grid_rows
        occupied = {(it.row, it.col) for it in active.items}
        for r in range(rows):
            for c in range(cols):
                if (r, c) not in occupied:
                    active.items.append(LayoutItem(widget_id=widget_id, row=r, col=c))
                    self._layout_model.save()
                    self._refresh()
                    return

    def _on_activated(self, widget_id: str):
        if self._widget_model:
            self._widget_model.activate_widget(widget_id)
            from app.services.desktop_widget_service import DesktopWidgetManager

            DesktopWidgetManager.instance().show_widget(widget_id)
            self._refresh()

    def _on_deactivated(self, widget_id: str):
        if self._widget_model:
            self._widget_model.deactivate_widget(widget_id)
            from app.services.desktop_widget_service import DesktopWidgetManager

            DesktopWidgetManager.instance().hide_widget(widget_id)
            self._refresh()

    def _add_all_widgets(self):
        if not self._widget_model:
            return
        active = self._layout_model.get_active_layout()
        active.items.clear()
        r, c = 0, 0
        for w in self._widget_model.get_all_widgets():
            active.items.append(LayoutItem(widget_id=w.id, row=r, col=c))
            c += 1
            if c >= active.grid_cols:
                c = 0
                r += 1
        self._layout_model.save()
        self._selected_id = None
        self._refresh()

    def _reset_layout(self):
        self._add_all_widgets()
