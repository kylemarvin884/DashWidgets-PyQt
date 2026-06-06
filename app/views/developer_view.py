"""
开发者视图：开发者文档、插件开发指南、API 参考
"""
import webbrowser
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFrame, QWidget,
    QFormLayout, QTextBrowser,
)
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices

from qfluentwidgets import (
    ScrollArea, FluentIcon as FIF, PushButton, CardWidget,
    BodyLabel, TitleLabel, SubtitleLabel, StrongBodyLabel,
    PrimaryPushButton, HyperlinkButton, LineEdit,
    isDarkTheme, qconfig,
)

from app.constants import BASE_DIR, PLUGINS_DIR
from loguru import logger


class DeveloperView(ScrollArea):
    """开发者视图"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("developerView")
        self.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.viewport().setAutoFillBackground(False)

        self._build_ui()

    def _build_ui(self):
        container = QWidget()
        container.setAutoFillBackground(False)
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(16)

        # 标题
        layout.addWidget(TitleLabel("开发者"))
        layout.addSpacing(8)

        # ── 文档区域 ─────────────────────────────────────────────── #
        layout.addWidget(StrongBodyLabel("文档"))
        
        # 插件开发指南卡片
        doc_card = CardWidget()
        doc_card.setAutoFillBackground(False)
        doc_layout = QVBoxLayout(doc_card)
        doc_layout.setContentsMargins(20, 16, 20, 16)
        doc_layout.setSpacing(12)

        # 插件开发文档
        plugin_dev_row = QHBoxLayout()
        plugin_dev_row.addWidget(BodyLabel("插件开发文档"))
        plugin_dev_row.addStretch()
        plugin_dev_btn = PushButton("打开文档", self)
        plugin_dev_btn.setIcon(FIF.DOCUMENT)
        plugin_dev_btn.clicked.connect(lambda: self._open_doc("PLUGIN_DEVELOPMENT.md"))
        plugin_dev_row.addWidget(plugin_dev_btn)
        doc_layout.addLayout(plugin_dev_row)

        # 快速入门文档
        readme_row = QHBoxLayout()
        readme_row.addWidget(BodyLabel("自述文件"))
        readme_row.addStretch()
        readme_btn = PushButton("打开文档", self)
        readme_btn.setIcon(FIF.DOCUMENT)
        readme_btn.clicked.connect(lambda: self._open_doc("README.md"))
        readme_row.addWidget(readme_btn)
        doc_layout.addLayout(readme_row)

        layout.addWidget(doc_card)

        # ── 开发工具 ─────────────────────────────────────────────── #
        layout.addWidget(StrongBodyLabel("开发工具"))

        tools_card = CardWidget()
        tools_card.setAutoFillBackground(False)
        tools_layout = QVBoxLayout(tools_card)
        tools_layout.setContentsMargins(20, 16, 20, 16)
        tools_layout.setSpacing(12)

        # 打开插件目录
        plugin_dir_row = QHBoxLayout()
        plugin_dir_row.addWidget(BodyLabel("插件目录"))
        plugin_dir_row.addStretch()
        open_plugin_btn = PushButton("打开目录", self)
        open_plugin_btn.setIcon(FIF.FOLDER)
        open_plugin_btn.clicked.connect(self._open_plugin_dir)
        plugin_dir_row.addWidget(open_plugin_btn)
        tools_layout.addLayout(plugin_dir_row)

        # 创建示例插件
        example_row = QHBoxLayout()
        example_row.addWidget(BodyLabel("示例插件"))
        example_row.addStretch()
        example_btn = PrimaryPushButton("创建示例插件", self)
        example_btn.setIcon(FIF.ADD)
        example_btn.clicked.connect(self._create_example_plugin)
        example_row.addWidget(example_btn)
        tools_layout.addLayout(example_row)

        layout.addWidget(tools_card)

        # ── API 参考 ─────────────────────────────────────────────── #
        layout.addWidget(StrongBodyLabel("API 参考"))

        api_card = CardWidget()
        api_card.setAutoFillBackground(False)
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(20, 16, 20, 16)
        api_layout.setSpacing(12)

        # API 概览
        api_items = [
            ("PluginAPI", "插件与宿主交互的核心接口"),
            ("BasePlugin", "所有插件的基类"),
            ("HookType", "可订阅的钩子类型枚举"),
            ("PluginMeta", "插件元数据定义"),
            ("PluginPermission", "插件权限枚举"),
            ("LibraryPlugin", "依赖插件基类"),
        ]

        for api_name, api_desc in api_items:
            row = QHBoxLayout()
            code_label = BodyLabel(f"<code>{api_name}</code>")
            code_label.setStyleSheet("font-family: Consolas, monospace;")
            row.addWidget(code_label)
            row.addWidget(BodyLabel(api_desc))
            row.addStretch()
            api_layout.addLayout(row)

        layout.addWidget(api_card)

        # ── 链接 ─────────────────────────────────────────────── #
        layout.addWidget(StrongBodyLabel("相关链接"))

        links_card = CardWidget()
        links_card.setAutoFillBackground(False)
        links_layout = QVBoxLayout(links_card)
        links_layout.setContentsMargins(20, 16, 20, 16)
        links_layout.setSpacing(12)

        # GitHub 链接
        github_row = QHBoxLayout()
        github_row.addWidget(BodyLabel("GitHub"))
        github_row.addStretch()
        github_btn = HyperlinkButton("https://github.com", "访问")
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com")))
        github_row.addWidget(github_btn)
        links_layout.addLayout(github_row)

        layout.addWidget(links_card)

        # 底部留白
        layout.addStretch()

        self.setWidget(container)
        self.setWidgetResizable(True)

    def _open_doc(self, doc_name: str):
        """打开文档"""
        doc_path = BASE_DIR / doc_name
        if doc_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(doc_path)))
            logger.info("打开文档: {}", doc_path)
        else:
            logger.warning("文档不存在: {}", doc_path)

    def _open_plugin_dir(self):
        """打开插件目录"""
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(PLUGINS_DIR)))
        logger.info("打开插件目录: {}", PLUGINS_DIR)

    def _create_example_plugin(self):
        """创建示例插件"""
        example_dir = PLUGINS_DIR / "example_plugin"
        if example_dir.exists():
            logger.info("示例插件已存在: {}", example_dir)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(example_dir)))
            return

        # 创建示例插件目录
        example_dir.mkdir(parents=True, exist_ok=True)

        # 创建 __init__.py
        init_content = '''"""示例插件"""
from app.plugins import BasePlugin, PluginAPI, PluginMeta, HookType


class Plugin(BasePlugin):
    """示例插件 - 展示基本用法"""
    
    meta = PluginMeta(
        id="example_plugin",
        name="示例插件",
        version="1.0.0",
        author="开发者",
        description="这是一个示例插件，展示了插件的基本结构",
    )

    def __init__(self):
        self._api: PluginAPI | None = None

    def on_load(self, api: PluginAPI) -> None:
        """插件加载时调用"""
        self._api = api
        api.logger.info("示例插件已加载")
        
        # 注册钩子
        api.register_hook(HookType.ON_WIDGET_ADDED, self._on_widget_added)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        if self._api:
            self._api.logger.info("示例插件已卸载")

    def _on_widget_added(self, widget_id: str) -> None:
        """小组件添加回调"""
        if self._api:
            self._api.show_toast("示例插件", f"小组件已添加: {widget_id}")
'''
        (example_dir / "__init__.py").write_text(init_content, encoding="utf-8")

        # 创建 plugin.json
        plugin_json = '''{
    "id": "example_plugin",
    "name": "示例插件",
    "version": "1.0.0",
    "author": "开发者",
    "description": "这是一个示例插件",
    "plugin_type": "feature",
    "tags": ["example"]
}
'''
        (example_dir / "plugin.json").write_text(plugin_json, encoding="utf-8")

        # 创建 requirements.txt（空文件）
        (example_dir / "requirements.txt").write_text("", encoding="utf-8")

        logger.info("示例插件已创建: {}", example_dir)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(example_dir)))
