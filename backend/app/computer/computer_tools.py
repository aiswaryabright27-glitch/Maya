"""Registers computer-control tools into the agent registry."""
from __future__ import annotations

from ..agent.permissions import Level
from ..agent.registry import Tool, ToolRegistry
from . import apps, files, input as cinput, projects, terminal, undo, windows


def _p(schema_props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": schema_props, "required": required}


def register_computer_tools(registry: ToolRegistry, *,
                            data_dir,
                            undo_stack: undo.UndoStack | None = None,
                            project_registry: projects.ProjectRegistry | None = None) -> None:
    undo_stack = undo_stack or undo.UndoStack()
    project_registry = project_registry or projects.ProjectRegistry(data_dir / "projects.db")
    extra_roots: list[str] = []

    def _files_extra(_args):
        return extra_roots

    registry.register(Tool(
        "apps.open", "Open an application by name",
        _p({"name": {"type": "string"}, "target": {"type": "string"}}, ["name"]),
        lambda a: apps.open_application(a.get("target") or a["name"]),
        level=Level.INTERACTIVE, risk_class="safe", timeout=15))
    registry.register(Tool(
        "apps.close", "Close an application window by name",
        _p({"name": {"type": "string"}}, ["name"]),
        lambda a: apps.close_application(a["name"]),
        level=Level.MODIFY, risk_class="modify", timeout=15))
    registry.register(Tool(
        "apps.list", "List open windows/apps",
        _p({}, []),
        lambda a: apps.list_open_apps(),
        level=Level.READ_ONLY, timeout=10))
    registry.register(Tool(
        "windows.focus", "Focus a window by title fragment",
        _p({"query": {"type": "string"}}, ["query"]),
        lambda a: _focus(a["query"]),
        level=Level.INTERACTIVE, timeout=10))
    registry.register(Tool(
        "files.search", "Search files by name under Documents/Desktop/Downloads",
        _p({"pattern": {"type": "string"}, "folder": {"type": "string"}}, ["pattern"]),
        lambda a: files.search_files(a["pattern"], a.get("folder"), extra_roots),
        level=Level.READ_ONLY, timeout=30))
    registry.register(Tool(
        "files.read", "Read a text file (allowed folders only)",
        _p({"path": {"type": "string"}}, ["path"]),
        lambda a: files.read_file(a["path"], extra_roots),
        level=Level.READ_ONLY, timeout=15))
    registry.register(Tool(
        "files.organize", "Move/rename files (previewed, undoable)",
        _p({"operations": {"type": "array"}}, ["operations"]),
        lambda a: files.organize_files(a["operations"], undo_stack),
        level=Level.MODIFY, risk_class="modify", timeout=60))
    registry.register(Tool(
        "files.undo", "Undo the last file organization",
        _p({}, []),
        lambda a: undo_stack.undo_last(),
        level=Level.MODIFY, risk_class="modify", timeout=15))
    registry.register(Tool(
        "terminal.run", "Run an allowlisted command in an approved folder",
        _p({"command": {"type": "string"}, "args": {"type": "string"}, "cwd": {"type": "string"}}, ["command"]),
        lambda a: terminal.run_command(a["command"], a.get("args", ""), a.get("cwd")),
        level=Level.MODIFY, risk_class="modify", timeout=130))
    registry.register(Tool(
        "input.dictate", "Type text into the focused field",
        _p({"text": {"type": "string"}}, ["text"]),
        lambda a: cinput.dictate_text(a["text"]),
        level=Level.INTERACTIVE, timeout=15))
    registry.register(Tool(
        "input.click", "Click at screen coordinates",
        _p({"x": {"type": "integer"}, "y": {"type": "integer"}}, ["x", "y"]),
        lambda a: cinput.click_at(a["x"], a["y"]),
        level=Level.INTERACTIVE, timeout=10))
    registry.register(Tool(
        "input.scroll", "Scroll the mouse wheel",
        _p({"amount": {"type": "integer"}}, ["amount"]),
        lambda a: cinput.scroll(a["amount"]),
        level=Level.INTERACTIVE, timeout=10))
    registry.register(Tool(
        "projects.list", "List registered projects",
        _p({}, []),
        lambda a: {"projects": project_registry.list(), "evidence": "registry"},
        level=Level.READ_ONLY, timeout=10))
    registry.register(Tool(
        "projects.register", "Register a project folder with aliases/commands",
        _p({"name": {"type": "string"}, "path": {"type": "string"},
            "aliases": {"type": "array"}, "commands": {"type": "object"},
            "editor": {"type": "string"}}, ["name", "path"]),
        lambda a: project_registry.register(a["name"], a["path"], a.get("aliases"),
                                            a.get("commands"), a.get("editor")),
        level=Level.MODIFY, risk_class="modify", timeout=15))
    registry.register(Tool(
        "projects.resolve", "Resolve a spoken project name/alias",
        _p({"name": {"type": "string"}}, ["name"]),
        lambda a: {"project": project_registry.resolve(a["name"]), "evidence": "registry lookup"},
        level=Level.READ_ONLY, timeout=10))


def _focus(query: str) -> dict:
    if windows.check_secure_desktop():
        return {"ok": False, "error": "foreground window is elevated/secure; refusing to act",
                "evidence": "secure desktop check"}
    w = windows.find_window(query)
    if not w:
        return {"ok": False, "error": f"no window matching '{query}'"}
    ok = windows.focus_window(w.hwnd)
    return {"ok": ok, "window": w.title, "evidence": f"SetForegroundWindow({w.hwnd}) -> {ok}"}
