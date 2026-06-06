"""
主页视图：仪表板式布局，Windows 11 风格
"""

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
)
from PySide6.QtCore import Qt, QTimer

from qfluentwidgets import (
    ScrollArea,
    FluentIcon as FIF,
    PushButton,
    ToolButton,
    BodyLabel,
    StrongBodyLabel,
    CaptionLabel,
    CardWidget,
    IconWidget,
    isDarkTheme,
    qconfig,
)

from app.models.widget_model import WidgetModel
from app.services.usage_tracker import UsageStatsService
from app.services.desktop_widget_service import Win11Style
from loguru import logger


class _SectionHeader(QWidget):
    """统一的分区标题"""

    def __init__(self, title: str, icon: FIF | None = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._icon = icon
        self._setup_ui()

    def _setup_ui(self):
        # 只清除自身布局中的直接子控件（不用 findChildren 避免误删其他区域控件）
        lay = self.layout()
        if lay is None:
            lay = QHBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        if self._icon:
            lbl = QLabel()
            lbl.setPixmap(self._icon.icon(Win11Style.c()["accent"], 16).pixmap(16, 16))
            lbl.setFixedSize(20, 20)
            lay.addWidget(lbl)

        t = StrongBodyLabel(self._title)
        t.setStyleSheet(
            f"font-family:{Win11Style.FONT_FAMILY};font-size:16px;"
            f"color:{Win11Style.c()['text_primary']};background:transparent;"
        )
        lay.addWidget(t)
        lay.addStretch()

    def update_theme(self):
        self._setup_ui()


class _StatCard(CardWidget):
    """小型统计卡片"""

    def __init__(
        self, icon: FIF, value: str, label: str, color: str | None = None, parent=None
    ):
        super().__init__(parent)
        self._icon = icon
        self._value = value
        self._label = label
        self._color = color
        self._setup_ui()

    def _setup_ui(self):
        c = Win11Style.c()
        accent = self._color or c["accent"]
        self.setFixedSize(160, 80)
        self.setAutoFillBackground(False)

        # 只清除自身布局中的直接子控件
        lay = self.layout()
        if lay is None:
            lay = QVBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(2)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._icon.icon(accent, 18).pixmap(18, 18))
        lay.addWidget(icon_lbl)

        val = StrongBodyLabel(self._value)
        val.setStyleSheet(
            f"font-family:{Win11Style.FONT_FAMILY};font-size:22px;"
            f"font-weight:600;color:{c['text_primary']};background:transparent;"
        )
        lay.addWidget(val)

        cap = CaptionLabel(self._label)
        cap.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
        lay.addWidget(cap)

    def update_theme(self):
        self._setup_ui()


class _ActiveChip(QWidget):
    """已激活小组件的小标签"""

    def __init__(self, widget_info, parent=None):
        super().__init__(parent)
        self._widget_info = widget_info
        self._setup_ui()

    def _setup_ui(self):
        c = Win11Style.c()
        self.setFixedSize(130, 44)
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            f"QWidget{{background-color:{c['bg']};border-radius:10px;"
            f"border:1px solid {c['card_border']};}}"
        )
        # 只清除自身布局中的直接子控件
        lay = self.layout()
        if lay is None:
            lay = QHBoxLayout(self)
        else:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)
        icon = IconWidget(getattr(FIF, self._widget_info.icon_name, FIF.APPLICATION), self)
        icon.setFixedSize(20, 20)
        lay.addWidget(icon)
        name = CaptionLabel(self._widget_info.name)
        name.setStyleSheet(f"color:{c['text_primary']};background:transparent;")
        lay.addWidget(name)

    def update_theme(self):
        self._setup_ui()


