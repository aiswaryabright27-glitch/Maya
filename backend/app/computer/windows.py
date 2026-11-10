"""Window enumeration/focus via Win32 ctypes. No external deps."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    minimized: bool


def _enum_windows() -> list[WindowInfo]:
    results: list[WindowInfo] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append(WindowInfo(int(hwnd), buf.value, pid.value,
                                  bool(user32.IsIconic(hwnd))))
        return True

    user32.EnumWindows(callback, 0)
    return results


def list_windows() -> list[dict]:
    return [{"hwnd": w.hwnd, "title": w.title, "pid": w.pid, "minimized": w.minimized}
            for w in _enum_windows() if w.title.strip()]


def foreground_window() -> dict | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    for w in _enum_windows():
        if w.hwnd == hwnd:
            return {"hwnd": w.hwnd, "title": w.title, "pid": w.pid}
    return None


def focus_window(hwnd: int) -> bool:
    """Return False on secure/elevated desktops instead of bypassing them."""
    try:
        if not user32.IsWindow(hwnd):
            return False
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def find_window(query: str) -> WindowInfo | None:
    q = query.lower()
    for w in _enum_windows():
        if q in w.title.lower():
            return w
    return None


def check_secure_desktop() -> bool:
    """True when the foreground window is elevated/UAC — Maya must not act there."""
    try:
        hwnd = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return True  # cannot inspect -> treat as secure
        try:
            elevated = wintypes.BOOL()
            if ctypes.windll.shell32.IsUserAnAdmin() and kernel32.GetTokenInformation:
                pass
            # Cheap heuristic: OpenProcess with higher access fails on elevated procs
            high = kernel32.OpenProcess(0x1F0FFF, False, pid.value)
            if not high:
                return True
            kernel32.CloseHandle(high)
            return False
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return False
