"""
天气服务

支持自动检测位置并获取实时天气数据。
使用 Open-Meteo API（免费、无需API Key）
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

from loguru import logger


@dataclass
class WeatherData:
    """天气数据"""
    temperature: float
    condition: str
    icon: str
    humidity: int
    wind_speed: float
    city: str
    country: str
    last_updated: float


class WeatherService:
    """天气服务 - 单例"""

    _instance: Optional["WeatherService"] = None
    _CACHE_FILE: Path = Path(__file__).parent.parent.parent / "config" / "weather_cache.json"
    _CACHE_DURATION: int = 1800  # 缓存30分钟

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._weather: Optional[WeatherData] = None
        self._location: Optional[tuple[float, float]] = None
        self._load_cache()

    # ------------------------------------------------------------------ #
    # 位置检测
    # ------------------------------------------------------------------ #

    def get_location(self) -> tuple[float, float] | None:
        """
        获取当前位置（经纬度）

        Returns
        -------
        tuple[float, float] | None
            (latitude, longitude) 或 None
        """
        if self._location:
            return self._location

        try:
            # 使用 ip-api.com 获取位置（免费、无需API Key）
            url = "http://ip-api.com/json/?fields=status,lat,lon,city,country"
            req = urllib.request.Request(url, headers={"User-Agent": "DashWidgets/1.0"})

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("status") == "success":
                    lat = data.get("lat", 0)
                    lon = data.get("lon", 0)
                    self._location = (lat, lon)
                    logger.info(f"检测到位置: {lat}, {lon}")
                    return self._location
                else:
                    logger.warning("IP定位失败")
                    return None

        except Exception as e:
            logger.error(f"获取位置失败: {e}")
            return None

    def get_location_info(self) -> tuple[str, str]:
        """
        获取位置信息（城市、国家）

        Returns
        -------
        tuple[str, str]
            (city, country)
        """
        try:
            url = "http://ip-api.com/json/?fields=status,city,country"
            req = urllib.request.Request(url, headers={"User-Agent": "DashWidgets/1.0"})

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("status") == "success":
                    city = data.get("city", "未知")
                    country = data.get("country", "")
                    return city, country
                else:
                    return "未知", ""

        except Exception as e:
            logger.error(f"获取位置信息失败: {e}")
            return "未知", ""

    # ------------------------------------------------------------------ #
    # 天气获取
    # ------------------------------------------------------------------ #

    def get_weather(self, force_refresh: bool = False) -> WeatherData | None:
        """
        获取天气数据

        Parameters
        ----------
        force_refresh : bool
            是否强制刷新

        Returns
        -------
        WeatherData | None
            天气数据或None
        """
        # 检查缓存
        if not force_refresh and self._weather:
            if time.time() - self._weather.last_updated < self._CACHE_DURATION:
                return self._weather

        # 获取位置
        location = self.get_location()
        if not location:
            # 使用默认位置（北京）
            location = (39.9042, 116.4074)
            logger.info("使用默认位置: 北京")

        lat, lon = location

        try:
            # 使用 Open-Meteo API 获取天气（免费、无需API Key）
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=auto"

            req = urllib.request.Request(url, headers={"User-Agent": "DashWidgets/1.0"})

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

                current = data.get("current", {})

                # 解析天气数据
                temperature = current.get("temperature_2m", 0)
                humidity = current.get("relative_humidity_2m", 0)
                wind_speed = current.get("wind_speed_10m", 0)
                weather_code = current.get("weather_code", 0)

                # 获取城市名称
                city, country = self.get_location_info()

                # 转换天气代码为文字描述和图标
                condition, icon = self._weather_code_to_text(weather_code)

                self._weather = WeatherData(
                    temperature=temperature,
                    condition=condition,
                    icon=icon,
                    humidity=humidity,
                    wind_speed=wind_speed,
                    city=city,
                    country=country,
                    last_updated=time.time(),
                )

                self._save_cache()
                logger.info(f"获取天气成功: {city} {temperature}°C {condition}")
                return self._weather

        except Exception as e:
            logger.error(f"获取天气失败: {e}")
            # 返回缓存数据
            if self._weather:
                return self._weather
            return None

    def _weather_code_to_text(self, code: int) -> tuple[str, str]:
        """
        将 WMO 天气代码转换为文字描述和 FluentIcon 名称

        https://open-meteo.com/en/docs#weathervariables=weather_code
        """
        weather_map = {
            0: ("晴朗", "SUNNY"),
            1: ("大部晴朗", "PARTLY_SUNNY"),
            2: ("多云", "CLOUD"),
            3: ("阴天", "CLOUD"),
            45: ("有雾", "FOG"),
            48: ("雾凇", "FOG"),
            51: ("小毛毛雨", "RAIN"),
            53: ("中毛毛雨", "RAIN"),
            55: ("大毛毛雨", "RAIN"),
            56: ("冻毛毛雨", "SNOW"),
            57: ("强冻毛毛雨", "SNOW"),
            61: ("小雨", "RAIN"),
            63: ("中雨", "RAIN"),
            65: ("大雨", "RAIN"),
            66: ("冻雨", "SNOW"),
            67: ("强冻雨", "SNOW"),
            71: ("小雪", "SNOW"),
            73: ("中雪", "SNOW"),
            75: ("大雪", "SNOW"),
            77: ("雪粒", "SNOW"),
            80: ("小阵雨", "RAIN"),
            81: ("中阵雨", "RAIN"),
            82: ("大阵雨", "RAIN"),
            85: ("小阵雪", "SNOW"),
            86: ("大阵雪", "SNOW"),
            95: ("雷暴", "THUNDER"),
            96: ("雷暴伴小冰雹", "THUNDER"),
            99: ("雷暴伴大冰雹", "THUNDER"),
        }

        return weather_map.get(code, ("未知", "WEATHER"))

    # ------------------------------------------------------------------ #
    # 缓存
    # ------------------------------------------------------------------ #

    def _load_cache(self):
        """加载缓存"""
        if not self._CACHE_FILE.exists():
            return

        try:
            with open(self._CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._location = tuple(data.get("location", [])) if data.get("location") else None

            weather_data = data.get("weather")
            if weather_data:
                self._weather = WeatherData(**weather_data)

            logger.info("天气缓存已加载")

        except Exception as e:
            logger.error(f"加载天气缓存失败: {e}")

    def _save_cache(self):
        """保存缓存"""
        try:
            self._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "location": list(self._location) if self._location else None,
                "weather": self._weather.__dict__ if self._weather else None,
            }

            with open(self._CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"保存天气缓存失败: {e}")


def get_weather_service() -> WeatherService:
    """获取天气服务单例"""
    return WeatherService()
