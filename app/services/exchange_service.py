"""
汇率服务

使用 frankfurter.app（欧洲央行参考汇率，免费、无需 API Key）。
带本地缓存，供汇率小组件在工作线程调用。支持任意基准货币与
目标货币列表（API 单次请求可携带多货币）。
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


@dataclass(frozen=True)
class PairKey:
    """一个货币对的请求标识（frankfurter 以 EUR 为中转，任意对均可换算）"""
    base: str
    quote: str

    @staticmethod
    def of(base: str, quote: str) -> "PairKey":
        return PairKey(base.upper(), quote.upper())


@dataclass
class ExchangeData:
    """任意货币对的汇率：1 单位 base = X quote"""
    rates: dict[str, float]  # {"BASE/QUOTE": 每1 base 兑 quote 数}
    last_updated: float

    def rate_for(self, base: str, quote: str) -> Optional[float]:
        return self.rates.get(f"{base.upper()}/{quote.upper()}")


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
        获取汇率数据。缓存过期时发起一次网络请求。

        以 EUR 为中转：一次请求取 EUR→各货币的汇率，任意货币对
        (A/B) 的汇率 = EUR→B ÷ EUR→A。缓存里保存的是 EUR→X 的
        原始值，展示时按需换算，支持任意货币组合。

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
                symbols = ",".join(self._SUPPORTED_CURRENCIES)
                url = f"https://api.frankfurter.app/latest?from=EUR&to={symbols}"
                req = urllib.request.Request(url, headers={"User-Agent": "DashWidgets/1.0"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                rates = payload.get("rates", {})
                if not rates:
                    raise ValueError("API 返回为空")
                rates["EUR"] = 1.0  # 基准本身

                self._data = ExchangeData(rates=rates, last_updated=time.time())
                self._save_cache()
                logger.info("获取汇率成功: {} 个货币", len(rates))
                return self._data
            except Exception as e:
                logger.error(f"获取汇率失败: {e}")
                if self._data:
                    return self._data  # 离线时回退到旧缓存
                raise RuntimeError(f"获取汇率失败: {e}") from e

    # 支持的货币（frankfurter 全集）
    _SUPPORTED_CURRENCIES = [
        "USD", "EUR", "GBP", "JPY", "HKD", "CNY", "KRW", "AUD", "CAD", "CHF",
        "SGD", "NZD", "INR", "THB", "MYR", "SEK", "NOK", "DKK", "PLN", "CZK",
    ]

    @staticmethod
    def cross_rate(data: ExchangeData, base: str, quote: str) -> Optional[float]:
        """计算任意货币对汇率：1 base = ? quote（EUR 中转换算）"""
        base = base.upper()
        quote = quote.upper()
        if base == quote:
            return 1.0
        r_base = data.rates.get(base)
        r_quote = data.rates.get(quote)
        if not r_base or not r_quote:
            return None
        return r_quote / r_base

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
