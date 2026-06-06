"""示例依赖插件（LibraryPlugin）— 提供可复用工具方法

依赖插件规范要点
-----------------
1. 主入口类名必须为 ``Plugin``，继承 :class:`~app.plugins.LibraryPlugin`。
2. ``plugin.json`` 中 ``plugin_type`` 必须为 ``"library"``。
3. 实现 ``export()`` 方法，返回供其他插件使用的公开接口对象。
   - 可以直接返回 ``self``（简单场景）
   - 推荐返回一个独立的接口对象（接口与实现分离，更易维护）
4. 依赖插件本身同样可以声明 ``requires``，依赖其他库插件。
5. 依赖插件 **不应** 直接修改 UI 状态，但可以注册钩子。
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime

from app.plugins import LibraryPlugin, PluginAPI, PluginMeta, PluginType


# --------------------------------------------------------------------------- #
# 公开接口对象（推荐与插件实现分离）
# --------------------------------------------------------------------------- #

class ExampleLibInterface:
    """供其他插件调用的公开接口。

    功能
    ----
    - 文本处理工具
    - 时间格式化工具
    - 简单哈希工具

    用法示例::

        lib = api.get_plugin("example_lib")
        if lib:
            ts = lib.format_timestamp(datetime.now())
            h  = lib.md5("hello")
    """

    # ------------------------------------------------------------------ #
    # 文本工具
    # ------------------------------------------------------------------ #

    def truncate(self, text: str, max_len: int = 50, ellipsis: str = "…") -> str:
        """截断文本，超出部分用省略号代替。

        Parameters
        ----------
        text : str
            待截断文本。
        max_len : int
            最大字符数（含省略号），默认 50。
        ellipsis : str
            省略符号，默认 "…"。
        """
        if len(text) <= max_len:
            return text
        return text[: max_len - len(ellipsis)] + ellipsis

    def strip_html(self, html: str) -> str:
        """移除 HTML 标签，返回纯文本。"""
        return re.sub(r"<[^>]+>", "", html).strip()

    # ------------------------------------------------------------------ #
    # 时间工具
    # ------------------------------------------------------------------ #

    def format_timestamp(self, dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """格式化 datetime 对象为字符串。

        Parameters
        ----------
        dt : datetime
            要格式化的时间。
        fmt : str
            strftime 格式字符串，默认 ``"%Y-%m-%d %H:%M:%S"``。
        """
        return dt.strftime(fmt)

    def friendly_duration(self, seconds: int) -> str:
        """将秒数转为人类可读的时长字符串。

        例如：``3661`` → ``"1 小时 1 分 1 秒"``。
        """
        if seconds < 0:
            return "0 秒"
        parts = []
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h:
            parts.append(f"{h} 小时")
        if m:
            parts.append(f"{m} 分")
        if s or not parts:
            parts.append(f"{s} 秒")
        return " ".join(parts)

    # ------------------------------------------------------------------ #
    # 哈希工具
    # ------------------------------------------------------------------ #

    def md5(self, text: str, encoding: str = "utf-8") -> str:
        """计算字符串的 MD5 哈希值（十六进制）。"""
        return hashlib.md5(text.encode(encoding)).hexdigest()

    def sha256(self, text: str, encoding: str = "utf-8") -> str:
        """计算字符串的 SHA-256 哈希值（十六进制）。"""
        return hashlib.sha256(text.encode(encoding)).hexdigest()


# --------------------------------------------------------------------------- #
# 依赖插件主类
# --------------------------------------------------------------------------- #

class Plugin(LibraryPlugin):
    """示例依赖插件主类。

    ``plugin.json`` 已声明 ``plugin_type: "library"``，
    此处 ``meta.plugin_type`` 仅作无清单时的回退。
    """

    meta = PluginMeta(
        id          = "example_lib",
        name        = "示例工具库",
        version     = "1.0.0",
        description = "演示依赖插件格式：提供文本、时间、哈希工具方法",
        plugin_type = PluginType.LIBRARY,
    )

    def __init__(self):
        self._interface = ExampleLibInterface()

    def on_load(self, api: PluginAPI) -> None:
        """依赖插件也可以使用 on_load 做初始化，但不要修改 UI。"""
        # 无需注册钩子，仅准备好接口对象即可
        pass

    def on_unload(self) -> None:
        pass

    def export(self) -> ExampleLibInterface:
        """返回公开接口对象供其他插件调用。

        Returns
        -------
        ExampleLibInterface
            包含文本、时间、哈希工具方法的接口对象。
        """
        return self._interface
