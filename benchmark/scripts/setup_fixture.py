#!/usr/bin/env python3
"""Initialize the fixture as a local git repo pinned at tag base-v0.1.0.

The fixture (`fixtures/redundra-utils`) must be its own git repo so the harness
can create clean worktrees of ONLY the fixture (the agent must not see the
benchmark's gold patches). That nested repo is not committed to this repository,
so after a clone run this once to (re)create it.

The commit uses a fixed identity and date, so the resulting commit SHA is
deterministic and identical on every machine. Idempotent: does nothing if the
tag already exists.

Usage:  python3 benchmark/scripts/setup_fixture.py
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "redundra-utils"
TAG = "base-v0.1.0"
IDENT = {
    "GIT_AUTHOR_NAME": "Redundra-Bench",
    "GIT_AUTHOR_EMAIL": "bench@redundra.local",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
    "GIT_COMMITTER_NAME": "Redundra-Bench",
    "GIT_COMMITTER_EMAIL": "bench@redundra.local",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
}


def git(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=FIXTURE, capture_output=True, text=True, **kw)


def tag_exists() -> bool:
    return (FIXTURE / ".git").exists() and git(["rev-parse", "-q", "--verify", f"refs/tags/{TAG}"]).returncode == 0


def main() -> None:
    if tag_exists():
        sha = git(["rev-parse", TAG]).stdout.strip()
        print(f"fixture already initialized at {TAG} = {sha}")
        return

    env = {**os.environ, **IDENT}
    if not (FIXTURE / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=FIXTURE, check=True)
    subprocess.run(["git", "add", "-A"], cwd=FIXTURE, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m",
         "redundra-utils fixture v0.1.0 (base commit for Redundra-Bench)"],
        cwd=FIXTURE, check=True, env=env,
    )
    subprocess.run(["git", "tag", TAG], cwd=FIXTURE, check=True)
    sha = git(["rev-parse", TAG]).stdout.strip()
    print(f"initialized fixture at {TAG} = {sha}")


if __name__ == "__main__":
    main()
