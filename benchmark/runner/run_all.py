#!/usr/bin/env python3
"""Run the full matrix: tasks x arms x seeds.

Usage:
    python3 benchmark/runner/run_all.py --run-id RUN [--seeds 5]
        [--arms with-redundra,without-redundra] [--tasks pos-01-url-path,...]
        [--timeout 600] [--smoke]

`--smoke` runs a tiny subset (3 tasks x with/without x 1 seed) for a cheap check.
Results land in benchmark/results/<run-id>/. Re-running skips completed cells
(idempotent) unless --force.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import settings as S
from _common import all_task_ids
from run_task import run_one

SMOKE_TASKS = ["pos-01-url-path", "neg-03-shallow-override", "ext-01-truncate-whole-words"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--arms", default=",".join(S.ARMS))
    ap.add_argument("--tasks", default="")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    if args.smoke:
        tasks = SMOKE_TASKS
        arms = [a for a in arms if a in ("with-redundra", "without-redundra")] or [
            "with-redundra", "without-redundra"
        ]
        seeds = 1
    else:
        tasks = [t.strip() for t in args.tasks.split(",") if t.strip()] or all_task_ids()
        seeds = args.seeds

    out_dir = S.RESULTS_DIR / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    cells = [(t, a, s) for t in tasks for a in arms for s in range(seeds)]
    print(f"run-id={args.run_id}  cells={len(cells)}  "
          f"({len(tasks)} tasks x {len(arms)} arms x {seeds} seeds)  provider={S.PROVIDER} model={S.MODEL}")

    done = 0
    for (t, a, s) in cells:
        stem = f"{t}__{a}__seed{s}"
        result_path = out_dir / f"{stem}.json"
        if result_path.exists() and not args.force:
            print(f"  skip {stem} (exists)")
            done += 1
            continue
        print(f"  run  {stem} ...", flush=True)
        try:
            r = run_one(t, a, s, run_id=args.run_id, timeout=args.timeout)
            print(f"       success={r['functional_success']} reuse={r['reuse_satisfied']} "
                  f"tokens={r['usage']['total_tokens']} lines=+{r['added_lines']} "
                  f"rc={r['codex_returncode']} {r['wall_seconds']}s")
            done += 1
        except Exception as exc:  # keep going; record the failure
            print(f"       ERROR: {exc}")
            (out_dir / f"{stem}.error.txt").write_text(str(exc))

    print(f"\nCompleted {done}/{len(cells)} cells -> {out_dir}")
    print(f"Analyze with: python3 benchmark/analysis/analyze.py {args.run_id}")


if __name__ == "__main__":
    main()
