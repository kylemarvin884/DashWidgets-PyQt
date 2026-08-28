"""番茄钟小组件 — Win11 风格，完整功能版"""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont,
    QConicalGradient, QFontMetrics,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDialog, QSpinBox, QPushButton, QDialogButtonBox,
    QFormLayout,
)
from qfluentwidgets import ToolButton, FluentIcon as FIF, qconfig

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style
from app.constants import POMODORO_WORK, POMODORO_SHORT_BREAK, POMODORO_LONG_BREAK
from loguru import logger


# ── 配置持久化 ────────────────────────────────────────────────── #

_STATS_DIR = Path(__file__).parent.parent.parent.parent / "config"
_STATS_FILE = _STATS_DIR / "pomodoro.json"


def _load_stats() -> dict:
    """加载番茄钟统计数据"""
    default = {"today": str(date.today()), "pomodoros": 0, "focus_seconds": 0}
    try:
        if _STATS_FILE.exists():
            with open(_STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 检查是否跨天
            if data.get("today") != str(date.today()):
                return default
            return data
    except Exception:
        pass
    return default


def _save_stats(data: dict):
    """保存番茄钟统计数据"""
    try:
        _STATS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"保存番茄钟统计失败: {e}")


# ── 环形进度 ──────────────────────────────────────────────────── #

