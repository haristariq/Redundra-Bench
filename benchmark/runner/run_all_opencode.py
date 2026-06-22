#!/usr/bin/env python3
"""Run the full matrix with the OpenCode agent (DeepSeek via OpenRouter).

Usage:
    python3 benchmark/runner/run_all_opencode.py --run-id RUN [--seeds 5]
        [--arms ...] [--tasks ...] [--model M] [--variant V] [--timeout S] [--smoke]

Requires OPENROUTER_API_KEY in the environment (or `opencode auth login` once).
Idempotent: completed cells are skipped unless --force.
"""

from __future__ import annotations

import argparse

import settings as S
from _common import all_task_ids
from run_opencode import OC_MODEL, OC_VARIANT, run_one

SMOKE_TASKS = ["pos-01-url-path", "neg-03-shallow-override", "ext-01-truncate-whole-words"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--arms", default=",".join(S.ARMS))
    ap.add_argument("--tasks", default="")
    ap.add_argument("--model", default=OC_MODEL)
    ap.add_argument("--variant", default=OC_VARIANT)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    if args.smoke:
        tasks = SMOKE_TASKS
        arms = [a for a in arms if a in ("with-redundra", "without-redundra")] or [
            "with-redundra", "without-redundra"]
        seeds = 1
    else:
        tasks = [t.strip() for t in args.tasks.split(",") if t.strip()] or all_task_ids()
        seeds = args.seeds

    out_dir = S.RESULTS_DIR / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    cells = [(t, a, s) for t in tasks for a in arms for s in range(seeds)]
    print(f"run-id={args.run_id} agent=opencode model={args.model} variant={args.variant or '-'}  "
          f"cells={len(cells)} ({len(tasks)}x{len(arms)}x{seeds})")

    done = 0
    for (t, a, s) in cells:
        stem = f"{t}__{a}__seed{s}"
        if (out_dir / f"{stem}.json").exists() and not args.force:
            print(f"  skip {stem}")
            done += 1
            continue
        print(f"  run  {stem} ...", flush=True)
        try:
            r = run_one(t, a, s, run_id=args.run_id, model=args.model,
                        variant=args.variant, timeout=args.timeout)
            print(f"       success={r['functional_success']} reuse={r['reuse_satisfied']} "
                  f"tokens={r['usage']['total_tokens']} cost=${r['usage']['cost_usd']:.4f} "
                  f"lines=+{r['added_lines']} rc={r['returncode']} {r['wall_seconds']}s")
            done += 1
        except Exception as exc:
            print(f"       ERROR: {exc}")
            (out_dir / f"{stem}.error.txt").write_text(str(exc))

    print(f"\nCompleted {done}/{len(cells)} cells -> {out_dir}")
    print(f"Analyze with: python3 benchmark/analysis/analyze.py {args.run_id}")


if __name__ == "__main__":
    main()
