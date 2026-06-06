"""
Windows 媒体控制服务

纯 Win32 API 实现，无需额外依赖：
1. 发送媒体键控制（播放/暂停、上一曲、下一曲）
2. 通过 Windows Audio Session 枚举活跃音频会话
3. 窗口标题回退探测常见音乐应用
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# ── Windows 常量 ──────────────────────────────────────────────── #

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32


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
        # 手动跟踪播放状态（用于图标切换）
        self._manually_playing = False

    # ------------------------------------------------------------------ #
    #  媒体键控制（纯 Win32 keybd_event）
    # ------------------------------------------------------------------ #

    def play_pause(self) -> None:
        self._send_media_key(VK_MEDIA_PLAY_PAUSE)
        # 切换手动跟踪的播放状态
        self._manually_playing = not self._manually_playing
        if self._manually_playing and not self._state.title:
            # 如果还没有歌曲信息，至少标记为"播放中"
            pass
        # 立即刷新 UI
        self.refresh()

    def next_track(self) -> None:
        self._send_media_key(VK_MEDIA_NEXT_TRACK)

    def prev_track(self) -> None:
        self._send_media_key(VK_MEDIA_PREV_TRACK)

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
        self._polling = True

        def _poll():
            last_title = ""
            while self._polling:
                self.refresh()
                if self._state.title != last_title and self._callbacks:
                    for cb in self._callbacks:
                        try:
                            cb(self._state)
                        except Exception:
                            pass
                    last_title = self._state.title
                time.sleep(interval_ms / 1000.0)

        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def stop_polling(self) -> None:
        self._polling = False

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
                if thumb and len(bytes(thumb)) > 100:
                    from pathlib import Path
                    out_dir = Path(__file__).parent.parent.parent / "data"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / "_media_thumb.jpg"
                    with open(out_path, "wb") as f:
                        f.write(bytes(thumb))
                    self._state.thumbnail_path = str(out_path)
            except Exception:
                pass
            return True

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_async_read())
            loop.close()
            return result
        except Exception:
            return False

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
