"""File search/read/organize inside allowed roots only. Path-traversal safe."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

MAX_READ_BYTES = 200_000


def _allowed_roots(extra: list[str] | None = None) -> list[Path]:
    roots = [Path.home() / "Documents", Path.home() / "Desktop", Path.home() / "Downloads"]
    roots += [Path(p) for p in (extra or [])]
    return [r.resolve() for r in roots if r.exists()]


def _resolve(path: str, roots: list[Path]) -> Path | None:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.home() / p
    try:
        resolved = p.resolve()
    except OSError:
        return None
    for root in roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    return None


def search_files(pattern: str, folder: str | None = None, extra_roots: list[str] | None = None) -> dict:
    roots = _allowed_roots(extra_roots)
    base = _resolve(folder, roots) if folder else None
    if folder and base is None:
        return {"error": "folder outside allowed roots"}
    search_dirs = [base] if base else roots
    matches: list[str] = []
    for d in search_dirs:
        try:
            for p in d.rglob(pattern if "*" in pattern else f"*{pattern}*"):
                if p.is_file():
                    matches.append(str(p))
                    if len(matches) >= 50:
                        return {"matches": matches, "truncated": True,
                                "evidence": f"{len(matches)} matches (truncated)"}
        except (OSError, PermissionError):
            continue
    return {"matches": matches, "evidence": f"{len(matches)} matches"}


def read_file(path: str, extra_roots: list[str] | None = None) -> dict:
    p = _resolve(path, _allowed_roots(extra_roots))
    if p is None or not p.is_file():
        return {"error": "file not found or outside allowed folders"}
    if p.stat().st_size > MAX_READ_BYTES:
        return {"error": "file too large"}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"error": f"cannot read: {type(exc).__name__}"}
    # Untrusted content marker for downstream prompt-injection defense
    return {"path": str(p), "content": text[:MAX_READ_BYTES],
            "untrusted": True, "evidence": f"read {len(text)} chars"}


def organize_files(operations: list[dict], undo_stack: list | None = None) -> dict:
    """operations: [{"from": path, "to": path}] — moves within allowed roots only.
    Records inverse ops into undo_stack for 'undo that'."""
    roots = _allowed_roots()
    results, inverses = [], []
    for op in operations[:20]:
        src = _resolve(str(op.get("from", "")), roots)
        dst = _resolve(str(op.get("to", "")), roots)
        if src is None or dst is None or not src.is_file():
            results.append({"ok": False, "op": op, "reason": "path outside allowed roots or missing"})
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
            inverses.append({"from": str(dst), "to": str(src)})
            results.append({"ok": True, "from": str(src), "to": str(dst)})
        except OSError as exc:
            results.append({"ok": False, "op": op, "reason": type(exc).__name__})
    if undo_stack is not None and inverses:
        undo_stack.append({"kind": "file_moves", "inverse": inverses, "ts": time.time()})
    done = sum(1 for r in results if r["ok"])
    return {"moved": done, "total": len(results), "results": results,
            "evidence": f"{done}/{len(results)} moves verified on disk"}
