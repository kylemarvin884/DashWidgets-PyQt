"""
调试窗口 — Windows 11 Fluent 风格（独立窗口）

借鉴 Little-Tree-Clock 项目的调试面板设计：
  - 概览页：运行时基础信息（PID、Python 版本、运行时长、内存）
  - 线程页：Qt 线程、Python 线程列表
  - 日志页：带高级筛选（级别、搜索、正则、大小写敏感、导出）
  - 服务页：小组件状态、插件状态
  - 工具页：性能信息、快速操作

通过 Ctrl+Shift+D 快捷键打开，作为独立窗口运行。
"""

from __future__ import annotations

import io
import os
import sys
import re
import threading
import platform
import html as _html
from collections import deque
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QObject, Slot
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QApplication,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QSizePolicy,
    QTabWidget,
    QStackedWidget,
    QMenuBar,
    QMainWindow,
)

from qfluentwidgets import (
    CardWidget,
    TitleLabel,
    BodyLabel,
    CaptionLabel,
    PushButton,
    ToolButton,
    SwitchButton,
    ComboBox,
    SearchLineEdit,
    CheckBox,
    TextEdit,
    FluentIcon as FIF,
    isDarkTheme,
    qconfig,
    InfoBar,
    InfoBarPosition,
)

from app.services.desktop_widget_service import Win11Style


# ════════════════════════════════════════════════════════════════════════════
#  全局日志缓冲区 — 应用启动即开始捕获
# ════════════════════════════════════════════════════════════════════════════


class _LogBuffer(QObject):
    """全局日志缓冲区，始终在后台运行"""

    MAX_ENTRIES = 10000

    def __init__(self):
        super().__init__()
        self._entries: deque[tuple[str, str | None]] = deque(maxlen=self.MAX_ENTRIES)
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        # 注意：不再替换 sys.stdout/stderr，避免与 QApplication 冲突
        # 仅通过 loguru sink 捕获日志
        self._add_loguru_sink()

    def stop(self):
        if not self._started:
            return
        self._started = False
        # stdout/stderr 不再被替换，无需恢复

    def _on_stdout(self, text: str):
        self._entries.append((text, None))

    def _on_stderr(self, text: str):
        self._entries.append((text, "#F85149"))

    def _add_loguru_sink(self):
        try:
            from loguru import logger

            def _sink(message):
                record = message.record
                level = record["level"].name
                ts = record["time"].strftime("%H:%M:%S.%f")[:-3]
                text = f"[{ts}] [{level}] {record['message']}\n"
                color_map = {
                    "DEBUG": "#8B949E",
                    "INFO": "#58A6FF",
                    "SUCCESS": "#3FB950",
                    "WARNING": "#D29922",
                    "ERROR": "#F85149",
                    "CRITICAL": "#FF7B72",
                }
                self._entries.append((text, color_map.get(level, "#D4D4D4")))

            logger.add(_sink, format="{message}", enqueue=False)
        except ImportError:
            pass

    def get_new_entries(
        self, after_index: int
    ) -> tuple[int, list[tuple[str, str | None]]]:
        entries = list(self._entries)
        new = entries[after_index:]
        return len(entries), new

    def get_all_entries(self) -> list[tuple[str, str | None]]:
        return list(self._entries)

    def clear(self):
        self._entries.clear()


class _LogStream(io.TextIOBase):
    def __init__(self, callback):
        super().__init__()
        self._cb = callback
        # 保存原始 stdout/stderr 避免递归
        self._original_stdout = sys.__stdout__
        self._original_stderr = sys.__stderr__

    def write(self, s: str) -> int:
        if s:
            try:
                self._cb(s)
            except Exception:
                # 如果 callback 出错，使用原始 stdout
                self._original_stderr.write(f"[_LogStream Error] {s}")
        return len(s)

    def flush(self):
        pass


_log_buffer = _LogBuffer()


def get_log_buffer() -> _LogBuffer:
    return _log_buffer


def start_log_capture():
    _log_buffer.start()


# ════════════════════════════════════════════════════════════════════════════
#  KV 表格组件（支持主题）
# ════════════════════════════════════════════════════════════════════════════


