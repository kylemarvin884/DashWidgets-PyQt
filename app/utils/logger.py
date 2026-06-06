"""
全局日志配置 — 基于 loguru

使用方式（任意模块）::

    from app.utils.logger import logger
    logger.info("消息")
    logger.debug("调试")
    logger.warning("警告")
    logger.error("错误")

内存日志（供调试面板实时读取）::

    from app.utils.logger import memory_log
    records = memory_log.get()   # -> list[dict]  每条含 level / text
"""
import sys
from collections import deque
from typing import Any
from loguru import logger

from app.constants import LOG_DIR

# 确保日志目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 配置loguru
logger.remove()  # 移除默认的handler

# 添加文件输出
_ = logger.add(
    LOG_DIR / "dashwidgets_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    level="INFO",
    encoding="utf-8",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# 添加控制台输出
_ = logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)


# ────────────────────────────────────────────────────────────────────────── #
# 内存 sink —— 保留最近 2000 条，供调试面板实时查看
# ────────────────────────────────────────────────────────────────────────── #

class _MemoryLog:
    """线程安全的环形缓冲日志仓库。"""

    def __init__(self, maxlen: int = 2000):
        self._buf: deque[dict[str, str]] = deque(maxlen=maxlen)

    def write(self, message: Any) -> None:
        """loguru sink 回调，message 带有 .record 元数据。"""
        self._buf.append({
            "level": message.record["level"].name,
            "text":  str(message).rstrip(),
        })

    def get(self, level: str = "") -> list[dict[str, str]]:
        """返回所有记录；level 非空时仅返回匹配级别。"""
        if level:
            return [r for r in self._buf if r["level"] == level]
        return list(self._buf)

    def clear(self) -> None:
        self._buf.clear()


memory_log = _MemoryLog()
