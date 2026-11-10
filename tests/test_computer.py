from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.computer import apps, files, terminal, windows


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows computer controls")


def test_file_search_and_read_in_sandbox(tmp_path: Path) -> None:
    note = tmp_path / "maya-computer-test.txt"
    note.write_text("sandbox content", encoding="utf-8")

    search = files.search_files("maya-computer-test", extra_roots=[str(tmp_path)])
    assert str(note) in search["matches"]

    result = files.read_file(str(note), extra_roots=[str(tmp_path)])
    assert result["content"] == "sandbox content"
    assert result["untrusted"] is True


def test_file_access_rejects_path_outside_sandbox(tmp_path: Path) -> None:
    outside = tmp_path.parent / "maya-outside.txt"
    outside.write_text("must not be read", encoding="utf-8")
    try:
        result = files.read_file(str(outside), extra_roots=[str(tmp_path)])
        assert "outside" in result["error"] or "not found" in result["error"]
    finally:
        outside.unlink(missing_ok=True)


def test_terminal_allowlist_runs_read_only_command() -> None:
    result = terminal.run_command("python", "--version", str(Path.home()))
    assert result["ok"] is True
    assert result["stdout"] or result["stderr"]


def test_terminal_rejects_shell_and_outside_cwd(tmp_path: Path) -> None:
    denied = terminal.run_command("cmd", "/c whoami", str(Path.home()))
    assert denied["ok"] is False
    assert "allowlist" in denied["evidence"]

    outside_root = Path(os.environ.get("WINDIR", "C:\\Windows"))
    outside = terminal.check_command("python", "--version", str(outside_root))
    assert outside == (False, "working directory outside allowed roots")


def test_window_enumeration_is_read_only() -> None:
    listed = windows.list_windows()
    assert isinstance(listed, list)
    foreground = windows.foreground_window()
    assert foreground is None or {"hwnd", "title", "pid"} <= foreground.keys()


@pytest.mark.skipif(
    os.environ.get("MAYA_LIVE_COMPUTER") != "1",
    reason="set MAYA_LIVE_COMPUTER=1 to launch Notepad and test dictation",
)
def test_live_notepad_dictation() -> None:
    launched = apps.open_application("notepad")
    assert launched["launched"] == "notepad"
    assert launched["window_found"] is not None

    try:
        dictated = __import__("app.computer.input", fromlist=["dictate_text"]).dictate_text(
            "Maya live computer test"
        )
        assert dictated["ok"] is True
    finally:
        closed = apps.close_application("Notepad")
        assert closed["closed"] is True
