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


def _build_menu_production(widget_id: str, settings: dict | None = None):
    """生产路径：不传 widget_instance，由窗口经注册表自行创建组件

    回归：曾因创建的实例未赋回 _widget_instance，统一菜单丢失组件动作。
    """
    from app.services.desktop_widget_service import DesktopWidgetWindow
    from app.models.widget_model import WidgetInfo

    info = WidgetInfo(id=widget_id, name=widget_id, custom_settings=settings or {})
    win = DesktopWidgetWindow(info)  # 与 show_widget 相同的构造方式
    menu, _actions = win._build_context_menu()
    labels = [a.text() for a in menu.actions() if a.text()]
    win.deleteLater()
    return labels


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

    def test_close_action_included(self):
        """统一菜单必须包含可用的「关闭小组件」动作（回归：act_close 曾丢失）"""
        labels, _ = _build_menu("clock", {})
        assert "关闭小组件" in labels

    def test_widget_actions_via_production_path(self):
        """生产路径（窗口自行创建组件实例）下组件动作也要出现在菜单中"""
        labels = _build_menu_production("image", {})
        assert "更换图片" in labels, labels
        assert "组件设置..." in labels and "关闭小组件" in labels

        labels2 = _build_menu_production("image", {"image_path": "x.png"})
        assert "清除图片" in labels2, labels2

    def test_widget_instance_recorded_and_teardown(self):
        """窗口必须记录创建的组件实例；关闭时调用其 on_close（幂等）"""
        from PySide6.QtWidgets import QApplication
        from app.services.desktop_widget_service import DesktopWidgetWindow
        from app.models.widget_model import WidgetInfo
        from app.widgets.base_widget import WidgetConfig, WidgetBase

        # 借用 image 组件记录 on_close 调用次数
        info = WidgetInfo(id="image", name="图片")
        win = DesktopWidgetWindow(info)
        assert win._widget_instance is not None, "生产路径未记录组件实例"

        calls = {"n": 0}
        orig_on_close = win._widget_instance.on_close

        def _counting_on_close():
            calls["n"] += 1
            orig_on_close()

        win._widget_instance.on_close = _counting_on_close
        win._teardown_widget()
        win._teardown_widget()  # 幂等
        assert calls["n"] == 1
        win.deleteLater()
        _ = QApplication.instance()

    def test_build_menu_returns_close_action_ref(self):
        from app.services.desktop_widget_service import DesktopWidgetWindow
        from app.models.widget_model import WidgetInfo

        win = DesktopWidgetWindow(WidgetInfo(id="clock", name="时钟"))
        _menu, actions = win._build_context_menu()
        assert actions["close"] is not None
        assert actions["close"].text() == "关闭小组件"
        win.deleteLater()


class TestHomeViewPlaceholder:
    """主页排行占位符的重复刷新回归（曾因 QLayoutItem 失效崩溃）"""

    @pytest.fixture(scope="class", autouse=True)
    def _qapp(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        yield app

    def test_placeholder_refresh_twice(self):
        """占位符已存在时再次刷新不应崩溃"""
        from app.views.home_view import HomeView

        view = HomeView()
        # 无使用数据时 _refresh_leaderboard 走占位符路径
        view._show_board_placeholder()
        view._show_board_placeholder()  # 第二次：移除旧占位符再新建
        view._refresh_leaderboard()
        placeholders = [
            view._board_lay.itemAt(i).widget()
            for i in range(view._board_lay.count())
            if view._board_lay.itemAt(i).widget()
            and view._board_lay.itemAt(i).widget().objectName() == "boardPlaceholder"
        ]
        assert len(placeholders) == 1, "占位符应恰好一个"
        view.deleteLater()
