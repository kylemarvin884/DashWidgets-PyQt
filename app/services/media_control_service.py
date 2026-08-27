"""
Windows 媒体控制服务

纯 Win32 API 实现，无需额外依赖：
1. 发送媒体键控制（播放/暂停、上一曲、下一曲）
2. 通过 Windows Audio Session 枚举活跃音频会话
3. 窗口标题回退探测常见音乐应用

线程模型：单个轮询线程负责探测状态，通过 Qt 信号（自动排队到主线程）
通知 UI；UI 线程只读 state，不再触发探测，避免阻塞主线程。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, Signal

# ── Windows 常量 ──────────────────────────────────────────────── #

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32


class _MediaSignals(QObject):
    """跨线程媒体状态信号桥（轮询线程 → UI 线程，Qt 自动排队）"""
    state_changed = Signal(object)  # MediaState
    media_key_sent = Signal(str)


media_signals = _MediaSignals()


@dataclass
class MediaState:
    """当前媒体状态"""
    is_playing: bool = False
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    position: float = 0.0
    thumbnail_path: str = ""


class MediaControlService:
    """Windows 媒体控制服务 — 单例"""

    _instance: Optional["MediaControlService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._state = MediaState()
        self._callbacks: list = []
        self._polling = False
        self._poll_lock = threading.Lock()
        self._listeners = 0
        self._wake = threading.Event()
        self._local = threading.local()  # 每线程独立的 winrt 事件循环
        self._last_emitted: tuple | None = None  # (title, artist, is_playing)
        self._last_thumb_bytes: bytes | None = None
        # 手动跟踪播放状态（用于图标切换）
        self._manually_playing = False

    # ------------------------------------------------------------------ #
    #  媒体键控制（纯 Win32 keybd_event）
    # ------------------------------------------------------------------ #

    def play_pause(self) -> None:
        self._send_media_key(VK_MEDIA_PLAY_PAUSE)
        # 切换手动跟踪的播放状态
        self._manually_playing = not self._manually_playing
        media_signals.media_key_sent.emit("play_pause")
        self.request_refresh()

    def next_track(self) -> None:
        self._send_media_key(VK_MEDIA_NEXT_TRACK)
        media_signals.media_key_sent.emit("next")
        self.request_refresh()

    def prev_track(self) -> None:
        self._send_media_key(VK_MEDIA_PREV_TRACK)
        media_signals.media_key_sent.emit("prev")
        self.request_refresh()

    def previous_track(self) -> None:
        """prev_track 的别名（保持旧 API 兼容）"""
        self.prev_track()

    def stop(self) -> None:
        self._send_media_key(VK_MEDIA_STOP)
        self._manually_playing = False

    @staticmethod
    def _send_media_key(vk_code: int) -> None:
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    # ------------------------------------------------------------------ #
    #  状态查询
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> MediaState:
        return self._state

    def refresh(self) -> MediaState:
        self._try_read_state()
        return self._state

    def on_state_changed(self, callback) -> None:
        self._callbacks.append(callback)

    def start_polling(self, interval_ms: int = 2000) -> None:
        """启动（或加入）单一轮询线程；多次调用不会创建额外线程"""
        with self._poll_lock:
            self._listeners += 1
            interval_ms = min(
                interval_ms,
                getattr(self, "_interval_ms", interval_ms),
            )
            self._interval_ms = interval_ms
            if self._polling:
                return
            self._polling = True

        t = threading.Thread(
            target=self._poll_loop,
            args=(interval_ms / 1000.0,),
            daemon=True,
            name="DashWidgetsMediaPoll",
        )
        t.start()

    def stop_polling(self) -> None:
        """引用计数式停止：所有监听者退出后才真正结束轮询线程"""
        with self._poll_lock:
            self._listeners = max(0, self._listeners - 1)
            if self._listeners == 0:
                self._polling = False
                self._wake.set()

    def request_refresh(self) -> None:
        """让轮询线程立刻探测一次（无需等待下个周期）"""
        self._wake.set()

    def _poll_loop(self, interval: float) -> None:
        while self._polling:
            self.refresh()
            self._notify_if_changed()
            # 用 Event.wait 代替 time.sleep，便于被立即唤醒
            self._wake.wait(interval)
            self._wake.clear()

    def _notify_if_changed(self) -> None:
        """状态摘要变化时通过 Qt 信号广播（自动排队到 UI 线程）"""
        sig = (self._state.title, self._state.artist, self._state.is_playing)
        if sig != self._last_emitted:
            self._last_emitted = sig
            media_signals.state_changed.emit(self._state)
            for cb in self._callbacks:
                try:
                    cb(self._state)
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    #  状态读取：多级策略
    # ------------------------------------------------------------------ #

    def _try_read_state(self) -> None:
        # 方法1：尝试 winrt（如果可用）
        if self._try_winrt():
            return

        # 方法2：枚举音频会话
        if self._try_audio_sessions():
            return

        # 方法3：窗口标题探测
        self._detect_by_window_title()

    def _try_winrt(self) -> bool:
        try:
            from winrt.windows.media.controls import GlobalSystemMediaTransportControlsSessionManager as GSMTCManager
            self._has_winrt = True
            return self._read_via_winrt()
        except ImportError:
            return False
        except Exception:
            return False

    def _read_via_winrt(self) -> bool:
        import asyncio

        async def _async_read():
            from winrt.windows.media.controls import (
                GlobalSystemMediaTransportControlsSessionManager,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus,
            )
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            if not session:
                self._state = MediaState(is_playing=False)
                return False

            info = await session.try_get_media_properties_async()
            pb_info = session.get_playback_info()

            playing = pb_info.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING

            self._state = MediaState(
                is_playing=playing,
                title=(info.title or "")[:60],
                artist=(info.artist or "")[:40],
                album=(info.album_title or "")[:40],
                duration=float(info.duration.total_seconds()) if info.duration else 0.0,
            )

            try:
                thumb = info.thumbnail
                if thumb:
                    thumb_bytes = bytes(thumb)
                    if len(thumb_bytes) > 100 and thumb_bytes != self._last_thumb_bytes:
                        from pathlib import Path
                        out_dir = Path(__file__).parent.parent.parent / "data"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_path = out_dir / "_media_thumb.jpg"
                        with open(out_path, "wb") as f:
                            f.write(thumb_bytes)
                        self._last_thumb_bytes = thumb_bytes
                        self._state.thumbnail_path = str(out_path)
            except Exception:
                pass
            return True

        try:
            loop = self._winrt_loop()
            return loop.run_until_complete(_async_read())
        except Exception:
            return False

    def _winrt_loop(self):
        """复用当前线程的 asyncio 事件循环（避免每次探测都新建/销毁）"""
        import asyncio

        loop = getattr(self._local, "loop", None)
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            self._local.loop = loop
        return loop

    # ── 音频会话枚举（通过 Windows Core Audio API）── #

    def _try_audio_sessions(self) -> bool:
        """枚举系统音频会话，获取活跃的音频源信息"""
        try:
            ole32 = ctypes.windll.ole32
            ole32.CoInitializeEx(None, 2)  # COINIT_MULTITHREADED
        except Exception:
            pass

        try:
            CLSID_MMDeviceEnumerator = ctypes.GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            IID_IMMDeviceEnumerator = ctypes.GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            IID_IAudioSessionManager2 = ctypes.GUID("{77AA95A9-451B-4DA3-B955-9382073FC48B}")
            IID_IAudioSessionEnumerator = ctypes.GUID("{E2F5BB11-D87B-70B-94EC-63AC67721A69}")
            IID_IAudioSessionControl = ctypes.GUID("{F4B1A599-7B36-4B17-9192-8AE9AAE22F99}")

            dev_enum = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(
                ctypes.byref(CLSID_MMDeviceEnumerator), None,
                1,  # CLSCTX_ALL
                ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(dev_enum),
            )
            if hr or not dev_enum:
                return False

            default_dev = ctypes.c_void_p()
            IID_IID_MmDev = ctypes.GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            hr = dev_enum.GetDefaultAudioEndpoint(0, 0, ctypes.byref(IID_IID_MmDev), ctypes.byref(default_dev))
            if hr or not default_dev:
                return False

            asm2 = ctypes.c_void_p()
            hr = default_dev.Activate(ctypes.byref(IAudioSessionManager2), 1, None, ctypes.byref(asm2))
            if hr or not asm2:
                return False

            sess_enum = ctypes.c_void_p()
            asm2.GetSessions(ctypes.byref(sess_enum))
            if not sess_enum:
                return False

            count = ctypes.c_int(0)
            sess_enum.GetCount(ctypes.byref(count))

            sessions = []
            for i in range(min(count.value, 30)):
                ctrl = ctypes.c_void_p()
                hr = sess_enum.GetSession(i, ctypes.byref(ctrl))
                if hr or not ctrl:
                    continue
                try:
                    # GetDisplayName
                    buf = ctypes.create_unicode_buffer(512)
                    ctrl.GetDisplayName(buf, ctypes.byref(ctypes.c_uint(512)))
                    display_name = buf.value.strip()

                    # GetState (Active=1)
                    st = ctypes.c_int(0)
                    ctrl.GetState(ctypes.byref(st))

                    # GetProcessId via IAudioSessionControl2
                    IID_ASC2 = ctypes.GUID("{87CE1963-C148-4931-BBE2-FAFF997245B6}")
                    ctrl2 = ctypes.c_void_p()
                    hr_qi = ctrl.QueryInterface(ctypes.byref(IID_ASC2), ctypes.byref(ctrl2))
                    pid_val = 0
                    if not hr_qi and ctrl2:
                        pid = ctypes.c_uint()
                        ctrl2.GetProcessId(ctypes.byref(pid))
                        pid_val = pid.value

                    if st.value == 1 and display_name:
                        sessions.append((display_name, pid_val))
                except Exception:
                    continue

            # 选择最佳匹配（排除系统声音）
            system_sounds = ["系统声音", "System Sounds", "通信", "Communication",
                            "Windows", "Microsoft", "Audio Mixer", "扬声器"]
            best = None
            for name, pid in sessions:
                if any(s in name for s in system_sounds):
                    continue
                if not best or len(name) > len(best[0]):
                    best = (name, pid)

            if best:
                name, pid = best
                proc_name = self._get_process_name(pid).lower()
                # 尝试解析 "歌名 - 歌手" 格式
                parts = name.split(" - ", 1)
                if len(parts) >= 2:
                    self._state = MediaState(
                        is_playing=True,
                        title=parts[0].strip(),
                        artist=parts[1].strip(),
                    )
                elif len(parts) == 1:
                    self._state = MediaState(is_playing=True, title=name.strip())
                return True

            return False
        except Exception:
            return False

    @staticmethod
    def _get_process_name(pid: int) -> str:
        try:
            import psutil
            p = psutil.Process(pid)
            return p.name() or ""
        except ImportError:
            # 回退：用 Win32 API
            try:
                hProcess = user32.OpenProcess(0x0410, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                if hProcess:
                    buf = ctypes.create_unicode_buffer(260)
                    ctypes.windll.kernel32.QueryFullProcessImageNameW(hProcess, 0, buf, ctypes.byref(ctypes.c_uint(260)))
                    from pathlib import Path
                    name = Path(buf.value).name
                    user32.CloseHandle(hProcess)
                    return name
            except Exception:
                pass
            return ""
        except Exception:
            return ""

    # ── 窗口标题探测（最终回退）── #

    def _detect_by_window_title(self) -> None:
        """通过窗口标题探测常见音乐应用"""

        EnumWindows = user32.EnumWindows
        GetWindowTextW = user32.GetWindowTextW
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        IsWindowVisible = user32.IsWindowVisible

        results = []

        def _enum_cb(hwnd, lparam):
            if not IsWindowVisible(hwnd):
                return True  # 继续枚举
            buf = ctypes.create_unicode_buffer(512)
            GetWindowTextW(hwnd, buf, 512)
            title = buf.value.strip()
            if title and len(title) > 3:
                pid = ctypes.wintypes.DWORD()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                results.append((hwnd, title, pid.value))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        EnumWindows(WNDENUMPROC(_enum_cb), 0)

        psutil_ok = False
        try:
            import psutil
            psutil_ok = True
        except ImportError:
            pass

        best_match = None
        for hwnd, title, pid in results:
            title_lower = title.lower()

            # Spotify: "歌曲 − 歌手"
            if "spotify" in title_lower:
                parts = title.split(" \u2212 ", 1) if " \u2212 " in title else title.split(" - ", 1)
                if len(parts) >= 2:
                    best_match = MediaState(is_playing=True, title=parts[0].strip(), artist=parts[1].strip())
                else:
                    best_match = MediaState(is_playing=True, title=title.strip())
                break

            # QQ音乐/网易云音乐/酷狗 等
            if psutil_ok:
                try:
                    pname = self._get_process_name(pid).lower()
                    music_apps = {
                        "qqmusic": ("QQ音乐", "-"),
                        "neteasecloudmusic": ("网易云音乐", "-"),
                        "cloudmusic": ("网易云音乐", "-"),
                        "kugou": ("酷狗", "-"),
                        "kuwo": ("酷我", "-"),
                        "aimp": ("AIMP", "-"),
                        "foobar2000": ("foobar2000", " | "),
                        "itunes": ("iTunes", " - "),
                        "potplayer": ("PotPlayer", " - "),
                    }
                    for app_key, (_, sep) in music_apps.items():
                        if app_key in pname:
                            parts = title.split(sep, 1)
                            if len(parts) >= 2:
                                best_match = MediaState(is_playing=True, title=parts[0].strip(), artist=parts[1].strip())
                                break
                            elif parts:
                                best_match = MediaState(is_playing=True, title=title.strip())
                            break
                    if best_match:
                        break
                except Exception:
                    pass

            # YouTube Music in browser
            if "youtube music" in title_lower or " - youtube music" in title_lower:
                clean = title.replace(" - YouTube Music", "").replace(" - Music", "").strip()
                parts = clean.split(" - ", 1)
                if len(parts) >= 2:
                    best_match = MediaState(is_playing=True, title=parts[0].strip(), artist=parts[1].strip())
                elif parts:
                    best_match = MediaState(is_playing=True, title=clean.strip())
                break

            # 通用模式：任何包含进程名是音乐应用的窗口
            if psutil_ok and not best_match:
                try:
                    pname = self._get_process_name(pid).lower()
                    if any(k in pname for k in ["spotify", "music", "itunes", "foobar", "aimp"]):
                        parts = title.split(" - ", 1)
                        if len(parts) >= 2:
                            best_match = MediaState(is_playing=True, title=parts[0].strip(), artist=parts[1].strip())
                        else:
                            best_match = MediaState(is_playing=True, title=title.strip())
                        break
                except Exception:
                    pass

        if best_match:
            self._state = best_match
        elif self._state.is_playing:
            # 如果之前有播放状态但这次没找到，保留但不标记 playing
            pass


def get_media_service() -> MediaControlService:
    return MediaControlService()
