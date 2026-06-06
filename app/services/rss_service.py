"""
RSS订阅服务

支持获取和解析RSS/Atom源，缓存文章列表。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from loguru import logger
import feedparser


@dataclass
class RSSItem:
    """RSS文章项"""
    title: str
    link: str
    description: str = ""
    published: str = ""
    author: str = ""
    read: bool = False


@dataclass
class RSSFeed:
    """RSS源"""
    url: str
    title: str = ""
    description: str = ""
    items: list[RSSItem] = field(default_factory=list)
    last_updated: float = 0.0
    error: str = ""


class RSSService:
    """RSS订阅服务 - 单例"""

    _instance: Optional["RSSService"] = None
    _CACHE_FILE: Path = Path(__file__).parent.parent.parent / "config" / "rss_cache.json"
    _FEEDS_FILE: Path = Path(__file__).parent.parent.parent / "config" / "rss_feeds.json"
    _CACHE_DURATION: int = 600  # 缓存10分钟

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._feeds: dict[str, RSSFeed] = {}
        self._load_feeds()

    # ------------------------------------------------------------------ #
    # 源管理
    # ------------------------------------------------------------------ #

    def add_feed(self, url: str, title: str = "") -> tuple[bool, str]:
        """
        添加RSS源

        Returns
        -------
        tuple[bool, str]
            (success, message)
        """
        # 规范化URL
        url = url.strip()
        if not url:
            return False, "URL不能为空"

        # 检查是否已存在
        if url in self._feeds:
            return False, "该RSS源已存在"

        # 验证URL格式
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return False, "无效的URL格式"
        except Exception as e:
            return False, f"URL解析失败: {e}"

        # 创建源对象
        feed = RSSFeed(url=url, title=title or self._extract_title_from_url(url))
        self._feeds[url] = feed

        # 立即获取内容
        success, msg = self.refresh_feed(url)
        if not success:
            # 获取失败也保存，但不显示内容
            logger.warning(f"添加RSS源成功但获取内容失败: {msg}")

        self._save_feeds()
        return True, f"已添加RSS源: {feed.title or url}"

    def remove_feed(self, url: str) -> tuple[bool, str]:
        """移除RSS源"""
        if url not in self._feeds:
            return False, "RSS源不存在"

        del self._feeds[url]
        self._save_feeds()
        return True, "已移除RSS源"

    def get_feeds(self) -> list[RSSFeed]:
        """获取所有RSS源"""
        return list(self._feeds.values())

    def get_feed(self, url: str) -> Optional[RSSFeed]:
        """获取指定RSS源"""
        return self._feeds.get(url)

    # ------------------------------------------------------------------ #
    # 内容获取
    # ------------------------------------------------------------------ #

    def refresh_feed(self, url: str) -> tuple[bool, str]:
        """
        刷新RSS源内容

        Returns
        -------
        tuple[bool, str]
            (success, message)
        """
        if url not in self._feeds:
            return False, "RSS源不存在"

        feed = self._feeds[url]

        try:
            logger.info(f"正在获取RSS源: {url}")

            # 使用feedparser解析
            parsed = feedparser.parse(url)

            # 检查解析错误
            if hasattr(parsed, 'bozo') and parsed.bozo:
                error_msg = str(parsed.bozo_exception) if hasattr(parsed, 'bozo_exception') else "未知错误"
                feed.error = f"解析错误: {error_msg}"
                logger.error(f"RSS解析错误: {error_msg}")
                return False, feed.error

            # 更新源信息
            feed.title = getattr(parsed.feed, 'title', '') or feed.title
            feed.description = getattr(parsed.feed, 'description', '')
            feed.last_updated = time.time()
            feed.error = ""

            # 解析文章列表
            feed.items = []
            for entry in parsed.entries[:20]:  # 最多20篇
                item = RSSItem(
                    title=getattr(entry, 'title', '无标题'),
                    link=getattr(entry, 'link', ''),
                    description=self._clean_description(getattr(entry, 'description', '')),
                    published=self._format_date(getattr(entry, 'published', '')),
                    author=getattr(entry, 'author', ''),
                )
                feed.items.append(item)

            logger.info(f"RSS源刷新成功: {feed.title}, {len(feed.items)}篇文章")
            self._save_feeds()
            return True, f"刷新成功，获取{len(feed.items)}篇文章"

        except Exception as e:
            error_msg = f"获取RSS失败: {e}"
            feed.error = error_msg
            logger.error(error_msg)
            return False, error_msg

    def refresh_all(self) -> tuple[int, int]:
        """
        刷新所有RSS源

        Returns
        -------
        tuple[int, int]
            (成功数, 失败数)
        """
        success_count = 0
        fail_count = 0

        for url in self._feeds:
            ok, _ = self.refresh_feed(url)
            if ok:
                success_count += 1
            else:
                fail_count += 1

        return success_count, fail_count

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #

    def _load_feeds(self):
        """加载RSS源配置"""
        if not self._FEEDS_FILE.exists():
            # 创建默认配置
            self._create_default_feeds()
            return

        try:
            with open(self._FEEDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for url, feed_data in data.get("feeds", {}).items():
                items = [
                    RSSItem(**item_data)
                    for item_data in feed_data.get("items", [])
                ]
                self._feeds[url] = RSSFeed(
                    url=url,
                    title=feed_data.get("title", ""),
                    description=feed_data.get("description", ""),
                    items=items,
                    last_updated=feed_data.get("last_updated", 0.0),
                    error=feed_data.get("error", ""),
                )

            logger.info(f"加载了 {len(self._feeds)} 个RSS源")

        except Exception as e:
            logger.error(f"加载RSS配置失败: {e}")

    def _save_feeds(self):
        """保存RSS源配置"""
        try:
            self._FEEDS_FILE.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "feeds": {
                    url: {
                        "title": feed.title,
                        "description": feed.description,
                        "items": [
                            {
                                "title": item.title,
                                "link": item.link,
                                "description": item.description,
                                "published": item.published,
                                "author": item.author,
                                "read": item.read,
                            }
                            for item in feed.items
                        ],
                        "last_updated": feed.last_updated,
                        "error": feed.error,
                    }
                    for url, feed in self._feeds.items()
                }
            }

            with open(self._FEEDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("RSS配置已保存")

        except Exception as e:
            logger.error(f"保存RSS配置失败: {e}")

    def _create_default_feeds(self):
        """创建默认RSS源配置"""
        # 添加一些默认的RSS源示例
        default_feeds = [
            ("https://sspai.com/feed", "少数派"),
            ("https://www.ifanr.com/feed", "爱范儿"),
        ]

        for url, title in default_feeds:
            feed = RSSFeed(url=url, title=title)
            self._feeds[url] = feed

        self._save_feeds()

        # 尝试刷新内容
        for url in self._feeds:
            self.refresh_feed(url)

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #

    def _extract_title_from_url(self, url: str) -> str:
        """从URL提取标题"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace('www.', '')
        except Exception:
            return url[:30]

    def _clean_description(self, desc: str) -> str:
        """清理描述文本"""
        if not desc:
            return ""
        # 移除HTML标签
        import re
        desc = re.sub(r'<[^>]+>', '', desc)
        # 截断过长的描述
        if len(desc) > 150:
            desc = desc[:150] + "..."
        return desc.strip()

    def _format_date(self, date_str: str) -> str:
        """格式化日期"""
        if not date_str:
            return ""
        try:
            # 尝试解析各种日期格式
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.strftime("%m-%d %H:%M")
        except Exception:
            return date_str[:16] if len(date_str) > 16 else date_str


# 模块级单例访问
def get_rss_service() -> RSSService:
    """获取RSS服务单例"""
    return RSSService()
