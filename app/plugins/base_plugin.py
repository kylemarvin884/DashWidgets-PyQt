"""插件基类与钩子定义"""
from __future__ import annotations

import json
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    pass

from loguru import logger


class HookType(Enum):
    """插件可注册的钩子点"""
    # 生命周期
    ON_LOAD = auto()      # 插件加载后
    ON_UNLOAD = auto()    # 插件卸载前

    # 小组件事件
    ON_WIDGET_ADDED = auto()     # 小组件添加
    ON_WIDGET_REMOVED = auto()   # 小组件移除
    ON_WIDGET_SHOWN = auto()     # 小组件显示
    ON_WIDGET_HIDDEN = auto()    # 小组件隐藏

    # 应用事件
    ON_APP_STARTUP = auto()      # 应用启动
    ON_APP_SHUTDOWN = auto()     # 应用关闭

    # 闹钟 (LTC 特有)
    ON_ALARM_BEFORE = auto()     # 闹钟即将触发（可取消）
    ON_ALARM_AFTER = auto()      # 闹钟已触发

    # 计时器 (LTC 特有)
    ON_TIMER_DONE = auto()       # 计时器归零
    ON_STOPWATCH_LAP = auto()    # 秒表记圈

    # 专注 (LTC 特有)
    ON_FOCUS_START = auto()      # 专注会话开始
    ON_FOCUS_END = auto()        # 专注会话结束

    # 自动化扩展
    CUSTOM_TRIGGER = auto()      # 注册自定义触发器
    CUSTOM_ACTION = auto()       # 注册自定义动作

    # UI
    SETTINGS_WIDGET = auto()     # 在设置页注入插件配置面板
    SIDEBAR_WIDGET = auto()      # 在侧边栏注入额外面板


class PluginType(Enum):
    """插件类型。

    FEATURE
        功能插件（面向用户）。提供时钟、通知等实际功能，
        可订阅钩子、注册自动化触发器/动作、扩展 UI。

    LIBRARY
        依赖插件（面向开发者）。封装可复用的能力（HTTP 客户端、
        数据库访问、第三方 SDK 等），通过 :meth:`LibraryPlugin.export`
        向其他插件暴露公开接口。不直接面向普通用户。
    """
    FEATURE = "feature"
    LIBRARY = "library"


class PluginPermission(Enum):
    """插件权限（LTC 兼容）"""
    NETWORK = "network"       # 网络访问
    FS_READ = "fs_read"       # 读取文件系统
    FS_WRITE = "fs_write"     # 写入文件系统
    OS_EXEC = "os_exec"       # 执行外部命令
    OS_ENV = "os_env"         # 读写系统环境变量
    CLIPBOARD = "clipboard"   # 读写剪贴板
    INSTALL_PKG = "install_pkg"  # 安装包
    NOTIFICATION = "notification"  # 通知


@dataclass
class PluginMeta:
    """插件元数据。

    必填字段
    --------
    id : str
        全局唯一标识符，建议用 ``snake_case``，例如 ``my_widget_plugin``。
    name : str
        用户可见的插件名称（支持中文）。

    可选字段
    --------
    version : str
        遵循语义化版本格式，默认 ``"1.0.0"``。
    author : str
        作者名或联系邮箱。
    description : str
        一句话描述插件功能，显示在插件管理界面。
    homepage : str
        项目主页 / 文档 URL。
    min_host_version : str
        要求的最低宿主版本。
    plugin_type : PluginType
        插件类型，默认 ``PluginType.FEATURE``（功能插件）。
        设为 ``PluginType.LIBRARY`` 声明为依赖插件。
    requires : list[str]
        所依赖的其他插件 ID 列表，例如 ``["http_lib", "db_lib"]``。
        管理器会确保依赖在本插件之前加载；若某依赖缺失则本插件
        加载失败并报错。
    dependencies : list[str]
        PyPI 包依赖列表，管理器仅做声明记录，不自动安装。
    tags : list[str]
        分类标签，例如 ``["widget", "clock"]``。
    permissions : list[PluginPermission]
        插件需要的权限列表。
    """
    id: str
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    homepage: str = ""
    min_host_version: str = ""
    plugin_type: PluginType = PluginType.FEATURE
    requires: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    permissions: list[PluginPermission] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PluginMeta":
        """从字典（通常来自 plugin.json）构建 PluginMeta。"""
        raw_type = d.get("plugin_type", "feature")
        try:
            ptype = PluginType(raw_type)
        except ValueError:
            logger.warning("plugin.json plugin_type 未知值 '{}', 回退到 feature", raw_type)
            ptype = PluginType.FEATURE
        
        # 解析权限
        permissions = []
        raw_permissions = d.get("permissions", [])
        for p in raw_permissions:
            try:
                if isinstance(p, str):
                    permissions.append(PluginPermission(p))
                elif isinstance(p, PluginPermission):
                    permissions.append(p)
            except ValueError:
                logger.warning("plugin.json permissions 未知值 '{}', 忽略", p)
        
        return cls(
            id=d["id"],
            name=d["name"],
            version=d.get("version", "1.0.0"),
            author=d.get("author", ""),
            description=d.get("description", ""),
            homepage=d.get("homepage", ""),
            min_host_version=d.get("min_host_version", ""),
            plugin_type=ptype,
            requires=d.get("requires", []),
            dependencies=d.get("dependencies", []),
            tags=d.get("tags", []),
            permissions=permissions,
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "homepage": self.homepage,
            "min_host_version": self.min_host_version,
            "plugin_type": self.plugin_type.value,
            "requires": self.requires,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "permissions": [p.value for p in self.permissions],
        }


