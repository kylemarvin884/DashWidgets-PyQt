"""内置小组件包"""
from app.widgets.builtin.clock_widget import ClockWidget
from app.widgets.builtin.stopwatch_widget import StopwatchWidget
from app.widgets.builtin.timer_widget import TimerWidget
from app.widgets.builtin.pomodoro_widget import PomodoroWidget
from app.widgets.builtin.system_monitor_widget import SystemMonitorWidget
from app.widgets.builtin.network_monitor_widget import NetworkMonitorWidget
from app.widgets.builtin.weather_widget import WeatherWidget
from app.widgets.builtin.calendar_widget import CalendarWidget
from app.widgets.builtin.todo_widget import TodoWidget
from app.widgets.builtin.music_widget import MusicWidget
from app.widgets.builtin.shortcut_widget import ShortcutWidget
from app.widgets.builtin.note_widget import NoteWidget
from app.widgets.builtin.exchange_widget import ExchangeWidget
from app.widgets.builtin.rss_widget import RssWidget
from app.widgets.builtin.automation_widget import AutomationWidget
from app.widgets.builtin.image_widget import ImageWidget
from app.widgets.builtin.document_viewer_widget import DocumentViewerWidget

__all__ = [
    'ClockWidget', 'StopwatchWidget', 'TimerWidget', 'PomodoroWidget',
    'SystemMonitorWidget', 'NetworkMonitorWidget',
    'WeatherWidget', 'CalendarWidget', 'TodoWidget', 'MusicWidget',
    'ShortcutWidget', 'NoteWidget', 'ExchangeWidget', 'RssWidget',
    'AutomationWidget', 'ImageWidget', 'DocumentViewerWidget',
]