class _KVTable(QTableWidget):
    """两列（字段 / 值）只读表格，高度随行数自适应"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["字段", "值"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.update_style()

    def update_style(self):
        """根据当前主题更新样式"""
        c = Win11Style.c()
        self.setStyleSheet(f"""
            QTableWidget {{
                background: transparent;
                border: 1px solid {c['card_border']};
                border-radius: 8px;
                gridline-color: {c['divider']};
                font-family: {Win11Style.FONT_FAMILY};
                font-size: 12px;
                color: {c['text_primary']};
            }}
            QHeaderView::section {{
                background: transparent;
                border: none;
                padding: 6px;
                font-family: {Win11Style.FONT_FAMILY};
                font-weight: 600;
                color: {c['text_secondary']};
            }}
            QTableWidget::item {{
                color: {c['text_primary']};
            }}
            QTableWidget::item:alternate {{
                background: {c['bg']};
            }}
        """)

    def set_rows(self, rows: list[tuple[str, str]]):
        self.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            ki = QTableWidgetItem(k)
            ki.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            vi = QTableWidgetItem(str(v))
            vi.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(r, 0, ki)
            self.setItem(r, 1, vi)
        self.resizeRowsToContents()

    def ideal_height(self) -> int:
        h = self.horizontalHeader().height() + 6
        for r in range(self.rowCount()):
            h += self.rowHeight(r)
        return h


# ════════════════════════════════════════════════════════════════════════════
#  调试页面基类
# ════════════════════════════════════════════════════════════════════════════


class _DebugBasePage(QWidget):
    """调试页面基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(24, 16, 24, 16)
        self._root.setSpacing(12)

    def _add_card(self, title: str) -> tuple[CardWidget, QVBoxLayout]:
        self._root.addWidget(TitleLabel(title))

        card = CardWidget()
        card.setAutoFillBackground(False)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        self._root.addWidget(card)
        return card, lay

    def refresh(self):
        pass

    def update_theme(self):
        """更新主题时调用"""
        pass


# ════════════════════════════════════════════════════════════════════════════
#  概览页
# ════════════════════════════════════════════════════════════════════════════

_START_TIME = __import__("time").monotonic()


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class OverviewPage(_DebugBasePage):
    """概览页：运行时基础信息"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("debugOverviewPage")
        self._root.addWidget(TitleLabel("运行时概览"))
        self._root.addSpacing(8)

        _, rl = self._add_card("系统信息")
        self._table = _KVTable()
        rl.addWidget(self._table)

        # 小组件统计
        _, ws = self._add_card("小组件统计")
        self._widget_table = _KVTable()
        ws.addWidget(self._widget_table)

        self.refresh()

    def refresh(self):
        import time

        secs = int(time.monotonic() - _START_TIME)
        h, r = divmod(secs, 3600)
        m, s = divmod(r, 60)
        uptime = f"{h:02d}:{m:02d}:{s:02d}"

        rows = [
            ("PID", str(os.getpid())),
            ("Python", sys.version.split()[0]),
            ("平台", sys.platform),
            ("系统", f"{platform.system()} {platform.release()}"),
            ("运行时长", uptime),
            ("Python 线程数", str(threading.active_count())),
            ("当前时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ]

        try:
            import psutil

            proc = psutil.Process()
            mem = proc.memory_info()
            rows.insert(4, ("RSS 内存", _fmt_bytes(mem.rss)))
            rows.insert(5, ("VMS 内存", _fmt_bytes(mem.vms)))
            rows.insert(6, ("CPU 占用", f"{proc.cpu_percent(interval=None):.1f}%"))
        except Exception:
            pass

        self._table.set_rows(rows)
        self._table.setFixedHeight(self._table.ideal_height())

        # 小组件统计
        try:
            from app.models.widget_model import WidgetModel

            model = WidgetModel()
            all_w = model.get_all_widgets()
            active = [w for w in all_w if w.is_active]
            w_rows = [
                ("总计", str(len(all_w))),
                ("已激活", str(len(active))),
                ("未激活", str(len(all_w) - len(active))),
            ]
        except Exception as e:
            w_rows = [("错误", str(e))]

        self._widget_table.set_rows(w_rows)
        self._widget_table.setFixedHeight(self._widget_table.ideal_height())

    def update_theme(self):
        self._table.update_style()
        self._widget_table.update_style()


# ════════════════════════════════════════════════════════════════════════════
#  线程页
# ════════════════════════════════════════════════════════════════════════════


class ThreadPage(_DebugBasePage):
    """线程页：Qt 线程、Python 线程"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("debugThreadPage")
        self._root.addWidget(TitleLabel("线程信息"))
        self._root.addSpacing(8)

        _, qt_l = self._add_card("Qt 线程")
        self._qt_table = _KVTable()
        qt_l.addWidget(self._qt_table)

        _, py_l = self._add_card("Python 线程")
        self._py_table = _KVTable()
        py_l.addWidget(self._py_table)

        self._root.addStretch()
        self.refresh()

    def refresh(self):
        from PySide6.QtCore import QThread

        rows = []
        app = QApplication.instance()
        if app:
            for obj in app.findChildren(QThread):
                name = obj.objectName() or obj.__class__.__name__
                status = "运行中" if obj.isRunning() else "已停止"
                rows.append((name, f"{status} | id={id(obj):#x}"))
        if not rows:
            rows = [("无独立 QThread", "所有逻辑均在主线程完成")]
        self._qt_table.set_rows(rows)
        self._qt_table.setFixedHeight(self._qt_table.ideal_height())

        main_id = threading.main_thread().ident
        rows = []
        for t in sorted(threading.enumerate(), key=lambda x: x.ident or 0):
            tag = " [主线程]" if t.ident == main_id else ""
            daemon = "守护" if t.daemon else "普通"
            alive = "存活" if t.is_alive() else "已终止"
            rows.append((f"#{t.ident}{tag}", f"{t.name} | {alive} | {daemon}"))
        self._py_table.set_rows(rows)
        self._py_table.setFixedHeight(self._py_table.ideal_height())

    def update_theme(self):
        self._qt_table.update_style()
        self._py_table.update_style()


