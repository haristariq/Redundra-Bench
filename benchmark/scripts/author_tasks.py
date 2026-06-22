#!/usr/bin/env python3
"""Generate task directories (task.yaml, gold.patch, test.patch) from specs.

For each spec in ``task_specs.TASKS`` this:
  1. checks out the pinned base commit into a throwaway git worktree,
  2. writes the gold solution files and captures ``git diff`` -> gold.patch,
  3. resets, writes the hidden test files and captures -> test.patch,
  4. writes task.yaml with all metadata + the resolved base SHA.

Patches are produced with git so they apply cleanly later with `git apply`.
Re-running is idempotent: task directories are overwritten.

Usage:
    python3 benchmark/scripts/author_tasks.py
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from task_specs import TASKS

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "fixtures" / "redundra-utils"
TASKS_DIR = REPO_ROOT / "benchmark" / "tasks"
BASE_REF = "base-v0.1.0"


def git(args: list[str], cwd: Path) -> str:
    out = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return out.stdout


def write_files(root: Path, files: dict[str, str]) -> None:
    for relpath, content in files.items():
        dest = root / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)


def capture_diff(worktree: Path, files: dict[str, str]) -> str:
    git(["reset", "-q", "--hard"], worktree)
    git(["clean", "-fdq"], worktree)
    write_files(worktree, files)
    git(["add", "-A"], worktree)
    diff = git(["diff", "--cached"], worktree)
    return diff


def main() -> None:
    base_sha = git(["rev-parse", BASE_REF], FIXTURE).strip()
    print(f"base {BASE_REF} = {base_sha}")

    for task in TASKS:
        tid = task["id"]
        tmp = Path(tempfile.mkdtemp(prefix=f"author-{tid}-"))
        worktree = tmp / "wt"
        git(["worktree", "add", "--detach", "-q", str(worktree), BASE_REF], FIXTURE)
        try:
            gold_patch = capture_diff(worktree, task["gold_files"])
            test_patch = capture_diff(worktree, task["test_files"])
        finally:
            git(["worktree", "remove", "--force", str(worktree)], FIXTURE)
            shutil.rmtree(tmp, ignore_errors=True)

        if not gold_patch.strip():
            raise SystemExit(f"{tid}: empty gold patch")
        if not test_patch.strip():
            raise SystemExit(f"{tid}: empty test patch")

        task_dir = TASKS_DIR / tid
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "gold.patch").write_text(gold_patch)
        (task_dir / "test.patch").write_text(test_patch)

        meta = {
            "id": tid,
            "klass": task["klass"],
            "repo": "redundra-utils",
            "base_ref": BASE_REF,
            "base_sha": base_sha,
            "reuse_target": task["reuse_target"],
            "tempting_symbol": task["tempting_symbol"],
            "prompt": task["prompt"],
            "fail_to_pass": task["fail_to_pass"],
            "pass_to_pass": task["pass_to_pass"],
            "rationale": task["rationale"],
            "gold_files": sorted(task["gold_files"].keys()),
            "test_files": sorted(task["test_files"].keys()),
        }
        with (task_dir / "task.yaml").open("w") as fh:
            yaml.safe_dump(meta, fh, sort_keys=False, width=100, allow_unicode=True)
        print(f"  wrote {tid} ({task['klass']})")

    print(f"\nAuthored {len(TASKS)} tasks into {TASKS_DIR}")


if __name__ == "__main__":
    main()
