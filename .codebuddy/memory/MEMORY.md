# DashWidgets-PyQt 项目记忆

## 项目概述
- Windows 桌面小组件管理器，PySide6 + Fluent Design
- 依赖：PySide6, PySide6-Fluent-Widgets, loguru, psutil, feedparser, pynput
- 包管理：uv (pyproject.toml)

## 架构
- `app/constants.py` — 全局常量（路径、尺寸、颜色方案）
- `app/events.py` — 事件总线（EventBus 单例）
- `app/models/widget_model.py` — WidgetInfo dataclass + WidgetModel 单例（JSON 持久化）
- `app/services/settings_service.py` — 应用设置（单例，JSON 持久化）
- `app/services/desktop_widget_service.py` — 桌面组件窗口管理（DWM hack、拖拽、缩放）+ Win11Style + DesktopWidgetManager
- `app/widgets/base_widget.py` — 组件基类 WidgetBase + WidgetConfig
- `app/widgets/registry.py` — 组件注册表（单例，内置 + 插件）
- `app/widgets/glass_surface.py` — GlassCard（液态玻璃渲染，paintEvent 手绘）
- `app/widgets/widget_settings_dialog.py` — 设置对话框（实时推送，无保存按钮）
- `app/window.py` — 主窗口（FluentWindow，导航、托盘、插件）
- `app/views/` — 各视图页面

## 组件系统 (17 个内置)
时钟、秒表、计时器、番茄钟、系统监控、网络监控、天气、日历、待办、音乐、快捷方式、笔记、汇率、RSS、自动化点击、图片、文档查看器

## 桌面组件窗口样式
- Windows 11 实色卡片：暗色 `#2c2c2c` / 亮色 `#f3f3f3`（通过 `isDarkTheme()` 切换）
- 轻阴影（3层）+ 细边框（暗色 rgba(255,255,255,25) / 亮色 rgba(0,0,0,18)）
- 时钟组件：无边框透明窗口（_is_frameless=True）
- 组件颜色通过 `Win11Style.widget_colors()` 获取，支持明暗主题自适应

## 已知坑点
1. `desktop_widget_service._open_appearance_dialog()` 必须导入 `app.widgets.widget_settings_dialog`
2. `WidgetSettingsDialog` 必须传 `widget_id` 参数才能正确推送设置
3. `home_view` 没有 `_load_recommendations()` 方法，应使用 `refresh()`
4. `main.py` 中 `conn.readAll().data()` 返回 memoryview，需 `bytes()` 包装
5. `glass_base.py` 是废弃文件，不要引用
6. DWM hack 需要具名常量（DWMNCRP_DISABLED 等）
7. `QPointF`, `QRectF` 在 PySide6 中属于 `QtCore`，不能从 `QtGui` 导入（会导致 import 失败）
