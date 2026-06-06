"""
小组件视图：显示所有可用的小组件 — Windows 11 风格
"""

from typing import Optional

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut

from qfluentwidgets import (
    ScrollArea,
    FluentIcon as FIF,
    PushButton,
    ToolButton,
    ComboBox,
    SearchLineEdit,
    SubtitleLabel,
    CheckBox,
    isDarkTheme,
    qconfig,
)

from app.models.widget_model import WidgetModel
from app.widgets.widget_card import WidgetCard
from app.services.desktop_widget_service import Win11Style
from app.views.toast_notification import show_success, show_warning, show_info
from app.utils.logger import logger


class WidgetsView(QFrame):
    """小组件视图"""

    _widget_model: WidgetModel
    _search_line: SearchLineEdit
    _category_combo: ComboBox
    _select_all_cb: CheckBox
    _batch_activate_btn: PushButton
    _batch_deactivate_btn: PushButton
    _scroll_area: ScrollArea
    _scroll_content: QWidget
    _grid_layout: QGridLayout
    _search_timer: Optional[QTimer]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("widgetsView")

        self._widget_model = WidgetModel()
        self._widget_cards: dict[str, WidgetCard] = {}
        self._selected_cards: dict[str, bool] = {}
        self._search_timer = None

        self._build_ui()
        self._load_widgets()
        self._connect_theme_signals()
        self._connect_widget_signals()

    def _connect_theme_signals(self) -> None:
        """连接主题变化信号"""
        qconfig.themeChanged.connect(self._on_theme_changed)

    def _connect_widget_signals(self) -> None:
        """连接桌面小组件状态变更信号"""
        from app.services.desktop_widget_service import widget_signals

        widget_signals.widget_closed.connect(self._on_widget_closed_externally)
        widget_signals.widget_shown.connect(self._on_widget_shown_externally)

    def _on_widget_closed_externally(self, widget_id: str) -> None:
        """桌面小组件被外部关闭时的回调（如点击窗口 X 按钮）"""
        if widget_id in self._widget_cards:
            self._widget_cards[widget_id].update_status(False)

    def _on_widget_shown_externally(self, widget_id: str) -> None:
        """桌面小组件被外部显示时的回调"""
        if widget_id in self._widget_cards:
            self._widget_cards[widget_id].update_status(True)

    def _on_theme_changed(self) -> None:
        """主题变化回调"""
        self._update_theme()

    def _update_theme(self) -> None:
        """更新主题颜色"""
        c = Win11Style.c()
        self._header.setStyleSheet("QFrame { background: transparent; }")
        self._batch_bar.setStyleSheet("QFrame { background: transparent; }")
        self._scroll_area.setStyleSheet(
            f"ScrollArea {{ background: {c['card_bg']}; border: none; }}"
        )
        self._scroll_content.setStyleSheet(f"QWidget {{ background: {c['card_bg']}; }}")
        for card in self._widget_cards.values():
            card.update_theme()

    def _build_ui(self) -> None:
        """构建UI"""
        c = Win11Style.c()
        self.setStyleSheet("WidgetsView { background: transparent; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部标题栏
        self._header = QFrame()
        self._header.setStyleSheet("QFrame { background: transparent; }")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(36, 28, 36, 16)
        header_layout.setSpacing(16)

        title = SubtitleLabel("小组件")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 搜索框
        self._search_line = SearchLineEdit(self)
        self._search_line.setPlaceholderText("搜索小组件...")
        self._search_line.setMinimumWidth(200)
        _ = self._search_line.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self._search_line)

        # 分类筛选下拉框
        self._category_combo = ComboBox()
        self._category_combo.setMinimumWidth(150)
        self._category_combo.addItems(["全部"])
        for category in self._widget_model.get_categories():
            self._category_combo.addItem(category)
        _ = self._category_combo.currentTextChanged.connect(self._on_category_changed)
        header_layout.addWidget(self._category_combo)

        # 刷新按钮
        refresh_btn = ToolButton(FIF.SYNC, parent=self)
        refresh_btn.setToolTip("刷新列表 (F5)")
        _ = refresh_btn.clicked.connect(self._load_widgets)
        refresh_btn.setShortcut(QKeySequence.StandardKey.Refresh)
        header_layout.addWidget(refresh_btn)

        layout.addWidget(self._header)

        # 批量操作栏
        self._batch_bar = QFrame()
        self._batch_bar.setStyleSheet("QFrame { background: transparent; }")
        batch_layout = QHBoxLayout(self._batch_bar)
        batch_layout.setContentsMargins(36, 8, 36, 8)
        batch_layout.setSpacing(12)

        self._select_all_cb = CheckBox("全选")
        _ = self._select_all_cb.stateChanged.connect(self._on_select_all_changed)
        batch_layout.addWidget(self._select_all_cb)

        batch_layout.addStretch()

        self._batch_activate_btn = PushButton(FIF.ADD, "批量激活", parent=self)
        _ = self._batch_activate_btn.clicked.connect(self._on_batch_activate)
        self._batch_activate_btn.setEnabled(False)
        batch_layout.addWidget(self._batch_activate_btn)

        self._batch_deactivate_btn = PushButton(FIF.CANCEL, "批量停用", parent=self)
        _ = self._batch_deactivate_btn.clicked.connect(self._on_batch_deactivate)
        self._batch_deactivate_btn.setEnabled(False)
        batch_layout.addWidget(self._batch_deactivate_btn)

        layout.addWidget(self._batch_bar)

        # 滚动区域
        self._scroll_area = ScrollArea(self)
        c = Win11Style.c()
        self._scroll_area.setStyleSheet(
            f"ScrollArea {{ background: {c['card_bg']}; border: none; }}"
        )
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet(f"QWidget {{ background: {c['card_bg']}; }}")
        self._grid_layout = QGridLayout(self._scroll_content)
        self._grid_layout.setContentsMargins(36, 16, 36, 36)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll_area.setWidget(self._scroll_content)
        layout.addWidget(self._scroll_area)

        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        """设置快捷键"""
        refresh_shortcut = QShortcut(QKeySequence.StandardKey.Refresh, self)
        _ = refresh_shortcut.activated.connect(self._load_widgets)

        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        _ = search_shortcut.activated.connect(lambda: self._search_line.setFocus())

        select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        _ = select_all_shortcut.activated.connect(
            lambda: self._select_all_cb.setChecked(True)
        )

        delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self)
        _ = delete_shortcut.activated.connect(self._on_batch_deactivate)

    def _load_widgets(self) -> None:
        """加载小组件"""
        self._clear_widgets()

        category = self._category_combo.currentText()
        if category == "全部":
            widgets = self._widget_model.get_all_widgets()
        else:
            widgets = self._widget_model.get_widgets_by_category(category)

        # 过滤掉来自禁用插件的小组件
        disabled_plugin_ids = set()
        window = self.window()
        if hasattr(window, "_plugin_mgr"):
            for entry in window._plugin_mgr.all_entries():
                if not entry.enabled:
                    disabled_plugin_ids.add(entry.meta.id)

        if disabled_plugin_ids:
            widgets = [w for w in widgets if w.plugin_id not in disabled_plugin_ids]

        # 应用搜索过滤
        search_text = self._search_line.text().lower()
        if search_text:
            widgets = [
                w
                for w in widgets
                if search_text in w.name.lower() or search_text in w.description.lower()
            ]

        # 创建卡片（使用网格布局）
        row = 0
        col = 0
        for widget_info in widgets:
            card_container = QFrame()
            card_container.setStyleSheet("QFrame { background: transparent; }")
            container_layout = QVBoxLayout(card_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(8)

            cb = CheckBox()
            _ = cb.stateChanged.connect(
                lambda state, wid=widget_info.id: self._on_card_selected(wid, state)
            )
            self._selected_cards[widget_info.id] = False
            container_layout.addWidget(cb)

            card = WidgetCard(widget_info, self._scroll_content)
            _ = card.activated.connect(self._on_widget_activated)
            _ = card.deactivated.connect(self._on_widget_deactivated)
            _ = card.settings_clicked.connect(self._on_widget_settings)

            self._widget_cards[widget_info.id] = card
            container_layout.addWidget(card)

            self._grid_layout.addWidget(card_container, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

        self._grid_layout.setRowStretch(row, 1)
        self._update_batch_buttons()

    def _clear_widgets(self) -> None:
        """清空所有小组件卡片"""
        self._widget_cards.clear()
        self._selected_cards.clear()

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def _on_search_changed(self, _text: str) -> None:
        """搜索文本改变"""
        if self._search_timer is not None:
            self._search_timer.stop()
            try:
                self._search_timer.timeout.disconnect()
            except Exception:
                pass
        else:
            self._search_timer = QTimer(self)
            self._search_timer.setSingleShot(True)

        self._search_timer.timeout.connect(self._load_widgets)
        self._search_timer.start(300)

    def _on_category_changed(self, category: str) -> None:
        """分类改变事件"""
        logger.info(f"切换到分类: {category}")
        self._load_widgets()

    def _on_card_selected(self, widget_id: str, state: int) -> None:
        """卡片选择状态改变"""
        self._selected_cards[widget_id] = state == 2
        self._update_batch_buttons()

    def _on_select_all_changed(self, state: int) -> None:
        """全选状态改变"""
        checked = state == 2
        self._selected_cards = {wid: checked for wid in self._selected_cards.keys()}

        for i in range(self._grid_layout.count()):
            item = self._grid_layout.itemAt(i)
            if item is not None:
                container = item.widget()
                if container is not None and isinstance(container, QFrame):
                    container_layout = container.layout()
                    if container_layout is not None:
                        cb_item = container_layout.itemAt(0)
                        if cb_item is not None:
                            cb = cb_item.widget()
                            if isinstance(cb, CheckBox):
                                cb.setChecked(checked)

        self._update_batch_buttons()

    def _update_batch_buttons(self) -> None:
        """更新批量操作按钮状态"""
        selected_count = sum(
            1 for selected in self._selected_cards.values() if selected
        )
        has_selection = selected_count > 0

        self._batch_activate_btn.setEnabled(has_selection)
        self._batch_deactivate_btn.setEnabled(has_selection)

        if has_selection:
            self._batch_activate_btn.setText(f"批量激活 ({selected_count})")
            self._batch_deactivate_btn.setText(f"批量停用 ({selected_count})")
        else:
            self._batch_activate_btn.setText("批量激活")
            self._batch_deactivate_btn.setText("批量停用")

    def _on_batch_activate(self) -> None:
        """批量激活小组件"""
        selected_widgets = [
            wid
            for wid, selected in self._selected_cards.items()
            if selected
            and (w := self._widget_model.get_widget(wid)) is not None
            and not w.is_active
        ]

        if not selected_widgets:
            show_warning("提示", "没有可激活的小组件")
            return

        from app.services.desktop_widget_service import DesktopWidgetManager

        widget_manager = DesktopWidgetManager.instance()

        for widget_id in selected_widgets:
            self._widget_model.activate_widget(widget_id)
            widget_manager.show_widget(widget_id)

            if widget_id in self._widget_cards:
                self._widget_cards[widget_id].update_status(True)

        self._select_all_cb.setChecked(False)
        show_success("批量激活成功", f"已激活 {len(selected_widgets)} 个小组件")
        logger.info(f"批量激活了 {len(selected_widgets)} 个小组件")

    def _on_batch_deactivate(self) -> None:
        """批量停用小组件"""
        selected_widgets = [
            wid
            for wid, selected in self._selected_cards.items()
            if selected
            and (w := self._widget_model.get_widget(wid)) is not None
            and w.is_active
        ]

        if not selected_widgets:
            show_warning("提示", "没有可停用的小组件")
            return

        from app.services.desktop_widget_service import DesktopWidgetManager

        widget_manager = DesktopWidgetManager.instance()

        for widget_id in selected_widgets:
            self._widget_model.deactivate_widget(widget_id)
            widget_manager.hide_widget(widget_id)

            if widget_id in self._widget_cards:
                self._widget_cards[widget_id].update_status(False)

        self._select_all_cb.setChecked(False)
        show_info("批量停用成功", f"已停用 {len(selected_widgets)} 个小组件")
        logger.info(f"批量停用了 {len(selected_widgets)} 个小组件")

    def _on_widget_activated(self, widget_id: str) -> None:
        """激活小组件"""
        self._widget_model.activate_widget(widget_id)

        from app.services.desktop_widget_service import DesktopWidgetManager

        widget_manager = DesktopWidgetManager.instance()
        widget_manager.show_widget(widget_id)

        if widget_id in self._widget_cards:
            self._widget_cards[widget_id].update_status(True)

        widget = self._widget_model.get_widget(widget_id)
        widget_name = widget.name if widget is not None else widget_id
        show_success("已激活", f"小组件「{widget_name}」已添加到桌面")
        logger.info(f"激活小组件: {widget_id}")

    def _on_widget_deactivated(self, widget_id: str) -> None:
        """停用小组件"""
        self._widget_model.deactivate_widget(widget_id)

        from app.services.desktop_widget_service import DesktopWidgetManager

        widget_manager = DesktopWidgetManager.instance()
        widget_manager.hide_widget(widget_id)

        if widget_id in self._widget_cards:
            self._widget_cards[widget_id].update_status(False)

        widget = self._widget_model.get_widget(widget_id)
        widget_name = widget.name if widget is not None else widget_id
        show_info("已停用", f"小组件「{widget_name}」已从桌面移除")
        logger.info(f"停用小组件: {widget_id}")

    def _on_widget_settings(self, widget_id: str) -> None:
        """打开小组件设置"""
        from app.widgets.widget_settings_dialog import WidgetSettingsDialog

        dialog = WidgetSettingsDialog(widget_id, self)
        _ = dialog.exec()
        logger.info(f"打开小组件设置: {widget_id}")
