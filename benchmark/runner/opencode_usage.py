"""Parse OpenCode `run --format json` output for tokens, cost, and tool calls.

OpenCode emits JSONL events. The two we care about:
  - ``step_finish``: ``part.tokens = {total,input,output,reasoning,cache:{read,write}}``
                     and ``part.cost`` (USD). One per model step; we sum them.
  - ``tool_use``:    ``part.tool`` is the tool name. Built-in tools are bare
                     (bash/read/write/edit/...); MCP tools are server-prefixed
                     (e.g. ``redundra_find_reusable``), which is how we identify
                     Redundra calls - never by substring-matching payloads (the
                     repo path/package name contains "redundra").

Token source of truth for cost remains OpenRouter accounting (openrouter.py) /
``part.cost`` here; these stream counts are the cross-check.
"""

from __future__ import annotations

import json
from pathlib import Path

# MCP server names this benchmark attaches (opencode prefixes tool names with them).
MCP_SERVER_PREFIXES = ("redundra_", "null_control_")
REDUNDRA_PREFIX = "redundra_"


def _load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    text = path.read_text(errors="replace")
    # Prefer JSONL (opencode's actual format); fall back to a JSON array.
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            doc = json.loads(stripped)
            return doc if isinstance(doc, list) else [doc]
        except json.JSONDecodeError:
            pass
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def parse_opencode_stream(path: Path) -> dict:
    events = _load_events(path)
    u = {
        "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0,
        "cache_read_tokens": 0, "cache_write_tokens": 0,
        "cost_usd": 0.0, "steps": 0, "tool_calls": 0, "mcp_tool_calls": 0,
        "redundra_tool_calls": 0, "events": len(events), "session_id": "",
    }
    for ev in events:
        etype = ev.get("type")
        part = ev.get("part") or {}
        sid = ev.get("sessionID")
        if isinstance(sid, str) and sid:
            u["session_id"] = sid

        if etype == "step_finish":
            u["steps"] += 1
            tok = part.get("tokens") or {}
            u["input_tokens"] += int(tok.get("input", 0) or 0)
            u["output_tokens"] += int(tok.get("output", 0) or 0)
            u["reasoning_tokens"] += int(tok.get("reasoning", 0) or 0)
            cache = tok.get("cache") or {}
            u["cache_read_tokens"] += int(cache.get("read", 0) or 0)
            u["cache_write_tokens"] += int(cache.get("write", 0) or 0)
            cost = part.get("cost")
            if isinstance(cost, (int, float)):
                u["cost_usd"] += float(cost)

        elif etype == "tool_use":
            name = str(part.get("tool") or part.get("name") or "")
            u["tool_calls"] += 1
            if name.startswith(MCP_SERVER_PREFIXES):
                u["mcp_tool_calls"] += 1
                if name.startswith(REDUNDRA_PREFIX):
                    u["redundra_tool_calls"] += 1

    u["cost_usd"] = round(u["cost_usd"], 6)
    u["total_tokens"] = u["input_tokens"] + u["output_tokens"] + u["reasoning_tokens"]
    return u
