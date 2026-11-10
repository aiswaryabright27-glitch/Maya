"""App launching/closing. Uses ShellExecute 'start' verb and WM_CLOSE; no bypass."""
from __future__ import annotations

import subprocess
import time
import urllib.parse

from .windows import focus_window, find_window, list_windows

_APP_ALIASES = {
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "notepad": "notepad", "note pad": "notepad", "notepad.exe": "notepad", "calculator": "calc", "calc": "calc",
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "spotify": "spotify",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "terminal": "wt", "cmd": "cmd", "powershell": "powershell",
    "settings": "ms-settings:", "explorer": "explorer",
    "snipping tool": "snippingtool", "paint": "mspaint",
}


def resolve_app(name: str) -> str:
    return _APP_ALIASES.get(name.strip().lower(), name.strip())


def open_application(name: str) -> dict:
    """Launch via cmd start verb (Start Menu/App Paths resolution by Windows)."""
    target = resolve_app(name)
    quoted = f'"{target}"' if " " in target else target
    subprocess.Popen(["cmd", "/c", "start", "", quoted],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    window = find_window(target) or find_window(name)
    focused = focus_window(window.hwnd) if window else False
    return {"launched": target, "window_found": window.title if window else None,
            "focused": focused,
            "evidence": f"start verb issued for '{target}'; window_found={bool(window)}; focused={focused}"}


def open_url(url: str) -> dict:
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    subprocess.Popen(["cmd", "/c", "start", "", url],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"opened": url, "evidence": "start verb issued for URL"}


def search_web(query: str) -> dict:
    url = "https://duckduckgo.com/?q=" + urllib.parse.quote(query)
    return open_url(url) | {"query": query}


def close_application(name: str) -> dict:
    """Close the window matching name via WM_CLOSE (graceful, allows save prompts)."""
    window = find_window(name)
    if not window:
        return {"closed": False, "reason": f"no window matching '{name}'",
                "evidence": "window not found"}
    import ctypes
    user32 = ctypes.windll.user32
    WM_CLOSE = 0x0010
    user32.PostMessageW(window.hwnd, WM_CLOSE, 0, 0)
    time.sleep(0.5)
    still = find_window(name)
    return {"closed": still is None or still.hwnd != window.hwnd,
            "window": window.title,
            "evidence": f"WM_CLOSE posted to hwnd {window.hwnd}"}


def list_open_apps() -> dict:
    titles = [w["title"] for w in list_windows()]
    return {"windows": titles, "evidence": f"{len(titles)} visible windows"}
