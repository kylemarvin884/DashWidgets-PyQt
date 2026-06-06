"""
开机自启服务

支持在 Windows 下通过注册表实现开机自启。

Windows 注册表结构（HKCU）：

    HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
        DashWidgets = '"<python>" "<main.py>" --autostart'
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

# Windows 注册表仅在 Windows 下可用
_WIN = sys.platform == "win32"
if _WIN:
    import winreg


# 注册表键名
_APP_NAME = "DashWidgets"


def _python_exe() -> str:
    """返回当前 Python 解释器路径"""
    return sys.executable


def _main_script() -> str:
    """返回 main.py 的绝对路径"""
    return str(Path(__file__).resolve().parent.parent.parent / "main.py")


def _startup_command() -> str:
    """写入注册表的启动命令（Windows 风格）"""
    exe = _python_exe()
    main = _main_script()
    return f'"{exe}" "{main}" --autostart'


# --------------------------------------------------------------------------- #
# 公开 API
# --------------------------------------------------------------------------- #

def is_autostart_enabled() -> bool:
    """检查开机自启是否已启用"""
    if not _WIN:
        return False
    try:
        key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            val, _ = winreg.QueryValueEx(k, _APP_NAME)
            return bool(val)
    except OSError:
        return False


def enable_autostart() -> tuple[bool, str]:
    """
    启用开机自启。

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """
    if not _WIN:
        return False, "开机自启仅支持 Windows"

    try:
        key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_ALL_ACCESS) as k:
            winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, _startup_command())

        logger.info("开机自启已启用")
        return True, "已启用开机自启"

    except Exception as exc:
        msg = f"启用开机自启失败：{exc}"
        logger.error(msg)
        return False, msg


def disable_autostart() -> tuple[bool, str]:
    """
    禁用开机自启。

    Returns
    -------
    tuple[bool, str]
        (success, message)
    """
    if not _WIN:
        return False, "开机自启仅支持 Windows"

    try:
        key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_ALL_ACCESS) as k:
            winreg.DeleteValue(k, _APP_NAME)

        logger.info("开机自启已禁用")
        return True, "已禁用开机自启"

    except FileNotFoundError:
        return True, "开机自启未启用"
    except Exception as exc:
        msg = f"禁用开机自启失败：{exc}"
        logger.error(msg)
        return False, msg


# 兼容旧名称
is_enabled = is_autostart_enabled
enable = enable_autostart
disable = disable_autostart
