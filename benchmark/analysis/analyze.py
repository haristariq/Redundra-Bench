#!/usr/bin/env python3
"""Aggregate a run's results into the Redundra-Bench leaderboard table.

Reports, per arm: functional pass rate, reuse rate (positive+extension),
false-block rate (negatives), median LOC added, median turns, median total
tokens. Then the headline A/B: net token delta (with vs without) with a 95%
bootstrap CI and a paired Wilcoxon signed-rank test across tasks.

Usage:  python3 benchmark/analysis/analyze.py <run-id> [--baseline without-redundra]
                                                        [--treatment with-redundra]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

RESULTS = Path(__file__).resolve().parents[1] / "results"


def load_results(run_id: str) -> list[dict]:
    d = RESULTS / run_id
    if not d.exists():
        sys.exit(f"no results dir: {d}")
    out = []
    for p in sorted(d.glob("*.json")):
        # Skip non-result files: the written summary and any per-cell event logs.
        if p.name == "summary.json" or p.name.endswith((".error.json", ".events.json")):
            continue
        try:
            row = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if "arm" in row:  # result cells only
            out.append(row)
    return out


def _median(xs: list[float]) -> float:
    return round(statistics.median(xs), 1) if xs else float("nan")


def per_arm_summary(rows: list[dict]) -> dict:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)

    summary = {}
    for arm, rs in by_arm.items():
        pos = [r for r in rs if r["klass"] in ("positive", "extension")]
        neg = [r for r in rs if r["klass"] == "negative"]
        n = len(rs)
        passed = [r for r in rs if r["functional_success"]]
        reuse_ok = [r for r in pos if r["reuse_satisfied"] and r["functional_success"]]
        # false block: forced the tempting symbol AND it broke (not functional success)
        false_blocks = [
            r for r in neg
            if r["reuse"].get("invoked_tempting") and not r["functional_success"]
        ]
        summary[arm] = {
            "runs": n,
            "pass_rate": round(len(passed) / n, 3) if n else float("nan"),
            "reuse_rate": round(len(reuse_ok) / len(pos), 3) if pos else float("nan"),
            "false_block_rate": round(len(false_blocks) / len(neg), 3) if neg else float("nan"),
            "median_loc_added": _median([r["added_lines"] for r in rs]),
            # Codex reports "turns"; OpenCode reports "steps" - accept either.
            "median_turns": _median([
                r["usage"].get("turns", r["usage"].get("steps", 0)) for r in rs
            ]),
            "median_total_tokens": _median([r["usage"]["total_tokens"] for r in rs]),
            "median_cost_usd": round(sum(r["usage"].get("cost_usd", 0.0) for r in rs), 4),
            "median_wall_s": _median([r["wall_seconds"] for r in rs]),
            "redundra_tool_calls_total": sum(r["usage"].get("redundra_tool_calls", 0) for r in rs),
        }
    return summary


def paired_token_delta(rows: list[dict], baseline: str, treatment: str) -> dict:
    """Per-task mean tokens for each arm, then paired stats on the deltas."""
    def mean_by_task(arm: str, field) -> dict[str, float]:
        acc: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            if r["arm"] == arm:
                acc[r["task_id"]].append(field(r))
        return {t: statistics.mean(v) for t, v in acc.items() if v}

    b_tok = mean_by_task(baseline, lambda r: r["usage"]["total_tokens"])
    t_tok = mean_by_task(treatment, lambda r: r["usage"]["total_tokens"])
    common = sorted(set(b_tok) & set(t_tok))
    if not common:
        return {"error": "no common tasks between arms"}

    base = np.array([b_tok[t] for t in common], dtype=float)
    treat = np.array([t_tok[t] for t in common], dtype=float)
    deltas = treat - base  # negative => Redundra used fewer tokens

    # Bootstrap 95% CI on the mean delta and on the median pct change.
    rng = np.random.default_rng(0)
    n = len(deltas)
    boot = np.array([
        deltas[rng.integers(0, n, n)].mean() for _ in range(10000)
    ])
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])

    pct = (treat - base) / np.where(base == 0, np.nan, base) * 100
    out = {
        "tasks_paired": n,
        "baseline_mean_tokens": round(float(base.mean()), 1),
        "treatment_mean_tokens": round(float(treat.mean()), 1),
        "mean_delta_tokens": round(float(deltas.mean()), 1),
        "mean_delta_ci95": [round(float(ci_lo), 1), round(float(ci_hi), 1)],
        "median_pct_change": round(float(np.nanmedian(pct)), 2),
    }
    if n >= 6 and np.any(deltas != 0):
        w = stats.wilcoxon(treat, base, zero_method="wilcox", alternative="two-sided")
        out["wilcoxon_stat"] = round(float(w.statistic), 3)
        out["wilcoxon_p"] = round(float(w.pvalue), 5)
    else:
        out["wilcoxon_note"] = "need >=6 paired nonzero tasks for Wilcoxon"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--baseline", default="without-redundra")
    ap.add_argument("--treatment", default="with-redundra")
    args = ap.parse_args()

    rows = load_results(args.run_id)
    if not rows:
        sys.exit("no results loaded")
    summary = per_arm_summary(rows)

    print(f"\n=== Redundra-Bench results: {args.run_id} ({len(rows)} runs) ===\n")
    cols = ["pass_rate", "reuse_rate", "false_block_rate", "median_loc_added",
            "median_turns", "median_total_tokens", "median_wall_s"]
    header = f"{'arm':<18}" + "".join(f"{c:>20}" for c in cols)
    print(header)
    print("-" * len(header))
    for arm in sorted(summary):
        s = summary[arm]
        print(f"{arm:<18}" + "".join(f"{str(s[c]):>20}" for c in cols))

    print("\n--- Headline A/B (treatment vs baseline) ---")
    delta = paired_token_delta(rows, args.baseline, args.treatment)
    print(json.dumps(delta, indent=2))

    report = {"run_id": args.run_id, "n_runs": len(rows),
              "per_arm": summary, "token_delta": delta}
    out = RESULTS / args.run_id / "summary.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
