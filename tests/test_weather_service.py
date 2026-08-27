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
        """已知天气代码转换测试（icon 为 FluentIcon 名称）"""
        svc = WeatherService()

        test_cases = [
            (0, "晴朗", "SUNNY"),
            (1, "大部晴朗", "PARTLY_SUNNY"),
            (2, "多云", "CLOUD"),
            (3, "阴天", "CLOUD"),
            (45, "有雾", "FOG"),
            (61, "小雨", "RAIN"),
            (71, "小雪", "SNOW"),
            (95, "雷暴", "THUNDER"),
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
        assert icon == "WEATHER"

    def test_singleton(self):
        """单例模式测试"""
        svc1 = WeatherService()
        svc2 = WeatherService()
        assert svc1 is svc2

    def test_cache_load_save(self, tmp_path: Path, monkeypatch):
        """缓存加载/保存测试（含城市信息持久化）"""
        cache_file = tmp_path / "weather_cache.json"
        monkeypatch.setattr("app.services.weather_service.WeatherService._CACHE_FILE", cache_file)

        # 先创建并保存缓存
        svc1 = WeatherService()
        svc1._weather = WeatherData(
            temperature=22.0,
            condition="多云",
            icon="CLOUD",
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

    def test_get_weather_uses_cache(self):
        """缓存未过期时不发起网络请求"""
        import time

        svc = WeatherService()
        svc._weather = WeatherData(
            temperature=20.0, condition="晴朗", icon="SUNNY",
            humidity=50, wind_speed=5.0, city="北京", country="CN",
            last_updated=time.time(),
        )
        # get_location 若被调用会走网络；这里直接返回证明命中缓存路径
        result = svc.get_weather()
        assert result is svc._weather

    def test_get_weather_concurrent_dedup(self, monkeypatch):
        """并发调用只触发一次真实获取"""
        import threading
        import time

        svc = WeatherService()
        calls = {"n": 0}

        def _fake_location(self):
            return (39.9, 116.4)

        def _fake_location_info(self):
            return ("北京", "CN")

        monkeypatch.setattr(WeatherService, "get_location", _fake_location)
        monkeypatch.setattr(WeatherService, "get_location_info", _fake_location_info)

        def _slow_fetch(req, timeout=0):
            calls["n"] += 1
            time.sleep(0.05)

            class _Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return ('{"current": {"temperature_2m": 21, "relative_humidity_2m": 40,'
                            ' "weather_code": 0, "wind_speed_10m": 3}}').encode()

            return _Resp()

        monkeypatch.setattr("app.services.weather_service.urllib.request.urlopen", _slow_fetch)

        results = []

        def _worker():
            results.append(svc.get_weather())

        threads = [threading.Thread(target=_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert calls["n"] == 1, f"expected 1 fetch, got {calls['n']}"
        assert all(r is not None and r.temperature == 21 for r in results)
