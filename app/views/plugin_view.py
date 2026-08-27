"""插件管理视图"""
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QDialog,
    QLabel, QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from qfluentwidgets import (
    ScrollArea, CardWidget, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, SwitchButton,
    FluentIcon as FIF, isDarkTheme, qconfig,
    SubtitleLabel, SearchLineEdit, ComboBox, PillPushButton,
    IconWidget,
)
from app.views.toast_notification import show_success

# 权限显示相关配置
PERMISSION_DISPLAY_NAMES = {
    "network": "网络访问",
    "fs_read": "读取文件",
    "fs_write": "写入文件",
    "os_exec": "执行命令",
    "os_env": "环境变量",
    "clipboard": "剪贴板",
    "install_pkg": "安装包",
    "notification": "通知",
}

PERMISSION_ICONS = {
    "network": FIF.GLOBE,
    "fs_read": FIF.DOCUMENT,
    "fs_write": FIF.EDIT,
    "os_exec": FIF.COMMAND_PROMPT,
    "os_env": FIF.SETTING,
    "clipboard": FIF.COPY,
    "install_pkg": FIF.ADD_TO,
    "notification": FIF.RINGER,
}


class PermissionDialog(QDialog):
    """权限授权确认对话框"""

    def __init__(self, plugin_name: str, permissions: list, parent: QWidget | None = None):
        super().__init__(parent)
        self.setModal(True)
        self._permissions = permissions
        self._plugin_name = plugin_name
        self._accepted = False
        self._always_allow = False
        self._setup_ui()

    def _setup_ui(self):
        from qfluentwidgets import isDarkTheme

        self.setFixedSize(420, 320)
        self.setWindowTitle("插件权限请求")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # 根据主题设置颜色
        is_dark = isDarkTheme()
        if is_dark:
            bg_color = "#1F1F1F"
            text_color = "#E5E7EB"
            border_color = "#3F3F3F"
            input_bg = "#2D2D2D"
            btn_hover = "#3D3D3D"
        else:
            bg_color = "#FFFFFF"
            text_color = "#1F2937"
            border_color = "#E5E7EB"
            input_bg = "#F9FAFB"
            btn_hover = "#E5E7EB"

        # 设置窗口背景
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # 标题
        title = QLabel(f"插件「{self._plugin_name}」请求以下权限：")
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {text_color};")
        main_layout.addWidget(title)

        # 权限列表
        perm_container = QScrollArea()
        perm_container.setWidgetResizable(True)
        perm_container.setFixedHeight(140)
        perm_container.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {border_color};
                border-radius: 8px;
                background: {input_bg};
            }}
        """)

        perm_widget = QWidget()
        perm_layout = QVBoxLayout(perm_widget)
        perm_layout.setContentsMargins(10, 10, 10, 10)
        perm_layout.setSpacing(8)

        for perm in self._permissions:
            perm_value = perm.value if hasattr(perm, 'value') else str(perm)
            perm_name = PERMISSION_DISPLAY_NAMES.get(perm_value, perm_value)

            perm_item = QFrame()
            perm_item.setStyleSheet(f"""
                QFrame {{
                    background: {bg_color};
                    border-radius: 6px;
                    padding: 8px;
                }}
            """)
            perm_item_layout = QHBoxLayout(perm_item)
            perm_item_layout.setContentsMargins(10, 8, 10, 8)

            icon_w = IconWidget(PERMISSION_ICONS.get(perm_value, FIF.LOCK))
            icon_w.setFixedSize(18, 18)
            perm_item_layout.addWidget(icon_w)
            
            name_label = QLabel(perm_name)
            name_label.setStyleSheet(f"font-size: 13px; color: {text_color};")
            perm_item_layout.addWidget(name_label, 1)

            perm_layout.addWidget(perm_item)

        perm_container.setWidget(perm_widget)
        main_layout.addWidget(perm_container)

        # 始终允许复选框
        self.always_allow_check = QPushButton("始终允许此插件的权限请求")
        self.always_allow_check.setCheckable(True)
        self.always_allow_check.setChecked(False)
        self.always_allow_check.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                text-align: left;
                padding: 8px;
                font-size: 12px;
                color: {text_color};
            }}
            QPushButton:checked {{
                color: #10B981;
            }}
        """)
        self.always_allow_check.clicked.connect(lambda checked: self.always_allow_check.setText(
            "始终允许此插件的权限请求" if not checked else "已选择始终允许"
        ))
        main_layout.addWidget(self.always_allow_check)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        deny_btn = QPushButton("拒绝")
        deny_btn.setFixedHeight(36)
        deny_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_hover};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                color: {text_color};
            }}
            QPushButton:hover {{ background: {border_color}; }}
        """)
        deny_btn.clicked.connect(self._on_deny)

        accept_btn = QPushButton("允许")
        accept_btn.setFixedHeight(36)
        accept_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background: #2563EB; }
        """)
        accept_btn.clicked.connect(self._on_accept)

        btn_layout.addWidget(deny_btn)
        btn_layout.addWidget(accept_btn)
        main_layout.addLayout(btn_layout)

    def _on_accept(self):
        self._accepted = True
        self._always_allow = self.always_allow_check.isChecked()
        self.close()

    def _on_deny(self):
        self._accepted = False
        self._always_allow = False
        self.close()

    def get_result(self) -> tuple[bool, bool]:
        """返回 (是否接受, 是否始终允许)"""
        return self._accepted, self._always_allow


