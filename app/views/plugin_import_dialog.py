"""
.dw 插件包导入对话框

双击 .dw 文件或通过插件页面导入时弹出，显示插件元数据并让用户确认导入。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QFileDialog, QWidget,
)
from qfluentwidgets import (
    PrimaryPushButton, PushButton, BodyLabel, CaptionLabel,
    TitleLabel, SubtitleLabel, CardWidget, FluentIcon as FIF,
    isDarkTheme, qconfig, InfoBar, InfoBarPosition, IconWidget,
)

from app.constants import ICON_PATH

# 权限显示名称映射
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


class PluginImportDialog(QDialog):
    """插件导入确认对话框"""

    def __init__(self, dw_path: str, meta: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self._dw_path = dw_path
        self._meta = meta
        self._accepted = False

        self.setWindowTitle("导入插件")
        self.setMinimumWidth(480)
        self.setModal(True)

        # 监听主题变化
        qconfig.themeChanged.connect(self._apply_theme)
        self._setup_ui()
        self._apply_theme()

    def _apply_theme(self, theme=None):
        """应用主题样式"""
        is_dark = isDarkTheme()
        if is_dark:
            bg = "#2D2D2D"
            text = "#E5E7EB"
            secondary = "#9CA3AF"
            card_bg = "#363636"
            border = "#3F3F3F"
            perm_bg = "#10B98115"
            perm_text = "#34D399"
        else:
            bg = "#FFFFFF"
            text = "#1F2937"
            secondary = "#6B7280"
            card_bg = "#F9FAFB"
            border = "#E5E7EB"
            perm_bg = "#10B98115"
            perm_text = "#059669"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        if hasattr(self, "_icon_label"):
            self._icon_label.setStyleSheet(f"background: {card_bg}; border: 1px solid {border};")
        if hasattr(self, "_name_label"):
            self._name_label.setStyleSheet(f"color: {text}; font-size: 22px; font-weight: bold;")
        if hasattr(self, "_version_label"):
            self._version_label.setStyleSheet(f"color: {secondary}; font-size: 13px;")
        if hasattr(self, "_desc_label"):
            self._desc_label.setStyleSheet(f"color: {secondary};")
        if hasattr(self, "_author_label"):
            self._author_label.setStyleSheet(f"color: {secondary};")
        if hasattr(self, "_section_label"):
            self._section_label.setStyleSheet(f"color: {text}; font-size: 13px; font-weight: bold;")
        if hasattr(self, "_no_perm_label"):
            self._no_perm_label.setStyleSheet(f"color: {secondary}; font-size: 12px;")
        if hasattr(self, "_perm_card"):
            self._perm_card.setStyleSheet(
                f"CardWidget {{ background-color: {card_bg}; border: 1px solid {border}; border-radius: 8px; }}"
            )
        if hasattr(self, "_warning_label"):
            self._warning_label.setStyleSheet(f"color: #F59E0B; font-size: 12px;")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        # 顶部：图标 + 名称 + 版本
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        # 图标
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(56, 56)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if ICON_PATH and ICON_PATH.exists():
            pixmap = QPixmap(str(ICON_PATH)).scaled(
                48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._icon_label.setPixmap(pixmap)
        else:
            icon_widget = IconWidget(FIF.ADD_TO)
            icon_widget.setFixedSize(48, 48)
            header_layout.removeWidget(self._icon_label)
            self._icon_label.deleteLater()
            header_layout.insertWidget(0, icon_widget)
            self._icon_label = icon_widget
        header_layout.addWidget(self._icon_label)

        # 名称 + 版本
        name_layout = QVBoxLayout()
        name_layout.setSpacing(2)

        plugin_name = self._meta.get("name", "未知插件")
        plugin_version = self._meta.get("version", "1.0.0")
        plugin_desc = self._meta.get("description", "")
        plugin_author = self._meta.get("author", "")

        self._name_label = SubtitleLabel(plugin_name)
        name_layout.addWidget(self._name_label)

        self._version_label = CaptionLabel(f"v{plugin_version}")
        name_layout.addWidget(self._version_label)

        if plugin_desc:
            desc_label = CaptionLabel(plugin_desc)
            desc_label.setWordWrap(True)
            name_layout.addWidget(desc_label)

        if plugin_author:
            author_label = CaptionLabel(f"作者：{plugin_author}")
            name_layout.addWidget(author_label)
            self._author_label = author_label

        header_layout.addLayout(name_layout, 1)
        layout.addLayout(header_layout)

        # 分割线
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("QFrame { color: #E5E7EB; }")
        layout.addWidget(line)

        # 需要的权限
        permissions = self._meta.get("permissions", [])
        self._section_label = BodyLabel("需要的权限")
        layout.addWidget(self._section_label)

        self._perm_card = CardWidget()
        perm_layout = QVBoxLayout(self._perm_card)
        perm_layout.setContentsMargins(16, 12, 16, 12)
        perm_layout.setSpacing(8)

        if permissions:
            for perm in permissions:
                perm_str = str(perm)
                display_name = PERMISSION_DISPLAY_NAMES.get(perm_str, perm_str)
                perm_label = CaptionLabel(f"  {display_name}")
                perm_label.setStyleSheet(f"color: #059669; font-size: 12px;")
                perm_layout.addWidget(perm_label)

            # 依赖
            deps = self._meta.get("dependencies", [])
            if deps:
                deps_label = CaptionLabel(f"  依赖：{', '.join(deps)}")
                deps_label.setStyleSheet(f"color: #6B7280; font-size: 12px;")
                perm_layout.addWidget(deps_label)
        else:
            self._no_perm_label = CaptionLabel("  此插件不需要特殊权限")
            perm_layout.addWidget(self._no_perm_label)

        layout.addWidget(self._perm_card)

        # 警告提示
        self._warning_label = CaptionLabel("请确认来源可靠后再导入，恶意插件可能危害系统安全。")
        self._warning_label.setWordWrap(True)
        layout.addWidget(self._warning_label)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        import_btn = PrimaryPushButton("导入")
        import_btn.clicked.connect(self._on_import)
        btn_layout.addWidget(import_btn)

        layout.addLayout(btn_layout)

    def _on_import(self):
        """确认导入"""
        from app.services.dw_package_service import install_dw

        success, message = install_dw(self._dw_path)
        if success:
            self._accepted = True
            self.accept()
        else:
            InfoBar.warning(
                title="导入失败",
                content=message,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=5000,
            )

    def was_accepted(self) -> bool:
        return self._accepted


def show_import_dialog(dw_path: str, parent: QWidget | None = None) -> bool:
    """
    显示导入对话框的便捷函数。

    Parameters
    ----------
    dw_path : str
        .dw 文件路径
    parent : QWidget | None
        父窗口

    Returns
    -------
    bool
        是否成功导入
    """
    from app.services.dw_package_service import read_dw_meta

    meta = read_dw_meta(dw_path)
    if meta is None:
        InfoBar.warning(
            title="无法导入",
            content="无法读取插件信息，请检查文件是否为有效的 .dw 插件包。",
            parent=parent,
            position=InfoBarPosition.TOP,
            duration=5000,
        )
        return False

    dialog = PluginImportDialog(dw_path, meta, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.was_accepted()
    return False
