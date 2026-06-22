"""Parse a Codex `exec --json` JSONL stream for tokens, turns, and tool calls.

Tolerant of schema drift across Codex versions: we look for `turn.completed`
events carrying a `usage` object and sum them, and we count tool/command items.
Per BENCHMARK.md §D the Codex stream is a CROSS-CHECK; OpenRouter accounting is
the source of truth (and `reasoning_output_tokens` is dropped from the stream on
some Codex versions - openai/codex #19022).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


REDUNDRA_TOOLS = {"find_reusable", "review_draft", "safe_write", "reindex"}


@dataclass
class CodexUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    turns: int = 0
    shell_commands: int = 0
    mcp_tool_calls: int = 0
    redundra_tool_calls: int = 0
    file_changes: int = 0
    events: int = 0
    final_message: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        # cached_input_tokens is a SUBSET of input_tokens - don't double count.
        return self.input_tokens + self.output_tokens + self.reasoning_output_tokens

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["total_tokens"] = self.total_tokens
        return d


def _walk_find_usage(obj) -> dict | None:
    """Find a usage-like dict anywhere in an event (handles nesting)."""
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if {"input_tokens", "output_tokens"} & keys:
            return obj
        for v in obj.values():
            found = _walk_find_usage(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _walk_find_usage(v)
            if found:
                return found
    return None


def parse_stream(jsonl_path: Path) -> CodexUsage:
    u = CodexUsage()
    if not jsonl_path.exists():
        u.errors.append("no jsonl file")
        return u
    for raw in jsonl_path.read_text(errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        u.events += 1
        etype = str(ev.get("type") or ev.get("event") or "")

        if "turn.completed" in etype:
            u.turns += 1
            usage = _walk_find_usage(ev)
            if usage:
                u.input_tokens += int(usage.get("input_tokens", 0) or 0)
                u.cached_input_tokens += int(usage.get("cached_input_tokens", 0) or 0)
                u.output_tokens += int(usage.get("output_tokens", 0) or 0)
                u.reasoning_output_tokens += int(
                    usage.get("reasoning_output_tokens", 0) or 0
                )

        # Count each item exactly once, on its completion, by item.type.
        if etype == "item.completed":
            it = ev.get("item", {}) or {}
            itype = str(it.get("type") or it.get("item_type") or "")
            if itype == "command_execution":
                u.shell_commands += 1
            elif itype == "file_change":
                u.file_changes += 1
            elif "mcp" in itype or "tool_call" in itype:
                u.mcp_tool_calls += 1
                # Identify Redundra by explicit server/tool fields only (never by
                # the package name redundra_utils appearing in payloads).
                server = str(it.get("server") or it.get("server_name") or "").lower()
                tool = str(it.get("tool") or it.get("name") or it.get("tool_name") or "")
                if server == "redundra" or tool in REDUNDRA_TOOLS:
                    u.redundra_tool_calls += 1
            elif itype == "agent_message":
                txt = it.get("text")
                if isinstance(txt, str) and txt.strip():
                    u.final_message = txt

    return u
