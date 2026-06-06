"""
自定义 URL Scheme 注册与解析服务

支持将 ``dashwidgets://open/<view>`` 形式的 URL 映射到对应视图。

Windows 注册表结构（HKCU）：

    HKEY_CURRENT_USER\\Software\\Classes\\dashwidgets
        (Default)      = "URL:dashwidgets Protocol"
        URL Protocol   = ""
        \\shell\\open\\command
            (Default)  = '"<python>" "<main.py>" --url "%1"'
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

from app.constants import URL_SCHEME, URL_VIEW_MAP
from loguru import logger

# Windows 注册表仅在 Windows 下可用
_WIN = sys.platform == "win32"
if _WIN:
    import winreg
    import ctypes


def _python_exe() -> str:
    """返回当前 Python 解释器路径（Windows 下优先使用 pythonw.exe 避免弹出终端）"""
    exe = sys.executable
    if _WIN and exe.lower().endswith("python.exe"):
        exe = exe[:-4] + "pythonw.exe"
        if not Path(exe).exists():
            exe = sys.executable  # 回退
    return exe


def _main_script() -> str:
    """返回 main.py 的绝对路径"""
    return str(Path(__file__).resolve().parent.parent.parent / "main.py")


def _registry_key() -> str:
    """注册表键名"""
    return URL_SCHEME


def _open_command() -> str:
    """写入注册表的启动命令（Windows 风格）"""
    exe = _python_exe()
    main = _main_script()
    return f'"{exe}" "{main}" --url "%1"'


# --------------------------------------------------------------------------- #
# 公开 API
# --------------------------------------------------------------------------- #

def is_registered() -> bool:
    """检查当前 URL scheme 是否已在系统注册"""
    if not _WIN:
        return False
    try:
        key_path = f"Software\\Classes\\{_registry_key()}\\shell\\open\\command"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            val, _ = winreg.QueryValueEx(k, "")
            return bool(val)
    except OSError:
        return False


def register() -> tuple[bool, str]:
    """
    在 HKCU 注册 URL scheme。

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """
    if not _WIN:
        return False, "URL Scheme 注册仅支持 Windows"

    try:
        root = f"Software\\Classes\\{_registry_key()}"

        # 根键
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"URL:{URL_SCHEME} Protocol")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")

        # shell\open\command
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                               f"{root}\\shell\\open\\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _open_command())

        logger.info("URL Scheme '{}://' 注册成功", URL_SCHEME)
        return True, f"已成功注册 {URL_SCHEME}:// 协议"

    except Exception as exc:  # noqa: BLE001
        msg = f"注册失败：{exc}"
        logger.error(msg)
        return False, msg


def unregister() -> tuple[bool, str]:
    """
    从 HKCU 移除 URL scheme 注册。

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """
    if not _WIN:
        return False, "URL Scheme 注册仅支持 Windows"

    def _del_tree(key_path: str) -> None:
        """递归删除注册表键（含子键）"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                                 access=winreg.KEY_ALL_ACCESS) as k:
                while True:
                    try:
                        sub = winreg.EnumKey(k, 0)
                        _del_tree(f"{key_path}\\{sub}")
                    except OSError:
                        break
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except OSError:
            pass

    root = f"Software\\Classes\\{_registry_key()}"
    _del_tree(f"{root}\\shell\\open\\command")
    _del_tree(f"{root}\\shell\\open")
    _del_tree(f"{root}\\shell")
    _del_tree(root)

    logger.info("URL Scheme '{}://' 已注销", URL_SCHEME)
    return True, f"已移除 {URL_SCHEME}:// 协议注册"


