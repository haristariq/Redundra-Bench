"""A tiny dependency-free MCP stdio server.

Implements just enough of the Model Context Protocol stdio transport
(newline-delimited JSON-RPC 2.0) for Codex to attach a server, list its tools,
and call them. Used by the Redundra stub and the null-MCP length control so the
benchmark harness runs end-to-end without the real Redundra product.
"""

from __future__ import annotations

import json
import sys
from typing import Callable

DEFAULT_PROTOCOL = "2025-06-18"


def serve(server_name: str, server_version: str, tools: list[dict], handler: Callable[[str, dict], str]) -> None:
    """Run the stdio loop.

    ``tools`` is a list of MCP tool descriptors (name/description/inputSchema).
    ``handler(name, arguments) -> str`` returns the text content for a call.
    """
    out = sys.stdout

    def send(msg: dict) -> None:
        out.write(json.dumps(msg) + "\n")
        out.flush()

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        req_id = req.get("id")
        is_request = req_id is not None

        if method == "initialize":
            params = req.get("params") or {}
            send(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL),
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": server_name, "version": server_version},
                    },
                }
            )
        elif method == "tools/list":
            if is_request:
                send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}})
        elif method == "tools/call":
            params = req.get("params") or {}
            name = params.get("name", "")
            arguments = params.get("arguments") or {}
            try:
                text = handler(name, arguments)
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            except Exception as exc:  # surface tool errors as MCP errors, don't crash
                result = {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True,
                }
            if is_request:
                send({"jsonrpc": "2.0", "id": req_id, "result": result})
        elif method == "ping":
            if is_request:
                send({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method and method.startswith("notifications/"):
            pass  # notifications get no response
        else:
            if is_request:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"method not found: {method}"},
                    }
                )
