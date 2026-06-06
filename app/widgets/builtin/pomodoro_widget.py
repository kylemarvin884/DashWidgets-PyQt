"""番茄钟小组件 — Win11 风格"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QConicalGradient, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import ToolButton, FluentIcon as FIF

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style
from app.constants import POMODORO_WORK, POMODORO_SHORT_BREAK, POMODORO_LONG_BREAK


class TimerRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._text = "25:00"
        self.setStyleSheet("background: transparent;")

    def set_progress(self, value: float, text: str) -> None:
        self._progress = value
        self._text = text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = Win11Style.widget_colors()
        cx, cy = 50, 50
        r = 38
        pen_w = 4

        bg_pen = QPen(QColor(c["track"]), pen_w)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(bg_pen)
        p.drawEllipse(QPointF(cx, cy), r, r)

        if self._progress > 0:
            span = int(-self._progress * 360 * 16)
            accent = QColor(c["accent"])
            grad = QConicalGradient(cx, cy, 90)
            grad.setColorAt(0.0, accent)
            grad.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 120))
            fg_pen = QPen(QBrush(grad), pen_w)
            fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(fg_pen)
            p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 90 * 16, span)

        font = QFont("Segoe UI Variable", 18, QFont.Weight.ExtraLight)
        p.setFont(font)
        p.setPen(QColor(c["text"]))
        p.drawText(QRectF(cx - 30, cy - 12, 60, 24), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


class PomodoroWidget(WidgetBase):
    WIDGET_TYPE = "pomodoro"
    WIDGET_NAME = "番茄钟"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._phase = "work"
        self._remaining_s = POMODORO_WORK * 60
        self._total_s = POMODORO_WORK * 60
        self._running = False
        self._pomodoros_done = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._ring = TimerRing(self)
        self._ring.setFixedSize(100, 100)
        main_layout.addWidget(self._ring, alignment=Qt.AlignmentFlag.AlignCenter)

        self._phase_label = QLabel("专注中")
        self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._phase_label.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
        self._phase_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        main_layout.addWidget(self._phase_label)

        self._count_label = QLabel("已完成 0 个番茄")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_label.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Light))
        self._count_label.setStyleSheet(f"color: {c['text_dim']}; background: transparent;")
        main_layout.addWidget(self._count_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._start_btn = ToolButton(FIF.PLAY)
        self._start_btn.setFixedSize(36, 36)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self._start_btn)

        self._skip_btn = ToolButton(FIF.SKIP_FORWARD)
        self._skip_btn.setFixedSize(36, 36)
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.clicked.connect(self._skip)
        btn_row.addWidget(self._skip_btn)
        main_layout.addLayout(btn_row)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._update_display()

    def _toggle(self) -> None:
        self._running = not self._running
        if self._running:
            self._tick.start(1000)
        else:
            self._tick.stop()
        self._start_btn.setIcon(FIF.PAUSE if self._running else FIF.PLAY)

    def _skip(self) -> None:
        self._running = False
        self._tick.stop()
        self._next_phase()

    def _next_phase(self) -> None:
        if self._phase == "work":
            self._pomodoros_done += 1
            if self._pomodoros_done % 4 == 0:
                self._phase = "long_break"
                self._total_s = POMODORO_LONG_BREAK * 60
            else:
                self._phase = "short_break"
                self._total_s = POMODORO_SHORT_BREAK * 60
        else:
            self._phase = "work"
            self._total_s = POMODORO_WORK * 60
        self._remaining_s = self._total_s
        self._start_btn.setIcon(FIF.PLAY)
        self._update_display()

    def _on_tick(self) -> None:
        self._remaining_s -= 1
        if self._remaining_s <= 0:
            self._remaining_s = 0
            self._running = False
            self._tick.stop()
            self._start_btn.setIcon(FIF.PLAY)
            self._next_phase()
        self._update_display()

    def _update_display(self) -> None:
        progress = 1.0 - (self._remaining_s / self._total_s) if self._total_s > 0 else 0
        self._ring.set_progress(progress, f"{self._remaining_s // 60:02d}:{self._remaining_s % 60:02d}")
        phase_map = {"work": "专注中", "short_break": "短休息", "long_break": "长休息"}
        self._phase_label.setText(phase_map.get(self._phase, ""))
        self._count_label.setText(f"已完成 {self._pomodoros_done} 个番茄")
