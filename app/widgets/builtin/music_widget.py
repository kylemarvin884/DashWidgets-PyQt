"""音乐播放器小组件 — Win11 风格，支持系统媒体会话"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
)

from qfluentwidgets import ToolButton, FluentIcon as FIF

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


_PLAY_ICON = FIF.PLAY
_PAUSE_ICON = FIF.PAUSE
_PREV_ICON = FIF.PAGE_LEFT if hasattr(FIF, 'PAGE_LEFT') else FIF.LEFT_ARROW
_NEXT_ICON = FIF.PAGE_RIGHT if hasattr(FIF, 'PAGE_RIGHT') else FIF.RIGHT_ARROW


class MusicIcon(QWidget):
    """音乐图标 — 替代封面图"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = Win11Style.widget_colors()
        w, h = self.width(), self.height()
        bg_color = QColor(c["bg_input"])
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 8, 8)
        p.setPen(QPen(QColor(c["border_input"]), 1))
        p.setBrush(QBrush(bg_color))
        p.drawPath(path)

        text_color = QColor(c["text_dim"])
        note_font = QFont("Segoe UI Variable", 16, QFont.Weight.Light)
        p.setFont(note_font)
        p.setPen(text_color)
        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "♫")
        p.end()


class MusicWidget(WidgetBase):
    WIDGET_TYPE = "music"
    WIDGET_NAME = "音乐"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._media_svc = None
        self._show_artist = bool(config.settings.get("show_artist", True))
        self._manual_play_state: bool | None = None  # None=自动模式, True/False=手动锁定
        self._manual_timer = QTimer(self)  # 手动状态自动复位计时器
        self._manual_timer.setSingleShot(True)
        self._manual_timer.timeout.connect(self._reset_manual_state)
        self._setup_ui()
        self._artist_label.setVisible(self._show_artist)
        self._connect_media_service()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()

        btn_qss = (
            f"ToolButton {{ color: {c['text']}; background: transparent; border: none; border-radius: 18px; padding: 6px; }}"
            f"ToolButton:hover {{ background: rgba(128,128,128,0.12); border-radius: 18px; }}"
            f"ToolButton:pressed {{ background: rgba(128,128,128,0.22); border-radius: 18px; }}"
        )
        small_btn_qss = (
            f"ToolButton {{ color: {c['text']}; background: transparent; border: 1px solid {c['border_input']}; border-radius: 16px; padding: 4px; }}"
            f"ToolButton:hover {{ background: rgba(128,128,128,0.15); }}"
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(8)

        # ── 第一行：音乐图标 + 信息 ──
        row_info = QHBoxLayout()
        row_info.setSpacing(10)

        # 音乐图标（替代封面）
        self._icon = MusicIcon(self)
        row_info.addWidget(self._icon)

        # 信息列
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._title_label = QLabel("未在播放")
        self._title_label.setFont(QFont("Segoe UI Variable", 13, QFont.Weight.Light))
        self._title_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        info_col.addWidget(self._title_label)
        self._artist_label = QLabel("")
        self._artist_label.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.ExtraLight))
        self._artist_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        info_col.addWidget(self._artist_label)
        row_info.addLayout(info_col, stretch=1)

        main_layout.addLayout(row_info)

        # ── 第二行：控制按钮（上一曲 / 播放暂停 / 下一曲）──
        row_ctrl = QHBoxLayout()
        row_ctrl.setSpacing(8)
        row_ctrl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 上一曲
        self._btn_prev = ToolButton(_PREV_ICON)
        self._btn_prev.setFixedSize(32, 32)
        self._btn_prev.setStyleSheet(small_btn_qss)
        self._btn_prev.clicked.connect(self._on_prev)
        row_ctrl.addWidget(self._btn_prev)

        # 播放/暂停
        self._btn_play = ToolButton(_PLAY_ICON)
        self._btn_play.setFixedSize(38, 38)
        self._btn_play.setStyleSheet(btn_qss)
        self._btn_play.clicked.connect(self._on_play_pause)
        row_ctrl.addWidget(self._btn_play)

        # 下一曲
        self._btn_next = ToolButton(_NEXT_ICON)
        self._btn_next.setFixedSize(32, 32)
        self._btn_next.setStyleSheet(small_btn_qss)
        self._btn_next.clicked.connect(self._on_next)
        row_ctrl.addWidget(self._btn_next)

        main_layout.addLayout(row_ctrl)
        main_layout.addStretch()

    def _connect_media_service(self) -> None:
        try:
            from app.services.media_control_service import (
                get_media_service, media_signals,
            )
            self._media_svc = get_media_service()
            # 状态由服务轮询线程探测，经 Qt 信号（自动排队到 UI 线程）推送
            media_signals.state_changed.connect(self._update_ui)
            self._media_svc.start_polling(interval_ms=2000)
            self._refresh_state()
        except Exception as e:
            print(f"[MusicWidget] 连接媒体服务失败: {e}")

    def _refresh_state(self) -> None:
        if not self._media_svc:
            return
        try:
            state = self._media_svc.state
            self._update_ui(state)
        except Exception:
            pass

    def _update_ui(self, state) -> None:
        """更新UI"""
        has_content = bool(state.title)
        
        if has_content:
            self._title_label.setText(state.title[:30])
            self._artist_label.setText((state.artist or "")[:25])
        else:
            self._title_label.setText("未在播放")
            self._artist_label.setText("")

        # 播放/暂停图标：始终跟随实际状态（除非用户刚手动操作）
        if self._manual_play_state is not None:
            # 用户手动点击过按钮，用手动状态
            self._btn_play.setIcon(_PLAY_ICON if self._manual_play_state else _PAUSE_ICON)
        elif has_content:
            # 有歌曲信息，默认显示暂停图标（表示正在播放）
            self._btn_play.setIcon(_PAUSE_ICON)
        else:
            # 完全没有内容，显示播放图标
            self._btn_play.setIcon(_PLAY_ICON)

    def _reset_manual_state(self) -> None:
        """3秒后恢复自动跟随模式"""
        self._manual_play_state = None
        # 立即刷新一次，让图标回到实际状态
        self._refresh_state()

    def _on_play_pause(self) -> None:
        """播放/暂停"""
        if self._manual_play_state is None or self._manual_play_state is True:
            self._manual_play_state = False  # 显示暂停图标（表示即将播放）
        else:
            self._manual_play_state = True   # 显示播放图标（表示即将暂停）

        self._btn_play.setIcon(_PLAY_ICON if self._manual_play_state else _PAUSE_ICON)

        if self._media_svc:
            self._media_svc.play_pause()

        # 3秒后恢复自动模式，让 UI 跟随实际媒体状态
        self._manual_timer.start(3000)

    def _on_prev(self) -> None:
        """上一曲"""
        if self._media_svc:
            self._media_svc.previous_track()

    def _on_next(self) -> None:
        """下一曲"""
        if self._media_svc:
            self._media_svc.next_track()

    def on_settings_changed(self, settings: dict) -> None:
        if "show_artist" in settings:
            self._show_artist = bool(settings["show_artist"])
            self._artist_label.setVisible(self._show_artist)

    def on_close(self) -> None:
        try:
            if self._media_svc:
                self._media_svc.stop_polling()
            from app.services.media_control_service import media_signals
            media_signals.state_changed.disconnect(self._update_ui)
        except Exception:
            pass
