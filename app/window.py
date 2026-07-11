"""
主窗口：FluentWindow 骨架，负责导航和系统托盘
"""

from qfluentwidgets import (
    FluentWindow,
    FluentIcon as FIF,
    SplashScreen,
    NavigationItemPosition,
    qconfig,
    Theme,
    setTheme,
)
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtCore import Qt, QSize, QTimer, QPoint
from typing import TYPE_CHECKING
import sys

from app.constants import (
    APP_NAME,
    LONG_VER,
    ICON_PATH,
    MANAGER_WIDTH,
    MANAGER_HEIGHT,
    PLUGINS_DIR,
)
from app.services.settings_service import SettingsService
from app.views.toast_notification import show_success, show_warning, show_info
from app.views.plugin_view import PERMISSION_DISPLAY_NAMES
from loguru import logger

if TYPE_CHECKING:
    from app.services.settings_service import SettingsService
    from app.services.desktop_widget_service import DesktopWidgetManager
    from app.views.widgets_view import WidgetsView
    from app.views.home_view import HomeView
    from app.views.settings_view import SettingsView
    from app.views.plugin_view import PluginView
    from app.views.developer_view import DeveloperView
    from app.plugins.plugin_manager import PluginManager
    from app.views.toast_notification import ToastManager


class MainWindow(FluentWindow):
    """应用主窗口"""

    _settings: "SettingsService"
    _widget_manager: "DesktopWidgetManager"
    _plugin_mgr: "PluginManager"
    _toast_mgr: "ToastManager"
    home_view: "HomeView"
    widgets_view: "WidgetsView"
    groups_view: None
    settings_view: "SettingsView"
    plugin_view: "PluginView"
    developer_view: "DeveloperView"
    splash: SplashScreen
    _tray: QSystemTrayIcon
    _toggle_widgets_action: "PySide6.QtWidgets.QAction"
    _url_view_map: dict[str, object]
    _plugin_nav_widgets: dict[str, QWidget]  # 跟踪插件导航项

    def __init__(self):
        super().__init__()

        # 确保插件目录存在
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # 基础服务（无 UI 依赖，先初始化）
        # ------------------------------------------------------------------
        from app.services.settings_service import SettingsService

        self._settings = SettingsService.instance()

        # 初始化桌面小组件管理器
        from app.services.desktop_widget_service import DesktopWidgetManager

        self._widget_manager = DesktopWidgetManager.instance()
        # 显示所有激活的桌面小组件
        self._widget_manager.show_all_active_widgets()

        # 初始化 Toast 通知管理器
        from app.views.toast_notification import ToastManager, POS_BOTTOM_RIGHT

        self._toast_mgr = ToastManager(self)
        self._toast_mgr.set_position(POS_BOTTOM_RIGHT)
        self._toast_mgr.set_duration(5000)

        # 初始化插件管理器
        from app.plugins.plugin_manager import PluginManager

        self._plugin_mgr = PluginManager(
            services={
                "settings_service": self._settings,
                "widget_manager": self._widget_manager,
            },
            toast_callback=self._show_toast,
            permission_check_callback=self._check_plugin_permission,
            main_window=self,
        )

        # ------------------------------------------------------------------
        # 视图（延后导入避免循环依赖）
        # ------------------------------------------------------------------
        from app.views.widgets_view import WidgetsView
        from app.views.home_view import HomeView
        from app.views.settings_view import SettingsView
        from app.views.plugin_view import PluginView
        from app.views.developer_view import DeveloperView
        from app.views.groups_view import GroupsView

        self.home_view = HomeView()
        self.widgets_view = WidgetsView()
        self.groups_view = GroupsView()
        self.settings_view = SettingsView()
        self.plugin_view = PluginView(self._plugin_mgr)
        self.developer_view = DeveloperView()

        # ------------------------------------------------------------------
        # 调试窗口
        # ------------------------------------------------------------------
        from app.views.debug_view import DebugWindow

        self._debug_window = DebugWindow(self)
        self._debug_window.hide()

        # ------------------------------------------------------------------
        # 窗口初始化
        # ------------------------------------------------------------------
        self._init_window()
        self._init_splash()
        self._init_navigation()
        self._init_tray()

        # 视图映射：objectName → widget（供 URL 导航使用）
        self._url_view_map: dict[str, object] = {
            "homeView": self.home_view,
            "widgetsView": self.widgets_view,
            "groupsView": self.groups_view,
            "settingsView": self.settings_view,
            "pluginView": self.plugin_view,
        }

        # 加载插件并刷新导航和小组件列表
        self._plugin_mgr.discover_and_load()
        # 检查并显示权限请求通知
        self._check_plugin_permissions()
        self._refresh_plugin_navigations()
        self.widgets_view._load_widgets()
        self.plugin_view._load_plugins()

        logger.info("{} 已启动，版本：{}", APP_NAME, LONG_VER)

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _init_window(self):
        self.setObjectName("DashWidgets")
        self.resize(MANAGER_WIDTH, MANAGER_HEIGHT)
        self.setWindowIcon(QIcon(str(ICON_PATH)) if ICON_PATH else QIcon())
        self.setWindowTitle(f"{APP_NAME}  {LONG_VER}")

        # 应用 Claude 设计系统样式（覆盖 qfluentwidgets 默认风格）
        self._apply_claude_style()

        # 添加测试版本水印

    def _apply_claude_style(self):
        """应用 Claude 设计系统 — 奶油画布 + 珊瑚红 + 衬线标题 + 圆角卡片"""
        self.setStyleSheet("""
            /* ═══ 主窗口 ═══ */
            #DashWidgets {
                background-color: #faf9f5;
            }

            /* ═══ 导航面板 ═══ */
            NavigationInterface {
                background-color: #f5f0e8;
                border-right: 1px solid #e6dfd8;
            }
            QWidget#navigationInterface {
                background-color: #f5f0e8;
                border-right: 1px solid #e6dfd8;
            }
            /* 导航项 */
            NavigationPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                font-weight: 500;
                color: #6c6a64;
            }
            NavigationPushButton:hover {
                background-color: #efe9de;
                color: #141413;
            }
            NavigationPushButton:checked, NavigationPushButton[isSelected="true"] {
                background-color: #e8e0d2;
                color: #141413;
            }
            /* 导航分隔线 */
            NavigationSeparator {
                background-color: #e6dfd8;
            }

            /* ═══ 卡片 — 12px 圆角，奶油色底 ═══ */
            CardWidget, SimpleCardWidget, HeaderCardWidget {
                background-color: #efe9de;
                border: 1px solid #e6dfd8;
                border-radius: 12px;
            }
            /* 设置卡片 */
            SettingCard {
                background-color: #efe9de;
                border: 1px solid #e6dfd8;
                border-radius: 12px;
            }

            /* ═══ 按钮 ═══ */
            /* 主按钮 — 黑色 */
            PrimaryPushButton, PushButton {
                background-color: #141413;
                color: #faf9f5;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            PrimaryPushButton:hover, PushButton:hover {
                background-color: #252523;
            }
            PrimaryPushButton:pressed, PushButton:pressed {
                background-color: #252523;
            }
            PrimaryPushButton:disabled, PushButton:disabled {
                background-color: #e6dfd8;
                color: #6c6a64;
            }
            /* 次要/透明按钮 */
            TransparentPushButton, ToolButton {
                background-color: transparent;
                color: #141413;
                border: none;
                border-radius: 8px;
                padding: 8px;
            }
            TransparentPushButton:hover, ToolButton:hover {
                background-color: #efe9de;
            }

            /* ═══ 输入框 ═══ */
            LineEdit, ComboBox, SpinBox {
                background-color: #ffffff;
                color: #141413;
                border: 1px solid #e6dfd8;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
            }
            LineEdit:focus, ComboBox:focus, SpinBox:focus {
                border: 2px solid #cc785c;
                padding: 7px 11px;
            }
            TextEdit, PlainTextEdit {
                background-color: #ffffff;
                color: #141413;
                border: 1px solid #e6dfd8;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
            }

            /* ═══ 文字标签 ═══ */
            StrongBodyLabel {
                color: #141413;
                font-weight: 500;
            }
            BodyLabel {
                color: #3d3d3a;
                font-weight: 400;
            }
            CaptionLabel {
                color: #6c6a64;
                font-size: 13px;
            }
            SubtitleLabel {
                color: #141413;
                font-size: 14px;
                font-weight: 500;
            }
            TitleLabel {
                font-family: Georgia, Cambria, serif;
                font-weight: 400;
                letter-spacing: -0.5px;
            }

            /* ═══ 菜单 ═══ */
            QMenu, RoundMenu {
                background-color: #ffffff;
                border: 1px solid #e6dfd8;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item, RoundMenu::item {
                padding: 8px 24px;
                border-radius: 6px;
                color: #141413;
            }
            QMenu::item:selected, RoundMenu::item:selected {
                background-color: #efe9de;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e6dfd8;
                margin: 4px 8px;
            }

            /* ═══ 滚动条 ═══ */
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(20,20,19,0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(20,20,19,0.25);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 6px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: rgba(20,20,19,0.15);
                border-radius: 3px;
                min-width: 30px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }

            /* ═══ 滚动区域 ═══ */
            QScrollArea, ScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }

            /* ═══ 分隔线 ═══ */
            QFrame[separator="true"] {
                background-color: #e6dfd8;
                max-height: 1px;
                border: none;
            }

            /* ═══ 进度条 ═══ */
            QProgressBar {
                background-color: #e6dfd8;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #cc785c;
                border-radius: 3px;
            }

            /* ═══ 复选框 ═══ */
            QCheckBox {
                color: #3d3d3a;
                font-size: 14px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #e6dfd8;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #cc785c;
                border-color: #cc785c;
            }

            /* ═══ 选项卡 ═══ */
            QTabWidget::pane {
                border: 1px solid #e6dfd8;
                border-radius: 8px;
                background-color: #faf9f5;
            }
            QTabBar::tab {
                background-color: transparent;
                color: #6c6a64;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #efe9de;
                color: #141413;
            }

            /* ═══ 工具提示 ═══ */
            QToolTip {
                background-color: #252320;
                color: #faf9f5;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
        """)
        self._add_watermark()

    def _setup_mica(self):
        """云母效果已禁用 — Claude 设计使用不透明奶油画布"""
        pass

    def _add_watermark(self):
        """添加水印"""
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt

        self._watermark = QLabel("内部测试 · 非最终版", self)
        self._watermark.setStyleSheet("""
            QLabel {
                color: rgba(108, 106, 100, 180);
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }
        """)
        self._watermark.adjustSize()  # 自动计算尺寸
        self._watermark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._watermark.raise_()

    def resizeEvent(self, event):
        """窗口大小改变时更新水印位置"""
        super().resizeEvent(event)
        if hasattr(self, "_watermark"):
            # 确保水印在可见区域内
            margin = 15
            x = self.width() - self._watermark.width() - margin
            if x < 0:
                x = 0
            y = self.height() - self._watermark.height() - margin - 5
            if y < 0:
                y = 0
            self._watermark.move(x, y)

    def _init_splash(self):
        self.splash = SplashScreen(self.windowIcon(), self)
        # SplashScreen 没有 setIconSize 方法，使用 setFixedSize 替代
        self.splash.setFixedSize(QSize(102, 102))
        self.show()

    def _check_plugin_permission(
        self, plugin_name: str, permissions: list
    ) -> tuple[bool, bool]:
        """检查单个插件权限并显示授权对话框"""
        from app.views.plugin_view import PermissionDialog

        dialog = PermissionDialog(plugin_name, permissions, self)
        dialog.exec()
        return dialog.get_result()

    def _check_plugin_permissions(self):
        """检查插件权限并显示通知"""
        # 获取所有已加载的插件
        entries = self._plugin_mgr.all_entries()

        # 检查是否有需要用户授权的插件
        plugins_needing_permission = []

        for entry in entries:
            if not entry.enabled:
                continue

            # 获取插件声明的权限
            permissions = entry.meta.permissions or []
            if not permissions:
                continue

            # 新插件，需要用户确认
            plugins_needing_permission.append(
                {
                    "id": entry.meta.id,
                    "name": entry.meta.name,
                    "permissions": permissions,
                }
            )

        # 显示权限请求通知
        if plugins_needing_permission:
            # 统计需要授权的插件数量
            total_plugins = len(plugins_needing_permission)

            # 构建权限列表文本
            perm_summary = []
            for plugin in plugins_needing_permission[:3]:  # 最多显示3个插件
                perms_text = ", ".join(
                    [
                        PERMISSION_DISPLAY_NAMES.get(
                            p.value if hasattr(p, "value") else str(p), "未知权限"
                        )
                        for p in plugin["permissions"][:3]  # 每个插件最多显示3个权限
                    ]
                )
                perm_summary.append(f"{plugin['name']}: {perms_text}")

            summary_text = "\n".join(perm_summary)
            if total_plugins > 3:
                summary_text += f"\n...还有 {total_plugins - 3} 个插件"

            # 显示警告通知
            show_warning(
                f"插件权限请求 ({total_plugins} 个插件)",
                f"以下插件需要您的授权才能使用：\n{summary_text}\n\n请在「插件」页面管理插件权限。",
            )

    def _init_navigation(self):
        # 主功能
        self.addSubInterface(self.home_view, FIF.HOME, "主页")
        self.addSubInterface(self.widgets_view, FIF.TILES, "小组件")

        self.navigationInterface.addSeparator()

        # 插件
        self.addSubInterface(self.plugin_view, FIF.CONNECT, "插件")

        # 开发者页面不加入侧边栏，通过设置中的开关启动
        if SettingsService.instance().developer_mode:
            self.addSubInterface(self.developer_view, FIF.CODE, "开发者")

        # 从插件加载侧边栏导航项
        self._load_plugin_navigations()

        # 底部
        self.addSubInterface(
            self.settings_view,
            FIF.SETTING,
            "设置",
            NavigationItemPosition.BOTTOM,
        )

        show_info(APP_NAME, LONG_VER)
        self.splash.finish()

        # 初始化全局快捷键
        self._setup_global_shortcuts()

    def _load_plugin_navigations(self):
        """从插件加载侧边栏导航项"""
        # 初始化插件导航跟踪字典
        if not hasattr(self, "_plugin_nav_widgets"):
            self._plugin_nav_widgets: dict[str, QWidget] = {}

        try:
            # 先移除旧的插件导航项
            self._clear_plugin_navigations()

            nav_entries = self._plugin_mgr.get_navigation_entries()
            for entry in nav_entries:
                nav_info = entry.plugin.get_navigation_info()
                if nav_info and nav_info.get("widget"):
                    # 获取图标
                    icon = nav_info.get("icon", FIF.CODE)
                    title = nav_info.get("title", entry.meta.name)
                    position = nav_info.get("position")

                    # 添加到侧边栏
                    if position == "bottom":
                        self.addSubInterface(
                            nav_info["widget"],
                            icon,
                            title,
                            NavigationItemPosition.BOTTOM,
                        )
                    else:
                        self.addSubInterface(nav_info["widget"], icon, title)

                    # 跟踪导航项
                    self._plugin_nav_widgets[entry.meta.id] = nav_info["widget"]

                    # 注册到视图映射
                    self._url_view_map[f"{entry.meta.id}View"] = nav_info["widget"]

                    logger.info("加载插件导航: {} - {}", entry.meta.id, title)
        except Exception:
            logger.exception("加载插件导航失败")

    def _clear_plugin_navigations(self):
        """清除所有插件导航项"""
        if not hasattr(self, "_plugin_nav_widgets"):
            return

        for plugin_id, widget in list(self._plugin_nav_widgets.items()):
            # 从视图映射中移除
            view_key = f"{plugin_id}View"
            if view_key in self._url_view_map:
                del self._url_view_map[view_key]

            # 使用 removeInterface 移除子界面
            try:
                if widget:
                    self.removeInterface(widget)
            except Exception as e:
                logger.warning("移除插件导航失败: {}, 错误: {}", plugin_id, e)

        self._plugin_nav_widgets.clear()

    def _refresh_plugin_navigations(self):
        """刷新插件导航（在插件加载完成后调用）"""
        logger.info("刷新插件导航...")
        self._clear_plugin_navigations()
        self._load_plugin_navigations()

    def _sync_developer_nav(self, enabled: bool) -> None:
        """根据开发者模式开关动态显示/隐藏开发者导航项"""
        if enabled:
            # 在插件导航之后、底部之前插入
            self.addSubInterface(self.developer_view, FIF.CODE, "开发者")
        else:
            try:
                self.removeInterface(self.developer_view)
            except Exception:
                pass

    def _init_tray(self):
        """初始化系统托盘"""
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon(str(ICON_PATH)) if ICON_PATH else QIcon())

        from PySide6.QtWidgets import QMenu as StdMenu

        menu = StdMenu()

        # 小组件操作
        self._toggle_widgets_action = menu.addAction(
            "隐藏所有小组件", self.toggle_all_widgets
        )
        self._toggle_widgets_action.setIcon(FIF.VIEW.icon())
        menu.addAction("刷新小组件", self._refresh_all_widgets).setIcon(FIF.SYNC.icon())
        menu.addAction("解除所有鼠标穿透", self._disable_all_click_through).setIcon(
            FIF.CANCEL.icon()
        )

        # 主题子菜单
        theme_menu = menu.addMenu("切换主题")
        self._theme_light_action = theme_menu.addAction(
            "浅色模式", lambda: self._set_theme(Theme.LIGHT)
        )
        self._theme_light_action.setCheckable(True)
        self._theme_dark_action = theme_menu.addAction(
            "深色模式", lambda: self._set_theme(Theme.DARK)
        )
        self._theme_dark_action.setCheckable(True)
        self._theme_auto_action = theme_menu.addAction(
            "跟随系统", lambda: self._set_theme(Theme.AUTO)
        )
        self._theme_auto_action.setCheckable(True)

        # 设置与退出
        menu.addSeparator()
        menu.addAction("打开设置", self._open_settings).setIcon(FIF.SETTING.icon())
        menu.addSeparator()
        menu.addAction("显示窗口", self._restore_window).setIcon(FIF.LINK.icon())
        menu.addAction("退出", self._quit).setIcon(FIF.EMBED.icon())

        self._tray.setContextMenu(menu)

        _ = self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        # 更新主题菜单状态
        self._update_theme_menu_state()
        qconfig.themeChanged.connect(self._update_theme_menu_state)

    # ------------------------------------------------------------------
    # URL 导航
    # ------------------------------------------------------------------

    def handle_url(self, url: str) -> None:
        """
        解析并导航到 URL 指定的视图。

        支持格式：``dashwidgets://open/<view_key>``
        """
        from app.services.url_scheme_service import parse_url

        object_name = parse_url(url)
        if not object_name:
            logger.warning("无法识别的 URL：{}", url)
            show_warning("无效 URL", f"无法识别的地址：{url}")
            return

        # 调试视图 → 打开独立窗口
        if object_name == "debugView":
            self._open_debug_window()
            return

        view = self._url_view_map.get(object_name)
        if view is None:
            logger.warning("URL 对应视图不存在：{}", object_name)
            return

        # 唤起窗口并切换到目标视图
        self.showNormal()
        self.activateWindow()
        self.raise_()
        if isinstance(view, QWidget):
            self.switchTo(view)
        logger.info("URL 导航 → {} ({})", url, object_name)

    def handle_import(self, dw_path: str) -> None:
        """处理 .dw 插件导入请求（来自双击文件或转发）。"""
        from app.services.dw_package_service import read_dw_meta
        from app.views.plugin_import_dialog import show_import_dialog

        meta = read_dw_meta(dw_path)
        if meta is None:
            logger.warning("无法读取 .dw 插件信息: {}", dw_path)
            show_warning("导入失败", f"无法读取插件信息:\n{dw_path}")
            return

        # 唤起窗口
        self.showNormal()
        self.activateWindow()
        self.raise_()

        if show_import_dialog(dw_path, parent=self):
            self._plugin_mgr.discover_and_load()
            self._refresh_plugin_navigations()
            self.plugin_view._load_plugins()
            self.switchTo(self.plugin_view)

    def _open_debug_window(self) -> None:
        """打开独立的调试窗口"""
        if hasattr(self, "_debug_window") and self._debug_window is not None:
            self._debug_window.show()
            self._debug_window.raise_()
            self._debug_window.activateWindow()
            self._debug_window.refresh()

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """关闭窗口时最小化到系统托盘"""
        if self._tray.isVisible():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()
        # 右键菜单由 setContextMenu 自动处理，无需手动 exec

    def toggle_all_widgets(self):
        """切换所有小组件的显示/隐藏（公开方法，供全局热键调用）"""
        # 检查模型中是否有激活的小组件（而非运行时的 _active_widgets 字典）
        from app.models.widget_model import WidgetModel

        model = WidgetModel()
        active_widget_ids = [w.id for w in model.get_all_widgets() if w.is_active]
        if not active_widget_ids:
            show_info("提示", "当前没有激活的小组件")
            return

        # 用独立标志位追踪状态（hide_all 会清空 _active_widgets 导致无法判断）
        if not hasattr(self, "_widgets_hidden"):
            self._widgets_hidden = False

        if not self._widgets_hidden:
            # 隐藏所有小组件
            self._widget_manager.hide_all()
            self._toggle_widgets_action.setText("显示所有小组件")
            self._toggle_widgets_action.setIcon(FIF.VIEW.icon())
            self._widgets_hidden = True
            show_success("已隐藏", f"已隐藏 {len(active_widget_ids)} 个桌面小组件")
        else:
            # 显示所有小组件
            self._widget_manager.show_all_active_widgets()
            self._toggle_widgets_action.setText("隐藏所有小组件")
            self._toggle_widgets_action.setIcon(FIF.HIDE.icon())
            self._widgets_hidden = False
            show_success("已显示", f"已显示 {len(active_widget_ids)} 个桌面小组件")

    def _disable_all_click_through(self):
        """解除所有小组件的鼠标穿透"""
        disabled_count = 0
        for widget_id, window in self._widget_manager._active_widgets.items():
            if hasattr(window, "set_click_through"):
                window.set_click_through(False)
                disabled_count += 1
        if disabled_count:
            show_success("已解除", f"已解除 {disabled_count} 个小组件的鼠标穿透")
        else:
            show_info("提示", "当前没有激活的小组件")

    def _quit(self):
        """退出应用"""
        # 卸载所有插件
        self._plugin_mgr.unload_all()

        # 隐藏托盘图标
        self._tray.hide()

        # 退出应用
        QApplication.instance().quit()

    def _refresh_all_widgets(self):
        """刷新所有小组件"""
        self._widget_manager.hide_all()
        self._widget_manager.show_all_active_widgets()
        show_success("已刷新", "所有小组件已刷新")

    def _set_theme(self, theme: Theme):
        """设置主题"""
        qconfig.themeMode = theme
        setTheme(theme)

    def _update_theme_menu_state(self):
        """更新主题菜单选中状态"""
        current_theme = qconfig.themeMode.value
        self._theme_light_action.setChecked(current_theme == Theme.LIGHT)
        self._theme_dark_action.setChecked(current_theme == Theme.DARK)
        self._theme_auto_action.setChecked(current_theme == Theme.AUTO)

    def _open_settings(self):
        """打开设置页面"""
        self.showNormal()
        self.activateWindow()
        self.switchTo(self.settings_view)

    def _restore_window(self):
        """从托盘恢复窗口"""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _show_toast(self, title: str, message: str = "", level: str = "info") -> None:
        """显示 Toast 通知（供插件和内部调用）"""
        self._toast_mgr.show_toast(title, message, level=level)

    def _setup_global_shortcuts(self) -> None:
        """设置全局快捷键"""
        from PySide6.QtGui import QShortcut, QKeySequence

        # Ctrl+H: 隐藏/显示所有小组件
        toggle_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        _ = toggle_shortcut.activated.connect(self.toggle_all_widgets)

        # Ctrl+Shift+A: 显示添加小组件对话框
        add_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        _ = add_shortcut.activated.connect(self._show_add_widget_dialog)

        # Ctrl+Shift+D: 打开调试窗口
        debug_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        _ = debug_shortcut.activated.connect(self._open_debug_window)

        logger.info(
            "全局快捷键已初始化: Ctrl+H (切换小组件), Ctrl+Shift+A (添加小组件), Ctrl+Shift+D (调试面板)"
        )

    def _show_add_widget_dialog(self) -> None:
        """显示添加小组件对话框"""
        # 切换到小组件页面
        self.switchTo(self.widgets_view)
        show_info("添加小组件", "请选择要添加的小组件")
