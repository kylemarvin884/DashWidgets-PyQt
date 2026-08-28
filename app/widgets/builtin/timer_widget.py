"""计时器小组件 — Win11 风格，支持预设时间和自定义时长"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QElapsedTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDialog, QSpinBox, QPushButton, QDialogButtonBox,
    QFormLayout,
)
from qfluentwidgets import ToolButton, FluentIcon as FIF, qconfig

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


class TimerWidget(WidgetBase):
    WIDGET_TYPE = "timer"
    WIDGET_NAME = "计时器"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._remaining_ms = 5 * 60 * 1000
        self._remaining_at_start = self._remaining_ms
        self._clock = QElapsedTimer()  # 用单调时钟计时，避免 QTimer 累积漂移
        self._running = False
        self._finished = False
        self._styled_finished: bool | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._time_label = QLabel("05:00")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setFont(QFont("Segoe UI Variable", 28, QFont.Weight.ExtraLight))
        self._time_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(self._time_label)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
        self._status_label.setStyleSheet(f"color: {c['accent']}; background: transparent;")
        main_layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._start_btn = ToolButton(FIF.PLAY)
        self._start_btn.setFixedSize(36, 36)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self._start_btn)

        self._reset_btn = ToolButton(FIF.SYNC)
        self._reset_btn.setFixedSize(36, 36)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self._reset_btn)
        main_layout.addLayout(btn_row)

        # ── 预设时间快捷按钮 ──
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        preset_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_qss = (
            "QPushButton {"
            f"  color: {c['text_secondary']};"
            "  background: transparent;"
            f"  border: 1px solid {c['border_input']};"
            "  border-radius: 10px;"
            "  padding: 3px 8px;"
            "  font-size: 11px;"
            "}"
            "QPushButton:hover {"
            f"  color: {c['text']};"
            f"  background: {c['bg_input']};"
            "}"
            "QPushButton:pressed {"
            f"  background: {c['border_input']};"
            "}"
        )

        presets = [
            ("1分", 1), ("3分", 3), ("5分", 5), ("10分", 10), ("15分", 15),
        ]
        self._preset_buttons: list[QPushButton] = []
        for label_text, minutes in presets:
            btn = QPushButton(label_text)
            btn.setStyleSheet(btn_qss)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, m=minutes: self._set_time(m * 60 * 1000))
            preset_row.addWidget(btn)
            self._preset_buttons.append(btn)

        # 自定义按钮
        custom_btn = QPushButton("自定义")
        custom_btn.setStyleSheet(btn_qss)
        custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        custom_btn.clicked.connect(self._open_custom_dialog)
        preset_row.addWidget(custom_btn)

        main_layout.addLayout(preset_row)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._update_display()

    def _toggle(self) -> None:
        if self._finished:
            self._reset()
            return
        self._running = not self._running
        if self._running:
            self._remaining_at_start = self._remaining_ms
            self._clock.restart()
            self._tick.start(250)  # 显示精度为秒，250ms 足够流畅
        else:
            self._tick.stop()
        self._start_btn.setIcon(FIF.PAUSE if self._running else FIF.PLAY)

    def _set_time(self, ms: int) -> None:
        """设置自定义倒计时时长"""
        self._running = False
        self._finished = False
        self._remaining_ms = ms
        self._tick.stop()
        self._start_btn.setIcon(FIF.PLAY)
        self._status_label.setText("")
        self._update_display()

    def _open_custom_dialog(self) -> None:
        """打开自定义时间对话框"""
        dlg = CustomTimerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            total_ms = dlg.total_milliseconds()
            if total_ms > 0:
                self._set_time(total_ms)

    def _reset(self) -> None:
        self._running = False
        self._finished = False
        self._remaining_ms = 5 * 60 * 1000
        self._tick.stop()
        self._start_btn.setIcon(FIF.PLAY)
        self._status_label.setText("")
        self._update_display()

    def _on_tick(self) -> None:
        # 依据单调时钟计算剩余时间，不受 tick 抖动影响
        self._remaining_ms = max(0, self._remaining_at_start - self._clock.elapsed())
        if self._remaining_ms <= 0:
            self._running = False
            self._finished = True
            self._tick.stop()
            self._start_btn.setIcon(FIF.PLAY)
            self._status_label.setText("时间到!")
        self._update_display()

    def _update_display(self) -> None:
        total = max(0, self._remaining_ms)
        hours = total // 3600000
        mins = (total // 60000) % 60
        secs = (total // 1000) % 60
        if hours > 0:
            self._time_label.setText(f"{hours}:{mins:02d}:{secs:02d}")
        else:
            self._time_label.setText(f"{mins:02d}:{secs:02d}")
        # 仅在完成状态变化时更新样式，避免每 tick 重设样式表触发重绘
        if self._styled_finished != self._finished:
            self._styled_finished = self._finished
            if self._finished:
                self._time_label.setStyleSheet(f"color: {Win11Style.c()['danger']}; background: transparent;")
            else:
                c = Win11Style.widget_colors()
                self._time_label.setStyleSheet(f"color: {c['text']}; background: transparent;")


class CustomTimerDialog(QDialog):
    """自定义时间输入对话框 — 跟随主程序主题"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义倒计时")
        self.setFixedSize(280, 190)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._setup_ui()
        self._apply_theme()
        qconfig.themeChanged.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setContentsMargins(24, 18, 24, 16)
        layout.setSpacing(10)

        self._hour_spin = QSpinBox()
        self._hour_spin.setRange(0, 23)
        self._hour_spin.setSuffix(" 时")
        layout.addRow("小时：", self._hour_spin)

        self._min_spin = QSpinBox()
        self._min_spin.setRange(0, 59)
        self._min_spin.setSuffix(" 分")
        self._min_spin.setValue(5)
        layout.addRow("分钟：", self._min_spin)

        self._sec_spin = QSpinBox()
        self._sec_spin.setRange(0, 59)
        self._sec_spin.setSuffix(" 秒")
        layout.addRow("秒数：", self._sec_spin)

        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btn_box.accepted.connect(self.accept)
        self._btn_box.rejected.connect(self.reject)
        # 给确定按钮设置 objectName 以便 QSS 选中
        ok_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setObjectName("okBtn")
        layout.addRow(self._btn_box)

    def _apply_theme(self, _theme=None) -> None:
        """动态应用当前主题样式"""
        c = Win11Style.c()
        is_dark = Win11Style.is_dark()

        bg = c["card_bg"]
        text = c["text_primary"]
        text_secondary = c["text_secondary"]
        accent = c["accent"]
        border = c["card_border"]
        input_bg = "#3a3a3a" if is_dark else "#f0f0f0"
        input_border = "#505050" if is_dark else "#d0d0d0"
        input_border_hover = "#707070" if is_dark else "#b0b0b0"
        btn_bg = "#3d3d3d" if is_dark else "#e8e8e8"
        btn_hover = "#505050" if is_dark else "#dcdcdc"
        btn_text = text

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text};
                font-size: 12px;
            }}
            QSpinBox {{
                background: {input_bg};
                color: {text};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 14px;
                min-width: 70px;
            }}
            QSpinBox:hover {{
                border-color: {input_border_hover};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 18px;
                background: {btn_bg};
                border: none;
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 8px;
                height: 8px;
            }}
            QPushButton {{
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 13px;
                background: {btn_bg};
                color: {btn_text};
                border: 1px solid {border};
            }}
            QPushButton:hover {{
                background: {btn_hover};
                border-color: {accent};
            }}
            QPushButton:pressed {{
                background: {btn_hover};
            }}
            #okBtn {{
                background: {accent};
                color: {"#1a1a1a" if is_dark else "#ffffff"};
                border: none;
            }}
            #okBtn:hover {{
                background: {c["accent_hover"]};
            }}
        """)

    def total_milliseconds(self) -> int:
        h = self._hour_spin.value()
        m = self._min_spin.value()
        s = self._sec_spin.value()
        return (h * 3600 + m * 60 + s) * 1000