def parse_url(url: str) -> str | None:
    """
    解析 URL 并返回目标视图的 objectName。

    格式：``dashwidgets://open/<view_key>``

    Parameters
    ----------
    url : str
        完整 URL 字符串，例如 ``dashwidgets://open/widgets``

    Returns
    -------
    str | None
        视图的 ``objectName``，若无法识别则返回 ``None``
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != URL_SCHEME:
            return None

        # 路径格式：/open/<view_key>  或  open/<view_key>（host 作为第一段时）
        parts = parsed.path.strip("/").split("/")
        # urlparse 对 dashwidgets://open/widgets 会把 "open" 放到 netloc
        if parsed.netloc:
            parts = [parsed.netloc] + parts

        if len(parts) >= 2 and parts[0].lower() == "open":
            view_key = parts[1].lower()
            return URL_VIEW_MAP.get(view_key)
    except Exception:  # noqa: BLE001
        pass
    return None


# --------------------------------------------------------------------------- #
# .dw 文件关联注册
# --------------------------------------------------------------------------- #

_DW_EXT = ".dw"


def register_dw_file_association() -> tuple[bool, str]:
    """
    在 Windows 系统中注册 .dw 文件关联。

    注册表结构（HKCU）::

        HKEY_CURRENT_USER\\Software\\Classes\\.dw
            (Default) = "DashWidgets.Plugin"

        HKEY_CURRENT_USER\\Software\\Classes\\DashWidgets.Plugin
            (Default) = "DashWidgets 插件"

        HKEY_CURRENT_USER\\Software\\Classes\\DashWidgets.Plugin\\shell\\open\\command
            (Default) = '"<python>" "<main.py>" --import "%1"'

        HKEY_CURRENT_USER\\Software\\Classes\\DashWidgets.Plugin\\DefaultIcon
            (Default) = "<main.py>,0"

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """
    if not _WIN:
        return False, ".dw 文件关联注册仅支持 Windows"

    try:
        main = _main_script()

        # .dw 扩展名 → ProgID 映射
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.dw") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "DashWidgets.Plugin")

        # ProgID 描述
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Classes\DashWidgets.Plugin") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "DashWidgets 插件")

        # 默认图标
        icon_path = str(Path(main).parent / "assets" / "images" / "logo.ico")
        if not Path(icon_path).exists():
            icon_path = main  # 回退到 exe 图标
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Classes\DashWidgets.Plugin\DefaultIcon") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{icon_path}",0')

        # 打开命令（使用 pythonw.exe 避免弹出终端）
        exe_noconsole = _python_exe()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Classes\DashWidgets.Plugin\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe_noconsole}" "{main}" --import "%1"')

        # 通知 Windows 刷新图标缓存
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)

        logger.info(".dw 文件关联注册成功")
        return True, "已成功注册 .dw 文件关联"

    except Exception as exc:  # noqa: BLE001
        msg = f"注册 .dw 文件关联失败：{exc}"
        logger.error(msg)
        return False, msg


def unregister_dw_file_association() -> tuple[bool, str]:
    """
    从 Windows 系统移除 .dw 文件关联。

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """
    if not _WIN:
        return False, ".dw 文件关联注册仅支持 Windows"

    def _del_tree(key_path: str) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                                 access=winreg.KEY_ALL_ACCESS) as k:
                while True:
                    try:
                        sub = winreg.EnumKey(k, 0)
                        _del_tree(f"{key_path}\\{sub}")
                    except OSError:
                        break
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except OSError:
            pass

    try:
        _del_tree(r"Software\Classes\DashWidgets.Plugin\shell\open\command")
        _del_tree(r"Software\Classes\DashWidgets.Plugin\shell\open")
        _del_tree(r"Software\Classes\DashWidgets.Plugin\shell")
        _del_tree(r"Software\Classes\DashWidgets.Plugin\DefaultIcon")
        _del_tree(r"Software\Classes\DashWidgets.Plugin")
        _del_tree(r"Software\Classes\.dw")

        # 通知 Windows 刷新图标缓存
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)

        logger.info(".dw 文件关联已注销")
        return True, "已移除 .dw 文件关联"
    except Exception as exc:
        return False, f"注销失败：{exc}"


def is_dw_association_registered() -> bool:
    """检查 .dw 文件关联是否已注册"""
    if not _WIN:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Classes\.dw") as k:
            val, _ = winreg.QueryValueEx(k, "")
            return val == "DashWidgets.Plugin"
    except OSError:
        return False
