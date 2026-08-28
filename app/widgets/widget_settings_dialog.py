"""
小组件设置窗口 — FluentWindow（侧边导航 + 云母材质）

按 qfluentwidgets 官方推荐，组件设置从模态对话框升级为独立
FluentWindow：每个设置分区（外观 / 信息显示 / 快捷方式）是一个
子界面，通过左侧导航切换。所有变更实时生效，支持恢复默认。

实现说明：qfluentwidgets 的 SettingCard 系列需要 ConfigItem 驱动，
这里为每张卡片创建独立的临时 ConfigItem（不写入 qconfig 持久化），
valueChanged 信号桥接到组件设置的即时保存与推送。
"""
from __future__ import annotations
from typing import Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QColorDialog, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from qfluentwidgets import (
    BodyLabel, PushButton,
    SettingCard, SwitchSettingCard, RangeSettingCard, OptionsSettingCard,
    StrongBodyLabel, ComboBox,
    LineEdit, ToolButton, FluentIcon as FIF,
    PrimaryPushButton, FluentWindow, isDarkTheme, ScrollArea,
)
from qfluentwidgets.common.config import (
    ConfigItem, RangeConfigItem, OptionsConfigItem, RangeValidator, OptionsValidator,
)

from app.models.widget_model import WidgetModel, WidgetInfo
from app.widgets.widget_options import get_widget_options, get_option_defaults