# ════════════════════════════════════════════════════════════════════════════
#  日志页（带高级筛选 - HTML 格式化）
# ════════════════════════════════════════════════════════════════════════════


class LogPage(_DebugBasePage):
    """日志页：带级别筛选、搜索、正则、大小写敏感、导出、自动刷新"""

    _LEVEL_COLOR = {
        "TRACE": "#888888",
        "DEBUG": "#888888",
        "INFO": "#1a73e8",
        "SUCCESS": "#3FB950",
        "WARNING": "#D29922",
        "ERROR": "#F85149",
        "CRITICAL": "#FF7B72",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("debugLogPage")
        self._read_index = 0
        self._applog_refresh_pending = False

        self._root.addWidget(TitleLabel("日志查看器"))
        self._root.addSpacing(8)

        # 筛选工具栏
        self._build_filter_bar()

        # 日志输出（使用 HTML 格式化）
        card = CardWidget()
        card.setAutoFillBackground(False)
        ll = QVBoxLayout(card)
        ll.setContentsMargins(12, 12, 12, 12)
        self._log_edit = TextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMinimumHeight(200)
        self._log_edit.setStyleSheet(
            f"TextEdit{{background:transparent;border:none;border-radius:6px;padding:8px;"
            f"font-family:Consolas,'Cascadia Code',monospace;font-size:12px;}}"
        )
        ll.addWidget(self._log_edit)
        self._root.addWidget(card)

        # 状态栏
        self._status_lbl = CaptionLabel("")
        self._root.addWidget(self._status_lbl)

        self._root.addStretch()

        # 轮询定时器
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_logs)
        self._poll_timer.start(200)

        # 自动刷新定时器（可选）
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(2000)
        self._auto_timer.timeout.connect(self._refresh_filter)

        self._load_history()

    def _build_filter_bar(self):
        card = CardWidget()
        card.setAutoFillBackground(False)
        fc = QHBoxLayout(card)
        fc.setContentsMargins(16, 10, 16, 10)
        fc.setSpacing(10)

        fc.addWidget(BodyLabel("级别："))
        self._level_combo = ComboBox()
        for lvl in ("全部", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"):
            self._level_combo.addItem(lvl, userData=(lvl if lvl != "全部" else ""))
        self._level_combo.setFixedWidth(100)
        self._level_combo.currentIndexChanged.connect(self._refresh_filter)
        fc.addWidget(self._level_combo)

        fc.addSpacing(8)
        fc.addWidget(BodyLabel("搜索："))
        self._search = SearchLineEdit()
        self._search.setPlaceholderText("输入关键词筛选日志…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._refresh_filter)
        fc.addWidget(self._search)

        self._regex = SwitchButton()
        self._regex.setOffText("普通")
        self._regex.setOnText("正则")
        self._regex.checkedChanged.connect(self._refresh_filter)
        fc.addWidget(BodyLabel("模式："))
        fc.addWidget(self._regex)

        self._case = CheckBox("区分大小写")
        self._case.stateChanged.connect(self._refresh_filter)
        fc.addWidget(self._case)

        fc.addSpacing(8)

        # 自动刷新开关
        self._auto_refresh = SwitchButton()
        self._auto_refresh.setChecked(True)
        self._auto_refresh.setOffText("手动刷新")
        self._auto_refresh.setOnText("自动刷新")
        self._auto_refresh.checkedChanged.connect(self._toggle_auto_refresh)
        fc.addWidget(BodyLabel("自动刷新："))
        fc.addWidget(self._auto_refresh)

        fc.addStretch()

        clear_btn = ToolButton(FIF.DELETE)
        clear_btn.setToolTip("清空日志")
        clear_btn.clicked.connect(self._clear)
        fc.addWidget(clear_btn)

        export_btn = ToolButton(FIF.SAVE)
        export_btn.setToolTip("导出日志")
        export_btn.clicked.connect(self._export)
        fc.addWidget(export_btn)

        self._root.addWidget(card)

    def _toggle_auto_refresh(self, checked: bool):
        """切换自动刷新"""
        if checked:
            self._auto_timer.start()
        else:
            self._auto_timer.stop()

    def _load_history(self):
        entries = get_log_buffer().get_all_entries()
        self._read_index = len(entries)
        self._render_entries(entries)

    def _poll_logs(self):
        """轮询新日志"""
        if not self._auto_refresh.isChecked():
            return
        new_idx, entries = get_log_buffer().get_new_entries(self._read_index)
        if entries:
            self._read_index = new_idx
            self._append_entries(entries)

    def _render_entries(self, entries):
        """使用 HTML 格式化渲染日志"""
        if not entries:
            self._log_edit.setHtml(f"<span style='color:gray'>(暂无日志)</span>")
            return

        lines_html = []
        for text, color in entries:
            escaped = _html.escape(text)
            if color:
                lines_html.append(f"<span style='color:{color}'>{escaped}</span>")
            else:
                lines_html.append(f"<span>{escaped}</span>")

        self._log_edit.setHtml("<br>".join(lines_html))
        # 滚动到底部
        scrollbar = self._log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_entries(self, entries):
        """追加新日志（HTML 格式）"""
        for text, color in entries:
            escaped = _html.escape(text)
            if color:
                html = f"<span style='color:{color}'>{escaped}</span>"
            else:
                html = f"<span>{escaped}</span>"
            self._log_edit.append(html)

        # 限制行数
        doc = self._log_edit.toPlainText()
        lines = doc.split("\n")
        if len(lines) > 3000:
            self._log_edit.setPlainText("\n".join(lines[-3000:]))
            # 重新应用 HTML 格式
            self._refresh_filter()

    def _should_show(self, text: str) -> bool:
        level_filter = self._level_combo.currentData() or ""
        if level_filter:
            found_level = None
            for lvl in self._LEVEL_COLOR:
                if f"[{lvl}]" in text:
                    found_level = lvl
                    break
            if found_level and found_level != level_filter:
                return False

        search = self._search.text().strip()
        if search:
            if self._regex.isChecked():
                try:
                    flags = 0 if self._case.isChecked() else re.IGNORECASE
                    if not re.search(search, text, flags):
                        return False
                except re.error:
                    pass
            else:
                if self._case.isChecked():
                    if search not in text:
                        return False
                else:
                    if search.lower() not in text.lower():
                        return False
        return True

    def _refresh_filter(self):
        """刷新日志显示"""
        entries = get_log_buffer().get_all_entries()
        filtered = [(t, c) for t, c in entries if self._should_show(t)]
        self._render_entries(filtered)
        total = len(entries)
        shown = len(filtered)
        self._status_lbl.setText(f"总计 {total} 条 | 显示 {shown} 条")

    def _clear(self):
        get_log_buffer().clear()
        self._log_edit.clear()
        self._read_index = 0
        self._status_lbl.setText("已清空")

    def _export(self):
        entries = get_log_buffer().get_all_entries()
        filtered = [(t, c) for t, c in entries if self._should_show(t)]
        if not filtered:
            InfoBar.warning(
                title="导出失败",
                content="没有日志可导出",
                parent=self,
                position=InfoBarPosition.TOP
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出日志",
            f"DashWidgets_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                for text, _ in filtered:
                    f.write(text)
            InfoBar.success(
                title="导出成功",
                content=f"已导出 {len(filtered)} 条日志",
                parent=self,
                position=InfoBarPosition.TOP
            )

    def update_theme(self):
        """主题变化时更新样式"""
        self._refresh_filter()


# ════════════════════════════════════════════════════════════════════════════
#  服务页
# ════════════════════════════════════════════════════════════════════════════


class ServicesPage(_DebugBasePage):
    """服务页：小组件状态、插件状态"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("debugServicesPage")
        self._root.addWidget(TitleLabel("服务状态"))
        self._root.addSpacing(8)

        _, wl = self._add_card("桌面小组件")
        self._widget_table = _KVTable()
        wl.addWidget(self._widget_table)

        _, pl = self._add_card("插件")
        self._plugin_table = _KVTable()
        pl.addWidget(self._plugin_table)

        _, sl = self._add_card("后台服务")
        self._service_table = _KVTable()
        sl.addWidget(self._service_table)

        self._root.addStretch()
        self.refresh()

    def refresh(self):
        # 小组件状态
        try:
            from app.models.widget_model import WidgetModel

            model = WidgetModel()
            all_w = model.get_all_widgets()
            active = [w for w in all_w if w.is_active]
            rows = [
                ("总计", str(len(all_w))),
                ("已激活", str(len(active))),
                ("未激活", str(len(all_w) - len(active))),
            ]
            for w in all_w:
                status = "激活" if w.is_active else "停用"
                rows.append((f"  {w.name}", f"{status} {w.id}"))
        except Exception as e:
            rows = [("错误", str(e))]
        self._widget_table.set_rows(rows)
        self._widget_table.setFixedHeight(self._widget_table.ideal_height())

        # 插件状态
        try:
            from app.plugins.plugin_manager import PluginManager

            mgr = PluginManager()
            entries = mgr.all_entries()
            rows = [
                ("总计", str(len(entries))),
                ("已启用", str(sum(1 for e in entries if e.enabled))),
                ("已禁用", str(sum(1 for e in entries if not e.enabled))),
            ]
            for e in entries:
                status = "启用" if e.enabled else "禁用"
                err = f"  错误: {e.error}" if e.error else ""
                rows.append((f"  {e.meta.name}", f"{status} v{e.meta.version} by {e.meta.author}{err}"))
        except Exception as e:
            rows = [("错误", str(e))]
        self._plugin_table.set_rows(rows)
        self._plugin_table.setFixedHeight(self._plugin_table.ideal_height())

        # 后台服务状态
        try:
            from app.services.rss_service import get_rss_service
            from app.services.weather_service import get_weather_service

            rows = []

            # RSS 服务
            try:
                rss = get_rss_service()
                rows.append(("RSS 服务", f"已初始化 | {len(rss._feeds) if hasattr(rss, '_feeds') else 0} 个源"))
            except Exception as e:
                rows.append(("RSS 服务", f"未初始化: {e}"))

            # 天气服务
            try:
                weather = get_weather_service()
                rows.append(("天气服务", "已初始化"))
            except Exception as e:
                rows.append(("天气服务", f"未初始化: {e}"))

            # 小组件管理器
            try:
                from app.services.desktop_widget_service import DesktopWidgetManager
                mgr = DesktopWidgetManager.instance()
                rows.append(("小组件管理器", f"运行中 | {len(mgr._active_widgets) if hasattr(mgr, '_active_widgets') else 0} 个实例"))
            except Exception as e:
                rows.append(("小组件管理器", f"错误: {e}"))

        except Exception as e:
            rows = [("错误", str(e))]
        self._service_table.set_rows(rows)
        self._service_table.setFixedHeight(self._service_table.ideal_height())

    def update_theme(self):
        self._widget_table.update_style()
        self._plugin_table.update_style()
        self._service_table.update_style()


# ════════════════════════════════════════════════════════════════════════════
#  工具页
# ════════════════════════════════════════════════════════════════════════════


class ToolsPage(_DebugBasePage):
    """工具页：性能信息、快速操作"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("debugToolsPage")
        self._root.addWidget(TitleLabel("调试工具"))
        self._root.addSpacing(8)

        # 性能信息
        _, perf_l = self._add_card("性能信息")
        self._perf_lbl = CaptionLabel("")
        perf_l.addWidget(self._perf_lbl)
        self._perf_timer = QTimer(self)
        self._perf_timer.timeout.connect(self._update_perf)
        self._perf_timer.start(2000)
        self._update_perf()

        # 应用信息
        _, info_l = self._add_card("应用信息")
        self._info_lbl = CaptionLabel("")
        self._info_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        info_l.addWidget(self._info_lbl)
        self._update_info()

        # 快速操作
        _, act_l = self._add_card("快速操作")
        grid = QHBoxLayout()
        grid.setSpacing(10)

        refresh_btn = PushButton(FIF.SYNC, "刷新小组件")
        refresh_btn.clicked.connect(self._refresh_widgets)
        grid.addWidget(refresh_btn)

        reload_btn = PushButton(FIF.VIEW, "重载插件")
        reload_btn.clicked.connect(self._reload_plugins)
        grid.addWidget(reload_btn)

        dump_btn = PushButton(FIF.SAVE, "导出诊断")
        dump_btn.clicked.connect(self._export_diag)
        grid.addWidget(dump_btn)

        clear_cache_btn = PushButton(FIF.DELETE, "清理缓存")
        clear_cache_btn.clicked.connect(self._clear_cache)
        grid.addWidget(clear_cache_btn)

        act_l.addLayout(grid)

        self._root.addStretch()

    def _update_perf(self):
        try:
            import psutil

            proc = psutil.Process()
            mem_mb = proc.memory_info().rss / 1024 / 1024
        except Exception:
            mem_mb = 0
        app = QApplication.instance()
        wc = len(app.allWidgets()) if app else 0
        self._perf_lbl.setText(
            f"内存: {mem_mb:.1f} MB  |  控件数: {wc}  |  线程数: {threading.active_count()}"
        )

    def _update_info(self):
        try:
            from app.constants import (
                APP_NAME,
                APP_VERSION,
                LONG_VER,
                BASE_DIR,
                CONFIG_DIR,
                PLUGINS_DIR,
            )
            from PySide6.QtCore import qVersion

            theme = "深色" if isDarkTheme() else "浅色"
            lines = [
                f"应用: {APP_NAME} {APP_VERSION}",
                f"版本: {LONG_VER}",
                f"主题: {theme}  |  Python: {sys.version.split()[0]}  |  Qt: {qVersion()}",
                f"系统: {platform.system()} {platform.release()}",
                f"基础目录: {BASE_DIR}",
                f"配置目录: {CONFIG_DIR}",
                f"插件目录: {PLUGINS_DIR}",
            ]
            self._info_lbl.setText("\n".join(lines))
        except Exception:
            self._info_lbl.setText("信息加载失败")

    def _refresh_widgets(self):
        try:
            from app.services.desktop_widget_service import DesktopWidgetManager

            mgr = DesktopWidgetManager.instance()
            mgr.hide_all()
            mgr.show_all_active_widgets()
            InfoBar.success(
                title="已刷新",
                content="所有桌面小组件已强制刷新",
                parent=self,
                position=InfoBarPosition.TOP
            )
        except Exception as e:
            InfoBar.error(
                title="刷新失败",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP
            )

    def _reload_plugins(self):
        try:
            from app.window import MainWindow

            for w in QApplication.instance().topLevelWidgets():
                if isinstance(w, MainWindow):
                    mgr = w._plugin_mgr
                    # 对已加载的插件做真正的热重载（重新执行插件代码），
                    # 再扫描目录加载新出现的插件
                    reloaded, failed = 0, []
                    for entry in mgr.all_entries():
                        if entry.path is None:
                            continue
                        ok, _msg = mgr.reload_plugin(entry.meta.id)
                        if ok:
                            reloaded += 1
                        else:
                            failed.append(entry.meta.id)
                    mgr.discover_and_load()
                    w._refresh_plugin_navigations()
                    w.plugin_view._load_plugins()
                    w.widgets_view._load_widgets()
                    content = f"已热重载 {reloaded} 个插件"
                    if failed:
                        content += f"，失败: {', '.join(failed)}"
                    InfoBar.success(
                        title="已重载",
                        content=content,
                        parent=self,
                        position=InfoBarPosition.TOP
                    )
                    return
        except Exception as e:
            InfoBar.error(
                title="重载失败",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP
            )

    def _clear_cache(self):
        """清理缓存"""
        try:
            import shutil
            from app.constants import CONFIG_DIR
            cache_dir = CONFIG_DIR / "cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)
                InfoBar.success(
                    title="已清理",
                    content="缓存目录已清空",
                    parent=self,
                    position=InfoBarPosition.TOP
                )
            else:
                InfoBar.info(
                    title="无需清理",
                    content="缓存目录不存在",
                    parent=self,
                    position=InfoBarPosition.TOP
                )
        except Exception as e:
            InfoBar.error(
                title="清理失败",
                content=str(e),
                parent=self,
                position=InfoBarPosition.TOP
            )

    def _export_diag(self):
        from app.constants import APP_NAME, APP_VERSION, LONG_VER, BASE_DIR, CONFIG_DIR

        try:
            import psutil

            proc = psutil.Process()
            mem_mb = proc.memory_info().rss / 1024 / 1024
        except Exception:
            mem_mb = 0

        lines = [
            f"=== {APP_NAME} 诊断报告 ===",
            f"时间: {datetime.now().isoformat()}",
            f"版本: {LONG_VER}",
            "",
            "--- 系统 ---",
            f"OS: {platform.system()} {platform.version()}",
            f"Python: {sys.version.split()[0]}",
            f"PID: {os.getpid()}",
            f"内存: {mem_mb:.1f} MB",
            "",
            "--- 路径 ---",
            f"基础: {BASE_DIR}",
            f"配置: {CONFIG_DIR}",
            "",
            "--- 最近日志 (最后 100 条) ---",
        ]
        for text, _ in get_log_buffer().get_all_entries()[-100:]:
            lines.append(text.rstrip())

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出诊断",
            f"DashWidgets_Diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            InfoBar.success(
                title="已导出",
                content="诊断信息已保存",
                parent=self,
                position=InfoBarPosition.TOP
            )

    def update_theme(self):
        """主题变化时更新样式"""
        c = Win11Style.c()
        self._perf_lbl.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        self._info_lbl.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")


# ════════════════════════════════════════════════════════════════════════════
#  调试窗口（独立弹窗）
# ════════════════════════════════════════════════════════════════════════════


class DebugWindow(QMainWindow):
    """独立调试窗口，带 Tab 导航"""

    # 单例模式，确保只有一个实例
    _instance: Optional["DebugWindow"] = None

    @classmethod
    def get_instance(cls) -> "DebugWindow":
        """获取单例实例"""
        if cls._instance is None or not cls._instance.isVisible():
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DashWidgets — 调试面板")
        self.resize(1000, 750)
        self.setMinimumSize(800, 600)

        # 设置窗口标志 - 独立窗口，不依赖主窗口
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowStaysOnTopHint  # 调试时置顶
        )

        self._setup_ui()
        self._create_menu_bar()

        # 自动刷新
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(3000)
        self._auto_timer.timeout.connect(self.refresh)

        # 监听主题变化
        qconfig.themeChanged.connect(self._on_theme_changed)

    def _setup_ui(self):
        self.setStyleSheet("QMainWindow{background:transparent;}")

        # 创建 Tab 导航 - 使用 QTabWidget（支持左侧放置）
        self._tabs = QTabWidget(self)
        self._tabs.setTabPosition(QTabWidget.TabPosition.West)  # 左侧 Tab 导航
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar {
                background: transparent;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin: 4px 2px;
                border-radius: 6px;
                background: transparent;
            }
            QTabBar::tab:selected {
                background: rgba(255, 255, 255, 0.1);
            }
            QTabBar::tab:hover {
                background: rgba(255, 255, 255, 0.05);
            }
        """)

        # 创建页面
        self._overview = OverviewPage()
        self._threads = ThreadPage()
        self._logs = LogPage()
        self._services = ServicesPage()
        self._tools = ToolsPage()

        # 添加页面到 Tab
        self._tabs.addTab(self._overview, "概览")
        self._tabs.addTab(self._threads, "线程")
        self._tabs.addTab(self._logs, "日志")
        self._tabs.addTab(self._services, "服务")
        self._tabs.addTab(self._tools, "工具")

        # QMainWindow 使用 setCentralWidget 设置中央控件
        self.setCentralWidget(self._tabs)

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 导出日志
        export_log = QAction("导出日志(&L)", self)
        export_log.setShortcut(QKeySequence("Ctrl+E"))
        export_log.triggered.connect(lambda: self._logs._export())
        file_menu.addAction(export_log)

        # 导出诊断
        export_diag = QAction("导出诊断报告(&D)", self)
        export_diag.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_diag.triggered.connect(lambda: self._tools._export_diag())
        file_menu.addAction(export_diag)

        file_menu.addSeparator()

        # 刷新
        refresh_action = QAction("刷新(&R)", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.refresh)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        # 关闭
        close_action = QAction("关闭(&C)", self)
        close_action.setShortcut(QKeySequence("Ctrl+W"))
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        # 查看菜单
        view_menu = menubar.addMenu("查看(&V)")

        # 概览
        overview_action = QAction("概览", self)
        overview_action.setShortcut(QKeySequence("Ctrl+1"))
        overview_action.triggered.connect(lambda: self._tabs.setCurrentIndex(0))
        view_menu.addAction(overview_action)

        # 线程
        thread_action = QAction("线程", self)
        thread_action.setShortcut(QKeySequence("Ctrl+2"))
        thread_action.triggered.connect(lambda: self._tabs.setCurrentIndex(1))
        view_menu.addAction(thread_action)

        # 日志
        log_action = QAction("日志", self)
        log_action.setShortcut(QKeySequence("Ctrl+3"))
        log_action.triggered.connect(lambda: self._tabs.setCurrentIndex(2))
        view_menu.addAction(log_action)

        # 服务
        service_action = QAction("服务", self)
        service_action.setShortcut(QKeySequence("Ctrl+4"))
        service_action.triggered.connect(lambda: self._tabs.setCurrentIndex(3))
        view_menu.addAction(service_action)

        # 工具
        tools_action = QAction("工具", self)
        tools_action.setShortcut(QKeySequence("Ctrl+5"))
        tools_action.triggered.connect(lambda: self._tabs.setCurrentIndex(4))
        view_menu.addAction(tools_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        # 关于
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        """显示关于对话框"""
        from qfluentwidgets import MessageDialog

        about_info = MessageDialog(
            title="关于 DashWidgets 调试面板",
            content=(
                "DashWidgets 调试面板 v1.0\n\n"
                "借鉴 Little-Tree-Clock 项目的调试面板设计\n\n"
                "功能：\n"
                "• 概览：运行时基础信息\n"
                "• 线程：Qt 和 Python 线程状态\n"
                "• 日志：带高级筛选的日志查看器\n"
                "• 服务：小组件和插件状态\n"
                "• 工具：性能监控和快速操作\n\n"
                "快捷键：Ctrl+Shift+D 打开调试窗口"
            ),
            parent=self,
        )
        about_info.exec()

    def _on_theme_changed(self, theme):
        """主题变化时更新样式"""
        self.setStyleSheet("QMainWindow{background:transparent;}")
        # 更新所有页面的主题
        for page in (self._overview, self._threads, self._logs, self._services, self._tools):
            page.update_theme()
        # 刷新所有页面
        self.refresh()

    def refresh(self):
        for page in (self._overview, self._threads, self._services, self._tools):
            page.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self._auto_timer.start()
        self.refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._auto_timer.stop()

    def closeEvent(self, event):
        """关闭事件"""
        self._auto_timer.stop()
        event.accept()