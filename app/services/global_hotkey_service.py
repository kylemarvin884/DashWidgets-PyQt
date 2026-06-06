"""
全局热键服务

使用 pynput 监听系统级热键，通过 Qt Signal 与主线程安全交互。

支持的热键格式（pynput 语法）：
    '<cmd>+<shift>+d'   → Win+Shift+D
    '<ctrl>+<alt>+t'    → Ctrl+Alt+T
    '<f12>'             → F12
"""
from __future__ import annotations

from typing import Callable
from PySide6.QtCore import QObject, Signal
from pynput import keyboard

from loguru import logger


class GlobalHotkeyService(QObject):
    """全局热键服务。

    使用示例::

        service = GlobalHotkeyService()
        service.register("toggle", "<cmd>+<shift>+d")
        service.triggered.connect(lambda name: print(f"热键触发: {name}"))
        service.start()
        ...
        service.stop()
    """

    triggered = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._listener: keyboard.GlobalHotKeys | None = None
        self._combos: dict[str, str] = {}

    def register(self, name: str, combo: str) -> None:
        """注册一个热键。

        Parameters
        ----------
        name : str
            热键标识名称，触发时通过 :signal:`triggered` 传出。
        combo : str
            pynput 组合键字符串，如 ``"<cmd>+<shift>+d"``。
        """
        self._combos[name] = combo
        logger.debug("注册全局热键: {} -> {}", name, combo)

    def start(self) -> None:
        """启动热键监听（在后台线程中运行，不阻塞 Qt 事件循环）。"""
        if self._listener is not None:
            logger.warning("全局热键服务已在运行")
            return

        if not self._combos:
            logger.warning("没有注册任何热键")
            return

        hotkey_map: dict[str, Callable[[], None]] = {}
        for name, combo in self._combos.items():
            # 使用默认参数捕获 name，避免闭包延迟绑定问题
            hotkey_map[combo] = lambda n=name: self._emit(n)

        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
            logger.info("全局热键服务已启动: {}", list(self._combos.values()))
        except Exception as e:
            logger.error("全局热键服务启动失败: {}", e)
            self._listener = None

    def stop(self) -> None:
        """停止热键监听。"""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as e:
                logger.warning("停止全局热键服务异常: {}", e)
            finally:
                self._listener = None
                logger.info("全局热键服务已停止")

    def _emit(self, name: str) -> None:
        """在后台线程中被调用，通过 Signal 安全地传递到 Qt 主线程。"""
        self.triggered.emit(name)
