#!/usr/bin/env python3
"""Validate every task the SWE-bench way (`--predictions_path gold`).

For each task this asserts:
  1. EMPTY prediction  -> FAIL_TO_PASS tests do NOT all pass (task is non-trivial).
  2. GOLD  prediction  -> FAIL_TO_PASS all pass AND PASS_TO_PASS all pass.
  3. The reuse_check verdict on the gold diff matches the task class:
       positive  -> reuses reuse_target, no duplicate clone.
       extension -> modifies reuse_target's file (extends), no parallel clone.
       negative  -> does NOT invoke the tempting_symbol.

Exit code is non-zero if any task fails validation.

Usage:  python3 benchmark/scripts/validate_gold.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "runner"
sys.path.insert(0, str(RUNNER))

from _common import TASKS_DIR, all_task_ids, load_task  # noqa: E402
from reuse_check import analyze_diff  # noqa: E402
from score import score  # noqa: E402


def validate_one(task_id: str) -> list[str]:
    task = load_task(task_id)
    task_dir = TASKS_DIR / task_id
    problems: list[str] = []

    # 1. Empty prediction: FAIL_TO_PASS must not already be satisfied.
    empty = score(task, prediction_patch=None)
    if empty.f2p_ok:
        problems.append("FAIL_TO_PASS already passes on base (task is trivial)")

    # 2. Gold prediction: everything must pass.
    gold = score(task, prediction_patch_path=task_dir / "gold.patch")
    if not gold.prediction_applied:
        problems.append("gold.patch failed to apply")
    if not gold.f2p_ok:
        failed = [k for k, v in gold.fail_to_pass.items() if v != "PASSED"]
        problems.append(f"gold did not satisfy FAIL_TO_PASS: {failed}")
    if not gold.p2p_ok:
        failed = [k for k, v in gold.pass_to_pass.items() if v != "PASSED"]
        problems.append(f"gold broke PASS_TO_PASS: {failed}")

    # 3. Reuse verdict on the gold diff matches the task class.
    diff = (task_dir / "gold.patch").read_text()
    verdict = analyze_diff(
        diff,
        reuse_target=task["reuse_target"],
        tempting_symbol=task["tempting_symbol"],
        klass=task["klass"],
    )
    if not verdict["expected_for_gold"]:
        problems.append(f"reuse_check on gold unexpected: {verdict['reason']}")

    return problems


def main() -> None:
    ids = all_task_ids()
    print(f"Validating {len(ids)} tasks...\n")
    failures = 0
    for tid in ids:
        problems = validate_one(tid)
        status = "OK " if not problems else "FAIL"
        print(f"[{status}] {tid}")
        for p in problems:
            print(f"        - {p}")
        failures += bool(problems)
    print()
    if failures:
        print(f"{failures}/{len(ids)} tasks FAILED validation")
        sys.exit(1)
    print(f"All {len(ids)} tasks validated: gold solves, base fails, reuse verdict matches.")


if __name__ == "__main__":
    main()
