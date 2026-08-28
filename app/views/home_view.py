"""
主页视图：实时刷新，使用排行为主体

遵循 Fluent 2 规范：Type Ramp（Display 28 / Subtitle 20 / Body 14 /
Caption 12）、8px 间距节奏、卡片 8px 圆角；内容淡入使用 Fluent
标准快速动效（150ms fade + 24px slide-up，FastOutSlowIn 缓动）。
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QProgressBar,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QAbstractAnimation,
)
from PySide6.QtGui import QFont

from qfluentwidgets import (
    ScrollArea, FluentIcon as FIF,
    StrongBodyLabel, BodyLabel, CaptionLabel,
    CardWidget, IconWidget, qconfig,
)

from app.models.widget_model import WidgetModel
from app.services.usage_tracker import UsageStatsService
from app.services.desktop_widget_service import Win11Style


# ── Fluent 动效辅助 ─────────────────────────────────────────────── #

def _fluent_display_font(size: int) -> QFont:
    """Fluent Display 字体（Segoe UI Variable Display，Regular）"""
    f = QFont("Segoe UI Variable Display")
    if not f.exactMatch():
        f = QFont("Segoe UI Variable")
    f.setPointSize(size)
    f.setWeight(QFont.Weight.Normal)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 98)
    return f


def _fluent_subtitle_font(size: int = 20) -> QFont:
    """Fluent Subtitle（20px Semibold）"""
    f = QFont(Win11Style.FONT_SANS)
    f.setPointSize(size)
    f.setWeight(QFont.Weight.DemiBold)
    return f


def _fade_slide_in(widget: QWidget, delay_ms: int = 0, duration_ms: int = 150) -> None:
    """Fluent 入场动效：150ms 淡入 + 24px 上移（OutCubic 缓动）"""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    fade = QPropertyAnimation(effect, b"opacity", widget)
    fade.setDuration(duration_ms)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    slide = QPropertyAnimation(widget, b"pos", widget)
    slide.setDuration(duration_ms)
    slide.setEasingCurve(QEasingCurve.Type.OutCubic)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(fade)
    group.addAnimation(slide)

    def _start():
        base = widget.pos()
        slide.setStartValue(base + QPoint(0, 24))
        slide.setEndValue(base)
        group.start(QAbstractAnimation.DeletionPolicy.KeepWhenStopped)

    if delay_ms > 0:
        QTimer.singleShot(delay_ms, _start)
    else:
        _start()


class _StatCard(CardWidget):
    """紧凑统计卡片 — Fluent Card（8px 圆角）+ Display 数值"""

    def __init__(self, icon: FIF, value: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._value = value
        self._label = label
        self._color = color
        self._value_label: QLabel | None = None
        self._setup_ui()

    def _setup_ui(self):
        c = Win11Style.c()
        self.setFixedSize(170, 84)
        lay = self.layout()
        if lay is None:
            lay = QVBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)

        # 图标 + 标签同一行（Fluent 卡片头部模式）
        head = QHBoxLayout()
        head.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._icon.icon(c["accent"], 14).pixmap(14, 14))
        head.addWidget(icon_lbl)
        cap = CaptionLabel(self._label)
        cap.setStyleSheet(f"color:{c['text_secondary']};background:transparent;font-size:12px;")
        head.addWidget(cap)
        head.addStretch()
        lay.addLayout(head)

        # 数值 — Fluent Display（28px Regular）
        self._value_label = QLabel(self._value)
        self._value_label.setFont(_fluent_display_font(28))
        self._value_label.setStyleSheet(f"color:{c['text_primary']};background:transparent;")
        lay.addWidget(self._value_label)

    def set_value(self, value: str):
        if self._value_label:
            self._value_label.setText(value)
            self._value = value

    def update_theme(self):
        self._setup_ui()


class _ActiveChip(CardWidget):
    """已激活组件芯片 — 点击直接跳转管理"""

    clicked = None  # type: ignore

    def __init__(self, w, parent=None):
        super().__init__(parent)
        self._w = w
        self._setup_ui()

    def _setup_ui(self):
        c = Win11Style.c()
        ok = c["success"]
        self.setFixedSize(180, 44)
        lay = self.layout()
        if lay is None:
            lay = QHBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)

        icon = IconWidget(getattr(FIF, self._w.icon_name, FIF.APPLICATION), self)
        icon.setFixedSize(18, 18)
        lay.addWidget(icon)

        name = BodyLabel(self._w.name)
        name.setStyleSheet(f"color:{c['text_primary']};background:transparent;")
        lay.addWidget(name)
        lay.addStretch()

        # 状态指示灯（主题成功色圆点 = 已启用）
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background:{ok};border-radius:4px;border:none;"
        )
        lay.addWidget(dot)

    def update_theme(self):
        self._setup_ui()


class _RankRow(QWidget):
    """排行榜单行 — 名次 + 图标 + 名称 + 评分 + 进度条 + 时长 + 次数（支持原地更新）"""

    _RANK_NORMAL_W = 28

    def __init__(self, rank: int, w, score: float, total_sec: float, sessions: int, parent=None, top_score: float = 1.0):
        super().__init__(parent)
        self._rank = rank
        self._w = w
        self._score = score
        self._total_sec = total_sec
        self._sessions = sessions
        self._top_score = max(top_score, score, 1.0)
        self._setup_ui()

    def _setup_ui(self):
        c = Win11Style.c()
        self.setFixedHeight(48)
        lay = self.layout()
        if lay is None:
            lay = QHBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(0, 4, 4, 4)
        lay.setSpacing(10)

        # 名次 — 前三名用主题强调色系深浅区分（不再用金银铜硬编码色）
        self._rank_lbl = StrongBodyLabel(f"#{self._rank}")
        self._rank_lbl.setFixedWidth(self._RANK_NORMAL_W)
        rc = c["accent"] if self._rank <= 3 else c["text_secondary"]
        self._rank_lbl.setStyleSheet(
            f"font-size:14px;font-weight:600;color:{rc};background:transparent;"
        )
        lay.addWidget(self._rank_lbl)

        # 图标
        icon = IconWidget(getattr(FIF, self._w.icon_name, FIF.APPLICATION), self)
        icon.setFixedSize(18, 18)
        lay.addWidget(icon)

        # 名称 + 启用标记
        name_w = QWidget()
        name_lay = QHBoxLayout(name_w)
        name_lay.setContentsMargins(0, 0, 0, 0)
        name_lay.setSpacing(6)
        name_lbl = BodyLabel(self._w.name)
        name_lbl.setStyleSheet(f"color:{c['text_primary']};background:transparent;")
        name_lay.addWidget(name_lbl)
        self._active_lbl = CaptionLabel("启用中")
        ok = c["success"]
        self._active_lbl.setStyleSheet(
            f"color:{ok};background:transparent;font-size:12px;padding:1px 6px;"
            f"border:1px solid {ok};border-radius:6px;"
        )
        name_lay.addWidget(self._active_lbl)
        self._active_lbl.setVisible(bool(self._w.is_active))
        name_lay.addStretch()
        lay.addWidget(name_w, stretch=1)

        # 进度条表示使用程度 (相对最高分)
        self._bar = QProgressBar()
        self._bar.setFixedSize(60, 4)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            f"QProgressBar{{background:{c['divider']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{c['accent']};border-radius:2px;}}"
        )
        self._bar.setRange(0, 100)
        lay.addWidget(self._bar)

        # 时长
        self._time_lbl = CaptionLabel(self._fmt_time(self._total_sec))
        self._time_lbl.setFixedWidth(40)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._time_lbl.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        lay.addWidget(self._time_lbl)

        # 次数
        self._cnt_lbl = CaptionLabel(f"{self._sessions}次")
        self._cnt_lbl.setFixedWidth(32)
        self._cnt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._cnt_lbl.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        lay.addWidget(self._cnt_lbl)

        self._apply_score(self._score, animate=False)

    @staticmethod
    def _fmt_time(total_sec: float) -> str:
        if total_sec >= 3600:
            return f"{total_sec / 3600:.1f}h"
        return f"{int(total_sec / 60)}m"

    def _apply_score(self, score: float, animate: bool = True):
        """进度条长度 = 该组件得分相对榜首得分的比例（带 250ms 缓动动画）"""
        ratio = max(0.06, min(1.0, score / self._top_score)) if self._top_score > 0 else 0.06
        target = int(ratio * 100)
        if not animate:
            self._bar.setValue(target)
            return
        anim = QPropertyAnimation(self._bar, b"value", self._bar)
        anim.setDuration(250)
        anim.setStartValue(self._bar.value())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def update_data(self, rank: int, score: float, total_sec: float, sessions: int, top_score: float):
        """原地更新数值，避免整行销毁重建"""
        if rank != self._rank:
            self._rank = rank
            c = Win11Style.c()
            rc = c["accent"] if rank <= 3 else c["text_secondary"]
            self._rank_lbl.setText(f"#{rank}")
            self._rank_lbl.setStyleSheet(
                f"font-size:14px;font-weight:600;color:{rc};background:transparent;"
            )
        self._active_lbl.setVisible(bool(self._w.is_active))
        self._top_score = max(top_score, score, 1.0)
        self._apply_score(score)
        self._time_lbl.setText(self._fmt_time(total_sec))
        self._cnt_lbl.setText(f"{sessions}次")


class HomeView(QFrame):
    """主页仪表板 — 事件驱动刷新，以使用排行为主体"""

    # 数值 Tick 周期：只更新标签文本（使用时长会随进行中的会话增长）
    _TICK_MS = 30_000

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("homeView")
        self._widget_model = WidgetModel()
        self._usage_tracker = UsageStatsService()
        self._rows: dict[str, _RankRow] = {}
        self._row_order: list[str] = []
        self._entrance_played = False

        # 组件状态变化（增删启停）时全量刷新
        self._widget_model.widgets_changed.connect(self.refresh)
        from app.services.desktop_widget_service import widget_signals
        widget_signals.widget_shown.connect(self._on_widget_activity)
        widget_signals.widget_closed.connect(self._on_widget_activity)

        # 慢速 tick：仅原地更新数值文本，不重建任何控件
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(self._TICK_MS)
        self._tick_timer.timeout.connect(self._tick_numbers)

        # 主题变化
        qconfig.themeChanged.connect(self._on_theme_changed)

        self._stat_active: _StatCard | None = None
        self._stat_total: _StatCard | None = None
        self._stat_time: _StatCard | None = None

        self._build_ui()
        self._tick_timer.start()

    def _on_widget_activity(self, widget_id: str):
        """桌面组件显示/关闭：全量刷新（含排行数据落盘后的更新）"""
        self.refresh()

    # ------------------------------------------------------------------ #
    #  UI 构建
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        self.setStyleSheet("QFrame{background:transparent;}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll.viewport().setAutoFillBackground(False)

        content = QWidget()
        content.setAutoFillBackground(False)
        content.setStyleSheet("background:transparent;")
        # Fluent 8px 间距节奏：页面 40px 边距，分区 24px
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 24, 40, 24)
        cl.setSpacing(24)

        # ── 页面标题 — Fluent Display（28px Regular）──
        title = QLabel("主页")
        title.setFont(_fluent_display_font(28))
        title.setStyleSheet(
            f"color:{Win11Style.c()['text_primary']};background:transparent;"
        )
        cl.addWidget(title)

        # ── 统计卡片 ──
        self._build_stats(cl)

        # ── 已启用组件 ──
        self._build_active(cl)

        # ── 使用排行（主区域）──
        self._build_leaderboard(cl)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # 首次显示时播放分区入场动效
        self._entrance_pending = True

    def _build_stats(self, parent: QVBoxLayout):
        c = Win11Style.c()
        row = QHBoxLayout()
        row.setSpacing(8)  # Fluent 卡片间距 8px

        self._stat_active = _StatCard(FIF.TILES, "0", "已激活组件", c["accent"])
        row.addWidget(self._stat_active)

        self._stat_total = _StatCard(FIF.APPLICATION, "0", "可用组件", c["accent"])
        row.addWidget(self._stat_total)

        self._stat_time = _StatCard(FIF.HISTORY, "0m", "总使用时长", c["accent"])
        row.addWidget(self._stat_time)

        row.addStretch()
        parent.addLayout(row)

    def _build_active(self, parent: QVBoxLayout):
        c = Win11Style.c()
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 4, 0, 0)
        hdr.setSpacing(8)

        t = QLabel("已启用的组件")
        t.setFont(_fluent_subtitle_font(20))
        t.setStyleSheet(f"color:{c['text_primary']};background:transparent;")
        hdr.addWidget(t)
        hdr.addStretch()

        self._active_count_label = CaptionLabel("")
        self._active_count_label.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        hdr.addWidget(self._active_count_label)

        parent.addLayout(hdr)

        self._active_container = QWidget()
        self._active_lay = QHBoxLayout(self._active_container)
        self._active_lay.setContentsMargins(0, 4, 0, 0)
        self._active_lay.setSpacing(8)
        parent.addWidget(self._active_container)
        self._refresh_active()

    def _build_leaderboard(self, parent: QVBoxLayout):
        c = Win11Style.c()
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 4, 0, 0)
        hdr.setSpacing(8)

        t = QLabel("使用排行")
        t.setFont(_fluent_subtitle_font(20))
        t.setStyleSheet(f"color:{c['text_primary']};background:transparent;")
        hdr.addWidget(t)
        hdr.addStretch()

        parent.addLayout(hdr)

        # 表头 — Fluent Caption（12px 次要色）
        th = QHBoxLayout()
        th.setContentsMargins(4, 0, 4, 2)
        th.setSpacing(10)
        th.addWidget(CaptionLabel("名次"))
        th.addWidget(CaptionLabel(""))
        th.addWidget(CaptionLabel("组件"), stretch=1)
        th.addWidget(CaptionLabel("热度"))
        th.addWidget(CaptionLabel("时长"))
        th.addWidget(CaptionLabel("次数"))
        for i in range(th.count()):
            w = th.itemAt(i)
            if w and w.widget():
                w.widget().setStyleSheet(
                    f"color:{c['text_secondary']};background:transparent;font-size:12px;"
                )
        parent.addLayout(th)

        self._board_container = QWidget()
        self._board_lay = QVBoxLayout(self._board_container)
        self._board_lay.setContentsMargins(0, 0, 0, 0)
        self._board_lay.setSpacing(0)
        parent.addWidget(self._board_container)
        self._refresh_leaderboard()

    # ------------------------------------------------------------------ #
    #  动效
    # ------------------------------------------------------------------ #

    def showEvent(self, event):
        """首次切入主页时播放分区入场动效（Fluent 快速淡入+上移，阶梯延迟）"""
        super().showEvent(event)
        if getattr(self, "_entrance_pending", False) and not self._entrance_played:
            self._entrance_played = True
            sections = [
                self._stat_active, self._stat_total, self._stat_time,
                self._active_container, self._board_container,
            ]
            for i, w in enumerate(sections):
                if w is not None:
                    _fade_slide_in(w, delay_ms=40 * i)

    # ------------------------------------------------------------------ #
    #  刷新逻辑
    # ------------------------------------------------------------------ #

    def refresh(self):
        """全量刷新（组件集合变化时调用）"""
        self._refresh_stats()
        self._refresh_active()
        self._refresh_leaderboard()

    def _tick_numbers(self):
        """慢速数值更新：仅刷新文本，无控件销毁/创建"""
        if not self.isVisible():
            return
        all_w = self._widget_model.get_all_widgets()
        total_time = sum(self._usage_tracker.get_live_total_time(w.id) for w in all_w)
        if self._stat_time:
            if total_time >= 3600:
                self._stat_time.set_value(f"{total_time / 3600:.1f}h")
            else:
                self._stat_time.set_value(f"{int(total_time / 60)}m")

        entries = []
        for w in all_w:
            t = self._usage_tracker.get_live_total_time(w.id)
            s = self._usage_tracker.get_live_score(w.id)
            n = self._usage_tracker.get_session_count(w.id)
            if w.is_active:
                n += 1  # 进行中的会话尚未落盘，展示时 +1
            entries.append((w, s, t, n))
        top_score = max((e[1] for e in entries), default=0.0)
        for rank, (w, s, t, n) in enumerate(entries, start=1):
            row = self._rows.get(w.id)
            if row:
                row.update_data(rank, s, t, n, top_score)

    def _on_theme_changed(self):
        """主题切换重建"""
        for card in self.findChildren(_StatCard):
            card.update_theme()
        self.refresh()

    # ------------------------------------------------------------------ #
    #  统计卡片
    # ------------------------------------------------------------------ #

    def _refresh_stats(self):
        all_w = self._widget_model.get_all_widgets()
        active = [w for w in all_w if w.is_active]
        total_time = sum(self._usage_tracker.get_live_total_time(w.id) for w in all_w)

        if self._stat_active:
            self._stat_active.set_value(str(len(active)))
        if self._stat_total:
            self._stat_total.set_value(str(len(all_w)))
        if self._stat_time:
            if total_time >= 3600:
                self._stat_time.set_value(f"{total_time / 3600:.1f}h")
            else:
                self._stat_time.set_value(f"{int(total_time / 60)}m")

    # ------------------------------------------------------------------ #
    #  已启用组件
    # ------------------------------------------------------------------ #

    def _refresh_active(self):
        while self._active_lay.count():
            item = self._active_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        active = [w for w in self._widget_model.get_all_widgets() if w.is_active]
        if self._active_count_label:
            self._active_count_label.setText(f"共 {len(active)} 个")

        if not active:
            lbl = CaptionLabel("暂无已启用组件，前往「小组件」页面添加")
            lbl.setStyleSheet(
                f"color:{Win11Style.c()['text_secondary']};background:transparent;padding:12px;"
            )
            self._active_lay.addWidget(lbl)
        else:
            for w in active:
                self._active_lay.addWidget(_ActiveChip(w))
        self._active_lay.addStretch()

    # ------------------------------------------------------------------ #
    #  使用排行
    # ------------------------------------------------------------------ #

    def _refresh_leaderboard(self):
        # 收集所有组件的实时使用数据
        entries: list[tuple] = []
        for w in self._widget_model.get_all_widgets():
            t = self._usage_tracker.get_live_total_time(w.id)
            s = self._usage_tracker.get_live_score(w.id)
            n = self._usage_tracker.get_session_count(w.id)
            if w.is_active:
                n += 1  # 进行中的会话尚未落盘
            entries.append((w, s, t, n))
        # 按得分降序排列，得分相同按时长
        entries.sort(key=lambda x: (x[1], x[2]), reverse=True)

        has_data = any(s[1] > 0 or s[2] > 0 for s in entries)
        if not has_data:
            self._clear_rows()
            self._show_board_placeholder()
            return

        # 显示前 10 名
        top = entries[:10]
        top_score = max(e[1] for e in top)

        new_order = [w.id for w, *_ in top]
        if new_order == self._row_order:
            # 组件集合未变：原地更新数值
            for rank, (w, s, t, n) in enumerate(top, start=1):
                row = self._rows.get(w.id)
                if row:
                    row.update_data(rank, s, t, n, top_score)
            return

        # 集合变化：整表重建
        self._clear_rows()
        self._remove_board_placeholder()
        for rank, (w, s, t, n) in enumerate(top, start=1):
            row = _RankRow(rank, w, s, t, n, top_score=top_score)
            self._rows[w.id] = row
            self._board_lay.addWidget(row)
        self._row_order = new_order

    def _clear_rows(self):
        for row in self._rows.values():
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        self._row_order.clear()

    def _show_board_placeholder(self):
        self._remove_board_placeholder()
        lbl = CaptionLabel("暂无使用记录，启用组件后会开始统计")
        lbl.setObjectName("boardPlaceholder")
        lbl.setStyleSheet(
            f"color:{Win11Style.c()['text_secondary']};background:transparent;padding:16px;"
        )
        self._board_lay.addWidget(lbl)

    def _remove_board_placeholder(self):
        for i in range(self._board_lay.count()):
            item = self._board_lay.itemAt(i)
            w = item.widget() if item else None
            if w is not None and w.objectName() == "boardPlaceholder":
                # 先取引用再移除：setParent(None) 会令 QLayoutItem 失效，
                # 之后 item.widget() 返回 None
                self._board_lay.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
                break
