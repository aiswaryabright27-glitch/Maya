"""Command router: deterministic fast path for simple commands, LLM for the rest.

Deterministic rules cover stop/cancel, open app/url, web search, time/date,
and undo. Anything else returns kind='conversation' so the voice pipeline
answers normally, or 'task' when it looks like a multi-step instruction.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

STOP_RE = re.compile(r"^\s*(?:stop|stop maya|cancel|cancel that|nevermind|undo that|undo)\b[.!?\s]*$", re.I)
OPEN_URL_RE = re.compile(r"^\s*(?:open|go to|visit)\s+(https?://\S+|www\.\S+)\s*$", re.I)
OPEN_SITE_RE = re.compile(r"^\s*(?:open|go to)\s+(?:the\s+)?(?:website|site)\s+(?:of\s+)?([\w.-]+\.[a-z]{2,})\s*$", re.I)
SEARCH_RE = re.compile(r"^\s*(?:search(?:\s+(?:the\s+)?web)?|google|look up|find online)\s+(?:for\s+)?(.+)$", re.I)
# Speech recognition occasionally transposes adjacent letters in short commands.
OPEN_APP_RE = re.compile(r"^\s*(?:open|opne)\s+(?:the\s+)?(?:app\s+)?([a-zA-Z][\w .-]{1,40}?)\s*$", re.I)
TIME_RE = re.compile(r"^\s*(?:what(?:'s| is)\s+the\s+)?(?:time|date|day)\b", re.I)
TASK_HINT_RE = re.compile(r"\b(?:then|after that|and also|first .+ then|step \d)\b", re.I)

APP_ALIASES = {
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "notepad": "notepad", "calculator": "calc", "chrome": "chrome",
    "edge": "msedge", "firefox": "firefox", "spotify": "spotify",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "terminal": "wt", "cmd": "cmd", "settings": "ms-settings:",
}


@dataclass(frozen=True)
class RoutedCommand:
    kind: str                      # stop | tool | conversation | task
    tool: str | None = None
    args: dict = field(default_factory=dict)
    summary: str = ""
    confidence: float = 1.0


def route(text: str) -> RoutedCommand:
    t = text.strip()
    # Strip wake-word/vocative prefixes and trailing punctuation
    t = re.sub(r"^(?:hey\s+|ok(?:ay)?\s+)?maya[,!\s]*", "", t, flags=re.I).strip()
    t = re.sub(r"^(?:please\s+)", "", t, flags=re.I).strip()
    t = t.rstrip(".!?।")
    if STOP_RE.match(t):
        return RoutedCommand("stop", summary="stop")
    if OPEN_URL_RE.match(t):
        url = OPEN_URL_RE.match(t).group(1)  # type: ignore[union-attr]
        if not url.lower().startswith("http"):
            url = "https://" + url
        return RoutedCommand("tool", "web.open_url", {"url": url}, f"Open {url}")
    site = OPEN_SITE_RE.match(t)
    if site:
        url = "https://" + site.group(1)
        return RoutedCommand("tool", "web.open_url", {"url": url}, f"Open {url}")
    search = SEARCH_RE.match(t)
    if search and search.group(1).strip():
        return RoutedCommand("tool", "web.search", {"query": search.group(1).strip()},
                             f"Search the web for {search.group(1).strip()}")
    if TIME_RE.match(t):
        return RoutedCommand("tool", "system.time", {}, "Tell the time/date")
    if TASK_HINT_RE.search(t) and len(t.split()) >= 4:
        return RoutedCommand("task", summary=t[:120], confidence=0.6)
    app = OPEN_APP_RE.match(t)
    if app:
        name = re.sub(r"^(?:my|the|a|an)\s+", "", app.group(1).strip().lower())
        name = re.sub(r"\s+(?:app|application|program)$", "", name)
        target = APP_ALIASES.get(name, name)
        return RoutedCommand("tool", "apps.open", {"name": name, "target": target}, f"Open {name}")
    return RoutedCommand("conversation", summary=t[:120], confidence=0.9)