class HomeView(QFrame):
    """主页仪表板"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("homeView")
        self._widget_model = WidgetModel()
        self._usage_tracker = UsageStatsService()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(30000)

        # 监听主题变化
        qconfig.themeChanged.connect(self._on_theme_changed)

        self._build_ui()

    def _on_theme_changed(self):
        """主题变化时更新子组件样式"""
        # 更新统计卡片
        for child in self.findChildren(_StatCard):
            child.update_theme()
        # 更新已激活组件标签（需要重建，因为标签是动态创建的）
        self._load_active()
        # 排行榜需要重建
        self._load_leaderboard()

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
        cl.setSpacing(24)

        # 标题
        title = StrongBodyLabel("主页")
        title.setStyleSheet(
            f"font-family:{Win11Style.FONT_FAMILY};font-size:28px;"
            f"font-weight:700;color:{Win11Style.c()['text_primary']};background:transparent;"
        )
        cl.addWidget(title)

        # 统计概览
        self._build_stats(cl)

        # 已启动组件
        self._build_active(cl)

        # 使用排行
        self._build_leaderboard(cl)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _build_stats(self, parent: QVBoxLayout):
        all_w = self._widget_model.get_all_widgets()
        active = [w for w in all_w if w.is_active]
        total_time = sum(self._usage_tracker.get_total_time(w.id) for w in all_w)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(
            _StatCard(FIF.TILES, str(len(active)), "已激活组件", Win11Style.c()["accent"])
        )
        row.addWidget(
            _StatCard(
                FIF.APPLICATION, str(len(all_w)), "可用组件", Win11Style.c()["success"]
            )
        )

        hours = total_time / 3600
        time_str = f"{hours:.1f}h" if hours >= 1 else f"{int(total_time / 60)}m"
        row.addWidget(
            _StatCard(FIF.HISTORY, time_str, "总使用时长", Win11Style.c()["warning"])
        )
        row.addStretch()
        parent.addLayout(row)

    def _build_active(self, parent: QVBoxLayout):
        parent.addWidget(_SectionHeader("已启动的组件", FIF.TILES))

        self._active_container = QWidget()
        self._active_lay = QHBoxLayout(self._active_container)
        self._active_lay.setContentsMargins(0, 4, 0, 0)
        self._active_lay.setSpacing(8)
        parent.addWidget(self._active_container)
        self._load_active()

    def _load_active(self):
        while self._active_lay.count():
            item = self._active_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        active = [w for w in self._widget_model.get_all_widgets() if w.is_active]
        if not active:
            lbl = CaptionLabel("暂无已启动组件，前往「小组件」页面添加")
            lbl.setStyleSheet(
                f"color:{Win11Style.c()['text_secondary']};background:transparent;padding:8px;"
            )
            self._active_lay.addWidget(lbl)
        else:
            for w in active[:6]:
                self._active_lay.addWidget(_ActiveChip(w))
        self._active_lay.addStretch()

    def _build_leaderboard(self, parent: QVBoxLayout):
        parent.addWidget(_SectionHeader("使用排行", FIF.HISTORY))

        self._board_container = QWidget()
        self._board_lay = QVBoxLayout(self._board_container)
        self._board_lay.setContentsMargins(0, 4, 0, 0)
        self._board_lay.setSpacing(6)
        parent.addWidget(self._board_container)
        self._load_leaderboard()

    def _load_leaderboard(self):
        while self._board_lay.count():
            item = self._board_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scores = []
        for w in self._widget_model.get_all_widgets():
            t = self._usage_tracker.get_total_time(w.id)
            s = self._usage_tracker.get_score(w.id)
            n = self._usage_tracker.get_session_count(w.id)
            if s > 0:
                scores.append((w, s, t, n))
        scores.sort(key=lambda x: x[1], reverse=True)

        if not scores:
            lbl = CaptionLabel("暂无使用记录")
            lbl.setStyleSheet(
                f"color:{Win11Style.c()['text_secondary']};background:transparent;padding:12px;"
            )
            self._board_lay.addWidget(lbl)
            return

        c = Win11Style.c()
        rank_colors = [c["warning"], c["text_secondary"], "#CD7F32"]
        for i, (w, score, total, count) in enumerate(scores[:5]):
            row = QHBoxLayout()
            row.setSpacing(12)
            row.setContentsMargins(4, 6, 4, 6)

            rc = rank_colors[i] if i < 3 else c["text_secondary"]
            num = StrongBodyLabel(f"#{i + 1}")
            num.setStyleSheet(
                f"font-family:{Win11Style.FONT_FAMILY};font-size:16px;"
                f"font-weight:700;color:{rc};background:transparent;min-width:30px;"
            )
            row.addWidget(num)

            icon = IconWidget(getattr(FIF, w.icon_name, FIF.APPLICATION), self)
            icon.setFixedSize(20, 20)
            row.addWidget(icon)

            name = BodyLabel(w.name)
            name.setStyleSheet(
                f"font-family:{Win11Style.FONT_FAMILY};color:{c['text_primary']};"
                f"background:transparent;"
            )
            row.addWidget(name)
            row.addStretch()

            mins = int(total / 60)
            time_lbl = CaptionLabel(f"{mins} 分钟")
            time_lbl.setStyleSheet(
                f"color:{c['text_secondary']};background:transparent;"
            )
            row.addWidget(time_lbl)

            cnt_lbl = CaptionLabel(f"{count} 次")
            cnt_lbl.setStyleSheet(f"color:{c['text_secondary']};background:transparent;")
            row.addWidget(cnt_lbl)

            self._board_lay.addLayout(row)

    def refresh(self):
        self._load_active()
        self._load_leaderboard()
        logger.info("主页已刷新")

    def _auto_refresh(self):
        if self.isVisible():
            self._load_active()
            self._load_leaderboard()
