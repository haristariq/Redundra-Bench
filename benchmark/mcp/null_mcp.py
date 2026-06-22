#!/usr/bin/env python3
"""Null-MCP length control (BENCHMARK.md §F.3).

Exposes a tool with a schema and response of *similar size* to the Redundra
stub's, but whose content is irrelevant to reuse. Running a third arm with this
server isolates how much of any observed token delta is a prompt-length artifact
(tool schema + injected text) versus a genuine behaviour change.

Note: MCP servers cannot inject text unless their tool is called, so this only
fully matches Redundra's overhead when the agent actually calls the tool. The
tool description nudges the agent to call it once, mirroring how the agent is
nudged to call find_reuse_candidates. Treat this arm's parity as approximate and
report it as such.
"""

from __future__ import annotations

from _mcp_stdio import serve

# Roughly length-matched filler to the redundra stub's candidate listing.
_FILLER = (
    "Project knowledge note: this repository follows conventional Python packaging "
    "with a src layout, pytest-based tests, and Apache-2.0 licensing. Modules are "
    "organised by concern and public symbols are exported via __all__. No specific "
    "reuse guidance is available for this query from this index."
)


def lookup_project_notes(arguments: dict) -> str:
    return _FILLER


TOOLS = [
    {
        "name": "lookup_project_notes",
        "description": (
            "Look up general project notes and conventions relevant to a task. "
            "Call this once before implementing a general-purpose helper."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A short description of the behaviour you need (e.g. 'truncate a string with an ellipsis').",
                },
                "limit": {"type": "integer", "description": "Max notes to return.", "default": 5},
            },
            "required": ["query"],
        },
    }
]


def handler(name: str, arguments: dict) -> str:
    if name == "lookup_project_notes":
        return lookup_project_notes(arguments)
    raise ValueError(f"unknown tool: {name}")


if __name__ == "__main__":
    serve("null-control", "0.1.0", TOOLS, handler)
