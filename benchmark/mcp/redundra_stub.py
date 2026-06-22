#!/usr/bin/env python3
"""Redundra MCP stub server (offline reference implementation).

NOTE: This stub was NOT used for any published result. Every published run drove
the real Redundra MCP server (the default). This stub exists only so the harness
can run end-to-end without the real server, and so others can benchmark their own
reuse layer against the same tasks. It is opt-in via BENCH_USE_STUB=1.

Exposes a single tool, ``find_reuse_candidates``, that searches the existing
public symbols of the project on the agent's PYTHONPATH and returns candidates
the agent could reuse instead of re-implementing. This mimics what the real
Redundra MCP does (surface in-repo reuse opportunities).

To benchmark the real Redundra (the default), set REDUNDRA_SERVER_JS to its built
server module; see BENCHMARK.md. The stub introspects whatever package is
importable; the harness sets PYTHONPATH to the task worktree's ``src/``.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re

from _mcp_stdio import serve

TARGET_PACKAGE = "redundra_utils"


def _catalog() -> list[dict]:
    """Introspect TARGET_PACKAGE and return a flat list of public callables."""
    items: list[dict] = []
    try:
        pkg = importlib.import_module(TARGET_PACKAGE)
    except Exception:
        return items
    modules = [TARGET_PACKAGE]
    if hasattr(pkg, "__path__"):
        for info in pkgutil.iter_modules(pkg.__path__):
            modules.append(f"{TARGET_PACKAGE}.{info.name}")
    seen = set()
    for modname in modules:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for name, obj in vars(mod).items():
            if name.startswith("_") or not callable(obj):
                continue
            if getattr(obj, "__module__", None) != modname:
                continue
            key = f"{modname}.{name}"
            if key in seen:
                continue
            seen.add(key)
            try:
                sig = str(inspect.signature(obj))
            except (TypeError, ValueError):
                sig = "(...)"
            doc = inspect.getdoc(obj) or ""
            items.append(
                {
                    "symbol": key,
                    "signature": f"{name}{sig}",
                    "summary": doc.split("\n", 1)[0],
                    "doc": doc,
                }
            )
    return items


def _score(query: str, item: dict) -> int:
    q = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not q:
        return 0
    hay = f"{item['symbol']} {item['signature']} {item['doc']}".lower()
    hay_words = set(re.findall(r"[a-z0-9]+", hay))
    return len(q & hay_words)


def find_reuse_candidates(arguments: dict) -> str:
    query = str(arguments.get("query", ""))
    limit = int(arguments.get("limit", 5))
    catalog = _catalog()
    ranked = sorted(catalog, key=lambda it: _score(query, it), reverse=True)
    ranked = [it for it in ranked if _score(query, it) > 0][:limit]
    if not ranked:
        return (
            "No existing reuse candidates matched the query. "
            "If the project has no symbol matching this behaviour, writing new code is appropriate."
        )
    lines = ["Existing symbols you may be able to reuse instead of re-implementing:"]
    for it in ranked:
        lines.append(f"\n- {it['symbol']}  -  {it['signature']}")
        if it["summary"]:
            lines.append(f"    {it['summary']}")
    lines.append(
        "\nReuse one of these by importing and calling it if it matches the required "
        "behaviour. If none matches the exact semantics, prefer new code over a forced fit."
    )
    return "\n".join(lines)


TOOLS = [
    {
        "name": "find_reuse_candidates",
        "description": (
            "Search the current project for existing functions/utilities that already "
            "implement a behaviour, so you can reuse them instead of writing a near-duplicate. "
            "Call this before implementing any general-purpose helper."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A short description of the behaviour you need (e.g. 'truncate a string with an ellipsis').",
                },
                "limit": {"type": "integer", "description": "Max candidates to return.", "default": 5},
            },
            "required": ["query"],
        },
    }
]


def handler(name: str, arguments: dict) -> str:
    if name == "find_reuse_candidates":
        return find_reuse_candidates(arguments)
    raise ValueError(f"unknown tool: {name}")


if __name__ == "__main__":
    serve("redundra", "0.1.0", TOOLS, handler)
