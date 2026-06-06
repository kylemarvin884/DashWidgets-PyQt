"""示例插件"""
from app.plugins import BasePlugin, PluginAPI, PluginMeta, HookType


class Plugin(BasePlugin):
    """示例插件 - 展示基本用法"""
    
    meta = PluginMeta(
        id="example_plugin",
        name="示例插件",
        version="1.0.0",
        author="开发者",
        description="这是一个示例插件，展示了插件的基本结构",
    )

    def __init__(self):
        self._api: PluginAPI | None = None

    def on_load(self, api: PluginAPI) -> None:
        """插件加载时调用"""
        self._api = api
        api.logger.info("示例插件已加载")
        
        # 注册钩子
        api.register_hook(HookType.ON_WIDGET_ADDED, self._on_widget_added)

    def on_unload(self) -> None:
        """插件卸载时调用"""
        if self._api:
            self._api.logger.info("示例插件已卸载")

    def _on_widget_added(self, widget_id: str) -> None:
        """小组件添加回调"""
        if self._api:
            self._api.show_toast("示例插件", f"小组件已添加: {widget_id}")