class BasePlugin(ABC):
    """所有插件必须继承此类，并在类体或 ``plugin.json`` 中声明 :attr:`meta`。

    最小示例（不带配置文件）::

        class Plugin(BasePlugin):
            meta = PluginMeta(id="my_plugin", name="我的插件")

            def on_load(self, api: "PluginAPI") -> None:
                api.register_hook(HookType.ON_WIDGET_ADDED, self._on_widget_added)

            def _on_widget_added(self, widget_id: str) -> None:
                print("小组件添加了!", widget_id)

    推荐使用 ``plugin.json`` 声明元数据（见开发指南）。

    注意事项
    --------
    - 主入口类名必须为 ``Plugin``，管理器按此名称查找。
    - ``on_load`` / ``on_unload`` 均应捕获内部异常，不应向外抛出。
    - 插件数据请通过 ``api.get_config`` / ``api.set_config`` 持久化，
      不应直接读写宿主 ``config/`` 目录。
    """

    # 子类必须覆盖（或由 PluginManager 从 plugin.json 注入）
    meta: PluginMeta

    # -----------------------------------------------------------------   #
    # 生命周期 — 子类可选重写
    # -----------------------------------------------------------------   #

    def on_load(self, api: "PluginAPI") -> None:
        """插件加载时调用。在此注册钩子、触发器、动作等。"""

    def on_unload(self) -> None:
        """插件卸载时调用。在此清理资源、取消订阅等。"""

    # -----------------------------------------------------------------   #
    # UI 扩展点 — 子类可选重写
    # -----------------------------------------------------------------   #

    def create_settings_widget(self) -> "dict | None":
        """返回插件专属的设置面板配置（嵌入宿主设置页）。

        返回 dict：
        {
            "type": "html",
            "content": "<div>...</div>",   # HTML 内容
            "script": "...",               # 可选 JS 脚本
        }
        """
        return None

    def create_sidebar_widget(self) -> "dict | None":
        """返回插件专属的侧边栏面板配置。

        返回 dict：
        {
            "type": "html",
            "content": "<div>...</div>",
            "script": "...",
        }
        """
        return None

    def get_navigation_info(self) -> "dict | None":
        """返回插件的侧边栏导航信息。

        返回格式：
        {
            "title": "开发者",      # 导航标题
            "icon": "SETTING",          # 图标（FluentIcon 名称字符串或 SVG 路径）
            "position": "bottom",   # 位置：None(默认) 或 "bottom"
        }

        如果返回 None，则不添加侧边栏导航项。
        """
        return None

    def get_sidebar_icon(self) -> "str | None":
        """返回侧边栏图标。

        Returns
        -------
        str | None
            侧边栏图标，支持：
            - FluentIcon 名称字符串
            - SVG 图标路径字符串
            - None 使用默认图标
        """
        return None

    def get_sidebar_label(self) -> str:
        """返回侧边栏显示文字。

        Returns
        -------
        str
            侧边栏显示文字，默认为 meta.name。
        """
        return self.meta.name if hasattr(self, "meta") and self.meta else ""


class LibraryPlugin(BasePlugin):
    """依赖插件基类。

    继承此类代替 :class:`BasePlugin` 以声明本插件为 **依赖插件**
    （``plugin_type = library``）。依赖插件不直接面向用户，而是向其他插件
    提供可复用的公开接口。

    其他插件通过 ``api.get_plugin(plugin_id)`` 获取本插件的导出对象::

        # 在依赖插件中
        class Plugin(LibraryPlugin):
            meta = PluginMeta(
                id="http_lib", name="HTTP 工具库",
                plugin_type=PluginType.LIBRARY,
            )

            def fetch(self, url: str) -> dict:
                ...

            def export(self):
                return self   # 把自身作为公开接口

        # 在功能插件中
        class Plugin(BasePlugin):
            meta = PluginMeta(
                id="weather_plugin", name="天气插件",
                requires=["http_lib"],
            )

            def on_load(self, api):
                http = api.get_plugin("http_lib")
                if http:
                    data = http.fetch("https://api.example.com/weather")

    注意事项
    --------
    - ``export()`` 返回的对象即为其他插件拿到的接口，可以是 ``self``
      也可以是单独的接口类实例（推荐后者以更好地隔离内部实现）。
    - ``meta.plugin_type`` 必须为 ``PluginType.LIBRARY``；继承本类时
      若忘记设置，管理器会自动补正。
    - 依赖插件同样可以订阅钩子，但 **不应** 直接修改 UI 状态。
    """

    def export(self) -> Any:
        """返回供其他插件调用的公开接口对象。

        默认返回 ``self``；强烈建议子类返回专门的接口对象以隔离内部实现。
        """
        return self


# --------------------------------------------------------------------------- #
# PluginAPI
# --------------------------------------------------------------------------- #

