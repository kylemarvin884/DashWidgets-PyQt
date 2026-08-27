"""
小组件设置对话框 — 统一版

支持两种调用方式：
  1. 从 widgets_view 右键/齿轮按钮：传入 widget_id，实时推送到运行中的组件
  2. 从 desktop_widget_service 右键菜单：传入 widget_id，实时推送

所有设置变更立即生效（无保存按钮）。

注意：本对话框可能以桌面组件窗口为父窗口，而组件窗口的 QSS 是
``background: transparent``（样式表会沿父子链传播）。因此这里必须
设置自己的样式表覆盖继承值，否则对话框背景渲染为黑色。
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
    BodyLabel, PrimaryPushButton, PushButton,
    CardWidget, SpinBox, DoubleSpinBox,
    ComboBox, StrongBodyLabel,
    LineEdit, ToolButton, FluentIcon as FIF,
    Slider, qconfig,
)

from app.models.widget_model import WidgetModel, WidgetInfo
from app.services.desktop_widget_service import Win11Style


class WidgetSettingsDialog(QDialog):
    """小组件设置对话框 — 实时刷新，无需保存按钮"""

    widget_id: str
    _widget_model: WidgetModel
    widget_info: Optional[WidgetInfo]

    def __init__(self, widget_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.widget_id = widget_id
        self._widget_model = WidgetModel()
        self.widget_info = self._widget_model.get_widget(widget_id)

        widget_name = self.widget_info.name if self.widget_info else widget_id
        self.setWindowTitle(f"设置 - {widget_name}")
        self.setMinimumWidth(450)
        # 覆盖父窗口传播下来的 transparent 背景（否则对话框渲染为黑色）
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._current_color: QColor = QColor("#FFFFFF")

        self._init_ui()
        self._apply_theme()
        qconfig.themeChanged.connect(self._apply_theme)
        self._load_settings()

    def _apply_theme(self, _theme=None) -> None:
        """主题感知样式：跟随浅色奶油/深色海军蓝设计系统"""
        c = Win11Style.c()
        self.setStyleSheet(f"""
            WidgetSettingsDialog, QDialog {{
                background-color: {c['bg']};
            }}
            QLabel, BodyLabel, StrongBodyLabel {{
                color: {c['text_primary']};
                background: transparent;
            }}
            QScrollArea {{
                border: 1px solid {c['card_border']};
                border-radius: 6px;
                background: {c['surface_soft']};
            }}
            QScrollBar:vertical {{ width: 8px; background: transparent; }}
            QScrollBar::handle:vertical {{
                background: {c['card_border']}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {c['text_secondary']}; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        """)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = StrongBodyLabel("外观设置")
        layout.addWidget(title)

        form_card = CardWidget()
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(16)

        # ════════════════════════════════════
        #  时钟专用设置（实时生效）
        # ════════════════════════════════════
        if self.widget_id == "clock":
            self._build_clock_settings(form_layout)
        else:
            # ════════════════════════════════════
            #  其他组件的通用设置
            # ════════════════════════════════════
            self._build_general_settings(form_layout)

        # 快捷方式列表（仅快捷方式）
        if self.widget_id == "shortcut":
            self._build_shortcut_list(form_layout)

        layout.addWidget(form_card)

        # 底部：只保留关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = PrimaryPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _build_clock_settings(self, form_layout: QVBoxLayout) -> None:
        """时钟专用设置：显示秒数、字体大小、文字颜色、透明度"""
        # ── 显示秒数 ──
        sec_row = QHBoxLayout()
        sec_row.setSpacing(12)
        sec_label = BodyLabel("显示秒数:")
        sec_label.setMinimumWidth(80)
        sec_row.addWidget(sec_label)
        self._show_seconds_combo = ComboBox()
        self._show_seconds_combo.addItems(["否", "是"])
        self._show_seconds_combo.setMinimumWidth(200)
        self._show_seconds_combo.currentIndexChanged.connect(lambda: self._apply_realtime())
        sec_row.addWidget(self._show_seconds_combo)
        sec_row.addStretch()
        form_layout.addLayout(sec_row)

        # ── 字体大小滑块 ──
        fs_row = QHBoxLayout()
        fs_row.setSpacing(12)
        fs_label = BodyLabel("字体大小:")
        fs_label.setMinimumWidth(80)
        fs_row.addWidget(fs_label)
        self._font_size_slider = Slider(Qt.Orientation.Horizontal)
        self._font_size_slider.setRange(16, 120)
        self._font_size_slider.setValue(52)
        self._font_size_slider.setMinimumWidth(180)
        self._font_size_val = BodyLabel("52 px")
        self._font_size_val.setFixedWidth(50)
        self._font_size_slider.valueChanged.connect(
            lambda v: (self._font_size_val.setText(f"{v} px"), self._apply_realtime())
        )
        fs_row.addWidget(self._font_size_slider)
        fs_row.addWidget(self._font_size_val)
        fs_row.addStretch()
        form_layout.addLayout(fs_row)

        # ── 文字颜色 ──
        color_row = QHBoxLayout()
        color_row.setSpacing(12)
        color_label = BodyLabel("文字颜色:")
        color_label.setMinimumWidth(80)
        color_row.addWidget(color_label)

        self._color_btn = PushButton("选择颜色", self)
        self._color_btn.setFixedWidth(100)
        self._color_btn.clicked.connect(self._pick_color)
        self._color_preview = QWidget()
        self._color_preview.setFixedSize(28, 28)
        self._color_preview.setStyleSheet(
            "background: #FFFFFF; border-radius: 4px; border:1px solid rgba(0,0,0,0.15);"
        )
        color_row.addWidget(self._color_btn)
        color_row.addWidget(self._color_preview)
        color_row.addStretch()
        form_layout.addLayout(color_row)

        # ── 透明度 ──
        op_row = QHBoxLayout()
        op_row.setSpacing(12)
        op_label = BodyLabel("透明度:")
        op_label.setMinimumWidth(80)
        op_row.addWidget(op_label)
        self._opacity_spin = DoubleSpinBox()
        self._opacity_spin.setRange(30, 100)
        self._opacity_spin.setSuffix(" %")
        self._opacity_spin.setSingleStep(5)
        self._opacity_spin.setValue(100)
        self._opacity_spin.setMinimumWidth(200)
        self._opacity_spin.valueChanged.connect(lambda v: self._apply_realtime())
        op_row.addWidget(self._opacity_spin)
        op_row.addStretch()
        form_layout.addLayout(op_row)

    def _build_general_settings(self, form_layout: QVBoxLayout) -> None:
        """通用组件设置：尺寸、圆角、透明度、阴影"""
        # 组件尺寸
        size_layout = QHBoxLayout()
        size_layout.setSpacing(12)
        size_label = BodyLabel("组件尺寸:")
        size_label.setMinimumWidth(80)
        size_layout.addWidget(size_label)
        self._size_combo = ComboBox()
        self._size_combo.addItems(["小", "中", "大"])
        self._size_combo.setMinimumWidth(200)
        self._size_combo.currentIndexChanged.connect(lambda: self._apply_realtime())
        size_layout.addWidget(self._size_combo)
        size_layout.addStretch()
        form_layout.addLayout(size_layout)

        # 圆角
        radius_layout = QHBoxLayout()
        radius_layout.setSpacing(12)
        radius_label = BodyLabel("圆角大小:")
        radius_label.setMinimumWidth(80)
        radius_layout.addWidget(radius_label)
        self._radius_spin = SpinBox()
        self._radius_spin.setRange(0, 30)
        self._radius_spin.setSuffix(" px")
        self._radius_spin.setMinimumWidth(200)
        self._radius_spin.valueChanged.connect(lambda v: self._apply_realtime())
        radius_layout.addWidget(self._radius_spin)
        radius_layout.addStretch()
        form_layout.addLayout(radius_layout)

        # 透明度
        opacity_layout = QHBoxLayout()
        opacity_layout.setSpacing(12)
        opacity_label = BodyLabel("透明度:")
        opacity_label.setMinimumWidth(80)
        opacity_layout.addWidget(opacity_label)
        self._opacity_spin = DoubleSpinBox()
        self._opacity_spin.setRange(50, 100)
        self._opacity_spin.setSuffix(" %")
        self._opacity_spin.setSingleStep(5)
        self._opacity_spin.setMinimumWidth(200)
        self._opacity_spin.valueChanged.connect(lambda v: self._apply_realtime())
        opacity_layout.addWidget(self._opacity_spin)
        opacity_layout.addStretch()
        form_layout.addLayout(opacity_layout)

        # 阴影
        shadow_layout = QHBoxLayout()
        shadow_layout.setSpacing(12)
        shadow_label = BodyLabel("阴影强度:")
        shadow_label.setMinimumWidth(80)
        shadow_layout.addWidget(shadow_label)
        self._shadow_combo = ComboBox()
        self._shadow_combo.addItems(["无", "轻微", "中等", "强烈"])
        self._shadow_combo.setMinimumWidth(200)
        self._shadow_combo.currentIndexChanged.connect(lambda: self._apply_realtime())
        shadow_layout.addWidget(self._shadow_combo)
        shadow_layout.addStretch()
        form_layout.addLayout(shadow_layout)

    def _build_shortcut_list(self, form_layout: QVBoxLayout) -> None:
        self._shortcut_widgets: list[dict] = []
        shortcut_title = StrongBodyLabel("快捷方式列表")
        form_layout.addSpacing(8)
        form_layout.addWidget(shortcut_title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(150)
        self._shortcut_container = QWidget()
        self._shortcut_layout = QVBoxLayout(self._shortcut_container)
        self._shortcut_layout.setContentsMargins(8, 8, 8, 8)
        self._shortcut_layout.setSpacing(8)
        self._shortcut_layout.addStretch()
        scroll_area.setWidget(self._shortcut_container)
        form_layout.addWidget(scroll_area)

        add_btn = PushButton(FIF.ADD, "添加快捷方式")
        add_btn.clicked.connect(self._add_shortcut_row)
        form_layout.addWidget(add_btn)

    # ── 实时应用 ──────────────────────────────────────── #

    def _apply_realtime(self) -> None:
        """收集当前所有控件值 → 立即保存并应用到桌面组件"""
        if self.widget_info is None:
            return

        settings = self._collect_settings()
        self.widget_info.custom_settings = settings
        self._widget_model.save()
        self._push_to_widget(settings)

    def _collect_settings(self) -> dict[str, Any]:
        """从所有控件收集当前值"""
        d: dict[str, Any] = {}

        if self.widget_id == "clock":
            if hasattr(self, '_show_seconds_combo'):
                d["show_seconds"] = self._show_seconds_combo.currentIndex() == 1
            if hasattr(self, '_font_size_slider'):
                d["font_size"] = self._font_size_slider.value()
            c = getattr(self, '_current_color', None)
            if c:
                d["text_color"] = f"#{c.red():02x}{c.green():02x}{c.blue():02x}"
            if hasattr(self, '_opacity_spin'):
                d["opacity"] = self._opacity_spin.value() / 100.0
        else:
            if hasattr(self, '_size_combo'):
                sz_map = {"小": "small", "中": "medium", "大": "large"}
                d["size"] = sz_map.get(self._size_combo.currentText(), "medium")
            if hasattr(self, '_radius_spin'):
                d["border_radius"] = self._radius_spin.value()
            if hasattr(self, '_opacity_spin'):
                d["opacity"] = self._opacity_spin.value() / 100.0
            if hasattr(self, '_shadow_combo'):
                d["shadow"] = self._shadow_combo.currentText()

        return d

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

    # ── 颜色选择器 ────────────────────────────────────── #

    def _pick_color(self) -> None:
        initial = getattr(self, '_current_color', QColor("#FFFFFF"))
        c = QColorDialog.getColor(initial, self, "选择文字颜色",
                                   QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if c.isValid():
            self._current_color = c
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            self._color_preview.setStyleSheet(
                f"background: rgba({r},{g},{b},{a}); "
                f"border-radius: 4px; border:1px solid rgba(0,0,0,0.15);"
            )
            self._apply_realtime()

    # ── 加载已有设置 ───────────────────────────────────── #

    def _load_settings(self) -> None:
        if self.widget_info is None:
            return
        settings: dict[str, Any] = self.widget_info.custom_settings or {}

        if self.widget_id == "clock":
            # 显示秒数
            if hasattr(self, '_show_seconds_combo'):
                self._show_seconds_combo.setCurrentIndex(
                    1 if settings.get("show_seconds", False) else 0
                )

            # 字体大小
            if hasattr(self, '_font_size_slider'):
                fs = settings.get("font_size", 52)
                self._font_size_slider.setValue(max(16, min(120, int(fs))))

            # 文字颜色
            tc = settings.get("text_color")
            if tc:
                qc = QColor(tc)
                if qc.isValid():
                    self._current_color = qc
                    r, g, b, a = qc.red(), qc.green(), qc.blue(), qc.alpha()
                    self._color_preview.setStyleSheet(
                        f"background: rgba({r},{g},{b},{a}); "
                        f"border-radius: 4px; border:1px solid rgba(0,0,0,0.15);"
                    )

            # 透明度（存储为 0-1 小数）
            op = settings.get("opacity", 1.0)
            self._opacity_spin.setValue(float(op) * 100)
        else:
            # 尺寸
            if hasattr(self, '_size_combo'):
                sm = {"small": "小", "medium": "中", "large": "大"}
                ds = self.widget_info.size or "medium"
                t = sm.get(settings.get("size", ds), "中")
                idx = self._size_combo.findText(t)
                if idx >= 0:
                    self._size_combo.setCurrentIndex(idx)

            # 圆角
            if hasattr(self, '_radius_spin'):
                self._radius_spin.setValue(settings.get("border_radius", 16))

            # 透明度（存储为 0-1 小数，而非百分数）
            if hasattr(self, '_opacity_spin'):
                self._opacity_spin.setValue(float(settings.get("opacity", 0.95)) * 100)

            # 阴影
            if hasattr(self, '_shadow_combo'):
                sh = settings.get("shadow", "轻微")
                idx = self._shadow_combo.findText(sh)
                if idx >= 0:
                    self._shadow_combo.setCurrentIndex(idx)

        # 快捷方式
        if self.widget_id == "shortcut" and hasattr(self, '_shortcut_layout'):
            shortcuts = settings.get("shortcuts", [])
            for s in shortcuts:
                self._add_shortcut_row(s)

    # ── 快捷方式行 ────────────────────────────────────── #

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

        icon_combo = ComboBox()
        icon_combo.addItems([
            "APPLICATION", "BROWSER", "CALCULATOR", "CALENDAR",
            "CHAT", "CODE", "COMMAND_PROMPT", "DOCUMENT",
            "DOWNLOAD", "FOLDER", "GAME", "GLOBE",
            "HELP", "HOME", "IMAGE", "MAIL",
            "MEDIA", "MUSIC", "PHOTO", "PLAY",
            "SEARCH", "SETTING", "SHARE", "SHOP",
            "TAG", "VIDEO", "WORD", "ZIP",
        ])
        icon_combo.setCurrentText(shortcut.get("icon", "APPLICATION") if shortcut else "APPLICATION")
        icon_combo.setFixedWidth(120)
        row_layout.addWidget(icon_combo)

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
            "icon_combo": icon_combo,
        })

    def _remove_shortcut_row(self, row_widget: QWidget) -> None:
        self._shortcut_widgets = [r for r in self._shortcut_widgets if r["widget"] != row_widget]
        self._shortcut_layout.removeWidget(row_widget)
        row_widget.deleteLater()
