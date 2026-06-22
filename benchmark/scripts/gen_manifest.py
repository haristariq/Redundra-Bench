#!/usr/bin/env python3
"""Generate benchmark/manifest.yaml: pinned versions + per-task checksums.

Run after authoring/changing tasks to refresh the manifest used for
reproducibility verification.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "fixtures" / "redundra-utils"
TASKS = REPO / "benchmark" / "tasks"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def cmd(args: list[str], cwd: Path | None = None) -> str:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def main() -> None:
    fixture_sha = cmd(["git", "rev-parse", "HEAD"], FIXTURE)
    codex_ver = cmd(["codex", "--version"])
    node_ver = cmd(["node", "--version"])

    tasks = []
    for d in sorted(p for p in TASKS.iterdir() if (p / "task.yaml").exists()):
        meta = yaml.safe_load((d / "task.yaml").read_text())
        tasks.append({
            "id": meta["id"],
            "klass": meta["klass"],
            "reuse_target": meta["reuse_target"],
            "checksums": {
                "task.yaml": sha256(d / "task.yaml"),
                "gold.patch": sha256(d / "gold.patch"),
                "test.patch": sha256(d / "test.patch"),
            },
        })

    by_class: dict[str, int] = {}
    for t in tasks:
        by_class[t["klass"]] = by_class.get(t["klass"], 0) + 1

    manifest = {
        "benchmark": "Redundra-Bench",
        "phase": 0,
        "pins": {
            "fixture_repo": "redundra-utils",
            "fixture_commit": fixture_sha,
            "fixture_tag": "base-v0.1.0",
            "codex_cli_version": codex_ver,
            "node_version": node_ver,
            "default_model": "gpt-5.5 (Codex subscription) / deepseek/deepseek-v3.2 (OpenRouter)",
        },
        "task_counts": {"total": len(tasks), **by_class},
        "tasks": tasks,
    }
    out = REPO / "benchmark" / "manifest.yaml"
    out.write_text(yaml.safe_dump(manifest, sort_keys=False, width=100))
    print(f"wrote {out} ({len(tasks)} tasks)")


if __name__ == "__main__":
    main()
