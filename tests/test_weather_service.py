"""测试天气服务"""
from __future__ import annotations

import pytest
from pathlib import Path

from app.services.weather_service import WeatherService, WeatherData


class TestWeatherData:
    """WeatherData 单元测试"""

    def test_dataclass_creation(self):
        """数据类创建测试"""
        data = WeatherData(
            temperature=25.5,
            condition="晴朗",
            icon="☀️",
            humidity=60,
            wind_speed=12.3,
            city="北京",
            country="China",
            last_updated=1234567890.0,
        )
        assert data.temperature == 25.5
        assert data.condition == "晴朗"
        assert data.icon == "☀️"
        assert data.humidity == 60
        assert data.wind_speed == 12.3
        assert data.city == "北京"
        assert data.country == "China"


class TestWeatherService:
    """WeatherService 单元测试"""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self, tmp_path: Path, monkeypatch):
        """重置单例并使用临时缓存文件"""
        WeatherService._instance = None
        if hasattr(WeatherService, "_initialized"):
            delattr(WeatherService, "_initialized")

        cache_file = tmp_path / "weather_cache.json"
        monkeypatch.setattr("app.services.weather_service.WeatherService._CACHE_FILE", cache_file)
        yield

        WeatherService._instance = None
        if hasattr(WeatherService, "_initialized"):
            delattr(WeatherService, "_initialized")

    def test_weather_code_to_text_known_codes(self):
        """已知天气代码转换测试"""
        svc = WeatherService()

        test_cases = [
            (0, "晴朗", "☀️"),
            (1, "大部晴朗", "🌤️"),
            (2, "多云", "⛅"),
            (3, "阴天", "☁️"),
            (45, "有雾", "🌫️"),
            (61, "小雨", "🌧️"),
            (71, "小雪", "🌨️"),
            (95, "雷暴", "⛈️"),
        ]

        for code, expected_condition, expected_icon in test_cases:
            condition, icon = svc._weather_code_to_text(code)
            assert condition == expected_condition, f"Code {code} condition mismatch"
            assert icon == expected_icon, f"Code {code} icon mismatch"

    def test_weather_code_to_text_unknown(self):
        """未知天气代码应返回默认值"""
        svc = WeatherService()
        condition, icon = svc._weather_code_to_text(99999)
        assert condition == "未知"
        assert icon == "🌡️"

    def test_singleton(self):
        """单例模式测试"""
        svc1 = WeatherService()
        svc2 = WeatherService()
        assert svc1 is svc2

    def test_cache_load_save(self, tmp_path: Path, monkeypatch):
        """缓存加载/保存测试"""
        cache_file = tmp_path / "weather_cache.json"
        monkeypatch.setattr("app.services.weather_service.WeatherService._CACHE_FILE", cache_file)

        # 先创建并保存缓存
        svc1 = WeatherService()
        svc1._weather = WeatherData(
            temperature=22.0,
            condition="多云",
            icon="⛅",
            humidity=55,
            wind_speed=8.5,
            city="上海",
            country="China",
            last_updated=1234567890.0,
        )
        svc1._location = (31.2304, 121.4737)
        svc1._save_cache()

        assert cache_file.exists()

        # 重置单例后重新加载
        WeatherService._instance = None
        if hasattr(WeatherService, "_initialized"):
            delattr(WeatherService, "_initialized")

        svc2 = WeatherService()
        assert svc2._weather is not None
        assert svc2._weather.city == "上海"
        assert svc2._weather.temperature == 22.0
        assert svc2._location == (31.2304, 121.4737)
