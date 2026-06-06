# DashWidgets 插件开发指南

## 概述

DashWidgets 支持插件扩展，允许开发者创建自定义功能来扩展应用能力。

## 插件结构

### 方式一：包形式（推荐）

```
plugins_ext/
    my_plugin/
        __init__.py      # Plugin 类定义
        plugin.json      # 插件元数据
        config.json      # 插件配置（自动生成）
```

### 方式二：单文件形式

```
plugins_ext/
    my_simple_plugin.py   # 单文件插件
```

## 快速开始

### 1. 创建插件目录

```bash
mkdir plugins_ext/my_plugin
```

### 2. 创建 `plugin.json`

```json
{
    "id": "my_plugin",
    "name": "我的插件",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "这是一个示例插件",
    "tags": ["demo", "example"]
}
```

### 3. 创建 `__init__.py`

```python
from app.plugins import BasePlugin, PluginAPI, HookType

class Plugin(BasePlugin):
    meta = PluginMeta(
        id="my_plugin",
        name="我的插件",
        description="这是一个示例插件",
    )

    def on_load(self, api: PluginAPI) -> None:
        """插件加载时调用"""
        # 注册钩子
        api.register_hook(HookType.ON_WIDGET_ADDED, self._on_widget_added)
        
        # 显示通知
        api.show_toast("插件已加载", "我的插件已成功加载！")

    def on_unload(self) -> None:
        """插件卸载时调用"""
        pass

    def _on_widget_added(self, widget_id: str) -> None:
        """小组件添加时的回调"""
        self.api.show_toast("小组件添加", f"小组件 {widget_id} 已添加")
```

## API 参考

### PluginAPI 方法

| 方法 | 说明 |
|------|------|
| `register_hook(hook_type, callback)` | 注册钩子回调 |
| `unregister_hook(hook_type, callback)` | 注销钩子回调 |
| `get_config(key, default)` | 获取配置值 |
| `set_config(key, value)` | 设置配置值 |
| `show_toast(title, message, level)` | 显示通知 |
| `get_service(name)` | 获取宿主服务 |

### 可用钩子 (HookType)

| 钩子 | 说明 | 回调参数 |
|------|------|----------|
| `ON_LOAD` | 插件加载后 | 无 |
| `ON_UNLOAD` | 插件卸载前 | 无 |
| `ON_WIDGET_ADDED` | 小组件添加 | `widget_id: str` |
| `ON_WIDGET_REMOVED` | 小组件移除 | `widget_id: str` |
| `ON_WIDGET_SHOWN` | 小组件显示 | `widget_id: str` |
| `ON_WIDGET_HIDDEN` | 小组件隐藏 | `widget_id: str` |
| `ON_APP_STARTUP` | 应用启动 | 无 |
| `ON_APP_SHUTDOWN` | 应用关闭 | 无 |

### 可用服务

| 服务名 | 说明 |
|--------|------|
| `settings_service` | 设置服务 |
| `widget_manager` | 小组件管理器 |

## 示例：设置面板插件

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from app.plugins import BasePlugin, PluginAPI, PluginMeta, HookType

class Plugin(BasePlugin):
    meta = PluginMeta(
        id="settings_example",
        name="设置示例插件",
        description="演示如何在设置页添加面板",
    )

    def create_settings_widget(self) -> QWidget | None:
        """创建设置面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("这是插件的设置面板"))
        return widget
```

## 配置持久化

```python
def on_load(self, api: PluginAPI) -> None:
    # 读取配置
    enabled = api.get_config("enabled", True)
    
    # 写入配置
    api.set_config("enabled", False)
    
    # 支持嵌套路径
    api.set_config("notifications.email", "user@example.com")
```

## 注意事项

1. 插件类名必须为 `Plugin`
2. `on_load` 和 `on_unload` 不应抛出异常
3. 使用 `api.get_config/set_config` 存储数据，不要直接访问文件系统
4. 插件加载失败会在日志中记录，不会影响主程序运行
