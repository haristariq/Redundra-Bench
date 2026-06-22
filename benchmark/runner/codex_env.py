"""Render an isolated CODEX_HOME and per-arm profile configs.

The three arms share one base ``config.toml`` and differ ONLY by their profile
overlay (`<arm>.config.toml`), which Codex layers on top via `-p <arm>`:

  without-redundra : no MCP server (control).
  with-redundra    : the real Redundra MCP server, `required = true`.
  null-mcp         : a length-matched irrelevant MCP server (prompt-length control).

This guarantees the MCP attachment is the only manipulated variable.
"""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path

import settings as S


def _toml_str(value: str) -> str:
    return json.dumps(value)  # JSON string literals are valid TOML basic strings


def write_base_config(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Redundra-Bench base config (shared by all arms).",
        f"model = {_toml_str(S.MODEL)}",
        f'model_reasoning_effort = "{S.REASONING_EFFORT}"',
        '# Non-interactive batch execution: never pause for approval.',
        'approval_policy = "never"',
    ]
    if S.PROVIDER == "openrouter":
        lines += [
            'model_provider = "openrouter"',
            "",
            "[model_providers.openrouter]",
            'name = "OpenRouter"',
            'base_url = "https://openrouter.ai/api/v1"',
            'env_key = "OPENROUTER_API_KEY"',
            '# Codex dropped wire_api="chat" support; "responses" is mandatory.',
            'wire_api = "responses"',
        ]
    (home / "config.toml").write_text("\n".join(lines) + "\n")

    # Subscription auth: reuse the user's ChatGPT login.
    if S.PROVIDER == "codex":
        src_auth = S.USER_CODEX_HOME / "auth.json"
        if src_auth.exists():
            shutil.copy2(src_auth, home / "auth.json")


def _redundra_mcp_block(worktree: Path) -> str:
    if S.USE_STUB:
        command = "python3"
        args = [str(S.MCP_DIR / "redundra_stub.py")]
        env = {"PYTHONPATH": f"{S.MCP_DIR}:{worktree / 'src'}"}
    else:
        command = S.NODE_BIN
        args = [S.REDUNDRA_SERVER_JS]
        env = {"REDUNDRA_ROOT": str(worktree)}
    env_items = ", ".join(f"{k} = {_toml_str(v)}" for k, v in env.items())
    return "\n".join(
        [
            "[mcp_servers.redundra]",
            f"command = {_toml_str(command)}",
            f"args = {json.dumps(args)}",
            f"env = {{ {env_items} }}",
            "startup_timeout_sec = 30",
            "tool_timeout_sec = 60",
            "# Fail startup if Redundra can't initialize, so the with-arm truly had it.",
            "required = true",
        ]
    )


def _null_mcp_block() -> str:
    env_items = f'PYTHONPATH = {_toml_str(str(S.MCP_DIR))}'
    return "\n".join(
        [
            "[mcp_servers.null_control]",
            'command = "python3"',
            f"args = {json.dumps([str(S.MCP_DIR / 'null_mcp.py')])}",
            f"env = {{ {env_items} }}",
            "startup_timeout_sec = 30",
            "tool_timeout_sec = 60",
            "required = true",
        ]
    )


def write_arm_profiles(home: Path, worktree: Path) -> None:
    """(Re)write all three arm profile configs for a given worktree."""
    (home / "without-redundra.config.toml").write_text(
        "# Control arm: no MCP server attached.\n"
    )
    (home / "with-redundra.config.toml").write_text(_redundra_mcp_block(worktree) + "\n")
    (home / "null-mcp.config.toml").write_text(_null_mcp_block() + "\n")
    # Validate everything we just wrote is real TOML.
    for name in ("config.toml", "without-redundra.config.toml",
                 "with-redundra.config.toml", "null-mcp.config.toml"):
        with (home / name).open("rb") as fh:
            tomllib.load(fh)


def ensure_codex_home(worktree: Path) -> Path:
    """Return the CODEX_HOME to use and (re)write the per-arm profile files.

    For the ChatGPT-subscription provider we use the user's REAL ~/.codex as the
    home so there is exactly ONE auth.json that Codex rotates normally. Copying
    auth.json into a second home caused refresh-token rotation conflicts that
    invalidated the login (see BENCHMARK.md caveat). We only write the additive
    per-arm profile files there and never touch the user's config.toml/auth.json;
    model/effort/approval are supplied via `-c` flags in run_task.

    For the OpenRouter provider there is no subscription auth, so we keep an
    isolated home with a rendered base config.
    """
    if S.PROVIDER == "codex":
        home = S.USER_CODEX_HOME
        home.mkdir(parents=True, exist_ok=True)
        write_arm_profiles(home, worktree)
        return home
    home = S.CODEX_HOME
    write_base_config(home)
    write_arm_profiles(home, worktree)
    return home
