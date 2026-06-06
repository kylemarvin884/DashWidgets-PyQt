"""
设置视图：主题、个性化、备份等
"""

import json
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QWidget,
    QFormLayout,
)
from PySide6.QtCore import Qt

from qfluentwidgets import (
    ScrollArea,
    FluentIcon as FIF,
    PushButton,
    BodyLabel,
    TitleLabel,
    CardWidget,
    StrongBodyLabel,
    ComboBox,
    SpinBox,
    SettingCardGroup,
    OptionsSettingCard,
    RangeSettingCard,
    SwitchButton,
    CaptionLabel,
    qconfig,
    Theme,
)

from app.services.desktop_widget_service import Win11Style
from app.models.widget_model import WidgetModel
from app.views.toast_notification import (
    POSITION_LABELS,
    ALL_POSITIONS,
    show_success,
    show_error,
    show_warning,
)
from app.services import url_scheme_service as uss
from app.services import autostart_service as autostart
from app.services.settings_service import SettingsService
from app.constants import URL_SCHEME
from loguru import logger


class SettingsView(ScrollArea):
    """设置视图"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("settingsView")
        self.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.viewport().setAutoFillBackground(False)

        self._widget_model = WidgetModel()

        # 监听主题变化
        qconfig.themeChanged.connect(self._on_theme_changed)

        container = QWidget()
        container.setAutoFillBackground(False)
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(20)

        layout.addWidget(TitleLabel("设置"))

        # ── 外观设置 ─────────────────────────────────────────────── #

        # 使用 qfluentwidgets 默认的主题设置组件
        self.appearance_group = SettingCardGroup("外观设置", parent=self)

        # 主题模式设置卡片（使用 qfluentwidgets 内置配置）
        self.theme_card = OptionsSettingCard(
            qconfig.themeMode,
            FIF.PALETTE,
            "主题模式",
            "选择应用程序的主题模式",
            texts=["浅色", "深色", "跟随系统"],
            parent=self.appearance_group,
        )
        self.appearance_group.addSettingCard(self.theme_card)

        # 云母效果开关（仅 Windows 11）
        from qfluentwidgets import SettingCard

        self._mica_switch = SwitchButton()
        self._mica_switch.setChecked(SettingsService.instance().get_mica_enabled())
        self._mica_switch.checkedChanged.connect(self._on_mica_changed)
        mica_card = SettingCard(
            FIF.PALETTE,
            "云母效果",
            "启用 Windows 11 云母背景效果（需要 Windows 11 系统）",
            self._mica_switch,
        )
        self.appearance_group.addSettingCard(mica_card)

        layout.addWidget(self.appearance_group)

        # ── 通知系统 ─────────────────────────────────────────────── #
        layout.addWidget(Win11Style.label_title("通知系统"))
        notif_card = CardWidget()
        notif_card.setAutoFillBackground(False)
        notif_form = QFormLayout(notif_card)
        notif_form.setContentsMargins(20, 16, 20, 16)
        notif_form.setSpacing(12)
        notif_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # 出现位置
        self._notif_pos_combo = ComboBox()
        for key in ALL_POSITIONS:
            self._notif_pos_combo.addItem(POSITION_LABELS[key], userData=key)
        self._notif_pos_combo.setCurrentIndex(5)  # 默认右下
        self._notif_pos_combo.currentIndexChanged.connect(self._on_notif_pos_changed)
        notif_form.addRow("出现位置：", self._notif_pos_combo)

        # 停留时间
        dur_row = QHBoxLayout()
        self._notif_dur_spin = SpinBox()
        self._notif_dur_spin.setRange(0, 60)
        self._notif_dur_spin.setValue(5)
        self._notif_dur_spin.setSuffix(" 秒")
        self._notif_dur_spin.setSpecialValueText("常驻")
        self._notif_dur_spin.valueChanged.connect(self._on_notif_dur_changed)
        dur_row.addWidget(self._notif_dur_spin)
        dur_hint = CaptionLabel("0 = 常驻（需手动关闭）")
        dur_row.addWidget(dur_hint, 1)
        notif_form.addRow("停留时间：", dur_row)

        # 测试按钮
        self._notif_test_btn = PushButton(FIF.RINGER, "发送测试通知")
        self._notif_test_btn.clicked.connect(self._on_notif_test)
        notif_form.addRow("", self._notif_test_btn)

        layout.addWidget(notif_card)

        # ── URL Scheme ─────────────────────────────────────────────── #
        layout.addWidget(Win11Style.label_title("URL Scheme 协议"))
        url_card = CardWidget()
        url_card.setAutoFillBackground(False)
        url_form = QFormLayout(url_card)
        url_form.setContentsMargins(20, 16, 20, 16)
        url_form.setSpacing(12)
        url_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # 协议名称提示
        url_form.addRow(
            "协议名称：",
            BodyLabel(f"{URL_SCHEME}://"),
        )

        # 注册状态 + 操作按钮
        url_status_row = QHBoxLayout()
        self._url_status_label = CaptionLabel(self._url_status_text())
        self._url_reg_btn = PushButton(FIF.LINK, "")
        self._url_reg_btn.setFixedWidth(110)
        self._url_reg_btn.clicked.connect(self._on_url_toggle)
        self._refresh_url_btn_text()
        url_status_row.addWidget(self._url_status_label, 1)
        url_status_row.addWidget(self._url_reg_btn)
        url_form.addRow("注册状态：", url_status_row)

        layout.addWidget(url_card)

        # ── .dw 文件关联 ────────────────────────────────────────── #
        layout.addWidget(Win11Style.label_title(".dw 插件文件关联"))
        dw_card = CardWidget()
        dw_card.setAutoFillBackground(False)
        dw_form = QFormLayout(dw_card)
        dw_form.setContentsMargins(20, 16, 20, 16)
        dw_form.setSpacing(12)
        dw_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        dw_form.addRow(
            "文件扩展名：",
            BodyLabel(".dw"),
        )

        # 注册状态 + 操作按钮
        dw_status_row = QHBoxLayout()
        self._dw_status_label = CaptionLabel(self._dw_status_text())
        self._dw_reg_btn = PushButton(FIF.LINK, "")
        self._dw_reg_btn.setFixedWidth(110)
        self._dw_reg_btn.clicked.connect(self._on_dw_toggle)
        self._refresh_dw_btn_text()
        dw_status_row.addWidget(self._dw_status_label, 1)
        dw_status_row.addWidget(self._dw_reg_btn)
        dw_form.addRow("注册状态：", dw_status_row)

        layout.addWidget(dw_card)

        # ── 开发者选项 ─────────────────────────────────────────────── #
        layout.addWidget(Win11Style.label_title("开发者选项"))
        dev_card = CardWidget()
        dev_card.setAutoFillBackground(False)
        dev_form = QFormLayout(dev_card)
        dev_form.setContentsMargins(20, 16, 20, 16)
        dev_form.setSpacing(12)
        dev_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        dev_row = QHBoxLayout()
        self._dev_switch = SwitchButton()
        self._dev_switch.setChecked(SettingsService.instance().developer_mode)
        self._dev_switch.checkedChanged.connect(self._on_dev_mode_changed)
        dev_row.addWidget(self._dev_switch)
        self._dev_status_label = CaptionLabel(
            "已启用 — 侧边栏将显示开发者页面"
            if self._dev_switch.isChecked()
            else "已隐藏 — 开发者页面不会显示在侧边栏"
        )
        dev_row.addWidget(self._dev_status_label, 1)
        dev_form.addRow("开发者模式：", dev_row)

        layout.addWidget(dev_card)

        # ── 开机自启（系统设置） ────────────────────────────────── #
        layout.addWidget(Win11Style.label_title("系统设置"))
        system_card = CardWidget()
        system_card.setAutoFillBackground(False)
        system_form = QFormLayout(system_card)
        system_form.setContentsMargins(20, 16, 20, 16)
        system_form.setSpacing(12)
        system_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # 开机自启开关
        autostart_row = QHBoxLayout()
        self._autostart_switch = SwitchButton()
        self._autostart_switch.setChecked(autostart.is_enabled())
        self._autostart_switch.checkedChanged.connect(self._on_autostart_changed)
        autostart_row.addWidget(self._autostart_switch)
        self._autostart_status = CaptionLabel(self._autostart_status_text())
        autostart_row.addWidget(self._autostart_status, 1)
        system_form.addRow("开机自启：", autostart_row)

        layout.addWidget(system_card)

        # ── 备份恢复 ─────────────────────────────────────────────── #
        layout.addWidget(Win11Style.label_title("备份与恢复"))
        backup_card = CardWidget()
        backup_card.setAutoFillBackground(False)
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(20, 16, 20, 16)
        backup_layout.setSpacing(12)

        desc = CaptionLabel("导出或导入小组件配置，方便在不同设备间同步")
        backup_layout.addWidget(desc)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        export_btn = PushButton(FIF.SAVE, "导出配置", parent=self)
        export_btn.clicked.connect(self._export_config)
        btn_layout.addWidget(export_btn)

        import_btn = PushButton(FIF.FOLDER_ADD, "导入配置", parent=self)
        import_btn.clicked.connect(self._import_config)
        btn_layout.addWidget(import_btn)

        btn_layout.addStretch()

        backup_layout.addLayout(btn_layout)
        layout.addWidget(backup_card)

        layout.addStretch()

        self.setWidget(container)
        self.setWidgetResizable(True)

    def _on_theme_changed(self) -> None:
        """主题变化时刷新 QFormLayout 标签颜色"""
        c = Win11Style.c()
        label_style = f"color: {c['text_primary']}; background: transparent;"
        hint_style = f"color: {c['text_secondary']}; background: transparent;"

        # 直接遍历所有 CaptionLabel 和 BodyLabel
        for lbl in self.findChildren(CaptionLabel):
            lbl.setStyleSheet(hint_style)
        for lbl in self.findChildren(BodyLabel):
            lbl.setStyleSheet(label_style)

    # ── 云母效果 ─────────────────────────────────────────────── #

    def _on_mica_changed(self, checked: bool) -> None:
        """云母效果开关变化"""
        SettingsService.instance().set_mica_enabled(checked)

        # 实时应用云母效果
        try:
            w = self.window()
            import platform

            version = platform.version()
            if int(version.split(".")[2]) >= 22000:  # Windows 11
                # 使用 getattr 动态调用避免类型检查错误
                set_mica = getattr(w, "setMicaEnabled", None)
                if set_mica:
                    set_mica(checked)
                if checked:
                    show_success("云母效果", "云母效果已启用")
                else:
                    show_success("云母效果", "云母效果已禁用")
            else:
                show_warning("不支持", "当前系统不支持云母效果（需要 Windows 11）")
                self._mica_switch.setChecked(False)
        except Exception as e:
            logger.error("切换云母效果失败: {}", e)
            show_error("错误", str(e))

    # ── 通知系统 ─────────────────────────────────────────────── #

    def _on_notif_pos_changed(self, _: int) -> None:
        key = self._notif_pos_combo.currentData()
        if key:
            self._sync_toast_manager()

    def _on_notif_dur_changed(self, seconds: int) -> None:
        self._sync_toast_manager()

    def _sync_toast_manager(self) -> None:
        """将当前设置同步到 ToastManager"""
        try:
            w = self.window()
            if hasattr(w, "_toast_mgr") and w._toast_mgr is not None:  # pyright: ignore[reportAttributeAccessIssue]
                key = self._notif_pos_combo.currentData()
                if key:
                    w._toast_mgr.set_position(key)  # pyright: ignore[reportAttributeAccessIssue]
                w._toast_mgr.set_duration(self._notif_dur_spin.value() * 1000)  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            pass

    def _on_notif_test(self) -> None:
        """发送测试通知"""
        try:
            w = self.window()
            if hasattr(w, "_toast_mgr") and w._toast_mgr is not None:  # pyright: ignore[reportAttributeAccessIssue]
                w._toast_mgr.show_toast("测试通知", "这是一条自定义 Toast 通知示例。")  # pyright: ignore[reportAttributeAccessIssue]
        except Exception as e:
            show_error("测试失败", str(e))

    # ── URL Scheme ─────────────────────────────────────────────── #

    def _url_status_text(self) -> str:
        if not uss.is_registered():
            return "未注册（无法通过 URL 唤起）"
        return f"已注册：{URL_SCHEME}://open/<视图>"

    def _refresh_url_btn_text(self) -> None:
        if uss.is_registered():
            self._url_reg_btn.setText("取消注册")
        else:
            self._url_reg_btn.setText("立即注册")

    def _on_url_toggle(self) -> None:
        if uss.is_registered():
            ok, msg = uss.unregister()
        else:
            ok, msg = uss.register()

        self._url_status_label.setText(self._url_status_text())
        self._refresh_url_btn_text()

        if ok:
            show_success("URL Scheme", msg)
        else:
            show_error("URL Scheme", msg)

    # ── .dw 文件关联 ─────────────────────────────────────────── #

    def _dw_status_text(self) -> str:
        if not uss.is_dw_association_registered():
            return "未注册（双击 .dw 文件无法自动打开）"
        return "已注册（双击 .dw 文件将自动打开导入）"

    def _refresh_dw_btn_text(self) -> None:
        if uss.is_dw_association_registered():
            self._dw_reg_btn.setText("取消关联")
        else:
            self._dw_reg_btn.setText("立即关联")

    def _on_dw_toggle(self) -> None:
        if uss.is_dw_association_registered():
            ok, msg = uss.unregister_dw_file_association()
        else:
            ok, msg = uss.register_dw_file_association()

        self._dw_status_label.setText(self._dw_status_text())
        self._refresh_dw_btn_text()

        if ok:
            show_success("文件关联", msg)
        else:
            show_error("文件关联", msg)

    # ── 开发者选项 ─────────────────────────────────────────────── #

    def _on_dev_mode_changed(self, checked: bool) -> None:
        """开发者模式开关变化"""
        SettingsService.instance().set_developer_mode(checked)

        self._dev_status_label.setText(
            "已启用 — 侧边栏将显示开发者页面"
            if checked
            else "已隐藏 — 开发者页面不会显示在侧边栏"
        )

        # 通知主窗口更新导航
        w = self.window()
        sync = getattr(w, "_sync_developer_nav", None)
        if sync:
            sync(checked)

    # ── 开机自启 ─────────────────────────────────────────────── #

    def _autostart_status_text(self) -> str:
        if autostart.is_enabled():
            return "已启用（开机时自动启动）"
        return "未启用"

    def _on_autostart_changed(self, checked: bool) -> None:
        """开机自启开关变化"""
        ok, msg = autostart.toggle(checked)

        # 更新状态显示
        self._autostart_status.setText(self._autostart_status_text())

        # 同步到设置服务
        SettingsService.instance().set_autostart(checked)

        if ok:
            show_success("开机自启", msg)
        else:
            # 恢复开关状态
            self._autostart_switch.setChecked(not checked)
            show_error("开机自启", msg)

    # ── 备份恢复 ─────────────────────────────────────────────── #

    def _export_config(self) -> None:
        """导出配置"""
        config = {
            "export_date": datetime.now().isoformat(),
            "version": "1.0.0",
            "widgets": [w.to_dict() for w in self._widget_model.get_all_widgets()],
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出配置",
            f"DashWidgets_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON 文件 (*.json)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                show_success("导出成功", f"配置已导出到 {Path(file_path).name}")
                logger.info(f"配置导出到: {file_path}")
            except Exception as e:
                show_error("导出失败", str(e))
                logger.error(f"导出配置失败: {e}")

    def _import_config(self) -> None:
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入配置",
            "",
            "JSON 文件 (*.json)",
        )

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                if "widgets" not in config:
                    raise ValueError("无效的配置文件")

                # 导入小组件配置
                for widget_data in config["widgets"]:
                    widget_id = widget_data.get("id")
                    if widget_id:
                        existing_widget = self._widget_model.get_widget(widget_id)
                        if existing_widget:
                            existing_widget.custom_settings = widget_data.get(
                                "custom_settings", {}
                            )
                            existing_widget.position = widget_data.get("position")
                            existing_widget.size_override = widget_data.get(
                                "size_override"
                            )
                        self._widget_model.save()

                show_success(
                    "导入成功", f"已导入 {len(config['widgets'])} 个小组件配置"
                )
                logger.info(f"配置从 {file_path} 导入")

                # 刷新桌面小组件
                from app.services.desktop_widget_service import DesktopWidgetManager

                widget_manager = DesktopWidgetManager.instance()
                widget_manager.hide_all()
                widget_manager.show_all_active_widgets()

            except Exception as e:
                show_error("导入失败", str(e))
                logger.error(f"导入配置失败: {e}")
