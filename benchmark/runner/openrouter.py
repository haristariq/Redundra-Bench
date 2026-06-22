"""OpenRouter token accounting (source of truth for the DeepSeek arm).

Per BENCHMARK.md §D, when running through OpenRouter we provision a dedicated
API key per run and read OpenRouter's own accounting afterwards, capturing every
tool round-trip and test-feedback loop in native-tokenizer counts.

Two endpoints (management key required for activity):
  GET /api/v1/generation?id=<id>  -> native_tokens_prompt/completion + cost (per request)
  GET /api/v1/activity            -> per-day aggregates, filterable by api_key_hash

This module is only exercised when BENCH_PROVIDER=openrouter; it degrades to a
no-op (returning None) when no key is configured.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

BASE = "https://openrouter.ai/api/v1"


def _get(path: str, token: str) -> Optional[dict]:
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        return {"_error": str(exc)}


def activity(api_key_hash: Optional[str] = None) -> Optional[dict]:
    """Return aggregate usage for the management-keyed account (optionally filtered)."""
    token = os.environ.get("OPENROUTER_MANAGEMENT_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not token:
        return None
    path = "/activity"
    if api_key_hash:
        path += f"?api_key_hash={api_key_hash}"
    data = _get(path, token)
    if not data or "_error" in (data or {}):
        return data
    rows = data.get("data", [])
    agg = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "requests": 0,
        "usd": 0.0,
        "rows": len(rows),
    }
    for r in rows:
        agg["prompt_tokens"] += int(r.get("prompt_tokens", 0) or 0)
        agg["completion_tokens"] += int(r.get("completion_tokens", 0) or 0)
        agg["reasoning_tokens"] += int(r.get("reasoning_tokens", 0) or 0)
        agg["requests"] += int(r.get("requests", 0) or 0)
        agg["usd"] += float(r.get("usage", 0) or 0)
    agg["total_tokens"] = (
        agg["prompt_tokens"] + agg["completion_tokens"] + agg["reasoning_tokens"]
    )
    return agg


def generation(generation_id: str) -> Optional[dict]:
    token = os.environ.get("OPENROUTER_API_KEY")
    if not token:
        return None
    return _get(f"/generation?id={generation_id}", token)
