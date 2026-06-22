"""Central, env-overridable settings for the benchmark harness."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_ROOT / "benchmark"
MCP_DIR = BENCH_DIR / "mcp"
CODEX_HOME = Path(os.environ.get("BENCH_CODEX_HOME", BENCH_DIR / ".codex_home"))
RESULTS_DIR = Path(os.environ.get("BENCH_RESULTS_DIR", BENCH_DIR / "results"))

ARMS = ["without-redundra", "with-redundra", "null-mcp"]

# --- Model / provider --------------------------------------------------------
# provider: "codex" (ChatGPT subscription, default) or "openrouter" (DeepSeek).
PROVIDER = os.environ.get("BENCH_PROVIDER", "codex")
MODEL = os.environ.get("BENCH_MODEL", "gpt-5.5" if PROVIDER == "codex" else "deepseek/deepseek-v3.2")
REASONING_EFFORT = os.environ.get("BENCH_REASONING_EFFORT", "medium")
SANDBOX = os.environ.get("BENCH_SANDBOX", "workspace-write")

# --- Redundra MCP under test -------------------------------------------------
# By default we drive the real Redundra MCP server via its built module
# entrypoint (dist/mcp/server.js), which speaks MCP over stdio. Set the path with
# REDUNDRA_SERVER_JS; the default assumes a sibling `redundra` checkout next to
# this repository. Set BENCH_USE_STUB=1 to use the bundled offline stub instead.
REDUNDRA_SERVER_JS = os.environ.get(
    "REDUNDRA_SERVER_JS", str(REPO_ROOT.parent / "redundra" / "dist" / "mcp" / "server.js")
)
# Set BENCH_USE_STUB=1 to use the offline reference stub instead of real Redundra.
USE_STUB = os.environ.get("BENCH_USE_STUB", "0") == "1"
REDUNDRA_MIN_CORPUS = int(os.environ.get("BENCH_MIN_CORPUS_SYMBOLS", "3"))
REDUNDRA_MODE = os.environ.get("BENCH_REDUNDRA_MODE", "warn")  # warn | selective

CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
NODE_BIN = os.environ.get("NODE_BIN", "node")
USER_CODEX_HOME = Path(os.environ.get("USER_CODEX_HOME", Path.home() / ".codex"))
