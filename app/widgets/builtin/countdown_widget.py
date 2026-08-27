"""倒数日小组件 — Win11 风格，距目标日期的倒计天数"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QDialog, QVBoxLayout as QVBox,
    QDialogButtonBox, QDateEdit, QLineEdit, QFormLayout,
)

from qfluentwidgets import qconfig
from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style

_TICK_MS = 60_000  # 分钟级刷新（天数变化频率低）


class _CountdownDialog(QDialog):
    """设置倒数日目标与名称的对话框"""

    def __init__(self, title: str, target: QDate, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置倒数日")
        self.setFixedSize(300, 190)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        form = QFormLayout(self)
        form.setContentsMargins(24, 18, 24, 16)
        form.setSpacing(10)

        self._name_edit = QLineEdit(title or "倒数日")
        form.addRow("名称：", self._name_edit)

        self._date_edit = QDateEdit(target)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        form.addRow("目标日期：", self._date_edit)

        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setObjectName("okBtn")
        self._btn_box.accepted.connect(self.accept)
        self._btn_box.rejected.connect(self.reject)
        form.addRow(self._btn_box)
        self._apply_theme()
        qconfig.themeChanged.connect(self._apply_theme)

    def _apply_theme(self, _theme=None):
        c = Win11Style.c()
        is_dark = Win11Style.is_dark()
        self.setStyleSheet(f"""
            QDialog {{ background-color: {c['card_bg']}; border: 1px solid {c['card_border']}; border-radius: 8px; }}
            QLabel {{ color: {c['text_primary']}; font-size: 12px; }}
            QLineEdit, QDateEdit {{
                background: {'#3a3a3a' if is_dark else '#f0f0f0'}; color: {c['text_primary']};
                border: 1px solid {'#505050' if is_dark else '#d0d0d0'}; border-radius: 4px;
                padding: 5px 8px; font-size: 13px;
            }}
            QPushButton {{
                padding: 6px 18px; border-radius: 4px; font-size: 13px;
                background: {'#3d3d3d' if is_dark else '#e8e8e8'}; color: {c['text_primary']};
                border: 1px solid {c['card_border']};
            }}
            QPushButton:hover {{ border-color: {c['accent']}; }}
            #okBtn {{ background: {c['accent']}; color: {'#1a1a1a' if is_dark else '#ffffff'}; border: none; }}
        """)

    def name_text(self) -> str:
        return self._name_edit.text().strip() or "倒数日"

    def target_date(self) -> QDate:
        return self._date_edit.date()


class CountdownWidget(WidgetBase):
    WIDGET_TYPE = "countdown"
    WIDGET_NAME = "倒数日"

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        settings = config.settings or {}
        self._title = settings.get("countdown_title", "倒数日")
        self._target = QDate.fromString(
            settings.get("countdown_target", ""), "yyyy-MM-dd"
        )
        self._setup_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._update_display)
        self._update_display()
        self._timer.start()

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 10)
        main_layout.setSpacing(2)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel(self._title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setFont(QFont("Segoe UI Variable", 12, QFont.Weight.Light))
        self._title_label.setStyleSheet(f"color: {c['title']}; background: transparent;")
        main_layout.addWidget(self._title_label)

        self._days_label = QLabel("--")
        self._days_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._days_label.setFont(QFont("Segoe UI Variable", 30, QFont.Weight.ExtraLight))
        self._days_label.setStyleSheet(f"color: {c['text']}; background: transparent;")
        main_layout.addWidget(self._days_label)

        self._date_label = QLabel("点击设置目标日期")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._date_label.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.Light))
        self._date_label.setStyleSheet(f"color: {c['text_secondary']}; background: transparent;")
        main_layout.addWidget(self._date_label)
        main_layout.addStretch()

    def _update_display(self) -> None:
        if not self._target.isValid():
            self._days_label.setText("--")
            self._date_label.setText("点击设置目标日期")
            return
        today = QDate.currentDate()
        days = today.daysTo(self._target)
        if days > 0:
            self._days_label.setText(f"{days}")
            self._date_label.setText(
                f"天 · {self._target.toString('yyyy-MM-dd')}"
                f"（周{'一二三四五六日'[self._target.dayOfWeek() - 1]}）"
            )
        elif days == 0:
            self._days_label.setText("今天")
            self._date_label.setText(self._target.toString("yyyy-MM-dd"))
        else:
            self._days_label.setText(f"{-days}")
            self._date_label.setText(
                f"天前 · {self._target.toString('yyyy-MM-dd')}"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_settings()
        super().mousePressEvent(event)

    def _open_settings(self):
        target = self._target if self._target.isValid() else QDate.currentDate().addDays(30)
        dlg = _CountdownDialog(self._title, target, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._title = dlg.name_text()
            self._target = dlg.target_date()
            self._title_label.setText(self._title)
            self._update_display()
            self._save_config()

    def _save_config(self):
        self.config.settings["countdown_title"] = self._title
        self.config.settings["countdown_target"] = self._target.toString("yyyy-MM-dd")
        try:
            from app.models.widget_model import WidgetModel
            model = WidgetModel()
            w = model.get_widget(self.config.id)
            if w:
                w.custom_settings = dict(self.config.settings)
                model.save()
        except Exception:
            pass

    def on_close(self) -> None:
        self._timer.stop()

    def on_settings_changed(self, settings: dict) -> None:
        if "countdown_title" in settings:
            self._title = settings["countdown_title"]
            self._title_label.setText(self._title)
        if "countdown_target" in settings:
            self._target = QDate.fromString(settings["countdown_target"], "yyyy-MM-dd")
        self._update_display()
