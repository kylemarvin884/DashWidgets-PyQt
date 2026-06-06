"""快捷方式小组件 — Win11 风格，显示真实图标 + 右键管理"""
from __future__ import annotations
import os
import subprocess
import platform
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QEvent, QRectF, QMimeDatabase, QUrl, QTimer
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QIcon,
    QPainterPath, QRadialGradient, QPixmap, QAction,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDialog, QListWidget, QLineEdit, QPushButton,
    QListWidgetItem, QMenu, QMessageBox,
)

from app.widgets.base_widget import WidgetBase, WidgetConfig
from app.services.desktop_widget_service import Win11Style


# ── 全盘软件扫描 ────────────────────────────────────────────── #

class AppScanner:
    """扫描全盘已安装应用"""
    _instance = None
    _apps: list[dict] = []
    _scanned = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_apps(cls) -> list[dict]:
        if not cls._scanned:
            cls().scan()
        return cls._apps

    @staticmethod
    def extract_icon_from_exe(exe_path: str) -> QIcon | None:
        """从 exe 提取图标（Windows Shell32）"""
        if platform.system() != "Windows":
            return None
        # 尝试解析为完整路径
        resolved = AppScanner._resolve_path(exe_path)
        if not resolved or not os.path.exists(resolved):
            return None
        try:
            import ctypes
            from ctypes import wintypes

            SHGFI_ICON = 0x100
            SHGFI_LARGEICON = 0x0

            class SHFILEINFO(ctypes.Structure):
                _fields_ = [
                    ("hIcon", wintypes.HICON),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", wintypes.DWORD),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80),
                ]

            shell32 = ctypes.windll.shell32
            sfi = SHFILEINFO()
            result = shell32.SHGetFileInfoW(
                resolved, 0, ctypes.byref(sfi), ctypes.sizeof(sfi),
                SHGFI_ICON | SHGFI_LARGEICON
            )
            if sfi.hIcon and result:
                pm = _hicon_to_pixmap(sfi.hIcon, 48)
                user32 = ctypes.windll.user32
                user32.DestroyIcon(sfi.hIcon)
                if pm and not pm.isNull():
                    return QIcon(pm)
        except Exception:
            pass
        return None

    @staticmethod
    def _resolve_path(path: str) -> str | None:
        """解析可能不完整的应用路径"""
        if os.path.isabs(path) and os.path.exists(path):
            return path
        if not path:
            return None
        import shutil
        resolved = shutil.which(path)
        if resolved:
            return resolved
        # 搜索常见目录
        name = os.path.basename(path).lower()
        for base in [os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     os.environ.get("SYSTEMROOT", r"C:\Windows"),
                     os.environ.get("LOCALAPPDATA", ""),
                     ]:
            if not base:
                continue
            for root, dirs, files in os.walk(base):
                # 只遍历两层
                depth = root[len(base):].count(os.sep)
                if depth > 2:
                    continue
                for f in files:
                    if f.lower() == name or f.lower().rstrip('.exe') + '.exe' == name:
                        return os.path.join(root, f)
        return path  # 返回原始值，让调用方处理

    def scan(self) -> None:
        """扫描常用目录的 .exe 文件"""
        AppScanner._scanned = True
        seen_names: set[str] = set()
        apps: list[dict] = []

        # 扫描路径
        scan_dirs = self._get_scan_paths()

        for base_dir in scan_dirs:
            try:
                self._scan_dir(base_dir, apps, seen_names)
            except Exception:
                continue

        # 排序：按名称
        apps.sort(key=lambda x: x["name"].lower())
        AppScanner._apps = apps

    def _get_scan_paths(self) -> list[str]:
        paths = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
            os.environ.get("APPDATA", ""),
        ]
        result = [p for p in paths if p and os.path.isdir(p)]
        # 添加常见应用子目录
        extra = []
        for p in result:
            for sub in ["Programs", "Microsoft\\Windows\\Start Menu\\Programs",
                        "Programs", "Applications"]:
                full = os.path.join(p, sub)
                if os.path.isdir(full):
                    extra.append(full)
        result.extend(extra)
        return list(set(result))

    def _scan_dir(self, root: str, apps: list[dict], seen: set[str], depth=0) -> None:
        if depth > 2:
            return
        try:
            entries = os.listdir(root)
        except PermissionError:
            return
        for entry in entries:
            if entry.startswith('.'):
                continue
            path = os.path.join(root, entry)
            try:
                lower = entry.lower()
                # .lnk 快捷方式或 .exe
                if lower.endswith('.lnk'):
                    info = self._parse_lnk(path)
                    if info and info["name"] not in seen:
                        seen.add(info["name"])
                        apps.append(info)
                elif lower.endswith('.exe') and os.path.isfile(path):
                    name = entry.rsplit('.', 1)[0]
                    if name not in seen:
                        seen.add(name)
                        apps.append({"name": name, "path": path, "type": "exe"})
                elif os.path.isdir(path) and depth < 2:
                    self._scan_dir(path, apps, seen, depth + 1)
            except Exception:
                continue

    @staticmethod
    def _parse_lnk(lnk_path: str) -> dict | None:
        """解析 .lnk 快捷方式获取目标路径"""
        try:
            import comtypes.client
            shell = comtypes.client.CreateObject("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            target = shortcut.Targetpath
            name = os.path.splitext(os.path.basename(lnk_path))[0]
            if target and os.path.exists(target):
                return {"name": name, "path": target, "type": "lnk", "lnk": lnk_path}
        except Exception:
            pass
        # 回退：直接用 lnk 名称
        name = os.path.splitext(os.path.basename(lnk_path))[0]
        return {"name": name, "path": lnk_path, "type": "lnk"}


def _hicon_to_pixmap(hicon, size=48) -> QPixmap | None:
    """将 Windows HICON 转换为 QPixmap（使用 GetIconInfo + 位图数据）"""
    try:
        import ctypes
        from ctypes import wintypes
        from PySide6.QtGui import QImage

        class ICONINFO(ctypes.Structure):
            _fields_ = [
                ("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", ctypes.c_void_p),
                ("hbmColor", ctypes.c_void_p),
            ]

        class BITMAP(ctypes.Structure):
            _fields_ = [
                ("bmType", ctypes.c_long),
                ("bmWidth", ctypes.c_long),
                ("bmHeight", ctypes.c_long),
                ("bmWidthBytes", ctypes.c_long),
                ("bmPlanes", wintypes.WORD),
                ("bmBitsPixel", wintypes.WORD),
                ("bmBits", ctypes.c_void_p)
            ]

        GetIconInfo = ctypes.windll.user32.GetIconInfo
        GetObjectW = ctypes.windll.gdi32.GetObjectW
        GetBitmapBits = ctypes.windll.gdi32.GetBitmapBits
        DeleteObject = ctypes.windll.gdi32.DeleteObject

        ii = ICONINFO()
        if not GetIconInfo(hicon, ctypes.byref(ii)):
            return None

        hbm = ii.hbmColor or ii.hbmMask
        if not hbm:
            return None

        bm = BITMAP()
        n = GetObjectW(hbm, ctypes.sizeof(bm), ctypes.byref(bm))
        if not n:
            return None

        w = abs(bm.bmWidth)
        raw_h = abs(bm.bmHeight)
        h = raw_h // 2 if raw_h > w else raw_h
        h = max(h, 1)

        buf_size = w * h * 4
        buf = (ctypes.c_ubyte * buf_size)()
        copied = GetBitmapBits(hbm, buf_size, buf)

        if copied <= 0:
            return None

        img = QImage(bytes(buf), w, h, w * 4, QImage.Format_ARGB32).copy()
        img = img.mirrored(False, True)

        pm = QPixmap.fromImage(img.scaled(size, size,
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        return pm

    except Exception as e:
        pass
    return None


# ── 单个快捷图标 ────────────────────────────────────────────── #

class ShortcutItem(QWidget):
    def __init__(self, name: str, exec_path: str = "", parent=None):
        super().__init__(parent)
        self._name = name
        self._exec_path = exec_path
        self._hovered = False
        self._icon: QIcon | None = None
        self.setFixedSize(64, 76)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 异步加载图标
        self._load_icon()

    def _load_icon(self) -> None:
        if self._exec_path and os.path.exists(self._exec_path):
            self._icon = AppScanner.extract_icon_from_exe(self._exec_path)
        if not self._icon:
            self._icon = None

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._exec_path:
            try:
                if platform.system() == "Windows":
                    os.startfile(self._exec_path)
                else:
                    subprocess.Popen([self._exec_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        remove_act = menu.addAction("移除")
        action = menu.exec(self.mapToGlobal(pos))
        if action == remove_act:
            self.parentWidget().parentWidget()._remove_shortcut(self)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        c = Win11Style.widget_colors()
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2 - 6
        icon_size = 40

        # 背景
        bg_color = QColor(c["bg_input"]) if not self._hovered else QColor(c["track"])
        bg = QPainterPath()
        bg.addRoundedRect(cx - icon_size // 2, cy - icon_size // 2, icon_size, icon_size, 10, 10)
        p.setPen(QPen(QColor(c["border_input"]), 1))
        p.setBrush(QBrush(bg_color))
        p.drawPath(bg)

        # 图标
        if self._icon and not self._icon.isNull():
            pm = self._icon.pixmap(icon_size - 8, icon_size - 8, QIcon.Mode.Normal)
            if not pm.isNull():
                p.drawPixmap(cx - pm.width() // 2, cy - pm.height() // 2, pm)
        else:
            first_char = self._name[0].upper() if self._name else "?"
            char_font = QFont("Segoe UI Variable", 20, QFont.Weight.Light)
            p.setFont(char_font)
            p.setPen(QColor(c["text_secondary"]))
            p.drawText(QRectF(cx - icon_size // 2, cy - icon_size // 2, icon_size, icon_size),
                       Qt.AlignmentFlag.AlignCenter, first_char)
        p.end()

        # 名称
        p2 = QPainter(self)
        p2.setRenderHint(QPainter.RenderHint.Antialiasing)
        name_font = QFont("Segoe UI Variable", 9, QFont.Weight.Light)
        p2.setFont(name_font)
        p2.setPen(QColor(c["text"] if self._hovered else c["text_secondary"]))
        display_name = self._name[:5]
        if len(self._name) > 5:
            display_name += ".."
        p2.drawText(QRectF(0, h - 18, w, 16), Qt.AlignmentFlag.AlignCenter, display_name)
        p2.end()


# ── 添加应用对话框 ──────────────────────────────────────────── #

class AddAppDialog(QDialog):
    def __init__(self, existing_names: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加应用")
        self.setFixedSize(420, 520)
        self._existing = existing_names
        self._selected_app: dict | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 搜索框
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索应用...")
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        # 应用列表
        self._list = QListWidget()
        self._list.setIconSize(QSize(28, 28))
        layout.addWidget(self._list)

        # 按钮
        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._list.itemDoubleClicked.connect(self.accept)
        self._list.currentRowChanged.connect(self._on_select)

        # 加载应用（异步）
        QTimer.singleShot(100, self._load_apps)

    def _load_apps(self) -> None:
        apps = AppScanner.get_apps()
        self._all_apps = apps
        self._populate_list(apps)

    def _populate_list(self, apps: list[dict]) -> None:
        self._list.clear()
        for app in apps:
            if app["name"] in self._existing:
                continue
            item = QListWidgetItem(app["name"])
            item.setData(Qt.ItemDataRole.UserRole, app)
            # 尝试加载图标
            icon = AppScanner.extract_icon_from_exe(app.get("path", ""))
            if icon and not icon.isNull():
                item.setIcon(QIcon(icon.pixmap(24, 24)))
            else:
                # 默认图标
                item.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
            self._list.addItem(item)

    def _on_search(self, text: str) -> None:
        filtered = [a for a in self._all_apps if text.lower() in a["name"].lower()]
        self._populate_list(filtered)

    def _on_select(self, row: int) -> None:
        if row >= 0:
            item = self._list.item(row)
            self._selected_app = item.data(Qt.ItemDataRole.UserRole)

    def selected_app(self) -> dict | None:
        # 优先用双击/按钮确认时的选中项
        cur = self._list.currentItem()
        if cur:
            return cur.data(Qt.ItemDataRole.UserRole)
        return self._selected_app


# ── 快捷方式小组件主类 ───────────────────────────────────────── #

class ShortcutWidget(WidgetBase):
    WIDGET_TYPE = "shortcut"
    WIDGET_NAME = "快捷方式"

    DEFAULT_SHORTCUTS = [
        ("Chrome", "chrome.exe"),
        ("文件管理器", "explorer.exe"),
        ("终端", "cmd.exe"),
        ("记事本", "notepad.exe"),
        ("设置", "ms-settings:"),
    ]

    def __init__(self, config: WidgetConfig, services: dict, parent=None):
        super().__init__(config, services, parent)
        self._shortcuts: list[tuple[str, str]] = []  # [(name, exec_path)]
        self._icons: list[ShortcutItem] = []
        self._setup_ui()
        self._load_shortcuts()

        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._widget_context_menu)

    def _setup_ui(self) -> None:
        c = Win11Style.widget_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(4)
        title_lbl = QLabel("快捷方式")
        title_lbl.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.Light))
        title_lbl.setStyleSheet(f"color: {c['title']}; background: transparent;")
        main_layout.addWidget(title_lbl)

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        self._grid_layout = QHBoxLayout(grid_widget)
        self._grid_layout.setContentsMargins(0, 4, 0, 0)
        self._grid_layout.setSpacing(6)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(grid_widget, stretch=1)

    def _load_shortcuts(self) -> None:
        # 从配置加载，否则用默认
        saved = self.config.settings.get("shortcuts")
        if saved and isinstance(saved, list):
            self._shortcuts = [(s.get("name", ""), s.get("path", "")) for s in saved]
        else:
            self._shortcuts = list(self.DEFAULT_SHORTCUTS)
        self._rebuild_icons()

    def _save_config(self) -> None:
        self.config.settings["shortcuts"] = [
            {"name": n, "path": p} for n, p in self._shortcuts
        ]
        # 触发保存回调
        cb = getattr(self.services, 'on_config_changed', None)
        if cb:
            cb(self.config)

    def _rebuild_icons(self) -> None:
        # 清除旧图标
        for icon in self._icons:
            icon.deleteLater()
        self._icons.clear()

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for name, exec_path in self._shortcuts:
            si = ShortcutItem(name, exec_path, parent=self)
            self._grid_layout.addWidget(si)
            self._icons.append(si)

    # ── 右键菜单 ── #

    def _widget_context_menu(self, pos):
        menu = QMenu(self)
        add_act = menu.addAction("+ 添加应用")
        refresh_act = menu.addAction("刷新列表")
        action = menu.exec(self.mapToGlobal(pos))
        if action == add_act:
            self._open_add_dialog()
        elif action == refresh_act:
            AppScanner._scanned = False  # 强制重新扫描
            AppScanner().scan()

    def _open_add_dialog(self) -> None:
        existing = {n for n, _ in self._shortcuts}
        dlg = AddAppDialog(existing, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            app = dlg.selected_app()
            if app:
                self._shortcuts.append((app["name"], app["path"]))
                self._rebuild_icons()
                self._save_config()

    def _remove_shortcut(self, item: ShortcutItem) -> None:
        idx = None
        for i, si in enumerate(self._icons):
            if si is item:
                idx = i
                break
        if idx is not None:
            self._shortcuts.pop(idx)
            self._rebuild_icons()
            self._save_config()
