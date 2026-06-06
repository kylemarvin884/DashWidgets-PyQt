"""
应用全局常量
"""
from pathlib import Path

# 应用信息
APP_NAME = "DashWidgets"
APP_VERSION = "1.0.0"
LONG_VER = "1.0.0.Alpha.20260307"
URL_SCHEME = "dashwidgets"

# URL 路径 → 视图映射
URL_VIEW_MAP = {
    "home": "homeView",
    "widgets": "widgetsView",
    "groups": "groupsView",
    "settings": "settingsView",
    "plugins": "pluginView",
    "debug": "debugView",
}

# 本地路径
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
SETTINGS_DIR = CONFIG_DIR
TEMP_DIR = BASE_DIR / "temp"
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"
FONTS_DIR = ASSETS_DIR / "fonts"
ICON_PATH = IMAGES_DIR / "logo.ico"

# 配置文件
SETTINGS_CONFIG = CONFIG_DIR / "settings.json"
WIDGET_CONFIG = CONFIG_DIR / "widgets.json"
WIDGET_LAYOUT_CONFIG = CONFIG_DIR / "widget_layouts.json"

# 窗口尺寸
MANAGER_WIDTH = 1000
MANAGER_HEIGHT = 700
MANAGER_MIN_WIDTH = 900
MANAGER_MIN_HEIGHT = 600

# 小组件默认尺寸
WIDGET_SIZES = {
    "small": (150, 150),
    "medium": (200, 200),
    "large": (300, 300)
}

# 颜色方案
COLOR_SCHEMES = {
    "blue": {"accent": "#0078D4", "light": "#60CDFF", "name": "蓝色"},
    "green": {"accent": "#107C10", "light": "#6BBF6B", "name": "绿色"},
    "purple": {"accent": "#8764B8", "light": "#B8A4D4", "name": "紫色"},
    "orange": {"accent": "#FF8C00", "light": "#FFB84D", "name": "橙色"},
    "red": {"accent": "#D13438", "light": "#E87A7A", "name": "红色"},
    "teal": {"accent": "#00B7C3", "light": "#66D9E0", "name": "青色"},
}

# 番茄钟设置
POMODORO_WORK = 25
POMODORO_SHORT_BREAK = 5
POMODORO_LONG_BREAK = 15

# 网格对齐设置
DEFAULT_GRID_SIZE = 20

# 更新频率
DEFAULT_UPDATE_FREQUENCY = 1000  # ms

# 默认分组
DEFAULT_GROUPS = ["工作", "娱乐", "学习"]

# 日志目录
DATA_DIR = Path.home() / ".dashwidgets"
LOG_DIR = DATA_DIR / "logs"

# 插件目录
PLUGINS_DIR = BASE_DIR / "plugins_ext"
