"""分组管理视图"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QScrollArea, QFrame, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from qfluentwidgets import (
    ScrollArea, CardWidget, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, SwitchButton,
    FluentIcon as FIF, LineEdit, ListWidget,
)
from loguru import logger

from app.services.settings_service import SettingsService
from app.models.widget_model import WidgetModel


class GroupsView(ScrollArea):
    """分组管理视图"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("groupsView")
        self.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.viewport().setAutoFillBackground(False)

        self._settings = SettingsService.instance()
        self._widget_model = WidgetModel()

        container = QWidget()
        container.setAutoFillBackground(False)
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(16)

        # 标题
        from app.services.desktop_widget_service import Win11Style
        c = Win11Style.c()
        title = QLabel("分组管理")
        title.setFont(Win11Style.display_font(28))
        title.setStyleSheet(f"color: {c['text_primary']}; background: transparent;")
        layout.addWidget(title)

        # 说明
        desc = CaptionLabel("创建和管理小组件分组，控制不同场景下显示的小组件")
        desc.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        layout.addWidget(desc)

        layout.addSpacing(10)

        # 分组列表卡片
        groups_card = CardWidget()
        groups_layout = QVBoxLayout(groups_card)
        groups_layout.setContentsMargins(16, 16, 16, 16)
        groups_layout.setSpacing(12)

        # 分组列表标题
        groups_header = QHBoxLayout()
        groups_title = BodyLabel("分组列表")
        groups_title.setStyleSheet("font-weight: bold;")
        groups_header.addWidget(groups_title)
        groups_header.addStretch()

        # 添加分组按钮
        add_btn = PushButton("+ 添加分组")
        add_btn.clicked.connect(self._add_group)
        groups_header.addWidget(add_btn)
        groups_layout.addLayout(groups_header)

        # 分组列表
        self._group_list = ListWidget()
        self._group_list.setFixedHeight(200)
        self._group_list.itemClicked.connect(self._on_group_clicked)
        groups_layout.addWidget(self._group_list)

        layout.addWidget(groups_card)

        # 分组设置卡片
        self._settings_card = CardWidget()
        self._settings_layout = QVBoxLayout(self._settings_card)
        self._settings_layout.setContentsMargins(16, 16, 16, 16)
        self._settings_layout.setSpacing(12)

        # 默认显示提示
        self._no_group_label = BodyLabel("请选择一个分组进行设置")
        self._no_group_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_group_label.setStyleSheet("color: #9CA3AF; padding: 20px;")
        self._settings_layout.addWidget(self._no_group_label)

        layout.addWidget(self._settings_card)

        # 添加弹性空间
        layout.addStretch()

        self.setWidget(container)
        self._load_groups()

    def _load_groups(self):
        """加载分组列表"""
        self._group_list.clear()
        groups = self._settings.widget_groups

        for group in groups:
            item = QListWidgetItem(group)
            self._group_list.addItem(item)

    def _on_group_clicked(self, item):
        """点击分组项"""
        group_name = item.text()
        self._show_group_settings(group_name)

    def _show_group_settings(self, group_name: str):
        """显示分组设置"""
        # 清除现有设置
        while self._settings_layout.count():
            item = self._settings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 分组名称
        name_layout = QHBoxLayout()
        name_label = BodyLabel(f"分组: {group_name}")
        name_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        name_layout.addWidget(name_label)
        name_layout.addStretch()

        # 删除分组按钮
        delete_btn = PushButton("删除分组")
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['danger']};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {c['accent_hover']};
            }}
        """)
        delete_btn.clicked.connect(lambda: self._delete_group(group_name))
        name_layout.addWidget(delete_btn)

        self._settings_layout.addLayout(name_layout)

        # 分组可见性开关
        visibility_layout = QHBoxLayout()
        visibility_label = BodyLabel("显示此分组的小组件")
        visibility_layout.addWidget(visibility_label)
        visibility_layout.addStretch()

        visibility_switch = SwitchButton()
        visibility_switch.setChecked(self._settings.group_visibility.get(group_name, True))
        visibility_switch.checkedChanged.connect(
            lambda checked: self._update_group_visibility(group_name, checked)
        )
        visibility_layout.addWidget(visibility_switch)
        self._settings_layout.addLayout(visibility_layout)

        # 说明文字
        info_label = CaptionLabel("开启后，在小组件页面可以按分组筛选显示")
        info_label.setStyleSheet("color: #9CA3AF;")
        self._settings_layout.addWidget(info_label)

    def _update_group_visibility(self, group_name: str, visible: bool):
        """更新分组可见性"""
        visibility = self._settings.group_visibility
        visibility[group_name] = visible
        self._settings.set_group_visibility(visibility)
        logger.info(f"分组 {group_name} 可见性: {visible}")

    def _add_group(self):
        """添加分组"""
        text, ok = QInputDialog.getText(
            self, "添加分组", "请输入分组名称:"
        )

        if ok and text.strip():
            groups = self._settings.widget_groups
            if text.strip() in groups:
                QMessageBox.warning(self, "警告", "分组名称已存在")
                return

            groups.append(text.strip())
            self._settings.set_widget_groups(groups)

            # 初始化可见性
            visibility = self._settings.group_visibility
            visibility[text.strip()] = True
            self._settings.set_group_visibility(visibility)

            self._load_groups()
            logger.info(f"添加分组: {text.strip()}")

    def _delete_group(self, group_name: str):
        """删除分组"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除分组「{group_name}」吗？\n此分组下的小组件将移至默认分组。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            groups = self._settings.widget_groups
            if group_name in groups:
                groups.remove(group_name)
                self._settings.set_widget_groups(groups)

                # 清除该分组的可见性设置
                visibility = self._settings.group_visibility
                visibility.pop(group_name, None)
                self._settings.set_group_visibility(visibility)

                self._load_groups()

                # 显示提示
                while self._settings_layout.count():
                    item = self._settings_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                self._settings_layout.addWidget(self._no_group_label)

                logger.info(f"删除分组: {group_name}")
