"""Built-in safe tools: browser/URL launch, web search, time. No shell, no FS writes."""
from __future__ import annotations

import datetime
import urllib.parse
import webbrowser

from ..agent.permissions import Level
from ..agent.registry import Tool, ToolRegistry


def _open_url(args: dict) -> dict:
    url = str(args.get("url", "")).strip()
    if not url or any(c in url for c in " \t\n\r\"'"):
        raise ValueError("invalid url")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    opened = webbrowser.open(url)
    return {"opened": bool(opened), "url": url, "evidence": f"browser launch returned {opened}"}


def _search_web(args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    if not query or len(query) > 300:
        raise ValueError("invalid query")
    url = "https://duckduckgo.com/?q=" + urllib.parse.quote(query)
    opened = webbrowser.open(url)
    return {"opened": bool(opened), "query": query, "url": url,
            "evidence": f"browser launch returned {opened}"}


def _system_time(_args: dict) -> dict:
    now = datetime.datetime.now()
    return {"time": now.strftime("%H:%M"), "date": now.strftime("%A, %d %B %Y"),
            "evidence": "system clock"}


def _echo(args: dict) -> dict:
    return {"echo": str(args.get("text", ""))[:500], "evidence": "in-process"}


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(Tool(
        name="web.open_url",
        description="Open a URL in the default browser",
        parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
        handler=_open_url, level=Level.INTERACTIVE, risk_class="safe", timeout=10))
    registry.register(Tool(
        name="web.search",
        description="Search the web for a query in the default browser",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        handler=_search_web, level=Level.INTERACTIVE, risk_class="safe", timeout=10))
    registry.register(Tool(
        name="system.time",
        description="Tell the current time and date",
        parameters={"type": "object", "properties": {}},
        handler=_system_time, level=Level.READ_ONLY, risk_class="safe", timeout=5))
    registry.register(Tool(
        name="demo.echo",
        description="Echo text back (demo/test tool)",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        handler=_echo, level=Level.READ_ONLY, risk_class="safe", timeout=5))
    # apps.open is routed but intentionally unregistered until the app
    # registry/launcher lands in build step C; router results degrade to
    # 'unknown tool' honestly rather than pretending to open anything.
