# DashWidgets 插件开发文档

## 概述

DashWidgets 支持插件扩展，允许开发者创建自定义功能来扩展应用能力。插件可以：
- 监听应用事件（如小组件添加、移除、应用启动/关闭）
- 扩展 UI（在设置页添加配置面板）
- 持久化插件配置
- 显示用户通知
- 访问宿主服务（设置服务、小组件管理器）

插件管理器自动扫描 `plugins_ext/` 目录，加载符合规范的插件。插件加载失败不会影响主程序运行。

> 注：当前版本（DashWidgets）支持基本的插件功能。高级功能如依赖插件、自定义小组件注册等仅在 LTC（小树时钟）版本中实现，未来可能合并到主版本。

## 插件结构

### 方式一：包形式（推荐）

```
plugins_ext/
    my_plugin/
        __init__.py      # Plugin 类定义
        plugin.json      # 插件元数据
        config.json      # 插件配置（自动生成）
        requirements.txt # 可选，PyPI依赖声明
        assets/          # 可选，静态资源
```

### 方式二：单文件形式

```
plugins_ext/
    my_simple_plugin.py   # 单文件插件
```

单文件插件的配置数据将存储在 `plugins_ext/._data/my_simple_plugin/config.json`。

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

## 清单文件 (plugin.json)

`plugin.json` 位于插件目录根部，所有字段如下：

```json
{
  "id": "my_plugin",
  "name": "我的插件",
  "version": "1.0.0",
  "author": "作者名 <email@example.com>",
  "description": "一句话描述插件功能",
  "homepage": "https://github.com/yourname/my_plugin",
  "min_host_version": "1.0.0",
  "dependencies": ["requests>=2.31.0"],
  "tags": ["notification", "widget"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 全局唯一标识符，建议 `snake_case` |
| `name` | string | ✅ | 用户可见的插件名称，支持中文 |
| `version` | string | | 语义化版本，默认 `"1.0.0"` |
| `author` | string | | 作者名或邮箱 |
| `description` | string | | 一句话功能描述，显示在插件管理界面 |
| `homepage` | string | | 项目主页 / 文档 URL |
| `min_host_version` | string | | 要求的最低宿主版本，为空不限制 |
| `dependencies` | array | | PyPI 依赖列表，仅声明，不自动安装 |
| `tags` | array | | 分类标签 |

> `plugin.json` 中的元数据会覆盖 `Plugin.meta` 类属性，两者均写时以 `plugin.json` 为准。

## 主入口类 Plugin

- **类名必须为 `Plugin`**，管理器按此名称查找。
- 继承自 `app.plugins.BasePlugin`。
- `meta` 类属性为回退声明，通常由 `plugin.json` 覆盖。

```python
from app.plugins import BasePlugin, PluginMeta, HookType
from app.plugins.base_plugin import PluginAPI

class Plugin(BasePlugin):
    # 回退元数据（无 plugin.json 时生效）
    meta = PluginMeta(
        id="my_plugin",
        name="我的插件",
        version="1.0.0",
        author="作者",
        description="描述",
    )

    def __init__(self):
        self._api: PluginAPI | None = None

    def on_load(self, api: PluginAPI) -> None:
        """插件初始化：注册钩子、读取配置等。"""
        self._api = api
        # 注册钩子
        api.register_hook(HookType.ON_WIDGET_ADDED, self._on_widget_added)
        # 读取配置
        enabled = api.get_config("enabled", True)
        # 显示通知
        api.show_toast("插件加载", f"插件已加载，当前状态: {'启用' if enabled else '禁用'}")

    def on_unload(self) -> None:
        """插件卸载：清理定时器、释放资源等。"""
        if self._api:
            self._api.show_toast("插件卸载", "插件正在卸载")

    def create_settings_widget(self) -> QWidget | None:
        """返回插件专属的设置面板（嵌入宿主设置页）。"""
        return None
```

### 生命周期方法

| 方法 | 调用时机 | 说明 |
|------|----------|------|
| `on_load(api)` | 插件被加载后 | 注册钩子、读取配置、初始化状态 |
| `on_unload()` | 插件被卸载前 | 停止后台线程、清理资源 |
| `create_settings_widget()` | UI 需要时 | 返回设置面板 `QWidget`，可为 `None` |

## PluginAPI 接口参考

`on_load` 传入的 `api` 对象是插件与宿主通信的唯一通道。

### 钩子注册

```python
api.register_hook(HookType.ON_WIDGET_ADDED, callback)
api.unregister_hook(HookType.ON_WIDGET_ADDED, callback)
```

### 持久化配置

```python
# 读取（支持点号路径，不存在时返回 default）
value = api.get_config("notifications.enabled", default=True)