class TimerRing(QWidget):
    """环形倒计时进度（相位感知配色）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._text = "25:00"
        self._phase = "work"
        self._running = False
        self.setStyleSheet("background: transparent;")
        self._text_font = Win11Style.widget_font(21, QFont.Weight.Light)  # 只建一次

    def set_state(self, progress: float, text: str, phase: str, running: bool) -> None:
        self._progress = progress
        self._text = text
        self._phase = phase
        self._running = running
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = Win11Style.widget_colors()
        cx, cy = self.width() / 2, self.height() / 2
        r = min(cx, cy) - 6
        pen_w = 4

        # 背景轨道
        p.setPen(QPen(QColor(c["track"]), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # 前景进度 — 按相位配色
        if self._progress > 0:
            span = int(-self._progress * 360 * 16)
            if self._phase == "work":
                base = QColor("#ff6b6b")  # 红色 — 专注
            else:
                base = QColor("#4ecb71")  # 绿色 — 休息
            grad = QConicalGradient(cx, cy, 90)
            grad.setColorAt(0.0, base)
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 100))
            p.setPen(QPen(QBrush(grad), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 90 * 16, span)

        # 中心文字
        p.setFont(self._text_font)
        p.setPen(QColor(c["text"]))
        p.drawText(QRectF(cx - 28, cy - 12, 56, 24), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


# ── 自定义时长对话框 ──────────────────────────────────────────── #

class PomodoroSettingsDialog(QDialog):
    """番茄钟时长设置对话框"""

    def __init__(self, work_min: int, short_min: int, long_min: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("番茄钟设置")
        self.setFixedSize(280, 210)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._work = work_min
        self._short = short_min
        self._long = long_min
        self._setup_ui()
        self._apply_theme()
        qconfig.themeChanged.connect(self._apply_theme)

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(24, 18, 24, 16)
        layout.setSpacing(10)

        self._work_spin = QSpinBox()
        self._work_spin.setRange(1, 120)
        self._work_spin.setValue(self._work)
        self._work_spin.setSuffix(" 分钟")
        layout.addRow("专注时长：", self._work_spin)

        self._short_spin = QSpinBox()
        self._short_spin.setRange(1, 60)
        self._short_spin.setValue(self._short)
        self._short_spin.setSuffix(" 分钟")
        layout.addRow("短休息：", self._short_spin)

        self._long_spin = QSpinBox()
        self._long_spin.setRange(1, 120)
        self._long_spin.setValue(self._long)
        self._long_spin.setSuffix(" 分钟")
        layout.addRow("长休息：", self._long_spin)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setObjectName("okBtn")
        layout.addRow(btn_box)

    def _apply_theme(self, _theme=None):
        c = Win11Style.c()
        is_dark = Win11Style.is_dark()
        bg = c["card_bg"]
        text = c["text_primary"]
        accent = c["accent"]
        border = c["card_border"]
        input_bg = "#3a3a3a" if is_dark else "#f0f0f0"
        input_border = "#505050" if is_dark else "#d0d0d0"
        input_border_hover = "#707070" if is_dark else "#b0b0b0"
        btn_bg = "#3d3d3d" if is_dark else "#e8e8e8"
        btn_hover = "#505050" if is_dark else "#dcdcdc"
        arrow_color = "#999999" if is_dark else "#666666"

        self.setStyleSheet(f"""
            QDialog {{ background:{bg}; border:1px solid {border}; border-radius:8px; }}
            QLabel {{ color:{text}; font-size:12px; }}
            QSpinBox {{
                background:{input_bg}; color:{text};
                border:1px solid {input_border}; border-radius:4px;
                padding:5px 10px; font-size:14px; min-width:70px;
            }}
            QSpinBox:hover {{ border-color:{input_border_hover}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width:18px; background:{btn_bg}; border:none;
                border-left:1px solid {input_border};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background:{btn_hover};
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width:8px; height:8px;
            }}
            QSpinBox::up-arrow {{ border-image:none; }}
            QSpinBox::down-arrow {{ border-image:none; }}
            QPushButton {{
                padding:6px 18px; border-radius:4px; font-size:13px;
                background:{btn_bg}; color:{text}; border:1px solid {border};
            }}
            QPushButton:hover {{ background:{btn_hover}; }}
            #okBtn {{
                background:{accent};
                color:{"#1a1a1a" if is_dark else "#ffffff"};
                border:none;
            }}
            #okBtn:hover {{ background:{c["accent_hover"]}; }}
        """)

    def result(self) -> tuple[int, int, int]:
        return self._work_spin.value(), self._short_spin.value(), self._long_spin.value()


# ── 主组件 ────────────────────────────────────────────────────── #

class PomodoroWidget(WidgetBase):
    WIDGET_TYPE = "pomodoro"
    WIDGET_NAME = "番茄钟"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)

        # 可调时长（默认从常量读取）
        self._work_min = POMODORO_WORK
        self._short_break_min = POMODORO_SHORT_BREAK
        self._long_break_min = POMODORO_LONG_BREAK

        self._phase = "work"
        self._remaining_s = self._work_min * 60
        self._total_s = self._work_min * 60
        self._running = False
        self._pomodoros_today = 0
        self._focus_seconds_today = 0

        # 加载今日统计
        self._load_today_stats()

        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────── #

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(6)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 环形进度
        self._ring = TimerRing(self)
        self._ring.setFixedSize(90, 90)
        main_layout.addWidget(self._ring, alignment=Qt.AlignmentFlag.AlignCenter)

        # 相位标签
        self._phase_label = QLabel("专注中")
        self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._phase_label.setFont(Win11Style.widget_font(15, QFont.Weight.Light))
        self._phase_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(self._phase_label)

        # 统计行
        self._stats_label = QLabel("")
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats_label.setFont(Win11Style.widget_font(12, QFont.Weight.Light))
        self._stats_label.setStyleSheet(f"color: {c['text_dim']}; background: transparent;")
        main_layout.addWidget(self._stats_label)

        # 控制按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._reset_btn = ToolButton(FIF.SYNC)
        self._reset_btn.setFixedSize(30, 30)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setToolTip("重置当前阶段")
        self._reset_btn.clicked.connect(self._reset_current)
        btn_row.addWidget(self._reset_btn)

        self._start_btn = ToolButton(FIF.PLAY)
        self._start_btn.setFixedSize(34, 34)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self._start_btn)

        self._skip_btn = ToolButton(FIF.SKIP_FORWARD)
        self._skip_btn.setFixedSize(30, 30)
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.setToolTip("跳过当前阶段")
        self._skip_btn.clicked.connect(self._skip)
        btn_row.addWidget(self._skip_btn)

        main_layout.addLayout(btn_row)

        # 设置按钮
        settings_row = QHBoxLayout()
        settings_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._settings_btn = ToolButton(FIF.SETTING)
        self._settings_btn.setFixedSize(24, 24)
        self._settings_btn.setToolTip("时长设置")
        self._settings_btn.clicked.connect(self._open_settings)
        settings_row.addWidget(self._settings_btn)
        main_layout.addLayout(settings_row)

        # 计时器
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._update_display()

    # ── 控制 ──────────────────────────────────────────────────── #

    def _toggle(self) -> None:
        self._running = not self._running
        if self._running:
            self._tick.start(1000)
        else:
            self._tick.stop()
        self._start_btn.setIcon(FIF.PAUSE if self._running else FIF.PLAY)
        self._update_display()

    def _skip(self) -> None:
        self._running = False
        self._tick.stop()
        # 记录已完成工作阶段的统计数据
        if self._phase == "work":
            elapsed = self._total_s - self._remaining_s
            self._focus_seconds_today += elapsed
        self._next_phase()

    def _reset_current(self) -> None:
        """重置当前阶段（不切换相位）"""
        self._running = False
        self._tick.stop()
        self._remaining_s = self._total_s
        self._start_btn.setIcon(FIF.PLAY)
        self._update_display()

    # ── 相位切换 ──────────────────────────────────────────────── #

    def _next_phase(self) -> None:
        if self._phase == "work":
            self._pomodoros_today += 1
            self._focus_seconds_today += self._total_s  # 完整完成一个番茄
            self._save_today_stats()
            if self._pomodoros_today % 4 == 0:
                self._phase = "long_break"
                self._total_s = self._long_break_min * 60
            else:
                self._phase = "short_break"
                self._total_s = self._short_break_min * 60
        else:
            self._phase = "work"
            self._total_s = self._work_min * 60

        self._remaining_s = self._total_s
        self._start_btn.setIcon(FIF.PLAY)
        self._play_beep()
        self._update_display()

    # ── 计时 ──────────────────────────────────────────────────── #

    def _on_tick(self) -> None:
        self._remaining_s -= 1
        if self._remaining_s <= 0:
            self._remaining_s = 0
            self._running = False
            self._tick.stop()
            self._start_btn.setIcon(FIF.PLAY)
            self._next_phase()
        self._update_display()

    # ── 显示 ──────────────────────────────────────────────────── #

    def _update_display(self) -> None:
        progress = 1.0 - (self._remaining_s / self._total_s) if self._total_s > 0 else 0
        time_str = f"{self._remaining_s // 60:02d}:{self._remaining_s % 60:02d}"
        self._ring.set_state(progress, time_str, self._phase, self._running)

        # 相位（用圆点文字表示，颜色由环形进度指示）
        phase_map = {"work": "● 专注中", "short_break": "● 短休息", "long_break": "● 长休息"}
        self._phase_label.setText(phase_map.get(self._phase, ""))

        # 统计
        focus_min = self._focus_seconds_today // 60
        if focus_min >= 60:
            focus_str = f"{focus_min // 60}h{focus_min % 60}m"
        else:
            focus_str = f"{focus_min}m"
        self._stats_label.setText(f"已完成 {self._pomodoros_today} 个番茄 · 今日专注 {focus_str}")

    # ── 设置 ──────────────────────────────────────────────────── #

    def _open_settings(self) -> None:
        dlg = PomodoroSettingsDialog(
            self._work_min, self._short_break_min, self._long_break_min, self
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._work_min, self._short_break_min, self._long_break_min = dlg.result()
            # 仅在非运行或工作阶段更新时长
            if not self._running and self._phase == "work":
                self._total_s = self._work_min * 60
                self._remaining_s = self._total_s
            self._update_display()
            logger.info(f"番茄钟时长已更新: 专注={self._work_min}m, 短休={self._short_break_min}m, 长休={self._long_break_min}m")

    # ── 提示音 ────────────────────────────────────────────────── #

    @staticmethod
    def _play_beep() -> None:
        """播放系统提示音"""
        try:
            import ctypes
            ctypes.windll.user32.MessageBeep(0x00000040)  # MB_ICONASTERISK
        except Exception:
            pass

    # ── 统计持久化 ────────────────────────────────────────────── #

    def _load_today_stats(self) -> None:
        data = _load_stats()
        self._pomodoros_today = data.get("pomodoros", 0)
        self._focus_seconds_today = data.get("focus_seconds", 0)

    def _save_today_stats(self) -> None:
        _save_stats({
            "today": str(date.today()),
            "pomodoros": self._pomodoros_today,
            "focus_seconds": self._focus_seconds_today,
        })