# 插件视图颜色主题
class PluginViewColors:
    """插件视图颜色"""

    @staticmethod
    def get_text_secondary() -> str:
        return "#9CA3AF" if isDarkTheme() else "#6B7280"

    @staticmethod
    def get_text_tertiary() -> str:
        return "#6B7280" if isDarkTheme() else "#9CA3AF"

    @staticmethod
    def get_accent() -> str:
        return "#0078D4"

    @staticmethod
    def get_text_disabled() -> str:
        return "#6B7280" if isDarkTheme() else "#9CA3AF"


if TYPE_CHECKING:
    from app.plugins.plugin_manager import PluginManager, PluginEntry


class PluginCard(CardWidget):
    """插件卡片"""

    uninstallRequested = Signal(str)  # plugin_id

    def __init__(self, entry: "PluginEntry", manager: "PluginManager", parent: QWidget | None = None):
        super().__init__(parent)
        self.entry = entry
        self.manager = manager
        self.setAutoFillBackground(False)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # 左侧：图标区域（使用插件类型颜色）
        icon_frame = QFrame()
        icon_frame.setFixedSize(48, 48)
        
        # 根据插件类型设置颜色
        if self.entry.meta.plugin_type.value == "library":
            bg_color = "#8764B8"  # 紫色表示依赖插件
        else:
            bg_color = "#0078D4"  # 蓝色表示功能插件
            
        icon_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
            QLabel {{
                color: white;
                font-size: 20px;
                font-weight: bold;
            }}
        """)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(self.entry.meta.name[0] if self.entry.meta.name else "P")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_frame)

        # 中间：信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # 名称和版本
        name_layout = QHBoxLayout()
        name_label = BodyLabel(self.entry.meta.name)
        name_label.setStyleSheet("font-weight: bold;")
        name_layout.addWidget(name_label)

        version_label = CaptionLabel(f"v{self.entry.meta.version}")
        version_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()};")
        name_layout.addWidget(version_label)
        
        # 插件类型标签
        type_text = "库" if self.entry.meta.plugin_type.value == "library" else "功能"
        type_label = CaptionLabel(f"({type_text})")
        type_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()}; font-style: italic;")
        name_layout.addWidget(type_label)
        
        name_layout.addStretch()
        info_layout.addLayout(name_layout)

        # 描述
        desc = self.entry.meta.description or "暂无描述"
        desc_label = CaptionLabel(desc)
        desc_label.setStyleSheet(f"color: {PluginViewColors.get_text_secondary()};")
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)

        # 作者和标签
        meta_layout = QHBoxLayout()
        if self.entry.meta.author:
            author_label = CaptionLabel(f"作者: {self.entry.meta.author}")
            author_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()};")
            meta_layout.addWidget(author_label)
        if self.entry.meta.tags:
            for tag in self.entry.meta.tags:
                tag_btn = PillPushButton(tag)
                tag_btn.setFixedHeight(20)
                tag_btn.setStyleSheet(f"""
                    PillPushButton {{
                        background-color: {PluginViewColors.get_accent()}20;
                        color: {PluginViewColors.get_accent()};
                        border: none;
                        padding: 2px 8px;
                        font-size: 11px;
                    }}
                """)
                meta_layout.addWidget(tag_btn)
        meta_layout.addStretch()
        info_layout.addLayout(meta_layout)

        # 依赖信息
        if self.entry.meta.requires:
            deps_text = "依赖: " + ", ".join(self.entry.meta.requires)
            deps_label = CaptionLabel(deps_text)
            deps_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()}; font-size: 11px;")
            info_layout.addWidget(deps_label)

        # 权限信息
        permissions = self.entry.meta.permissions or []
        if permissions:
            perm_layout = QHBoxLayout()
            perm_layout.setSpacing(6)
            perm_label = CaptionLabel("权限:")
            perm_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()}; font-size: 11px;")
            perm_layout.addWidget(perm_label)
            
            for perm in permissions:
                # 获取权限值
                perm_value = perm.value if hasattr(perm, 'value') else str(perm)
                perm_display = PERMISSION_DISPLAY_NAMES.get(perm_value, perm_value)

                perm_btn = PillPushButton(perm_display)
                perm_btn.setFixedHeight(20)
                perm_btn.setStyleSheet(f"""
                    PillPushButton {{
                        background-color: #10B98120;
                        color: #10B981;
                        border: none;
                        padding: 2px 8px;
                        font-size: 11px;
                    }}
                """)
                perm_layout.addWidget(perm_btn)
            perm_layout.addStretch()
            info_layout.addLayout(perm_layout)

        # 错误信息
        if self.entry.error:
            error_label = CaptionLabel(f"错误: {self.entry.error}")
            error_label.setStyleSheet("color: #D13438;")
            info_layout.addWidget(error_label)

        layout.addLayout(info_layout, 1)

        # 右侧：按钮区域
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.switch = SwitchButton()
        self.switch.setChecked(self.entry.enabled)
        self.switch.checkedChanged.connect(self._on_switch_changed)
        btn_layout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignHCenter)

        export_btn = PushButton(FIF.SHARE, "导出")
        export_btn.setFixedHeight(28)
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        uninstall_btn = PushButton(FIF.DELETE, "卸载")
        uninstall_btn.setFixedHeight(28)
        uninstall_btn.clicked.connect(self._on_uninstall)
        btn_layout.addWidget(uninstall_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addLayout(btn_layout)

    def _on_switch_changed(self, checked: bool):
        self.manager.set_enabled(self.entry.meta.id, checked)
        status = "已启用" if checked else "已禁用"
        show_success("插件状态", f"{self.entry.meta.name} {status}")

        # 刷新整个软件（插件导航和小组件）
        window = self.window()
        if hasattr(window, '_refresh_plugin_navigations'):
            window._refresh_plugin_navigations()
        # 刷新小组件列表
        if hasattr(window, 'widgets_view'):
            window.widgets_view._load_widgets()
        # 刷新首页
        if hasattr(window, 'home_view'):
            window.home_view.refresh()

    def _on_export(self):
        """导出插件为 .dw 文件"""
        from PySide6.QtWidgets import QFileDialog
        from app.services.dw_package_service import create_dw

        # 获取插件目录
        plugin_dir = self.entry.api._data_dir
        if plugin_dir is None:
            show_success("导出失败", "无法获取插件目录")
            return

        # 检查是否为包插件（包含 plugin.json 和 __init__.py）
        if not (plugin_dir / "plugin.json").exists():
            show_success("导出失败", "该插件不是包插件，无法导出")
            return

        # 弹出保存对话框
        default_name = f"{self.entry.meta.id}.dw"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出插件",
            default_name,
            "DashWidgets 插件 (*.dw);;所有文件 (*)",
        )
        if not save_path:
            return

        # 确保扩展名为 .dw
        if not save_path.lower().endswith(".dw"):
            save_path += ".dw"

        success, msg = create_dw(plugin_dir, save_path)
        if success:
            show_success("导出成功", msg)
        else:
            show_success("导出失败", msg)

    def _on_uninstall(self):
        """卸载插件（弹出确认对话框）"""
        from app.views.toast_notification import show_error

        # 检查是否有插件依赖此插件
        if self.entry.dependents:
            names = []
            for dep_id in self.entry.dependents:
                dep_entry = self.manager.get_entry(dep_id)
                if dep_entry:
                    names.append(dep_entry.meta.name)
            if names:
                dep_list = "\n".join(f"  - {n}" for n in names)
                show_error(
                    "无法卸载",
                    f"以下插件依赖「{self.entry.meta.name}」，请先卸载它们：\n{dep_list}",
                )
                return

        # 弹出确认对话框
        dialog = _UninstallConfirmDialog(self.entry.meta.name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            success, msg = self.manager.uninstall(self.entry.meta.id)
            if success:
                from app.views.toast_notification import show_success as _ok
                _ok("卸载成功", msg)
                self.uninstallRequested.emit(self.entry.meta.id)
            else:
                show_error("卸载失败", msg)


class _UninstallConfirmDialog(QDialog):
    """卸载确认对话框"""

    def __init__(self, plugin_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setModal(True)
        self.setFixedSize(380, 180)
        self.setWindowTitle("确认卸载")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        is_dark = isDarkTheme()
        if is_dark:
            bg_color = "#1F1F1F"
            text_color = "#E5E7EB"
            border_color = "#3F3F3F"
        else:
            bg_color = "#FFFFFF"
            text_color = "#1F2937"
            border_color = "#E5E7EB"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg_color}; }}
            QLabel {{ color: {text_color}; background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        msg = QLabel(f"确定要卸载插件「{plugin_name}」吗？\n此操作不可撤销，插件文件将被永久删除。")
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 13px;")
        layout.addWidget(msg)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = PushButton("取消")
        cancel_btn.setFixedHeight(32)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = PushButton(FIF.DELETE, "确认卸载")
        confirm_btn.setFixedHeight(32)
        confirm_btn.setStyleSheet("""
            PushButton {
                background-color: #D13438;
                color: white;
                border: none;
                border-radius: 4px;
            }
            PushButton:hover { background-color: #A4262C; }
        """)
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)


class PluginView(ScrollArea):
    """插件管理视图"""
    
    # 筛选条件变化信号
    filterChanged = Signal()

    def __init__(self, manager: "PluginManager", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("pluginView")
        self.manager = manager
        self._current_filter = ""
        self._current_type = "all"
        self._current_tag = "all"
        self._setup_ui()
        self._load_plugins()

        # 主题变化时刷新
        qconfig.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme):
        """主题变化时刷新界面"""
        self._load_plugins()

    def _setup_ui(self):
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.viewport().setAutoFillBackground(False)

        # 主容器
        self.container = QWidget()
        self.container.setAutoFillBackground(False)
        self.container.setStyleSheet("background: transparent; ")
        self.setWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题区域
        header_layout = QHBoxLayout()

        title = SubtitleLabel("插件管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 刷新按钮
        refresh_btn = PushButton(FIF.SYNC, "刷新")
        refresh_btn.clicked.connect(self._load_plugins)
        header_layout.addWidget(refresh_btn)

        # 从文件夹打包按钮
        pack_btn = PushButton(FIF.FOLDER_ADD, "从文件夹打包")
        pack_btn.clicked.connect(self._package_from_folder)
        header_layout.addWidget(pack_btn)

        # 导入按钮
        import_btn = PrimaryPushButton(FIF.ADD, "导入插件")
        import_btn.clicked.connect(self._import_plugin)
        header_layout.addWidget(import_btn)

        layout.addLayout(header_layout)

        # 筛选栏
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        # 搜索框
        self.search_edit = SearchLineEdit()
        self.search_edit.setPlaceholderText("搜索插件...")
        self.search_edit.setFixedWidth(200)
        self.search_edit.searchSignal.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_edit)

        # 类型筛选
        type_label = CaptionLabel("类型:")
        type_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()};")
        filter_layout.addWidget(type_label)
        
        self.type_combo = ComboBox()
        self.type_combo.addItems(["全部", "功能插件", "依赖插件"])
        self.type_combo.setCurrentIndex(0)
        self.type_combo.setFixedWidth(120)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        filter_layout.addWidget(self.type_combo)

        # 标签筛选
        tag_label = CaptionLabel("标签:")
        tag_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()};")
        filter_layout.addWidget(tag_label)
        
        self.tag_combo = ComboBox()
        self.tag_combo.addItem("全部")
        self.tag_combo.setFixedWidth(120)
        self.tag_combo.currentTextChanged.connect(self._on_tag_changed)
        filter_layout.addWidget(self.tag_combo)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 统计信息
        self.stats_label = CaptionLabel("")
        self.stats_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()};")
        layout.addWidget(self.stats_label)

        # 插件列表容器
        self.plugin_container = QWidget()
        self.plugin_container.setAutoFillBackground(False)
        self.plugin_container.setStyleSheet("background: transparent; ")
        self.plugin_layout = QVBoxLayout(self.plugin_container)
        self.plugin_layout.setContentsMargins(0, 0, 0, 0)
        self.plugin_layout.setSpacing(8)
        layout.addWidget(self.plugin_container)

        layout.addStretch()

        # 提示信息
        hint_label = CaptionLabel(
            "点击「导入插件」按钮安装 .dw 插件包。\n"
            "也可以将插件目录放入 plugins_ext 目录后点击刷新加载。"
        )
        hint_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()};")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

    def _on_search_changed(self, text: str):
        """搜索文本变化"""
        self._current_filter = text.lower()
        self._load_plugins()

    def _on_type_changed(self, text: str):
        """类型筛选变化"""
        if text == "全部":
            self._current_type = "all"
        elif text == "功能插件":
            self._current_type = "feature"
        elif text == "依赖插件":
            self._current_type = "library"
        self._load_plugins()

    def _on_tag_changed(self, text: str):
        """标签筛选变化"""
        if text == "全部":
            self._current_tag = "all"
        else:
            self._current_tag = text
        self._load_plugins()

    def _update_tag_filter(self, entries: list["PluginEntry"]):
        """更新标签筛选器选项"""
        all_tags = set()
        for entry in entries:
            all_tags.update(entry.meta.tags)
        
        current_text = self.tag_combo.currentText()
        
        # 阻止信号以避免递归
        self.tag_combo.blockSignals(True)
        self.tag_combo.clear()
        self.tag_combo.addItem("全部")
        for tag in sorted(all_tags):
            self.tag_combo.addItem(tag)
        
        # 尝试恢复之前的选中项
        if current_text in ["全部"] + list(all_tags):
            index = self.tag_combo.findText(current_text)
            if index >= 0:
                self.tag_combo.setCurrentIndex(index)
            else:
                self.tag_combo.setCurrentIndex(0)
        else:
            self.tag_combo.setCurrentIndex(0)
        
        self.tag_combo.blockSignals(False)

    def _filter_entry(self, entry: "PluginEntry") -> bool:
        """判断插件是否满足当前筛选条件"""
        # 搜索筛选
        if self._current_filter:
            search_text = self._current_filter
            if (search_text not in entry.meta.name.lower() and
                search_text not in entry.meta.description.lower() and
                search_text not in entry.meta.id.lower() and
                not any(search_text in tag.lower() for tag in entry.meta.tags)):
                return False
        
        # 类型筛选
        if self._current_type != "all":
            if entry.meta.plugin_type.value != self._current_type:
                return False
        
        # 标签筛选
        if self._current_tag != "all":
            if self._current_tag not in entry.meta.tags:
                return False
        
        return True

    def _load_plugins(self):
        # 清空现有卡片
        while self.plugin_layout.count():
            item = self.plugin_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 获取所有插件条目
        entries = self.manager.all_entries()
        
        # 更新标签筛选器
        self._update_tag_filter(entries)
        
        # 应用筛选
        filtered_entries = [entry for entry in entries if self._filter_entry(entry)]
        
        # 更新统计信息
        total = len(entries)
        filtered = len(filtered_entries)
        feature_count = sum(1 for e in entries if e.meta.plugin_type.value == "feature")
        library_count = sum(1 for e in entries if e.meta.plugin_type.value == "library")
        
        stats_text = f"共 {total} 个插件 ({feature_count} 个功能插件, {library_count} 个依赖插件)"
        if filtered != total:
            stats_text += f"，筛选后显示 {filtered} 个"
        self.stats_label.setText(stats_text)

        # 加载插件卡片
        if not filtered_entries:
            empty_label = BodyLabel("暂无插件" if not entries else "没有匹配的插件")
            empty_label.setStyleSheet(f"color: {PluginViewColors.get_text_tertiary()};")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.plugin_layout.addWidget(empty_label)
        else:
            for entry in filtered_entries:
                card = PluginCard(entry, self.manager, self)
                card.uninstallRequested.connect(self._on_plugin_uninstalled)
                self.plugin_layout.addWidget(card)

    def _on_plugin_uninstalled(self, plugin_id: str):
        """插件卸载后的回调"""
        self._load_plugins()
        # 通知主窗口刷新导航和小组件
        window = self.window()
        if hasattr(window, '_refresh_plugin_navigations'):
            window._refresh_plugin_navigations()
        if hasattr(window, 'widgets_view'):
            window.widgets_view._load_widgets()
        if hasattr(window, 'home_view'):
            window.home_view.refresh()

    def _import_plugin(self):
        """导入 .dw 插件包"""
        from PySide6.QtWidgets import QFileDialog
        from app.views.plugin_import_dialog import show_import_dialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择插件包",
            "",
            "DashWidgets 插件 (*.dw);;所有文件 (*)",
        )
        if not path:
            return

        if show_import_dialog(path, parent=self):
            from app.services.dw_package_service import read_dw_meta
            meta = read_dw_meta(path) or {}
            plugin_id = meta.get("id", "")

            # 若是覆盖升级已加载的插件，热重载使其立即生效
            reloaded_msg = ""
            if plugin_id and self.manager.get_entry(plugin_id):
                ok, msg = self.manager.reload_plugin(plugin_id)
                reloaded_msg = msg if ok else f"热重载失败：{msg}"

            self.manager.discover_and_load()
            self._load_plugins()
            # 通知主窗口刷新导航
            window = self.window()
            if hasattr(window, '_refresh_plugin_navigations'):
                window._refresh_plugin_navigations()
            from app.views.toast_notification import show_success
            show_success("导入成功", reloaded_msg or "插件已安装并加载")

    def _package_from_folder(self):
        """从文件夹选择插件目录并打包为 .dw 文件"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.services.dw_package_service import create_dw

        folder = QFileDialog.getExistingDirectory(
            self,
            "选择插件文件夹",
            "",
        )
        if not folder:
            return

        plugin_dir = Path(folder)

        # 验证必要文件
        missing = []
        if not (plugin_dir / "plugin.json").exists():
            missing.append("plugin.json")
        if not (plugin_dir / "__init__.py").exists():
            missing.append("__init__.py")

        if missing:
            from app.views.toast_notification import show_error
            show_error(
                "打包失败",
                f"所选目录缺少必要文件：{', '.join(missing)}\n请选择有效的插件目录。",
            )
            return

        # 读取 plugin.json 获取插件名称
        try:
            import json
            with open(plugin_dir / "plugin.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
            plugin_id = meta.get("id", plugin_dir.name)
            plugin_name = meta.get("name", plugin_id)
        except Exception:
            plugin_id = plugin_dir.name
            plugin_name = plugin_id

        # 弹出保存对话框
        default_name = f"{plugin_id}.dw"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存插件包",
            default_name,
            "DashWidgets 插件 (*.dw);;所有文件 (*)",
        )
        if not save_path:
            return

        if not save_path.lower().endswith(".dw"):
            save_path += ".dw"

        success, msg = create_dw(plugin_dir, save_path)
        if success:
            show_success("打包成功", f"插件「{plugin_name}」已导出为 {Path(save_path).name}")
        else:
            from app.views.toast_notification import show_error
            show_error("打包失败", msg)
