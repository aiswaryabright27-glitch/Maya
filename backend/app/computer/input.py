"""Keyboard/mouse input: dictation via clipboard paste, click, scroll, type."""
from __future__ import annotations

import ctypes
import subprocess
import time

user32 = ctypes.windll.user32


def _clip_set(text: str) -> bool:
    """Set clipboard via PowerShell (Unicode-safe for Indic scripts)."""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
                       input=text, text=True, capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def _clip_get() -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout or ""
    except Exception:
        return ""


def _send_paste() -> None:
    user32.keybd_event(0x11, 0, 0, 0)      # Ctrl down
    user32.keybd_event(0x56, 0, 0, 0)      # V down
    user32.keybd_event(0x56, 0, 2, 0)      # V up
    user32.keybd_event(0x11, 0, 2, 0)      # Ctrl up
    time.sleep(0.15)


def dictate_text(text: str, restore_clipboard: bool = True) -> dict:
    """Type text into the focused field via clipboard paste; restores clipboard."""
    if not text or len(text) > 10_000:
        return {"ok": False, "error": "invalid text"}
    previous = _clip_get() if restore_clipboard else ""
    if not _clip_set(text):
        return {"ok": False, "error": "clipboard unavailable"}
    time.sleep(0.1)
    _send_paste()
    if restore_clipboard and previous:
        _clip_set(previous)
    return {"ok": True, "chars": len(text), "evidence": "clipboard paste sent to focused window"}


def type_text_ascii(text: str) -> dict:
    """ASCII-only typing via SendInput key events (fallback path)."""
    if not all(ord(c) < 128 for c in text):
        return {"ok": False, "error": "non-ASCII text; use dictate_text"}
    for ch in text[:2000]:
        vk = ord(ch.upper()) if ch.isalpha() else ord(ch)
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
    return {"ok": True, "chars": len(text), "evidence": "SendInput keys sent"}


def click_at(x: int, y: int) -> dict:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
    return {"ok": True, "x": x, "y": y, "evidence": f"click at ({x},{y})"}


def scroll(amount: int) -> dict:
    """amount >0 scroll up, <0 scroll down (120 = one notch)."""
    user32.mouse_event(0x0800, 0, 0, int(amount), 0)
    return {"ok": True, "amount": amount, "evidence": "mouse wheel event sent"}


def press_key(vk: int) -> dict:
    user32.keybd_event(int(vk), 0, 0, 0)
    user32.keybd_event(int(vk), 0, 2, 0)
    return {"ok": True, "vk": vk, "evidence": "key event sent"}
