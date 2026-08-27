"""
系统指标后台采样服务

psutil 采样（CPU/内存/磁盘/网速）统一放在单个后台线程执行，
组件通过 Qt 信号接收结果（自动排队回 UI 线程），避免在 UI 线程上
执行可能阻塞的调用（机械盘上的 disk_usage 尤其明显）。

引用计数启停：所有订阅者退出后才结束采样线程。
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

from loguru import logger

_SYSTEM_INTERVAL = 2.0   # 秒：CPU/内存/磁盘采样周期
_NETWORK_INTERVAL = 1.5  # 秒：网速采样周期
_TICK = 0.25             # 秒：调度粒度


class SystemStatsService(QObject):
    """系统/网络指标采样 — 单例"""

    _instance: Optional["SystemStatsService"] = None

    # payload 均为 dict；从工作线程发射，Qt 自动排队到接收者所在线程
    system_stats = Signal(object)   # {cpu, cpu_ghz, mem_percent, mem_used_gb, mem_total_gb, disk_percent, disk_used_gb, disk_total_gb}
    network_stats = Signal(object)  # {up_bps, down_bps, sent_bytes, recv_bytes}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True
        self._lock = threading.Lock()
        self._system_refs = 0
        self._network_refs = 0
        self._running = False
        self._wake = threading.Event()
        # 网速计算用的上一次计数
        self._last_sent = 0
        self._last_recv = 0
        self._last_net_time = 0.0
        self._last_sys_time = 0.0
        self._last_net_time_monotonic = 0.0

    # ------------------------------------------------------------------ #
    # 订阅（引用计数）
    # ------------------------------------------------------------------ #

    def acquire_system(self) -> None:
        with self._lock:
            self._system_refs += 1
            self._ensure_thread()

    def release_system(self) -> None:
        with self._lock:
            self._system_refs = max(0, self._system_refs - 1)
            self._maybe_stop()

    def acquire_network(self) -> None:
        with self._lock:
            self._network_refs += 1
            self._ensure_thread()

    def release_network(self) -> None:
        with self._lock:
            self._network_refs = max(0, self._network_refs - 1)
            self._maybe_stop()

    def _ensure_thread(self) -> None:
        if self._running:
            return
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True, name="DashWidgetsStats")
        t.start()

    def _maybe_stop(self) -> None:
        if self._system_refs == 0 and self._network_refs == 0:
            self._running = False
            self._wake.set()

    # ------------------------------------------------------------------ #
    # 采样循环
    # ------------------------------------------------------------------ #

    def _loop(self) -> None:
        # 初始化网速基线
        try:
            import psutil
            net = psutil.net_io_counters()
            self._last_sent = net.bytes_sent
            self._last_recv = net.bytes_recv
        except Exception as e:
            logger.warning("网络计数初始化失败: {}", e)
        self._last_net_time_monotonic = time.monotonic()
        self._last_sys_time = 0.0

        while self._running:
            with self._lock:
                need_sys = self._system_refs > 0
                need_net = self._network_refs > 0

            now = time.monotonic()

            if need_sys and now - self._last_sys_time >= _SYSTEM_INTERVAL:
                self._last_sys_time = now
                payload = self._sample_system()
                if payload is not None:
                    self.system_stats.emit(payload)

            if need_net and now - self._last_net_time_monotonic >= _NETWORK_INTERVAL:
                elapsed = now - self._last_net_time_monotonic
                self._last_net_time_monotonic = now
                payload = self._sample_network(elapsed)
                if payload is not None:
                    self.network_stats.emit(payload)

            self._wake.wait(_TICK)
            self._wake.clear()

    @staticmethod
    def _sample_system() -> dict | None:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            freq = psutil.cpu_freq()
            return {
                "cpu": cpu,
                "cpu_ghz": (freq.current / 1000) if freq and freq.current else 0.0,
                "mem_percent": mem.percent,
                "mem_used_gb": mem.used / 1024 ** 3,
                "mem_total_gb": mem.total / 1024 ** 3,
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used / 1024 ** 3,
                "disk_total_gb": disk.total / 1024 ** 3,
            }
        except Exception as e:
            logger.warning("系统指标采样失败: {}", e)
            return None

    def _sample_network(self, elapsed: float) -> dict | None:
        try:
            import psutil
            net = psutil.net_io_counters()
            dt = max(elapsed, 0.001)
            payload = {
                "up_bps": max(0, net.bytes_sent - self._last_sent) / dt,
                "down_bps": max(0, net.bytes_recv - self._last_recv) / dt,
                "sent_bytes": net.bytes_sent,
                "recv_bytes": net.bytes_recv,
            }
            self._last_sent = net.bytes_sent
            self._last_recv = net.bytes_recv
            return payload
        except Exception as e:
            logger.warning("网络指标采样失败: {}", e)
            return None


def get_system_stats_service() -> SystemStatsService:
    """获取系统指标采样服务单例"""
    return SystemStatsService()