# 写入并立即保存到磁盘
api.set_config("notifications.enabled", False)
api.set_config("stats.count", api.get_config("stats.count", 0) + 1)
```

### 用户通知

```python
api.show_toast("标题", "详细内容", level="info")
# level: "info" | "success" | "warning" | "error"
```

### 宿主服务访问

```python
settings_service = api.get_service("settings_service")
widget_manager = api.get_service("widget_manager")
```

可用服务名称：

| 名称 | 类型 | 说明 |
|------|------|------|
| `"settings_service"` | `SettingsService` | 应用设置读写 |
| `"widget_manager"` | `DesktopWidgetManager` | 小组件管理器 |

## 钩子 (HookType) 列表

宿主当前会触发以下钩子（其余为预留，暂无宿主调用点）：

| 钩子 | 说明 | 回调参数 | 宿主触发时机 |
|------|------|----------|--------------|
| `ON_APP_STARTUP` | 应用启动 | 无 | 所有插件加载完成后触发一次 |
| `ON_APP_SHUTDOWN` | 应用关闭 | 无 | 退出前、`on_unload` 之前触发 |
| `ON_WIDGET_SHOWN` | 小组件显示 | `widget_id: str` | 桌面组件显示时 |
| `ON_WIDGET_HIDDEN` | 小组件隐藏 | `widget_id: str` | 桌面组件隐藏时 |
| `ON_WIDGET_REMOVED` | 小组件移除 | `widget_id: str` | 桌面组件关闭并停用时 |

预留（注册后暂不会被宿主触发）：`ON_LOAD`、`ON_UNLOAD`（由生命周期方法 `on_load`/`on_unload` 承担）、`ON_WIDGET_ADDED`、`ON_ALARM_BEFORE`、`ON_ALARM_AFTER`、`ON_TIMER_DONE`、`ON_STOPWATCH_LAP`、`ON_FOCUS_START`、`ON_FOCUS_END`、`CUSTOM_TRIGGER`、`CUSTOM_ACTION`、`SETTINGS_WIDGET`、`SIDEBAR_WIDGET`。

注意：插件被 **禁用** 时，其钩子/触发器/动作会自动从宿主摘除（不再收到事件），重新 **启用** 时自动恢复。

## 热重载

- 调试窗口的「重载插件」按钮会对所有已加载插件执行真正的热重载（重新执行插件源码），并加载新发现的插件。
- 通过 `.dw` 包覆盖升级已加载的插件后，会自动热重载使其立即生效。
- 依赖库插件重载后，依赖它的功能插件持有的旧引用会失效，需要一并重载。

## 权限

- 声明了 `permissions` 的插件在首次加载时弹出授权确认；勾选「始终允许」后会持久化到 `config/plugin_permissions.json`，跨启动不再重复询问。
- 运行时通过 `api.has_permission(permission)` 检查是否已获授权（最小权限：未声明/未批准返回 `False`）。
- 运行时通过 `api.request_permission(permission, reason)` 弹窗申请额外权限，批准后立即生效。
- 卸载插件会同时撤销其「始终允许」授权。

## 版本兼容与升级

- `min_host_version` 会被强制校验：宿主版本过低时插件拒绝加载，并在插件页显示原因。
- 安装 `.dw` 包时按版本判断：仅允许同版本修复或升级安装，降级会被拒绝（需先卸载）；升级时会保留插件数据目录中的 `config.json`。

## 配置持久化

插件配置自动保存在插件目录下的 `config.json`（包形式）或 `plugins_ext/._data/<id>/config.json`（单文件形式）。

**支持点号路径的嵌套读写：**

```python
# 写入嵌套结构
api.set_config("ui.theme", "dark")
api.set_config("stats.alarm_count", 0)

# 读取嵌套值，不存在时返回默认值
theme = api.get_config("ui.theme", default="light")
count = api.get_config("stats.alarm_count", default=0)
```

生成的 `config.json` 示例：

```json
{
  "ui": { "theme": "dark" },
  "stats": { "alarm_count": 5 }
}
```

> 请勿在插件中直接读写宿主的 `config/` 目录，配置隔离是插件稳定运行的基础。

## UI 扩展点

### 设置面板

在 `Plugin` 类中重写 `create_settings_widget()`，返回一个 `QWidget`。
宿主会将其嵌入"设置 → 插件配置"区域。

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox

def create_settings_widget(self) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    
    # 添加自定义控件
    label = QLabel("插件专属设置")
    layout.addWidget(label)
    
    self.enable_checkbox = QCheckBox("启用功能")
    self.enable_checkbox.setChecked(self._api.get_config("enabled", True))
    self.enable_checkbox.stateChanged.connect(self._on_enable_changed)
    layout.addWidget(self.enable_checkbox)
    
    layout.addStretch()
    return w

def _on_enable_changed(self, state):
    self._api.set_config("enabled", state == Qt.CheckState.Checked)
```

## 注册自定义小组件类型（仅 LTC 版本）

