"""
主页视图：实时刷新，使用排行为主体
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QProgressBar,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from qfluentwidgets import (
    ScrollArea, FluentIcon as FIF,
    StrongBodyLabel, BodyLabel, CaptionLabel,
    CardWidget, IconWidget, qconfig,
)

from app.models.widget_model import WidgetModel
from app.services.usage_tracker import UsageStatsService
from app.services.desktop_widget_service import Win11Style
from loguru import logger


class _StatCard(CardWidget):
    """紧凑统计卡片"""

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
        self.setFixedSize(170, 72)
        lay = self.layout()
        if lay is None:
            lay = QVBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(0)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._icon.icon(self._color, 16).pixmap(16, 16))
        lay.addWidget(icon_lbl)

        self._value_label = StrongBodyLabel(self._value)
        self._value_label.setStyleSheet(
            f"font-family:{Win11Style.FONT_SERIF};font-size:28px;font-weight:400;"
            f"letter-spacing:-0.3px;color:{c['text_primary']};background:transparent;"
        )
        lay.addWidget(self._value_label)

        cap = CaptionLabel(self._label)
        cap.setStyleSheet(f"color:{c['text_secondary']};background:transparent;padding-top:2px;")
        lay.addWidget(cap)

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
        self.setFixedSize(170, 50)
        lay = self.layout()
        if lay is None:
            lay = QHBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        icon = IconWidget(getattr(FIF, self._w.icon_name, FIF.APPLICATION), self)
        icon.setFixedSize(20, 20)
        lay.addWidget(icon)

        name = BodyLabel(self._w.name)
        name.setStyleSheet(f"color:{c['text_primary']};background:transparent;")
        lay.addWidget(name)
        lay.addStretch()

        # 状态指示灯（绿色圆点 = 已启用）
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            "background:#5db872;border-radius:4px;border:none;"
        )
        lay.addWidget(dot)

    def update_theme(self):
        self._setup_ui()


class _RankRow(QWidget):
    """排行榜单行 — 名次 + 图标 + 名称 + 评分 + 进度条 + 时长 + 次数"""

    def __init__(self, rank: int, w, score: float, total_sec: float, sessions: int, parent=None):
        super().__init__(parent)
        self._rank = rank
        self._w = w
        self._score = score
        self._total_sec = total_sec
        self._sessions = sessions
        self._setup_ui()

    def _setup_ui(self):
        c = Win11Style.c()
        self.setFixedHeight(52)
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

        # 名次
        rank_colors = {1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32"}
        rc = rank_colors.get(self._rank, c["text_secondary"])
        rank_lbl = StrongBodyLabel(f"#{self._rank}")
        rank_lbl.setFixedWidth(28)
        rank_lbl.setStyleSheet(
            f"font-size:15px;font-weight:700;color:{rc};background:transparent;"
        )
        lay.addWidget(rank_lbl)

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
        if self._w.is_active:
            active_lbl = CaptionLabel("启用中")
            active_lbl.setStyleSheet(
                "color:#5db872;background:transparent;font-size:10px;padding:1px 6px;"
                "border:1px solid #5db872;border-radius:6px;"
            )
            name_lay.addWidget(active_lbl)
        name_lay.addStretch()
        lay.addWidget(name_w, stretch=1)

        # 进度条表示使用程度 (相对最高分)
        bar = QProgressBar()
        bar.setFixedSize(60, 4)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            f"QProgressBar{{background:{c['divider']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{c['accent']};border-radius:2px;}}"
        )
        bar.setRange(0, 100)
        bar.setValue(40 + self._rank * -8 if self._rank <= 5 else 20)  # 越靠前越长
        lay.addWidget(bar)

        # 时长
        if self._total_sec >= 3600:
            time_str = f"{self._total_sec / 3600:.1f}h"
        else:
            time_str = f"{int(self._total_sec / 60)}m"
        time_lbl = CaptionLabel(time_str)
        time_lbl.setFixedWidth(40)
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        time_lbl.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        lay.addWidget(time_lbl)

        # 次数
        cnt_lbl = CaptionLabel(f"{self._sessions}次")
        cnt_lbl.setFixedWidth(32)
        cnt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cnt_lbl.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        lay.addWidget(cnt_lbl)


class HomeView(QFrame):
    """主页仪表板 — 实时刷新，以使用排行为主体"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("homeView")
        self._widget_model = WidgetModel()
        self._usage_tracker = UsageStatsService()

        # 实时刷新：每秒更新
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(1000)

        # 小组件状态变化时立即刷新
        self._widget_model.widgets_changed.connect(self.refresh)

        # 主题变化
        qconfig.themeChanged.connect(self._on_theme_changed)

        self._stat_active: _StatCard | None = None
        self._stat_total: _StatCard | None = None
        self._stat_time: _StatCard | None = None

        self._build_ui()

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
        cl = QVBoxLayout(content)
        cl.setContentsMargins(36, 28, 36, 28)
        cl.setSpacing(20)

        # ── 标题（衬线 display）──
        title = StrongBodyLabel("主页")
        title.setStyleSheet(
            f"font-family:{Win11Style.FONT_SERIF};font-size:36px;"
            f"font-weight:400;letter-spacing:-0.5px;"
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

    def _build_stats(self, parent: QVBoxLayout):
        c = Win11Style.c()
        row = QHBoxLayout()
        row.setSpacing(12)

        self._stat_active = _StatCard(FIF.TILES, "0", "已激活组件", c["accent"])
        row.addWidget(self._stat_active)

        self._stat_total = _StatCard(FIF.APPLICATION, "0", "可用组件", c["success"])
        row.addWidget(self._stat_total)

        self._stat_time = _StatCard(FIF.HISTORY, "0m", "总使用时长", c["warning"])
        row.addWidget(self._stat_time)

        row.addStretch()
        parent.addLayout(row)

    def _build_active(self, parent: QVBoxLayout):
        c = Win11Style.c()
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 4, 0, 0)
        hdr.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(FIF.TILES.icon(c["accent"], 16).pixmap(16, 16))
        icon_lbl.setFixedSize(20, 20)
        hdr.addWidget(icon_lbl)

        t = StrongBodyLabel("已启用的组件")
        t.setStyleSheet(f"font-family:{Win11Style.FONT_SERIF};font-size:18px;font-weight:400;color:{c['text_primary']};background:transparent;")
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

        icon_lbl = QLabel()
        icon_lbl.setPixmap(FIF.HISTORY.icon(c["warning"], 16).pixmap(16, 16))
        icon_lbl.setFixedSize(20, 20)
        hdr.addWidget(icon_lbl)

        t = StrongBodyLabel("使用排行")
        t.setStyleSheet(f"font-family:{Win11Style.FONT_SERIF};font-size:22px;font-weight:400;letter-spacing:-0.3px;color:{c['text_primary']};background:transparent;")
        hdr.addWidget(t)
        hdr.addStretch()

        parent.addLayout(hdr)

        # 表头
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
                    f"color:{c['text_secondary']};background:transparent;font-size:11px;"
                )
        parent.addLayout(th)

        self._board_container = QWidget()
        self._board_lay = QVBoxLayout(self._board_container)
        self._board_lay.setContentsMargins(0, 0, 0, 0)
        self._board_lay.setSpacing(0)
        parent.addWidget(self._board_container)
        self._refresh_leaderboard()

    # ------------------------------------------------------------------ #
    #  刷新逻辑
    # ------------------------------------------------------------------ #

    def refresh(self):
        """全量刷新"""
        self._refresh_stats()
        self._refresh_active()
        self._refresh_leaderboard()

    def _auto_refresh(self):
        """定时刷新（仅在可见时）"""
        if self.isVisible():
            self.refresh()

    def _on_theme_changed(self):
        """主题切换重建"""
        # 统计卡片
        for card in self.findChildren(_StatCard):
            card.update_theme()
        self.refresh()

    # ------------------------------------------------------------------ #
    #  统计卡片
    # ------------------------------------------------------------------ #

    def _refresh_stats(self):
        all_w = self._widget_model.get_all_widgets()
        active = [w for w in all_w if w.is_active]
        total_time = sum(self._usage_tracker.get_total_time(w.id) for w in all_w)

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
        while self._board_lay.count():
            item = self._board_lay.takeAt(0)
            if isinstance(item, QVBoxLayout):
                self._clear_layout(item)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        # 收集所有有使用记录的组件
        scores: list[tuple] = []
        for w in self._widget_model.get_all_widgets():
            t = self._usage_tracker.get_total_time(w.id)
            s = self._usage_tracker.get_score(w.id)
            n = self._usage_tracker.get_session_count(w.id)
            scores.append((w, s, t, n))
        # 按得分降序排列，得分相同按时长
        scores.sort(key=lambda x: (x[1], x[2]), reverse=True)

        if not scores or all(s[1] == 0 for s in scores):
            lbl = CaptionLabel("暂无使用记录，启用组件后会开始统计")
            lbl.setStyleSheet(
                f"color:{Win11Style.c()['text_secondary']};background:transparent;padding:16px;"
            )
            self._board_lay.addWidget(lbl)
            return

        # 显示前 10 名
        for i, (w, sc, tm, cnt) in enumerate(scores[:10]):
            row = _RankRow(i + 1, w, sc, tm, cnt)
            self._board_lay.addWidget(row)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                HomeView._clear_layout(item.layout())
