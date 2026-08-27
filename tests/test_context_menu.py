"""组件右键统一菜单测试（组件动作合并 + 主题样式）"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _build_menu(widget_id: str, settings: dict | None = None):
    """创建 包着指定组件实例的窗口 并构建统一右键菜单，返回 (labels, qss)"""
    from app.services.desktop_widget_service import DesktopWidgetWindow
    from app.models.widget_model import WidgetInfo
    from app.widgets.registry import WidgetRegistry
    from app.widgets.base_widget import WidgetConfig

    info = WidgetInfo(id=widget_id, name=widget_id, custom_settings=settings or {})
    inst = WidgetRegistry.instance().create(
        WidgetConfig(widget_type=widget_id, id=widget_id,
                     width=320, height=220, settings=settings or {}),
        {},
    )
    assert inst is not None, f"{widget_id} 创建失败"
    win = DesktopWidgetWindow(info, widget_instance=inst)
    menu, _actions = win._build_context_menu()
    labels = [a.text() for a in menu.actions() if a.text()]
    qss = menu.styleSheet()
    win.deleteLater()
    return labels, qss


class TestUnifiedContextMenu:
    def test_image_actions_merged(self):
        labels, _ = _build_menu("image", {})
        assert "更换图片" in labels
        assert "清除图片" not in labels
        # 系统项与组件动作同处一个菜单
        for sys_item in ("组件设置...", "窗口层级", "鼠标穿透", "关闭小组件"):
            assert sys_item in labels

    def test_image_clear_when_set(self):
        labels, _ = _build_menu("image", {"image_path": "x.png"})
        assert "更换图片" in labels and "清除图片" in labels

    def test_document_viewer_actions(self):
        labels, _ = _build_menu("document_viewer", {"doc_path": "a.txt"})
        for item in ("更换文档", "清除文档", "全选", "复制选中"):
            assert item in labels

    def test_widget_without_actions(self):
        labels, _ = _build_menu("clock", {})
        assert "组件设置..." in labels
        assert "更换图片" not in labels

    def test_menu_has_opaque_background(self):
        """统一菜单自带不透明背景（修复继承透明样式导致的黑底）"""
        _, qss = _build_menu("image", {})
        assert "background: #" in qss
        # QMenu 规则段不含 transparent 背景
        menu_rule = qss.split("QMenu {", 1)[1]
        assert "background: transparent" not in menu_rule

    def test_widgets_no_longer_override_context_menu(self):
        """组件不应再自建 contextMenuEvent（会得到黑底菜单）"""
        from app.widgets.builtin.image_widget import ImageWidget
        from app.widgets.builtin.document_viewer_widget import DocumentViewerWidget
        for cls in (ImageWidget, DocumentViewerWidget):
            assert "contextMenuEvent" not in cls.__dict__, cls.__name__
            assert "get_context_menu_actions" in cls.__dict__, cls.__name__
