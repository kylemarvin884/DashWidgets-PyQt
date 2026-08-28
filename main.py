"""
DashWidgets - Windows桌面小组件管理器
PySide6 + Fluent Design

运行方式：
    uv run main.py
    或
    python main.py
"""
import sys
import argparse
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QFont

from app.constants import APP_NAME

_SERVER_NAME = f"{APP_NAME}.SingleInstanceServer"
_SOCKET_TIMEOUT_MS = 1_000


def _parse_args() -> tuple[str | None, bool, str | None]:
    """从命令行参数中提取 --url、--autostart 和 --import 值"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--url", default=None)
    parser.add_argument("--autostart", action="store_true", default=False)
    parser.add_argument("--import", dest="import_path", default=None,
                        help="导入 .dw 插件包文件")
    args, _ = parser.parse_known_args()
    return args.url, args.autostart, args.import_path


def _try_forward_to_running(message: str) -> bool:
    """尝试把消息转发给已运行的实例"""
    sock = QLocalSocket()
    sock.connectToServer(_SERVER_NAME)
    if sock.waitForConnected(_SOCKET_TIMEOUT_MS):
        sock.write(message.encode("utf-8"))
        sock.waitForBytesWritten(_SOCKET_TIMEOUT_MS)
        sock.disconnectFromServer()
        return True
    return False


def _load_custom_font() -> str | None:
    """加载自定义字体"""
    font_path = Path(__file__).parent / "assets" / "fonts" / "HarmonyOS_Sans_SC_Regular.ttf"

    if font_path.exists():
        try:
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    font_family = families[0]
                    from loguru import logger
                    logger.info("已加载自定义字体: {}", font_family)
                    return font_family
        except Exception as e:
            from loguru import logger
            logger.warning("字体加载异常: {}", e)
    return None


def main():
    """应用入口"""
    # 高DPI支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 字体：加载随包的 HarmonyOS Sans SC 作为应用默认字体
    # （中文渲染更佳；Fluent 控件各自的 font-family 样式不受影响）
    custom_font_family = _load_custom_font()
    if custom_font_family:
        default_font = QFont(custom_font_family, 10)
        app.setFont(default_font)

    # 主题交给 qfluentwidgets（默认 Auto 跟随系统）；窗口背景交由
    # FluentWindow 的 Mica 云母材质渲染——应用级 QSS 一律不设
    # QWidget background（会盖住云母，见 OPTIMIZATION_SUMMARY 第九轮）

    # 解析参数
    url_arg, is_autostart, import_path = _parse_args()

    # 尝试转发给已运行的实例
    if import_path:
        if _try_forward_to_running(f"--import:{import_path}"):
            sys.exit(0)
    elif url_arg:
        if _try_forward_to_running(url_arg):
            sys.exit(0)

    # 正常启动
    from app.window import MainWindow

    w = MainWindow()

    # 注册文件关联
    if sys.platform == "win32":
        from app.services.url_scheme_service import is_dw_association_registered, register_dw_file_association
        if not is_dw_association_registered():
            register_dw_file_association()

    # 显示窗口
    if is_autostart:
        w.hide()
    else:
        w.show()

    # 单实例服务
    _server = QLocalServer(app)
    QLocalServer.removeServer(_SERVER_NAME)
    _server.listen(_SERVER_NAME)

    def _on_new_connection():
        conn = _server.nextPendingConnection()
        if conn and conn.waitForReadyRead(500):
            raw = conn.readAll().data()
            data = bytes(raw).decode("utf-8", errors="ignore").strip()
            conn.disconnectFromServer()
            if not data:
                return
            if data.startswith("--import:"):
                import_file = data[len("--import:"):]
                w.handle_import(import_file)
            else:
                w.handle_url(data)

    _server.newConnection.connect(_on_new_connection)

    # 全局热键
    from app.services.global_hotkey_service import GlobalHotkeyService
    _hotkey_service = GlobalHotkeyService()
    _hotkey_service.register("toggle_widgets", "<cmd>+<shift>+d")
    _hotkey_service.triggered.connect(lambda name: w.toggle_all_widgets() if name == "toggle_widgets" else None)
    _hotkey_service.start()
    app.aboutToQuit.connect(_hotkey_service.stop)

    # 延迟处理 URL 和导入
    if url_arg:
        QTimer.singleShot(1200, lambda: w.handle_url(url_arg))
    if import_path:
        QTimer.singleShot(800, lambda: w.handle_import(import_path))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()