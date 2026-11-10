"""App launching/closing. Uses the Windows 'start' verb / Start Menu shortcuts and WM_CLOSE; no bypass.

open_application now VERIFIES the launch (a new window must appear) and reports failure
honestly instead of always saying "Done".
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path

from .windows import focus_window, find_window, list_windows

_APP_ALIASES = {
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "notepad": "notepad", "note pad": "notepad", "notepad.exe": "notepad", "calculator": "calc", "calc": "calc",
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "spotify": "spotify",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "terminal": "wt", "cmd": "cmd", "command prompt": "cmd", "powershell": "powershell",
    "settings": "ms-settings:", "explorer": "explorer", "file explorer": "explorer",
    "snipping tool": "snippingtool", "paint": "mspaint", "camera": "microsoft.windows.camera:", "clock": "ms-clock:",
}
# window-title fragment to look for after launch / when closing
_TITLE_HINTS = {
    "calc": "calculator", "code": "visual studio code", "winword": "word", "powerpnt": "powerpoint",
    "msedge": "edge", "wt": "terminal", "mspaint": "paint", "explorer": "file explorer",
    "ms-settings:": "settings", "snippingtool": "snipping", "ms-clock:": "clock",
    "microsoft.windows.camera:": "camera", "cmd": "command prompt",
}
_CLOSE_HINTS = {"vs code": "visual studio code", "command prompt": "command prompt", "file explorer": "file explorer",
                "calculator": "calculator", "settings": "settings"}


def resolve_app(name: str) -> str:
    return _APP_ALIASES.get(name.strip().lower(), name.strip())


def _start_menu_dirs() -> list[Path]:
    dirs = []
    for env, sub in (("ProgramData", r"Microsoft\Windows\Start Menu\Programs"),
                     ("APPDATA", r"Microsoft\Windows\Start Menu\Programs")):
        base = os.environ.get(env)
        if base:
            dirs.append(Path(base) / sub)
    return dirs


def find_start_menu_shortcut(name: str, dirs: list[Path] | None = None) -> Path | None:
    """Best .lnk in the Start Menu whose name contains the spoken name (shortest name wins)."""
    q = name.strip().lower()
    if len(q) < 3:
        return None
    best: Path | None = None
    for base in (dirs if dirs is not None else _start_menu_dirs()):
        if not base.exists():
            continue
        for lnk in base.rglob("*.lnk"):
            stem = lnk.stem.lower()
            if q in stem and "uninstall" not in stem and (best is None or len(stem) < len(best.stem)):
                best = lnk
    return best


def _is_launchable(target: str) -> bool:
    return target.endswith(":") or shutil.which(target) is not None or shutil.which(target + ".exe") is not None


def open_application(name: str) -> dict:
    spoken = name.strip()
    target = resolve_app(spoken)
    known_alias = spoken.lower() in _APP_ALIASES or target != spoken
    before = {w["hwnd"] for w in list_windows()}
    shortcut = None
    if known_alias or _is_launchable(target):
        quoted = f'"{target}"' if " " in target else target
        subprocess.Popen(["cmd", "/c", "start", "", quoted], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        how = f"start verb for '{target}'"
    else:
        shortcut = find_start_menu_shortcut(spoken)
        if shortcut is None:
            return {"ok": False, "error": f"I don't know an app called {spoken}",
                    "evidence": "no alias, PATH entry or Start Menu shortcut matched"}
        os.startfile(str(shortcut))  # type: ignore[attr-defined]
        how = f"Start Menu shortcut '{shortcut.stem}'"
    hint = _TITLE_HINTS.get(target, target.rstrip(":").lower())
    found = None
    deadline = time.time() + 5.0
    while time.time() < deadline and found is None:
        time.sleep(0.25)
        for w in list_windows():
            if w["hwnd"] not in before or hint in w["title"].lower():
                found = w
                break
    if found is None:
        return {"ok": False, "error": f"I tried to open {spoken} but no window appeared",
                "evidence": f"{how}; no new window within 5s"}
    focused = focus_window(found["hwnd"])
    return {"ok": True, "launched": spoken, "window_found": found["title"], "focused": focused,
            "evidence": f"{how}; window '{found['title']}' appeared; focused={focused}"}


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
    hint = _CLOSE_HINTS.get(name.strip().lower(), name.strip())
    window = find_window(hint) or find_window(name)
    if not window:
        return {"ok": False, "closed": False, "error": f"I can't find an open window for {name}",
                "evidence": "window not found"}
    import ctypes
    user32 = ctypes.windll.user32
    WM_CLOSE = 0x0010
    user32.PostMessageW(window.hwnd, WM_CLOSE, 0, 0)
    time.sleep(0.5)
    still = find_window(hint) or find_window(name)
    closed = still is None or still.hwnd != window.hwnd
    return {"ok": True, "closed": closed, "window": window.title,
            "evidence": f"WM_CLOSE posted to hwnd {window.hwnd}; closed={closed} (an app may be asking to save)"}


def list_open_apps() -> dict:
    titles = [w["title"] for w in list_windows()]
    return {"windows": titles, "evidence": f"{len(titles)} visible windows"}