class PluginAPI:
    """宿主程序提供给插件的能力接口。

    插件 **只应** 通过此接口与宿主交互，不应直接导入宿主内部模块。

    可用能力
    --------
    - 钩子注册：:meth:`register_hook` / :meth:`unregister_hook`
    - 自动化扩展：:meth:`register_trigger` / :meth:`register_action`
    - 持久化配置：:meth:`get_config` / :meth:`set_config`
    - 用户通知：:meth:`show_toast`
    - 宿主服务：:meth:`get_service`
    - 依赖插件访问：:meth:`get_plugin`
    - 资源加载：:meth:`load_resource`
    - 日志记录：:attr:`logger` 属性
    - i18n：:meth:`current_language` / :meth:`tr`
    - 时间：:meth:`get_corrected_time` / :meth:`get_corrected_utc` / :meth:`get_time_offset_seconds` / :meth:`set_time_offset_seconds`
    - 启动参数：:meth:`get_startup_args` / :meth:`register_startup_arg`
    - 首页卡片：:meth:`register_home_card_factory` / :meth:`unregister_home_card_factory`
    - 推荐功能：:meth:`register_recommendation_feature` / :meth:`record_recommendation_view` 等
    - URL Scheme：:meth:`register_url_scheme_view` / :meth:`unregister_url_scheme_view`
    - 权限：:meth:`has_permission` / :meth:`request_permission`
    """

    def __init__(self, plugin_data_dir: Path | None = None, plugin_id: str | None = None):
        self._hooks: dict[HookType, list[Callable]] = {}
        self._custom_triggers: dict[str, Callable] = {}
        self._custom_actions: dict[str, Callable] = {}
        self._trigger_metadata: dict[str, dict] = {}  # 存储触发器元数据
        self._config: dict[str, Any] = {}
        self._data_dir: Path | None = plugin_data_dir
        self._services: dict[str, Any] = {}
        self._toast_callback: Callable | None = None
        self._plugin_resolver: Callable | None = None   # 由管理器注入
        self._plugin_id: str | None = plugin_id
        self._time_offset_seconds: int = 0  # 时间偏移量（秒）
        self._startup_args: dict[str, Any] = {}  # 启动参数
        self._registered_startup_args: dict[str, Callable] = {}  # 注册的启动参数处理器
        self._home_card_factories: list[Callable] = []  # 首页卡片工厂
        self._recommendation_features: dict[str, str] = {}  # 推荐特征
        self._url_scheme_views: dict[str, str] = {}  # URL Scheme 视图映射

        # 主窗口引用
        self._evaluate_js: Callable[[str], Any] | None = None  # JS 执行回调
        self._main_window: Any | None = None  # 主窗口引用
        # 权限（由管理器注入）
        self._permission_checker: Callable[[PluginPermission], bool] | None = None
        self._permission_request_cb: Callable[[PluginPermission, str], bool] | None = None

        if self._data_dir is not None:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._load_config()

    # ------------------------------------------------------------------ #
    # 数据目录
    # ------------------------------------------------------------------ #

    def get_data_dir(self) -> Path | None:
        """获取插件数据目录。

        Returns
        -------
        Path | None
            插件专用数据目录，若未设置则返回 None。
        """
        return self._data_dir

    def resolve_data_path(self, *parts: str) -> Path | None:
        """解析插件数据目录下的文件路径。

        Parameters
        ----------
        *parts : str
            相对于数据目录的路径部分。

        Returns
        -------
        Path | None
            解析后的绝对路径，若数据目录未设置则返回 None。
        """
        if self._data_dir is None:
            return None
        path = self._data_dir.joinpath(*parts)
        # 自动创建父目录
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------ #
    # 时间
    # ------------------------------------------------------------------ #

    def get_corrected_time(self, timezone: str | None = None):
        """获取校准后的时间。

        Parameters
        ----------
        timezone : str, optional
            时区字符串，如 "Asia/Shanghai"。如果为 None，返回本地时间。

        Returns
        -------
        datetime
            校准后的时间。
        """
        from datetime import datetime, timezone as tz
        if timezone:
            import zoneinfo
            try:
                tz_info = zoneinfo.ZoneInfo(timezone)
                return datetime.now(tz_info)
            except Exception:
                logger.warning("无效时区: {}, 回退到本地时间", timezone)
        # 应用时间偏移
        from datetime import timedelta
        return datetime.now() + timedelta(seconds=self._time_offset_seconds)

    def get_corrected_utc(self):
        """获取校准后的 UTC 时间。

        Returns
        -------
        datetime
            校准后的 UTC 时间。
        """
        from datetime import datetime, timezone, timedelta
        return datetime.now(timezone.utc) + timedelta(seconds=self._time_offset_seconds)

    def get_time_offset_seconds(self) -> int:
        """获取当前时间偏移量（秒）。

        Returns
        -------
        int
            时间偏移量（秒），可正可负。
        """
        return self._time_offset_seconds

    def set_time_offset_seconds(self, offset: int) -> None:
        """设置时间偏移量。

        Parameters
        ----------
        offset : int
            时间偏移量（秒），正数表示时间提前，负数表示时间延后。
        """
        self._time_offset_seconds = int(offset)
        logger.debug("插件 {} 设置时间偏移: {} 秒", self._plugin_id, offset)

    # ------------------------------------------------------------------ #
    # i18n (国际化)
    # ------------------------------------------------------------------ #

    def current_language(self) -> str:
        """获取宿主当前语言。

        Returns
        -------
        str
            语言代码，如 "zh-CN" 或 "en-US"。
        """
        # 尝试从设置服务获取语言
        try:
            settings_svc = self.get_service("settings_service")
            if settings_svc and hasattr(settings_svc, "language"):
                return settings_svc.language
        except Exception:
            pass
        # 默认返回简体中文
        return "zh-CN"

    def tr(self, key: str, default: str = "") -> str:
        """翻译辅助函数，复用宿主已有的公共文案。

        Parameters
        ----------
        key : str
            翻译键。
        default : str
            默认文案（当键不存在时返回）。

        Returns
        -------
        str
            翻译后的文案。
        """
        # 这是一个占位实现，实际翻译取决于宿主提供的翻译资源
        # 插件可以通过 name_i18n / description_i18n 在 plugin.json 中声明多语言
        return default or key

    # ------------------------------------------------------------------ #
    # 启动参数
    # ------------------------------------------------------------------ #

    def get_startup_args(self) -> dict[str, Any]:
        """获取本次启动的上下文参数。

        Returns
        -------
        dict
            启动上下文，包含：
            - hidden_mode: bool - 是否以隐藏模式启动
            - extra_args: str - 原始 --extra-args 字符串
        """
        return dict(self._startup_args)

    def _set_startup_args(self, args: dict[str, Any]) -> None:
        """由管理器注入启动参数（内部使用）。"""
        self._startup_args = args

    def register_startup_arg(
        self,
        name: str,
        handler: Callable[[Any], None],
        *,
        default: Any = None,
        help: str = "",
        action: str | None = None,
    ) -> None:
        """注册自定义启动参数。

        Parameters
        ----------
        name : str
            参数名（建议使用插件 ID 前缀，如 "my-plugin.target"）。
        handler : Callable
            参数处理函数，接收参数值。
        default : Any
            默认值。
        help : str
            参数帮助说明。
        action : str, optional
            参数动作，如 "store_true"。
        """
        self._registered_startup_args[name] = handler
        # 如果有默认值，先调用一次
        if default is not None:
            try:
                handler(default)
            except Exception:
                logger.exception("启动参数 {} 默认值处理异常", name)
        logger.debug("插件 {} 注册启动参数: {}", self._plugin_id, name)

    def _process_startup_args(self, extra_args: str) -> None:
        """解析并分发启动参数（内部使用）。"""
        if not extra_args:
            return
        import argparse
        parser = argparse.ArgumentParser(allow_abbrev=False)
        for name in self._registered_startup_args:
            parser.add_argument(f"--{name}", default=argparse.SUPPRESS)
        try:
            parsed = parser.parse_args(extra_args.split())
            for name, handler in self._registered_startup_args.items():
                value = getattr(parsed, name.replace("-", "_"), None)
                if value is not None and value != argparse.SUPPRESS:
                    try:
                        handler(value)
                    except Exception:
                        logger.exception("启动参数 {} 处理异常", name)
        except Exception:
            logger.warning("启动参数解析失败: {}", extra_args)

    # ------------------------------------------------------------------ #
    # 首页卡片
    # ------------------------------------------------------------------ #

    def register_home_card_factory(
        self,
        factory: Callable,
        slot: str = "recommend",
        order: int = 100,
    ) -> None:
        """注册首页卡片工厂函数。

        Parameters
        ----------
        factory : Callable[[dict], dict | list[dict]]
            工厂函数，接收上下文字典，返回卡片 HTML 配置。
        slot : str
            卡片槽位："top"、"recommend" 或 "extra"。
        order : int
            排序顺序，数值越小越靠前。
        """
        # 存储工厂函数和元数据
        self._home_card_factories.append({
            "factory": factory,
            "slot": slot,
            "order": order,
            "plugin_id": self._plugin_id,
        })
        logger.debug("插件 {} 注册首页卡片工厂 (slot={}, order={})",
                     self._plugin_id, slot, order)

    def unregister_home_card_factory(self, factory: Callable) -> None:
        """注销首页卡片工厂。

        Parameters
        ----------
        factory : Callable
            之前注册的工厂函数。
        """
        self._home_card_factories = [
            f for f in self._home_card_factories
            if f["factory"] is not factory
        ]
        logger.debug("插件 {} 注销首页卡片工厂", self._plugin_id)

    def _get_home_card_factories(self, slot: str | None = None) -> list[dict]:
        """获取首页卡片工厂列表（内部使用）。"""
        if slot:
            return [f for f in self._home_card_factories if f["slot"] == slot]
        return sorted(self._home_card_factories, key=lambda x: x["order"])

    # ------------------------------------------------------------------ #
    # 推荐功能
    # ------------------------------------------------------------------ #

    def register_recommendation_feature(self, feature_id: str, display_name: str) -> None:
        """注册推荐特征。

        Parameters
        ----------
        feature_id : str
            特征 ID。
        display_name : str
            显示名称。
        """
        self._recommendation_features[feature_id] = display_name
        logger.debug("插件 {} 注册推荐特征: {}", self._plugin_id, feature_id)

    def record_recommendation_view(self, feature_id: str) -> None:
        """记录推荐项被查看。

        Parameters
        ----------
        feature_id : str
            特征 ID。
        """
        logger.debug("推荐特征 {} 被查看", feature_id)

    def record_recommendation_session_start(self, feature_id: str) -> None:
        """记录推荐会话开始。

        Parameters
        ----------
        feature_id : str
            特征 ID。
        """
        logger.debug("推荐特征 {} 会话开始", feature_id)

    def record_recommendation_session_end(self, feature_id: str) -> None:
        """记录推荐会话结束。

        Parameters
        ----------
        feature_id : str
            特征 ID。
        """
        logger.debug("推荐特征 {} 会话结束", feature_id)

    def rank_recommendation_features(self, feature_ids: list[str]) -> list[str]:
        """对推荐特征进行排序。

        Parameters
        ----------
        feature_ids : list[str]
            特征 ID 列表。

        Returns
        -------
        list[str]
            排序后的特征 ID 列表（此处返回原顺序，子类可重写实现自定义排序）。
        """
        return feature_ids

    # ------------------------------------------------------------------ #
    # URL Scheme
    # ------------------------------------------------------------------ #

    def register_url_scheme_view(self, view_key: str, object_name: str) -> bool:
        """注册 URL Scheme 视图映射。

        Parameters
        ----------
        view_key : str
            视图键，如 "study_schedule"。
        object_name : str
            目标视图标识符。

        Returns
        -------
        bool
            注册是否成功。
        """
        self._url_scheme_views[view_key] = object_name
        logger.debug("插件 {} 注册 URL Scheme: {} -> {}",
                     self._plugin_id, view_key, object_name)
        return True

    def unregister_url_scheme_view(self, view_key: str) -> None:
        """注销 URL Scheme 视图映射。

        Parameters
        ----------
        view_key : str
            视图键。
        """
        self._url_scheme_views.pop(view_key, None)
        logger.debug("插件 {} 注销 URL Scheme: {}", self._plugin_id, view_key)

    def _get_url_scheme_views(self) -> dict[str, str]:
        """获取 URL Scheme 视图映射（内部使用）。"""
        return dict(self._url_scheme_views)

    # ------------------------------------------------------------------ #
    # 权限
    # ------------------------------------------------------------------ #

    def has_permission(self, permission: PluginPermission) -> bool:
        """检查插件是否拥有指定权限（以加载时用户批准的权限列表为准）。

        Parameters
        ----------
        permission : PluginPermission
            权限枚举值。

        Returns
        -------
        bool
            是否拥有该权限。
        """
        if self._permission_checker is not None:
            try:
                return bool(self._permission_checker(permission))
            except Exception:
                logger.exception("权限检查异常: {}", permission)
                return False
        return False  # 未注入检查器时按最小权限处理

    def request_permission(
        self,
        permission: PluginPermission,
        reason: str = "",
    ) -> bool:
        """请求额外权限（运行时弹出确认）。

        Parameters
        ----------
        permission : PluginPermission
            权限枚举值。
        reason : str
            请求原因说明。

        Returns
        -------
        bool
            请求是否被批准。
        """
        if self.has_permission(permission):
            return True
        logger.info("插件 {} 请求权限 {} (原因: {})",
                    self._plugin_id, permission.value, reason)
        if self._permission_request_cb is not None:
            try:
                return bool(self._permission_request_cb(permission, reason))
            except Exception:
                logger.exception("权限请求异常: {}", permission)
        return False

    def _set_permission_checker(self, checker: Callable[[PluginPermission], bool]) -> None:
        """由管理器注入权限检查函数（内部使用）。"""
        self._permission_checker = checker

    def _set_permission_request_cb(self, cb: Callable[[PluginPermission, str], bool]) -> None:
        """由管理器注入运行时权限请求回调（内部使用）。"""
        self._permission_request_cb = cb

    # ------------------------------------------------------------------ #
    # 自动化触发
    # ------------------------------------------------------------------ #

    def fire_trigger(self, trigger_id: str, **kwargs: Any) -> None:
        """触发自动化规则。

        Parameters
        ----------
        trigger_id : str
            触发器 ID。
        **kwargs : Any
            传递给规则的上下文数据。
        """
        from app.events import EventBus, EventType
        try:
            EventBus.instance().emit(
                EventType.AUTOMATION_TRIGGERED,
                trigger_id=trigger_id,
                source_plugin=self._plugin_id,
                **kwargs,
            )
            logger.debug("插件 {} 触发自动化: {}", self._plugin_id, trigger_id)
        except Exception:
            logger.exception("插件 {} 触发自动化 {} 失败", self._plugin_id, trigger_id)

    # ------------------------------------------------------------------ #
    # 钩子注册
    # ------------------------------------------------------------------ #

    def register_hook(self, hook_type: HookType, callback: Callable) -> None:
        """注册钩子回调。同一回调可注册到多个钩子类型。"""
        self._hooks.setdefault(hook_type, []).append(callback)

    def unregister_hook(self, hook_type: HookType, callback: Callable) -> None:
        """注销指定钩子回调。"""
        if hook_type in self._hooks:
            self._hooks[hook_type] = [
                c for c in self._hooks[hook_type] if c is not callback
            ]

    def emit_hook(self, hook_type: HookType, *args: Any, **kwargs: Any) -> list[Any]:
        """宿主调用：触发某类钩子，收集所有回调返回值。"""
        results: list[Any] = []
        for cb in self._hooks.get(hook_type, []):
            try:
                results.append(cb(*args, **kwargs))
            except Exception:
                logger.exception("PluginAPI hook {} 回调异常", hook_type)
        return results

    # ------------------------------------------------------------------ #
    # 自定义触发器 / 动作
    # ------------------------------------------------------------------ #

    def register_trigger(self, trigger_id: str, handler: Callable | None = None, **kwargs) -> None:
        """注册自定义自动化触发器。

        Parameters
        ----------
        trigger_id : str
            全局唯一字符串，建议格式 ``{plugin_id}.{name}``，
            例如 ``"weather_plugin.on_rain"``。
        handler : Callable[[], bool]
            当自动化引擎查询时调用，返回 ``True`` 代表触发条件满足。
            可为 None，此时仅注册元数据（用于声明式触发器）。
        **kwargs : dict
            可选元数据，支持：
            - name: 触发器显示名称
            - description: 触发器描述
        """
        if handler is not None:
            self._custom_triggers[trigger_id] = handler
        # 存储元数据（即使没有 handler 也保存，用于声明式触发器）
        if kwargs:
            self._trigger_metadata[trigger_id] = kwargs

    def register_action(self, action_id: str, executor: Callable) -> None:
        """注册自定义自动化动作。

        Parameters
        ----------
        action_id : str
            全局唯一字符串，建议格式 ``{plugin_id}.{name}``，
            例如 ``"weather_plugin.send_alert"``。
        executor : Callable[[dict], None]
            执行动作的函数，接收一个参数字典。
        """
        self._custom_actions[action_id] = executor

    def unregister_trigger(self, trigger_id: str) -> None:
        """注销自定义自动化触发器。

        Parameters
        ----------
        trigger_id : str
            触发器 ID。
        """
        self._custom_triggers.pop(trigger_id, None)
        self._trigger_metadata.pop(trigger_id, None)
        logger.debug("插件 {} 注销触发器: {}", self._plugin_id, trigger_id)

    def unregister_action(self, action_id: str) -> None:
        """注销自定义自动化动作。

        Parameters
        ----------
        action_id : str
            动作 ID。
        """
        self._custom_actions.pop(action_id, None)
        logger.debug("插件 {} 注销动作: {}", self._plugin_id, action_id)

    def get_action_executor(self, action_id: str) -> Callable | None:
        """获取自定义动作的执行器。"""
        return self._custom_actions.get(action_id)

    def list_custom_triggers(self) -> dict[str, Callable]:
        """返回所有已注册的自定义触发器。"""
        return dict(self._custom_triggers)

    def list_custom_actions(self) -> dict[str, Callable]:
        """返回所有已注册的自定义动作。"""
        return dict(self._custom_actions)

    # ------------------------------------------------------------------ #
    # 事件订阅
    # ------------------------------------------------------------------ #

    def subscribe_event(self, event_type: Any, callback: Callable) -> None:
        """订阅全局事件。

        Parameters
        ----------
        event_type : EventType
            事件类型枚举。
        callback : Callable
            事件回调函数。
        """
        try:
            from app.events import EventBus
            EventBus.instance().subscribe(event_type, callback)
            logger.debug("插件 {} 订阅了事件 {}", self._plugin_id, event_type)
        except Exception:
            logger.warning("事件订阅失败: {}", event_type)

    def unsubscribe_event(self, event_type: Any, callback: Callable) -> None:
        """取消订阅全局事件。

        Parameters
        ----------
        event_type : EventType
            事件类型枚举。
        callback : Callable
            之前订阅的回调函数。
        """
        try:
            from app.events import EventBus
            EventBus.instance().unsubscribe(event_type, callback)
        except Exception:
            logger.warning("事件取消订阅失败: {}", event_type)

    # ------------------------------------------------------------------ #
    # 持久化配置
    # ------------------------------------------------------------------ #

    def get_config(self, key: str, default: Any = None) -> Any:
        """读取插件配置值。

        配置自动保存在 ``plugins_ext/<plugin_id>/config.json``。

        Parameters
        ----------
        key : str
            配置键名（支持点号路径，如 ``"notifications.enabled"``）。
        default : Any
            键不存在时的默认值。
        """
        keys = key.split(".")
        node: Any = self._config
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def set_config(self, key: str, value: Any) -> None:
        """写入插件配置值并立即持久化到磁盘。

        Parameters
        ----------
        key : str
            配置键名（支持点号路径，如 ``"notifications.enabled"``）。
        value : Any
            可 JSON 序列化的值。
        """
        keys = key.split(".")
        node = self._config
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value
        self._save_config()

    def _config_path(self) -> Path | None:
        if self._data_dir is None:
            return None
        return self._data_dir / "config.json"

    def _load_config(self) -> None:
        path = self._config_path()
        if path and path.exists():
            try:
                self._config = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("插件配置加载失败: {}", path)
                self._config = {}

    def _save_config(self) -> None:
        path = self._config_path()
        if path is None:
            return
        try:
            path.write_text(
                json.dumps(self._config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("插件配置保存失败: {}", path)

    # ------------------------------------------------------------------ #
    # 用户通知
    # ------------------------------------------------------------------ #

    def show_toast(self, title: str, message: str = "", *, level: str = "info") -> None:
        """弹出 Toast 通知。

        Parameters
        ----------
        title : str
            通知标题（简短）。
        message : str
            详细内容，可为空。
        level : str
            通知级别：``"info"`` | ``"success"`` | ``"warning"`` | ``"error"``。
        """
        if self._toast_callback:
            try:
                self._toast_callback(title, message, level)
            except Exception:
                logger.exception("插件 show_toast 回调异常")
        else:
            logger.info("[Plugin Toast][{}] {} {}", level, title, message)

    def _set_toast_callback(self, cb: Callable) -> None:
        """由宿主注入通知回调（内部使用）。"""
        self._toast_callback = cb

    # ------------------------------------------------------------------ #
    # 宿主服务访问
    # ------------------------------------------------------------------ #

    def get_service(self, name: str) -> Any | None:
        """获取宿主注册的服务对象。

        可用服务名称（由宿主注入）：
        - ``"settings_service"`` — 设置服务
        - ``"widget_manager"`` — 小组件管理器

        Parameters
        ----------
        name : str
            服务名称。

        Returns
        -------
        服务对象实例，若不存在则返回 ``None``。
        """
        return self._services.get(name)

    def _register_service(self, name: str, service: Any) -> None:
        """由宿主注入服务实例（内部使用）。"""
        self._services[name] = service

    # ------------------------------------------------------------------ #
    # 画布服务注册 (LTC 兼容)
    # ------------------------------------------------------------------ #

    def register_canvas_service(self, name: str, service: Any) -> None:
        """注册画布服务（LTC 兼容）。

        Parameters
        ----------
        name : str
            服务名称，如 "exam_service"、"study_service" 等。
        service : Any
            服务实例对象。
        """
        try:
            from app.services.canvas_service_registry import CanvasServiceRegistry
            CanvasServiceRegistry.instance().register(name, service, self._plugin_id)
            logger.debug("画布服务已注册: {} (来自插件: {})", name, self._plugin_id or "内置")
        except Exception:
            logger.warning("画布服务注册失败: {}", name)

    def register_canvas_topbar_btn_factory(self, factory: Callable) -> None:
        """注册画布顶栏按钮工厂函数（LTC 兼容）。

        Parameters
        ----------
        factory : Callable[[str], list[dict]]
            工厂函数，接收 zone_id 参数，返回按钮配置列表。
        """
        try:
            from app.services.canvas_service_registry import CanvasServiceRegistry
            CanvasServiceRegistry.instance().register_topbar_btn_factory(factory, self._plugin_id)
            logger.debug("画布顶栏按钮工厂已注册 (来自插件: {})", self._plugin_id or "内置")
        except Exception:
            logger.warning("画布顶栏按钮工厂注册失败")

    def get_canvas_layout(self, zone_id: str) -> list[dict]:
        """获取指定 zone 的画布布局。

        Parameters
        ----------
        zone_id : str
            画布 zone ID。

        Returns
        -------
        list[dict]
            布局配置列表，每项包含 widget_id, widget_type, grid_x, grid_y, grid_w, grid_h, props。
        """
        # 这里需要实际实现，可能需要通过服务获取
        logger.debug("获取画布布局: {}", zone_id)
        return []

    def apply_canvas_layout(self, zone_id: str, configs: list[dict]) -> bool:
        """应用画布布局。

        Parameters
        ----------
        zone_id : str
            画布 zone ID。
        configs : list[dict]
            布局配置列表。

        Returns
        -------
        bool
            是否应用成功。
        """
        # 这里需要实际实现
        logger.debug("应用画布布局: {}, 配置数: {}", zone_id, len(configs))
        return True

    # ------------------------------------------------------------------ #
    # 小组件注册 (LTC 兼容)
    # ------------------------------------------------------------------ #

    def register_widget_type(self, widget_cls: Any) -> None:
        """注册自定义小组件类型（LTC 兼容）。

        将自定义小组件类注册到全局注册表，使其出现在"添加小组件"菜单中。

        Parameters
        ----------
        widget_cls : type
            继承自 WidgetBase 的小组件类。

        Note
        ----
        此功能在 DashWidgets 主版本中为兼容层，实际小组件系统可能不同。
        注册时会自动标记来源插件。
        """
        try:
            from app.widgets.registry import WidgetRegistry
            WidgetRegistry.instance().register(widget_cls, plugin_id=self._plugin_id)
            logger.debug("小组件类型已注册: {} (来自插件: {})", 
                getattr(widget_cls, 'WIDGET_NAME', widget_cls.__name__),
                self._plugin_id or "内置")
        except Exception:
            logger.warning("小组件注册失败，可能需要 app.widgets.registry 模块")

    def unregister_widget_type(self, widget_type: str) -> None:
        """注销自定义小组件类型（LTC 兼容）。

        Parameters
        ----------
        widget_type : str
            小组件类型 ID（WIDGET_TYPE）。
        """
        try:
            from app.widgets.registry import WidgetRegistry
            WidgetRegistry.instance().unregister(widget_type, plugin_id=self._plugin_id)
            logger.debug("小组件类型已注销: {} (来自插件: {})",
                widget_type, self._plugin_id or "内置")
        except Exception:
            logger.warning("小组件注销失败: {}", widget_type)

    # ------------------------------------------------------------------ #
    # 依赖插件访问
    # ------------------------------------------------------------------ #

    def get_plugin(self, plugin_id: str) -> Any | None:
        """获取已加载的依赖插件（``PluginType.LIBRARY``）的公开接口对象。

        返回值为该依赖插件 :meth:`~LibraryPlugin.export` 方法的返回值。
        若目标插件未加载、未启用或类型不是 ``LIBRARY``，则返回 ``None``。

        Parameters
        ----------
        plugin_id : str
            依赖插件的 ID（与其 ``PluginMeta.id`` 一致）。

        Returns
        -------
        Any | None
            依赖插件导出的接口对象，或 ``None``。

        示例
        ----
        .. code-block:: python

            def on_load(self, api):
                http = api.get_plugin("http_lib")
                if http is None:
                    api.show_toast("初始化失败", "找不到 http_lib 插件", level="error")
                    return
                self._http = http
        """
        if self._plugin_resolver is None:
            return None
        try:
            return self._plugin_resolver(plugin_id)
        except Exception:
            logger.exception("get_plugin({}) 调用异常", plugin_id)
            return None

    def _set_plugin_resolver(self, resolver: Callable[[str], Any | None]) -> None:
        """由管理器注入依赖插件解析器（内部使用）。"""
        self._plugin_resolver = resolver

    # ------------------------------------------------------------------ #
    # 资源加载
    # ------------------------------------------------------------------ #

    def load_resource(self, relative_path: str, mode: str = "r") -> str | bytes | Path:
        """加载插件目录下的资源文件。

        资源文件应放在插件目录的 ``assets/`` 子目录中，或直接放在插件目录下。

        Parameters
        ----------
        relative_path : str
            相对于插件目录的路径，例如 ``"assets/icon.png"``。
        mode : str
            打开模式：``"r"`` 读取文本，``"rb"`` 读取二进制，``"path"`` 返回路径对象。

        Returns
        -------
        str | bytes | Path
            根据 mode 返回相应内容：
            - ``"r"``: 文件内容（字符串）
            - ``"rb"``: 文件内容（字节）
            - ``"path"``: Path 对象

        Raises
        ------
        FileNotFoundError
            资源文件不存在。
        """
        if self._data_dir is None:
            raise FileNotFoundError(f"插件数据目录未设置，无法加载资源: {relative_path}")
        
        resource_path = self._data_dir / relative_path
        if not resource_path.exists():
            # 尝试在插件目录下的 assets 子目录中查找
            resource_path = self._data_dir / "assets" / relative_path
            if not resource_path.exists():
                raise FileNotFoundError(f"资源文件不存在: {relative_path} (在 {self._data_dir})")
        
        if mode == "path":
            return resource_path
        elif mode == "r":
            return resource_path.read_text(encoding="utf-8")
        elif mode == "rb":
            return resource_path.read_bytes()
        else:
            raise ValueError(f"不支持的 mode: {mode}，可选 'r', 'rb', 'path'")

    # ------------------------------------------------------------------ #
    # 主窗口交互能力
    # ------------------------------------------------------------------ #

    def evaluate_js(self, script: str) -> Any:
        """在主窗口中执行 JavaScript 代码。

        Parameters
        ----------
        script : str
            JavaScript 代码字符串。

        Returns
        -------
        Any
            JS 表达式的返回值（如支持）。
        """
        if self._evaluate_js:
            try:
                return self._evaluate_js(script)
            except Exception:
                logger.exception("插件 {} evaluate_js 异常", self._plugin_id)
        else:
            logger.warning("evaluate_js 不可用，主窗口未就绪")
        return None

    def _set_evaluate_js(self, fn: Callable[[str], Any]) -> None:
        """由宿主注入 JS 执行回调（内部使用）。"""
        self._evaluate_js = fn

    def get_main_window(self) -> Any:
        """获取主窗口对象。

        Returns
        -------
        QWidget | None
            主窗口实例。
        """
        return self._main_window

    def _set_main_window(self, window: Any) -> None:
        """由宿主注入主窗口引用（内部使用）。"""
        self._main_window = window

    # ------------------------------------------------------------------ #
    # 日志记录
    # ------------------------------------------------------------------ #

    @property
    def logger(self):
        """返回与插件关联的日志记录器。

        使用示例::
            api.logger.info("插件已加载")
            api.logger.error("发生错误", exc_info=True)
        
        日志消息会自动包含插件 ID 前缀。
        """
        class PluginLogger:
            def __init__(self, plugin_id: str | None):
                self._plugin_id = plugin_id or "unknown"
            
            def _format_msg(self, msg: str) -> str:
                return f"[{self._plugin_id}] {msg}"
            
            def debug(self, msg: str, *args, **kwargs):
                logger.debug(self._format_msg(msg), *args, **kwargs)
            
            def info(self, msg: str, *args, **kwargs):
                logger.info(self._format_msg(msg), *args, **kwargs)
            
            def warning(self, msg: str, *args, **kwargs):
                logger.warning(self._format_msg(msg), *args, **kwargs)
            
            def error(self, msg: str, *args, **kwargs):
                logger.error(self._format_msg(msg), *args, **kwargs)
            
            def exception(self, msg: str, *args, **kwargs):
                logger.exception(self._format_msg(msg), *args, **kwargs)
        
        return PluginLogger(self._plugin_id)