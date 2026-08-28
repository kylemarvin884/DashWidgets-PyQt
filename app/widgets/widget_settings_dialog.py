"""
小组件设置对话框 — qfluentwidgets 原生 SettingCard 风格

结构：每个设置项是一张 SettingCard（图标 + 标题/描述 + 右侧控件），
与主窗口设置页视觉一致。所有变更实时生效（无保存按钮），
支持一键恢复默认值。

实现说明：qfluentwidgets 的 SettingCard 系列需要 ConfigItem 驱动，
这里为每张卡片创建独立的临时 ConfigItem（不写入 qconfig 持久化），
valueChanged 信号桥接到组件设置的即时保存与推送。
"""
from __future__ import annotations
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QWidget, QScrollArea, QColorDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from qfluentwidgets import (
    BodyLabel, PushButton,
    SettingCard, SwitchSettingCard, RangeSettingCard, OptionsSettingCard,
    StrongBodyLabel,
    LineEdit, ToolButton, FluentIcon as FIF,
    PrimaryPushButton, isDarkTheme,
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


class WidgetSettingsDialog(QDialog):
    """小组件设置对话框 — SettingCard 卡片式，实时生效"""

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
        self.setMinimumWidth(520)

        self._current_color: QColor = QColor("#FFFFFF")
        # 「信息显示」选项控件注册表 {key: (kind, card, default)}
        self._option_controls: dict[str, tuple[str, Any, Any]] = {}
        # 外观卡片注册表（恢复默认用）
        self._appearance_controls: dict[str, tuple[str, Any, Any]] = {}

        settings: dict[str, Any] = (
            self.widget_info.custom_settings if self.widget_info else {}
        ) or {}

        self._init_ui(settings)

    # ------------------------------------------------------------------ #
    # UI 构建
    # ------------------------------------------------------------------ #

    def _init_ui(self, settings: dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(8)

        # ── 外观分区 ──
        layout.addWidget(self._section_label("外观"))
        self._build_appearance_group(layout, settings)

        # ── 信息显示分区（声明式选项）──
        options = get_widget_options(self.widget_id)
        if options:
            layout.addSpacing(8)
            layout.addWidget(self._section_label("信息显示"))
            self._build_display_group(layout, options, settings)

        # ── 快捷方式分区 ──
        if self.widget_id == "shortcut":
            layout.addSpacing(8)
            layout.addWidget(self._section_label("快捷方式"))
            self._build_shortcut_list(layout, settings)

        layout.addStretch()

        # ── 底部操作 ──
        btn_row = QHBoxLayout()
        reset_btn = PushButton(FIF.SYNC, "恢复默认")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        close_btn = PrimaryPushButton("完成")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = StrongBodyLabel(text)
        lbl.setStyleSheet("padding: 4px 2px 0 2px;")
        return lbl

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
        # 默认滑杆 268px 在本对话框宽度下会溢出卡片，压缩到可用宽度
        card.slider.setMinimumWidth(150)
        card.slider.setMaximumWidth(200)
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
    # 外观分区
    # ------------------------------------------------------------------ #

    def _build_appearance_group(self, layout: QVBoxLayout, settings: dict) -> None:
        cards: list[SettingCard] = []
        is_clock = self.widget_id == "clock"
        reg = self._appearance_controls

        if is_clock:
            cards.append(self._make_range_card(
                FIF.FONT, "字体大小", "时钟文字的显示尺寸",
                16, 120, 52, "font_size", settings, reg))

            self._color_card = _ColorSettingCard(
                "文字颜色",
                settings.get("text_color", "#FFFFFF"),
                lambda name: self._apply_key("text_color", name),
                parent=self,
            )
            reg["text_color"] = ("color", self._color_card, "#FFFFFF")
            cards.append(self._color_card)
        else:
            cards.append(self._make_range_card(
                FIF.APPLICATION, "圆角大小", "组件卡片的圆角半径",
                0, 30, 16, "border_radius", settings, reg))

        # 透明度（所有组件）
        lo, hi = (30, 100) if is_clock else (50, 100)
        default_op = 1.0 if is_clock else 0.95
        cards.append(self._make_range_card(
            FIF.BRIGHTNESS, "透明度", "组件窗口的整体不透明度（%）",
            lo, hi, int(default_op * 100), "opacity_pct", settings, reg))
        # opacity_pct 的变化换算成 0-1 存储
        _, card, _d = reg.pop("opacity_pct")
        self._opacity_card = card
        reg["opacity"] = ("opacity", card, default_op)
        card.valueChanged.disconnect()
        card.valueChanged.connect(lambda v: self._apply_key("opacity", v / 100.0))

        if not is_clock:
            cards.append(self._make_options_card(
                FIF.BACK_TO_WINDOW, "阴影强度", "组件的阴影视觉效果",
                ["无", "轻微", "中等", "强烈"], "轻微", "shadow", settings, reg))

        for card in cards:
            layout.addWidget(card)

    # ------------------------------------------------------------------ #
    # 信息显示分区（schema 驱动）
    # ------------------------------------------------------------------ #

    def _build_display_group(self, layout: QVBoxLayout,
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
            else:
                continue

            layout.addWidget(card)

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
    # 快捷方式分区
    # ------------------------------------------------------------------ #

    def _build_shortcut_list(self, layout: QVBoxLayout, settings: dict) -> None:
        self._shortcut_widgets: list[dict] = []
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(150)
        scroll_area.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll_area.viewport().setAutoFillBackground(False)
        self._shortcut_container = QWidget()
        self._shortcut_container.setStyleSheet("background: transparent;")
        self._shortcut_layout = QVBoxLayout(self._shortcut_container)
        self._shortcut_layout.setContentsMargins(8, 8, 8, 8)
        self._shortcut_layout.setSpacing(8)
        self._shortcut_layout.addStretch()
        scroll_area.setWidget(self._shortcut_container)
        layout.addWidget(scroll_area)

        add_btn = PushButton(FIF.ADD, "添加快捷方式")
        add_btn.clicked.connect(self._add_shortcut_row)
        layout.addWidget(add_btn)

        for s in settings.get("shortcuts", []):
            self._add_shortcut_row(s)

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
