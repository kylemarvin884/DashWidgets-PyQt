"""
小组件使用时长追踪服务
记录每个小组件的使用时长，用于推荐算法
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app.constants import CONFIG_DIR


class UsageTracker:
    """小组件使用时长追踪器"""

    _instance: "UsageTracker | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._data_file = CONFIG_DIR / "usage_stats.json"
        self._usage_data: dict[str, dict[str, Any]] = {}
        self._session_start: dict[str, datetime] = {}  # 当前会话的开始时间
        self._load()

    def _load(self):
        """加载使用数据"""
        if self._data_file.exists():
            try:
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    self._usage_data = json.load(f)
                logger.info(f"加载使用统计数据: {len(self._usage_data)} 个组件")
            except Exception as e:
                logger.warning(f"加载使用统计数据失败: {e}")
                self._usage_data = {}

    def _save(self):
        """保存使用数据"""
        try:
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(self._usage_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存使用统计数据失败: {e}")

    def start_session(self, widget_id: str):
        """开始追踪某个组件的使用会话"""
        self._session_start[widget_id] = datetime.now()
        logger.debug(f"开始追踪组件使用: {widget_id}")

    def end_session(self, widget_id: str):
        """结束追踪某个组件的使用会话"""
        if widget_id not in self._session_start:
            return

        start_time = self._session_start.pop(widget_id)
        duration = (datetime.now() - start_time).total_seconds()

        if widget_id not in self._usage_data:
            self._usage_data[widget_id] = {
                "total_time": 0,
                "session_count": 0,
                "last_used": None,
            }

        self._usage_data[widget_id]["total_time"] += duration
        self._usage_data[widget_id]["session_count"] += 1
        self._usage_data[widget_id]["last_used"] = datetime.now().isoformat()

        self._save()
        logger.debug(f"结束追踪组件使用: {widget_id}, 本次时长: {duration:.1f}s")

    def get_total_time(self, widget_id: str) -> float:
        """获取某个组件的总使用时长（秒）"""
        if widget_id in self._usage_data:
            return self._usage_data[widget_id].get("total_time", 0)
        return 0

    def get_session_count(self, widget_id: str) -> int:
        """获取某个组件的使用次数"""
        if widget_id in self._usage_data:
            return self._usage_data[widget_id].get("session_count", 0)
        return 0

    def get_score(self, widget_id: str) -> float:
        """
        计算某个组件的推荐分数
        分数 = 总时长(小时) * 10 + 使用次数 * 5
        """
        total_time_hours = self.get_total_time(widget_id) / 3600
        session_count = self.get_session_count(widget_id)
        return total_time_hours * 10 + session_count * 5

    def get_ranked_widgets(self, limit: int = 10) -> list[tuple[str, float]]:
        """
        获取按分数排名的组件列表
        返回: [(widget_id, score), ...]
        """
        scores = [(wid, self.get_score(wid)) for wid in self._usage_data.keys()]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:limit]

    def get_usage_data(self) -> dict[str, dict[str, Any]]:
        """获取所有使用数据"""
        return self._usage_data.copy()

    def format_duration(self, seconds: float) -> str:
        """格式化时长显示"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}分钟"
        else:
            hours = seconds / 3600
            if hours < 24:
                return f"{hours:.1f}小时"
            else:
                days = hours / 24
                return f"{days:.1f}天"

    @classmethod
    def instance(cls) -> "UsageTracker":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# 别名，方便导入
UsageStatsService = UsageTracker
