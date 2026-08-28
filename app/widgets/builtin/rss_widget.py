"""RSS 订阅小组件 — Win11 风格，接入 RSSService 真实数据"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style
from app.utils.async_fetch import run_in_background

_MAX_ITEMS = 6
_REFRESH_MS = 10 * 60 * 1000  # 10 分钟


class _ItemRow(QWidget):
    """单条文章行：标题 + 来源，点击打开原文"""

    def __init__(self, title: str, source: str, link: str, show_source: bool = True, parent=None):
        super().__init__(parent)
        self._link = link
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(0)

        c = Win11Style.widget_colors()
        self._title_lbl = QLabel(title)
        self._title_lbl.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
        self._title_lbl.setStyleSheet(f"color: {c['text']}; background: transparent;")
        self._title_lbl.setWordWrap(True)
        lay.addWidget(self._title_lbl)

        if show_source and source:
            src_lbl = QLabel(source)
            src_lbl.setFont(QFont("Segoe UI Variable", 9, QFont.Weight.Light))
            src_lbl.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
            lay.addWidget(src_lbl)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._link:
            QDesktopServices.openUrl(QUrl(self._link))
        super().mousePressEvent(event)


class RssWidget(WidgetBase):
    WIDGET_TYPE = "rss"
    WIDGET_NAME = "RSS订阅"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._fetching = False
        self._task = None  # 持有后台任务信号对象，防止被 GC
        self._max_items = int(config.settings.get("max_items", _MAX_ITEMS) or _MAX_ITEMS)
        self._show_source = bool(config.settings.get("show_source", True))
        self._last_rows: list[tuple[str, str, str]] = []  # 最近一次数据，改设置时无需重新抓取
        self._setup_ui()
        self._refresh()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(_REFRESH_MS)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(4)

        self._title = Win11Style.widget_title("RSS 订阅")
        main_layout.addWidget(self._title)

        self._list_container = QWidget(self)
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(2)
        main_layout.addWidget(self._list_container)
        main_layout.addStretch()

    def _refresh(self):
        """后台线程刷新 RSS 内容（feedparser 为阻塞 IO）"""
        if self._fetching:
            return
        self._fetching = True
        self._title.setText("RSS 订阅 · 刷新中…")
        max_items = self._max_items

        def _work():
            from app.services.rss_service import get_rss_service
            svc = get_rss_service()
            svc.refresh_all()
            # 合并所有源的最近条目，按源内顺序交错取前 N 条
            merged: list[tuple[str, str, str]] = []  # (title, source, link)
            rounds = 0
            feeds = svc.get_feeds()
            while len(merged) < max_items and rounds < 20:
                progressed = False
                for feed in feeds:
                    if rounds < len(feed.items):
                        item = feed.items[rounds]
                        merged.append((item.title, feed.title, item.link))
                        progressed = True
                        if len(merged) >= max_items:
                            break
                if not progressed:
                    break
                rounds += 1
            has_any_feed = bool(feeds)
            return merged, has_any_feed

        self._task = run_in_background(_work, self._on_refreshed)

    def _on_refreshed(self, result):
        self._fetching = False
        if isinstance(result, Exception) or not isinstance(result, tuple):
            self._title.setText("RSS 订阅 · 刷新失败")
            return

        merged, has_any_feed = result
        self._last_rows = merged
        if not merged:
            self._title.setText("RSS 订阅" if has_any_feed else "RSS 订阅 · 暂无订阅源")
        else:
            self._title.setText("RSS 订阅")

        self._rebuild_rows()

    def _rebuild_rows(self):
        """按当前设置（条数/来源）重建条目行"""
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for title, source, link in self._last_rows[:self._max_items]:
            self._list_lay.addWidget(
                _ItemRow(title, source, link, self._show_source, self._list_container)
            )

    def on_settings_changed(self, settings: dict) -> None:
        changed = False
        if "max_items" in settings:
            try:
                self._max_items = max(1, min(10, int(settings["max_items"])))
                changed = True
            except (TypeError, ValueError):
                pass
        if "show_source" in settings:
            self._show_source = bool(settings["show_source"])
            changed = True
        if changed:
            self._rebuild_rows()

    def on_close(self):
        self._refresh_timer.stop()
