#!/usr/bin/env python3
"""OpenCode agent adapter for Redundra-Bench (DeepSeek via OpenRouter).

Mirrors run_task.py but drives the OpenCode CLI instead of Codex:
    opencode run --format json -m <model> --dir <wt> --dangerously-skip-permissions "<prompt>"

The three arms are identical except the MCP attachment, declared in a per-arm
`opencode.json` written into the worktree (committed to the run-base so it is
excluded from the captured prediction diff). Scoring, reuse detection, and the
prediction diff are shared with the Codex path (_common / score / reuse_check).

Auth: set OPENROUTER_API_KEY in the environment, or run `opencode auth login`
once (OpenCode persists the credential). Model default: deepseek-v4-pro.

Usage:
    python3 benchmark/runner/run_opencode.py <task_id> <arm> [--seed N]
        [--run-id ID] [--model M] [--variant V] [--timeout S]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import settings as S
from _common import _git, fresh_checkout, load_task
from opencode_usage import parse_opencode_stream
from reuse_check import analyze_diff, reuse_satisfied
from run_task import INSTRUCTION, NULL_AGENTS_MD, REDUNDRA_AGENTS_MD, _capture_prediction
from score import score

OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "opencode")
OC_MODEL = os.environ.get("OC_MODEL", "openrouter/deepseek/deepseek-v4-pro")
OC_VARIANT = os.environ.get("OC_VARIANT", "")  # provider reasoning effort, e.g. high/max


def _opencode_config(arm: str, worktree: Path) -> dict:
    cfg: dict = {"$schema": "https://opencode.ai/config.json"}
    if arm == "with-redundra":
        if S.USE_STUB:
            server = {
                "type": "local",
                "command": ["python3", str(S.MCP_DIR / "redundra_stub.py")],
                "environment": {"PYTHONPATH": f"{S.MCP_DIR}:{worktree / 'src'}"},
                "enabled": True,
            }
        else:
            server = {
                "type": "local",
                "command": [S.NODE_BIN, S.REDUNDRA_SERVER_JS],
                "environment": {"REDUNDRA_ROOT": str(worktree)},
                "enabled": True,
            }
        cfg["mcp"] = {"redundra": server}
    elif arm == "null-mcp":
        cfg["mcp"] = {
            "null_control": {
                "type": "local",
                "command": ["python3", str(S.MCP_DIR / "null_mcp.py")],
                "environment": {"PYTHONPATH": str(S.MCP_DIR)},
                "enabled": True,
            }
        }
    return cfg


def _setup_arm(worktree: Path, arm: str) -> str:
    gi = worktree / ".gitignore"
    gi.write_text(gi.read_text() + "\n.redundra/\n.opencode/\n")
    (worktree / "opencode.json").write_text(
        json.dumps(_opencode_config(arm, worktree), indent=2) + "\n"
    )
    if arm == "with-redundra":
        (worktree / "redundra.config.json").write_text(
            json.dumps({"mode": S.REDUNDRA_MODE, "minCorpusSymbols": S.REDUNDRA_MIN_CORPUS}) + "\n"
        )
        (worktree / "AGENTS.md").write_text(REDUNDRA_AGENTS_MD)
    elif arm == "null-mcp":
        (worktree / "AGENTS.md").write_text(NULL_AGENTS_MD)
    _git(["add", "-A"], worktree)
    _git(["-c", "user.name=rbench", "-c", "user.email=rbench@local",
          "commit", "-q", "-m", f"arm setup (opencode): {arm}"], worktree)
    return _git(["rev-parse", "HEAD"], worktree).stdout.strip()


def run_one(task_id: str, arm: str, seed: int = 0, run_id: str = "adhoc-oc",
            model: str = OC_MODEL, variant: str = OC_VARIANT, timeout: int = 600) -> dict:
    if arm not in S.ARMS:
        raise SystemExit(f"unknown arm {arm!r}")
    task = load_task(task_id)
    out_dir = S.RESULTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{task_id}__{arm}__seed{seed}"
    events_path = out_dir / f"{stem}.events.json"

    with fresh_checkout(task["base_ref"]) as wt:
        _setup_arm(wt, arm)
        prompt = INSTRUCTION + task["prompt"]
        argv = [OPENCODE_BIN, "run", "--format", "json",
                "-m", model, "--dir", str(wt), "--dangerously-skip-permissions"]
        if variant:
            argv += ["--variant", variant]
        argv += [prompt]

        t0 = time.time()
        timed_out = False
        with events_path.open("w") as ef:
            try:
                proc = subprocess.run(argv, cwd=str(wt), env=os.environ.copy(),
                                      stdout=ef, stderr=subprocess.PIPE, text=True,
                                      timeout=timeout)
                rc = proc.returncode
                stderr_tail = (proc.stderr or "")[-2000:]
            except subprocess.TimeoutExpired:
                timed_out, rc, stderr_tail = True, -1, "TIMEOUT"
        wall = round(time.time() - t0, 1)
        prediction = _capture_prediction(wt)

    sr = score(task, prediction_patch=prediction)
    verdict = analyze_diff(prediction, reuse_target=task["reuse_target"],
                           tempting_symbol=task["tempting_symbol"], klass=task["klass"])
    usage = parse_opencode_stream(events_path)
    added_lines = sum(1 for ln in prediction.splitlines()
                      if ln.startswith("+") and not ln.startswith("+++"))

    result = {
        "run_id": run_id, "task_id": task_id, "klass": task["klass"], "arm": arm,
        "seed": seed, "agent": "opencode", "model": model, "variant": variant,
        "returncode": rc, "timed_out": timed_out, "wall_seconds": wall,
        "stderr_tail": stderr_tail, "prediction_nonempty": bool(prediction.strip()),
        "added_lines": added_lines, "functional_success": sr.functional_success,
        "score": sr.to_dict(), "reuse": verdict,
        "reuse_satisfied": reuse_satisfied(verdict, task["klass"]), "usage": usage,
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(result, indent=2))
    (out_dir / f"{stem}.pred.patch").write_text(prediction)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_id")
    ap.add_argument("arm", choices=S.ARMS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--run-id", default="adhoc-oc")
    ap.add_argument("--model", default=OC_MODEL)
    ap.add_argument("--variant", default=OC_VARIANT)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    r = run_one(args.task_id, args.arm, args.seed, args.run_id, args.model,
                args.variant, args.timeout)
    print(json.dumps({k: r[k] for k in ("task_id", "arm", "seed", "functional_success",
          "reuse_satisfied", "added_lines", "returncode", "wall_seconds")}, indent=2))
    print("usage:", json.dumps(r["usage"]))


if __name__ == "__main__":
    main()
