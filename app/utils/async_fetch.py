"""
通用后台任务工具

把阻塞操作（网络请求、文件 IO 等）丢进 QThreadPool 工作线程执行，
完成后通过 Qt 信号自动排队回 UI 线程。用法：

    self._task = run_in_background(fn, self._on_done)

调用方必须持有返回对象（防止被 GC），回调签名 f(result)。
工作函数抛出的异常会作为 result 传入（Exception 实例）。
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    done = Signal(object)


class _FnTask(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: TaskSignals):
        super().__init__()
        self._fn = fn
        self._signals = signals

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as e:  # noqa: BLE001 — 异常作为结果回传
            result = e
        try:
            self._signals.done.emit(result)
        except RuntimeError:
            # 接收方（组件）在任务完成前已被销毁，安全忽略
            pass


def run_in_background(fn: Callable[[], Any], on_done: Callable[[Any], None]) -> TaskSignals:
    """在工作线程执行 fn，完成后在 UI 线程调用 on_done(result)"""
    signals = TaskSignals()
    signals.done.connect(on_done)
    QThreadPool.globalInstance().start(_FnTask(fn, signals))
    return signals
