#!/usr/bin/env python3
"""Run ONE (task, arm, seed): drive Codex, capture the diff, score, measure.

Usage:
    python3 benchmark/runner/run_task.py <task_id> <arm> [--seed N] [--run-id ID]
                                         [--timeout SECS] [--keep]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import settings as S
from _common import _git, fresh_checkout, load_task
from codex_env import ensure_codex_home
from codex_usage import parse_stream
from reuse_check import analyze_diff, reuse_satisfied
from score import score


def _q(value: str) -> str:
    """Quote a string as a TOML basic string for a `-c key=value` override."""
    return json.dumps(value)


# A neutral wrapper. It must NOT mention "reuse" - the only manipulated variable
# between arms is whether Redundra is attached.
INSTRUCTION = (
    "You are an automated coding agent working in the repository at the current "
    "working directory. Implement the change described below by editing files in "
    "this repository. Do not modify or add any files under the tests/ directory. "
    "Make the smallest correct change and ensure the code is syntactically valid "
    "Python. When finished, stop.\n\n--- TASK ---\n"
)

# AGENTS.md guidance that ships with a repo onboarded to Redundra (Loop A nudge).
REDUNDRA_AGENTS_MD = (
    "# Working in this repository with Redundra\n\n"
    "Before writing a utility, validator, formatter, wrapper, or transform helper, "
    "call the `find_reusable` MCP tool with your intent. If it returns a strong "
    "candidate, reuse or extend it instead of writing a new one. If unsure whether "
    "a draft duplicates existing code, call `review_draft` before applying it.\n"
)
# Length-matched, reuse-irrelevant control text for the null arm.
NULL_AGENTS_MD = (
    "# Working in this repository\n\n"
    "This project uses a standard src layout with pytest-based tests and follows "
    "conventional Python style. Keep changes small and focused, write clear "
    "docstrings, and ensure modules expose their public API via __all__. Run the "
    "existing test suite locally when convenient before finishing.\n"
)


def _setup_arm(worktree: Path, arm: str) -> str:
    """Apply arm-specific repo setup, commit it, return the run-base SHA.

    Committing the setup means it is excluded from the captured prediction diff.
    """
    # Ignore Redundra's on-disk index so it never leaks into the diff.
    gi = worktree / ".gitignore"
    gi.write_text(gi.read_text() + "\n.redundra/\n")

    if arm == "with-redundra":
        (worktree / "redundra.config.json").write_text(
            json.dumps({"mode": S.REDUNDRA_MODE, "minCorpusSymbols": S.REDUNDRA_MIN_CORPUS})
            + "\n"
        )
        (worktree / "AGENTS.md").write_text(REDUNDRA_AGENTS_MD)
    elif arm == "null-mcp":
        (worktree / "AGENTS.md").write_text(NULL_AGENTS_MD)

    _git(["add", "-A"], worktree)
    _git(
        ["-c", "user.name=rbench", "-c", "user.email=rbench@local",
         "commit", "-q", "-m", f"arm setup: {arm}"],
        worktree,
    )
    return _git(["rev-parse", "HEAD"], worktree).stdout.strip()


def _capture_prediction(worktree: Path) -> str:
    """Diff the agent's source changes against the run-base commit."""
    _git(["add", "-A", "--", "src"], worktree)
    return _git(["diff", "--cached", "--", "src"], worktree).stdout


def run_one(
    task_id: str,
    arm: str,
    seed: int = 0,
    run_id: str = "adhoc",
    timeout: int = 600,
    keep: bool = False,
) -> dict:
    if arm not in S.ARMS:
        raise SystemExit(f"unknown arm {arm!r}; choose from {S.ARMS}")
    task = load_task(task_id)
    out_dir = S.RESULTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{task_id}__{arm}__seed{seed}"
    jsonl_path = out_dir / f"{stem}.jsonl"
    last_msg_path = out_dir / f"{stem}.last.txt"

    with fresh_checkout(task["base_ref"]) as wt:
        _setup_arm(wt, arm)
        home = ensure_codex_home(wt)

        prompt = INSTRUCTION + task["prompt"]
        argv = [
            S.CODEX_BIN, "exec", "--json",
            "--skip-git-repo-check",
            "--sandbox", S.SANDBOX,
            "-C", str(wt),
            "-p", arm,
            "-c", f'model={_q(S.MODEL)}',
            "-c", f'model_reasoning_effort="{S.REASONING_EFFORT}"',
            "-c", 'approval_policy="never"',
            "-o", str(last_msg_path),
            prompt,
        ]
        env = {"CODEX_HOME": str(home)}
        import os
        full_env = {**os.environ, **env}

        t0 = time.time()
        timed_out = False
        with jsonl_path.open("w") as jf:
            try:
                proc = subprocess.run(
                    argv, cwd=str(wt), env=full_env, stdout=jf,
                    stderr=subprocess.PIPE, text=True, timeout=timeout,
                )
                rc = proc.returncode
                stderr_tail = (proc.stderr or "")[-2000:]
            except subprocess.TimeoutExpired:
                timed_out = True
                rc = -1
                stderr_tail = "TIMEOUT"
        wall = round(time.time() - t0, 1)

        prediction = _capture_prediction(wt)

    # ---- measure (outside the worktree; score uses its own checkout) ----
    sr = score(task, prediction_patch=prediction)
    verdict = analyze_diff(
        prediction,
        reuse_target=task["reuse_target"],
        tempting_symbol=task["tempting_symbol"],
        klass=task["klass"],
    )
    usage = parse_stream(jsonl_path)

    added_lines = sum(
        1 for ln in prediction.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    )

    result = {
        "run_id": run_id,
        "task_id": task_id,
        "klass": task["klass"],
        "arm": arm,
        "seed": seed,
        "codex_returncode": rc,
        "timed_out": timed_out,
        "wall_seconds": wall,
        "stderr_tail": stderr_tail,
        "prediction_nonempty": bool(prediction.strip()),
        "added_lines": added_lines,
        "functional_success": sr.functional_success,
        "score": sr.to_dict(),
        "reuse": verdict,
        "reuse_satisfied": reuse_satisfied(verdict, task["klass"]),
        "usage": usage.to_dict(),
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(result, indent=2))
    if not keep:
        # keep the prediction patch for auditing
        (out_dir / f"{stem}.pred.patch").write_text(prediction)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_id")
    ap.add_argument("arm", choices=S.ARMS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--run-id", default="adhoc")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    r = run_one(args.task_id, args.arm, args.seed, args.run_id, args.timeout, args.keep)
    print(json.dumps({k: r[k] for k in (
        "task_id", "arm", "seed", "functional_success", "reuse_satisfied",
        "added_lines", "codex_returncode", "wall_seconds")}, indent=2))
    print("usage:", json.dumps(r["usage"]))


if __name__ == "__main__":
    main()