> 此功能仅在 LTC（小树时钟）版本中可用，DashWidgets 主版本暂不支持。

在 LTC 版本中，插件可以注册新的小组件类型，使其出现在"添加小组件"菜单中。

```python
def on_load(self, api: PluginAPI) -> None:
    # 将自定义小组件注册到全局小组件注册表
    from app.widgets.registry import WidgetRegistry
    from .my_widget import MyCustomWidget
    
    WidgetRegistry.instance().register(MyCustomWidget)
    api.show_toast("自定义小组件", "插件已加载，可在添加组件菜单中找到新组件", level="success")
```

## 注意事项与最佳实践

### ✅ 应当

- 主类名严格使用 `Plugin`
- 在 `plugin.json` 中提供完整的元数据
- 在 `__init__` 中仅做轻量初始化（不访问 `api`）
- 在 `on_load` 中保存 `api` 引用：`self._api = api`
- 使用 `api.get_config` / `api.set_config` 持久化所有插件数据
- 在 `on_unload` 中停止所有后台线程和定时器
- 在钩子回调中捕获内部异常，不向外抛出

### ❌ 不应当

- 直接导入宿主内部模块（如 `from app.services.settings_service import SettingsService`）
- 直接读写 `config/` 目录下的宿主配置文件
- 在 `on_load` 中执行耗时操作（会阻塞 UI 启动）
- 使用与其他插件相同的钩子回调 ID（可能冲突）
- 在类体（`__init__` 之外）进行有副作用的 Qt 操作

### 依赖管理

在 `requirements.txt` 中声明所需 PyPI 包：

```
requests>=2.31.0
pillow>=10.0.0
```

> 管理器只读取 `plugin.json` 中的 `dependencies` 字段作信息展示，不自动安装。
> 用户需手动安装依赖：`pip install -r plugins_ext/my_plugin/requirements.txt`

## 示例插件

### Hello World 示例

参考 `plugins_ext/hello_world_plugin/`：

- `plugin.json`：插件元数据
- `__init__.py`：插件实现，演示钩子注册和配置持久化

### 自定义小组件示例（LTC 版本）

参考 LTC 版本的 `hitokoto_widget` 插件（位于 `LTC/plugins_ext/hitokoto_widget/`）：

- 注册新的小组件类型（仅 LTC 版本支持）
- 支持多种数据源（API、本地文件）
- 演示复杂插件的实现

> 注：此示例仅适用于 LTC 版本，DashWidgets 主版本暂无小组件注册表。

## 调试与日志

插件中的异常会被捕获并记录到日志。使用 `loguru` 记录器：

```python
from loguru import logger

def on_load(self, api: PluginAPI) -> None:
    logger.info("插件 {} 开始加载", self.meta.name)
    try:
        # 插件逻辑
        pass
    except Exception as e:
        logger.exception("插件加载异常")
```

日志文件位于：`~/.dashwidgets/logs/`

## 插件管理器界面

在主应用导航栏中点击"插件"进入插件管理界面，可以：
- 查看所有已加载插件
- 启用/禁用插件
- 查看插件元数据和错误信息
- 手动刷新插件列表

## 未来扩展计划

以下功能已在 LTC（小树时钟）版本中实现，DashWidgets 主版本未来可能支持：

1. **依赖插件 (LibraryPlugin)**：插件间共享代码，继承 `LibraryPlugin` 并实现 `export()` 方法
2. **自动化集成**：注册自定义触发器和动作，供自动化规则使用
3. **插件依赖声明**：通过 `requires` 字段声明插件间依赖关系，管理器自动处理加载顺序
4. **侧边栏扩展**：在主界面侧边栏添加面板，通过 `create_sidebar_widget()` 方法
5. **自定义小组件注册**：插件注册新的小组件类型，出现在添加菜单中
6. **插件类型 (PluginType)**：区分功能插件 (`feature`) 和库插件 (`library`)

> 这些高级功能的具体实现可参考 LTC 版本的 `PLUGIN_GUIDE.md` 和示例插件。

## 常见问题

### Q: 插件加载失败怎么办？
A: 检查日志文件 `~/.dashwidgets/logs/` 中的错误信息，常见原因：
- 缺少必填字段的 `plugin.json`
- `Plugin` 类未定义或继承错误
- 插件代码中存在语法错误

### Q: 插件如何更新配置？
A: 使用 `api.set_config()` 写入配置，配置会自动保存到插件目录下的 `config.json`。

### Q: 插件可以访问主窗口吗？
A: 不建议直接访问，应通过 `api.get_service()` 获取所需服务。如需访问 UI，考虑实现 `create_settings_widget()` 方法。

### Q: 插件可以添加新的导航项吗？
A: 当前版本不支持。未来版本可能支持侧边栏扩展（通过 `create_sidebar_widget()` 方法）。

---

*更多问题请参考项目 Issues 或提交新的 Issue。*