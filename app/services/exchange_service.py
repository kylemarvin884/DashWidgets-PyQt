"""
汇率服务

使用 frankfurter.app（欧洲央行参考汇率，免费、无需 API Key）。
带本地缓存，供汇率小组件在工作线程调用。
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import urllib.request

from loguru import logger

_BASE = "CNY"
_QUOTES = ["USD", "EUR", "GBP", "JPY", "HKD"]
_API_URL = f"https://api.frankfurter.app/latest?from={_BASE}&to={','.join(_QUOTES)}"


@dataclass
class ExchangeData:
    """以 CNY 为基准的汇率：1 单位外币 = X 人民币"""
    rates: dict[str, float]  # {外币代码: 每1外币兑CNY}
    last_updated: float


class ExchangeService:
    """汇率服务 - 单例"""

    _instance: Optional["ExchangeService"] = None
    _CACHE_FILE: Path = Path(__file__).parent.parent.parent / "config" / "exchange_cache.json"
    _CACHE_DURATION: int = 3600  # 缓存1小时（参考汇率每日更新）

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._data: Optional[ExchangeData] = None
        self._fetch_lock = threading.Lock()
        self._load_cache()

    def get_rates(self, force_refresh: bool = False) -> ExchangeData:
        """
        获取汇率数据（CNY 基准）。缓存过期时发起网络请求。

        Raises
        ------
        RuntimeError
            网络请求失败且无任何缓存可用时抛出。
        """
        if not force_refresh and self._data:
            if time.time() - self._data.last_updated < self._CACHE_DURATION:
                return self._data

        with self._fetch_lock:
            if not force_refresh and self._data:
                if time.time() - self._data.last_updated < self._CACHE_DURATION:
                    return self._data

            try:
                req = urllib.request.Request(_API_URL, headers={"User-Agent": "DashWidgets/1.0"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                base_rates = payload.get("rates", {})  # {外币: 每1 CNY 兑外币}
                if not base_rates:
                    raise ValueError("API 返回为空")

                # 换算为 "1 外币 = X CNY"，便于直接展示
                rates = {}
                for code, per_cny in base_rates.items():
                    if per_cny:
                        rates[code] = 1.0 / float(per_cny)

                self._data = ExchangeData(rates=rates, last_updated=time.time())
                self._save_cache()
                logger.info("获取汇率成功: {}", ", ".join(f"{k}={v:.4f}" for k, v in rates.items()))
                return self._data
            except Exception as e:
                logger.error(f"获取汇率失败: {e}")
                if self._data:
                    return self._data  # 离线时回退到旧缓存
                raise RuntimeError(f"获取汇率失败: {e}") from e

    # ------------------------------------------------------------------ #
    # 缓存
    # ------------------------------------------------------------------ #

    def _load_cache(self):
        if not self._CACHE_FILE.exists():
            return
        try:
            with open(self._CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            rates = data.get("rates", {})
            if rates:
                self._data = ExchangeData(
                    rates={k: float(v) for k, v in rates.items()},
                    last_updated=float(data.get("last_updated", 0)),
                )
                logger.info("汇率缓存已加载")
        except Exception as e:
            logger.error(f"加载汇率缓存失败: {e}")

    def _save_cache(self):
        try:
            self._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self._CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "rates": self._data.rates if self._data else {},
                    "last_updated": self._data.last_updated if self._data else 0,
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存汇率缓存失败: {e}")


def get_exchange_service() -> ExchangeService:
    """获取汇率服务单例"""
    return ExchangeService()