class _ColorSettingCard(SettingCard):
    """颜色选择卡片（SettingCard + 色块按钮）"""

    def __init__(self, title: str, color: str, callback, parent=None):
        super().__init__(FIF.PALETTE, title, "点击色块选择自定义颜色", parent)
        self._callback = callback
        self._color = QColor(color)

        self._swatch = QWidget(self)
        self._swatch.setFixedSize(24, 24)
        self._swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self._swatch.mousePressEvent = lambda _e: self.pick()
        self.hBoxLayout.addWidget(self._swatch, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self._apply_swatch()

    def _apply_swatch(self):
        border = "rgba(255,255,255,0.25)" if isDarkTheme() else "rgba(0,0,0,0.15)"
        self._swatch.setStyleSheet(
            f"background: {self._color.name()}; border-radius: 4px;"
            f"border: 1px solid {border};"
        )

    def pick(self):
        c = QColorDialog.getColor(self._color, self, "选择颜色",
                                  QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if c.isValid():
            self.setColor(c.name())
            self._callback(self._color.name())

    def setColor(self, color: str):
        self._color = QColor(color)
        self._apply_swatch()


class _SettingsPage(ScrollArea):
    """设置分区子界面 — 垂直卡片列表（透明背景以透出云母）"""

    def __init__(self, object_name: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(object_name)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.viewport().setAutoFillBackground(False)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._lay = QVBoxLayout(self._container)
        self._lay.setContentsMargins(36, 24, 36, 24)
        self._lay.setSpacing(8)
        self._lay.addStretch()
        self.setWidget(self._container)

    def add_card(self, card: QWidget) -> None:
        """在 stretch 之前插入卡片"""
        self._lay.insertWidget(self._lay.count() - 1, card)

    def add_widget(self, w: QWidget) -> None:
        self._lay.insertWidget(self._lay.count() - 1, w)

    def add_label(self, text: str) -> None:
        lbl = StrongBodyLabel(text)
        lbl.setStyleSheet("padding: 4px 2px 0 2px;")
        self.add_widget(lbl)


class _TightComboBox(ComboBox):
    """弹出菜单收紧阴影/边距的 ComboBox。

    默认 RoundMenu 带 30px 模糊半径的投影，弹出层的实际渲染尺寸
    比圆角卡片大一圈，边缘半透明像素在深浅背景交界处会显出一条
    模糊的"透明框"。这里用小半径清晰阴影 + 对称边距替代。

    注意：调整必须在 _createComboMenu 返回前完成（不能在子类
    __init__ 里 setShadowEffect——会导致 view 的 GC 状态异常，
    随后 exec 解析失败，见 OPTIMIZATION_SUMMARY）。
    """

    def _createComboMenu(self):
        from qfluentwidgets.components.widgets.combo_box import ComboBoxMenu
        menu = ComboBoxMenu(self)
        menu.setShadowEffect(blurRadius=12, offset=(0, 2), color=QColor(0, 0, 0, 60))
        menu.view.setViewportMargins(1, 2, 1, 4)
        return menu


class _CurrencyPairSettingCard(SettingCard):
    """货币对选择卡片（一行显示哪两种货币的汇率）"""

    def __init__(self, icon, title: str, currencies: list[str],
                 value: tuple[str, str], callback, parent=None):
        super().__init__(icon, title, "选择该行显示的两种货币", parent)
        self._callback = callback
        self._currencies = currencies

        self._base_combo = _TightComboBox(self)
        self._base_combo.addItems(currencies)
        self._quote_combo = _TightComboBox(self)
        self._quote_combo.addItems(currencies)
        for combo in (self._base_combo, self._quote_combo):
            combo.setMinimumWidth(86)
            combo.currentIndexChanged.connect(self._on_changed)

        self.setValue(value)

        self.hBoxLayout.addSpacing(4)
        self.hBoxLayout.addWidget(self._base_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addWidget(BodyLabel("/"), 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addWidget(self._quote_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def setValue(self, value: tuple[str, str]):
        base, quote = value
        if base in self._currencies:
            self._base_combo.setCurrentIndex(self._currencies.index(base))
        if quote in self._currencies:
            self._quote_combo.setCurrentIndex(self._currencies.index(quote))

    def _on_changed(self, _i):
        base = self._currencies[self._base_combo.currentIndex()]
        quote = self._currencies[self._quote_combo.currentIndex()]
        self._callback((base, quote))

    def value(self) -> tuple[str, str]:
        return (self._currencies[self._base_combo.currentIndex()],
                self._currencies[self._quote_combo.currentIndex()])


class WidgetSettingsWindow(FluentWindow):
    """小组件设置窗口 — FluentWindow（侧边导航分区 + 云母材质）"""

    widget_id: str
    _widget_model: WidgetModel
    widget_info: Optional[WidgetInfo]

    def __init__(self, widget_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.widget_id = widget_id
        self._widget_model = WidgetModel()
        self.widget_info = self._widget_model.get_widget(widget_id)

        widget_name = self.widget_info.name if self.widget_info else widget_id
        self.setWindowTitle(f"组件设置 - {widget_name}")
        self.setMinimumSize(760, 520)
        self.resize(820, 560)

        self._current_color: QColor = QColor("#FFFFFF")
        # 「信息显示」选项控件注册表 {key: (kind, card, default)}
        self._option_controls: dict[str, tuple[str, Any, Any]] = {}
        # 外观卡片注册表（恢复默认用）
        self._appearance_controls: dict[str, tuple[str, Any, Any]] = {}

        settings: dict[str, Any] = (
            self.widget_info.custom_settings if self.widget_info else {}
        ) or {}

        self._build_pages(settings)

    # ------------------------------------------------------------------ #
    # 页面构建
    # ------------------------------------------------------------------ #

    def _build_pages(self, settings: dict[str, Any]) -> None:
        # ── 外观页 ──
        appearance = _SettingsPage("widgetSettingsAppearance")
        self._build_appearance(appearance, settings)
        self.addSubInterface(appearance, FIF.BRIGHTNESS, "外观")

        # ── 信息显示页 ──
        options = get_widget_options(self.widget_id)
        if options:
            display = _SettingsPage("widgetSettingsDisplay")
            self._build_display(display, options, settings)
            self.addSubInterface(display, FIF.TILES, "信息显示")

        # ── 快捷方式页 ──
        if self.widget_id == "shortcut":
            shortcuts = _SettingsPage("widgetSettingsShortcuts")
            self._build_shortcuts(shortcuts, settings)
            self.addSubInterface(shortcuts, FIF.LINK, "快捷方式")

        # ── 底部操作（导航栏底部：恢复默认）──
        reset_btn = PushButton(FIF.SYNC, "恢复默认")
        reset_btn.clicked.connect(self._reset_defaults)
        self.navigationInterface.addItem(
            routeKey="widgetSettingsReset",
            icon=FIF.SYNC,
            text="恢复默认",
            onClick=self._reset_defaults,
            position=NavigationPositionBottomCompat.POSITION,
            tooltip="恢复默认",
            selectable=False,
        )

    # ------------------------------------------------------------------ #
    # 外观页
    # ------------------------------------------------------------------ #

    def _build_appearance(self, page: _SettingsPage, settings: dict) -> None:
        is_clock = self.widget_id == "clock"
        reg = self._appearance_controls

        if is_clock:
            page.add_card(self._make_range_card(
                FIF.FONT, "字体大小", "时钟文字的显示尺寸",
                16, 120, 52, "font_size", settings, reg))

            self._color_card = _ColorSettingCard(
                "文字颜色",
                settings.get("text_color", "#FFFFFF"),
                lambda name: self._apply_key("text_color", name),
                parent=self,
            )
            reg["text_color"] = ("color", self._color_card, "#FFFFFF")
            page.add_card(self._color_card)
        else:
            page.add_card(self._make_range_card(
                FIF.APPLICATION, "圆角大小", "组件卡片的圆角半径",
                0, 30, 16, "border_radius", settings, reg))

        # 透明度（所有组件）
        lo, hi = (30, 100) if is_clock else (50, 100)
        default_op = 1.0 if is_clock else 0.95
        card = self._make_range_card(
            FIF.BRIGHTNESS, "透明度", "组件窗口的整体不透明度（%）",
            lo, hi, int(default_op * 100), "opacity_pct", settings, reg)
        reg.pop("opacity_pct")
        self._opacity_card = card
        reg["opacity"] = ("opacity", card, default_op)
        card.valueChanged.disconnect()
        card.valueChanged.connect(lambda v: self._apply_key("opacity", v / 100.0))
        page.add_card(card)

        if not is_clock:
            page.add_card(self._make_options_card(
                FIF.BACK_TO_WINDOW, "阴影强度", "组件的阴影视觉效果",
                ["无", "轻微", "中等", "强烈"], "轻微", "shadow", settings, reg))

    # ------------------------------------------------------------------ #
    # 信息显示页（schema 驱动）
    # ------------------------------------------------------------------ #

    def _build_display(self, page: _SettingsPage,
                       options: list[dict], settings: dict) -> None:
        for opt in options:
            key, kind = opt["key"], opt["type"]
            default = opt.get("default")
            icon = self._icon_for(opt)

            if kind == "bool":
                card = self._make_switch_card(
                    icon, opt["label"], "开启后显示于组件上",
                    bool(default), key, settings, self._option_controls)
            elif kind == "choice":
                choices = opt.get("choices", [])
                card = self._make_options_card(
                    icon, opt["label"], "",
                    [display for _v, display in choices],
                    default, key, settings, self._option_controls)
            elif kind == "int":
                card = self._make_range_card(
                    icon, opt["label"],
                    f"范围 {opt.get('min', 0)} – {opt.get('max', 99)}",
                    int(opt.get("min", 0)), int(opt.get("max", 99)),
                    int(default or 0), key, settings, self._option_controls)
            elif kind == "currency_pair":
                currencies = opt.get("currencies", [])
                stored = settings.get(key, default)
                if not (isinstance(stored, (list, tuple)) and len(stored) == 2):
                    stored = default or ["USD", "CNY"]
                card = _CurrencyPairSettingCard(
                    icon, opt["label"], currencies, tuple(stored),
                    callback=lambda v, k=key: self._apply_key(k, list(v)),
                    parent=self,
                )
                self._option_controls[key] = ("pair", card, default)
            else:
                continue

            page.add_card(card)

        # ── 组件/插件注册的自定义设置页面（追加为独立导航页，可多个）──
        self._add_custom_pages()

    def _add_custom_pages(self) -> None:
        """把组件/插件注册的自定义设置页面加为独立导航页（可多个）"""
        from app.widgets.widget_options import get_settings_pages

        for spec in get_settings_pages(self.widget_id):
            try:
                page = _SettingsPage(f"widgetSettings_{spec['page_id']}")
                widget = spec["factory"]()
                if widget is None:
                    continue
                page.add_widget(widget)
                icon = spec.get("icon") or FIF.INFO
                self.addSubInterface(page, icon, spec["title"])
            except Exception:
                from loguru import logger
                logger.exception("注册组件自定义设置页面失败: {}", spec.get("page_id"))

    @staticmethod
    def _icon_for(opt: dict) -> Any:
        """按选项 key 选一个贴切的 Fluent 图标"""
        key = opt.get("key", "")
        mapping = {
            "show_date": FIF.CALENDAR, "show_seconds": FIF.DATE_TIME,
            "show_cpu": FIF.SPEED_HIGH, "show_mem": FIF.IOT, "show_disk": FIF.SAVE,
            "show_cpu_freq": FIF.SPEED_OFF, "show_totals": FIF.CLOUD,
            "show_detail": FIF.CLOUD, "show_artist": FIF.MUSIC, "show_time": FIF.HISTORY,
            "max_items": FIF.MARKET, "show_source": FIF.FEEDBACK,
            "show_usd": FIF.SHOPPING_CART, "show_eur": FIF.SHOPPING_CART,
            "show_gbp": FIF.SHOPPING_CART, "show_jpy": FIF.SHOPPING_CART,
            "show_hkd": FIF.SHOPPING_CART,
        }
        return mapping.get(key, FIF.INFO)

    # ------------------------------------------------------------------ #
    # 快捷方式页
    # ------------------------------------------------------------------ #

    def _build_shortcuts(self, page: _SettingsPage, settings: dict) -> None:
        self._shortcut_widgets: list[dict] = []
        rows = QWidget()
        rows.setStyleSheet("background: transparent;")
        self._shortcut_layout = QVBoxLayout(rows)
        self._shortcut_layout.setContentsMargins(0, 0, 0, 0)
        self._shortcut_layout.setSpacing(8)
        page.add_widget(rows)

        add_btn = PushButton(FIF.ADD, "添加快捷方式")
        add_btn.clicked.connect(self._add_shortcut_row)
        page.add_widget(add_btn)

        for s in settings.get("shortcuts", []):
            self._add_shortcut_row(s)

    # ------------------------------------------------------------------ #
    # 卡片工厂（每卡独立 ConfigItem，信号桥到 _apply_key）
    # ------------------------------------------------------------------ #

    def _make_range_card(self, icon, title: str, content: str,
                         lo: int, hi: int, default: int,
                         key: str, settings: dict, registry: dict) -> RangeSettingCard:
        item = RangeConfigItem(
            group=f"widget.{self.widget_id}", name=key,
            default=default, validator=RangeValidator(lo, hi),
        )
        card = RangeSettingCard(item, icon, title, content, parent=self)
        # 默认滑杆 268px 最小宽会溢出卡片，压缩到可用宽度
        card.slider.setMinimumWidth(150)
        card.slider.setMaximumWidth(220)
        card.setValue(int(settings.get(key, default)))
        card.valueChanged.connect(lambda v, k=key: self._apply_key(k, v))
        registry[key] = ("range", card, default)
        return card

    def _make_options_card(self, icon, title: str, content: str,
                           texts: list[str], default: str,
                           key: str, settings: dict, registry: dict) -> OptionsSettingCard:
        item = OptionsConfigItem(
            group=f"widget.{self.widget_id}", name=key,
            default=default, validator=OptionsValidator(texts),
        )
        card = OptionsSettingCard(item, icon, title, content, texts=texts, parent=self)
        cur = settings.get(key, default)
        if cur in texts:
            card.setValue(cur)
        item.valueChanged.connect(lambda val, k=key: self._apply_key(k, val))
        registry[key] = ("options", card, default)
        return card

    def _make_switch_card(self, icon, title: str, content: str,
                          default: bool, key: str, settings: dict,
                          registry: dict) -> SwitchSettingCard:
        item = ConfigItem(group=f"widget.{self.widget_id}", name=key, default=default)
        card = SwitchSettingCard(icon, title, content, configItem=item, parent=self)
        card.setChecked(bool(settings.get(key, default)))
        card.checkedChanged.connect(lambda on, k=key: self._apply_key(k, on))
        registry[key] = ("switch", card, default)
        return card

    # ------------------------------------------------------------------ #
    # 实时应用
    # ------------------------------------------------------------------ #

    def _apply_key(self, key: str, value: Any) -> None:
        """单键更新：保存并即时推送到运行中的组件"""
        if self.widget_info is None:
            return
        settings = self.widget_info.custom_settings or {}
        settings[key] = value
        self.widget_info.custom_settings = settings
        self._widget_model.save()
        self._push_to_widget(settings)

    def _apply_realtime(self) -> None:
        """全量应用（快捷方式编辑后调用）"""
        if self.widget_info is None:
            return
        self._widget_model.save()
        self._push_to_widget(self.widget_info.custom_settings or {})

    def _push_to_widget(self, settings: dict) -> None:
        """将设置推送到正在运行的桌面组件实例"""
        from app.services.desktop_widget_service import DesktopWidgetManager
        try:
            manager = DesktopWidgetManager.instance()
            widget = manager._active_widgets.get(self.widget_id)
            if widget:
                if hasattr(widget, "update_settings"):
                    widget.update_settings(settings)
                elif hasattr(widget, "apply_settings"):
                    widget.apply_settings(settings)
                elif hasattr(widget, "on_settings_changed"):
                    widget.on_settings_changed(settings)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 恢复默认
    # ------------------------------------------------------------------ #

    def _reset_defaults(self) -> None:
        """把所有设置恢复为默认值（外观 + 信息显示）"""
        if self.widget_info is None:
            return

        defaults: dict[str, Any] = {}

        for key, (kind, card, default) in {
            **self._appearance_controls,
            **self._option_controls,
        }.items():
            defaults[key] = default
            try:
                if kind == "range":
                    card.setValue(int(default))
                elif kind == "switch":
                    card.setChecked(bool(default))
                elif kind == "options":
                    card.setValue(default)
                elif kind == "color":
                    card.setColor(str(default))
            except Exception:
                pass

        self.widget_info.custom_settings = defaults
        self._widget_model.save()
        self._push_to_widget(defaults)

    # ------------------------------------------------------------------ #
    # 兼容旧接口
    # ------------------------------------------------------------------ #

    def _pick_color(self) -> None:
        if hasattr(self, "_color_card"):
            self._color_card.pick()

    def _load_settings(self) -> None:
        """兼容旧调用（设置已在构造时应用）"""

    def _add_shortcut_row(self, shortcut: Optional[dict] = None) -> None:
        if not hasattr(self, '_shortcut_layout'):
            return
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        name_edit = LineEdit()
        name_edit.setPlaceholderText("名称")
        name_edit.setText(shortcut.get("name", "") if shortcut else "")
        name_edit.setMinimumWidth(100)
        row_layout.addWidget(name_edit)

        command_edit = LineEdit()
        command_edit.setPlaceholderText("命令或路径")
        command_edit.setText(shortcut.get("command", "") if shortcut else "")
        row_layout.addWidget(command_edit, 1)

        remove_btn = ToolButton(FIF.DELETE)
        remove_btn.setFixedWidth(32)
        remove_btn.clicked.connect(lambda: self._remove_shortcut_row(row_widget))
        row_layout.addWidget(remove_btn)

        index = self._shortcut_layout.count() - 1
        self._shortcut_layout.insertWidget(index, row_widget)
        self._shortcut_widgets.append({
            "widget": row_widget,
            "name_edit": name_edit,
            "command_edit": command_edit,
        })

    def _remove_shortcut_row(self, row_widget: QWidget) -> None:
        self._shortcut_widgets = [r for r in self._shortcut_widgets if r["widget"] != row_widget]
        self._shortcut_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._apply_realtime()


class NavigationPositionBottomCompat:
    """navigationInterface.addItem 的底部位置参数（避免循环导入的兼容写法）"""
    POSITION = None  # 运行时由模块底部覆盖


# 底部位置常量（在 import 末尾解析，避免顶部循环导入）
from qfluentwidgets import NavigationItemPosition  # noqa: E402
NavigationPositionBottomCompat.POSITION = NavigationItemPosition.BOTTOM
