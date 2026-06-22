"""Shared harness primitives: worktrees, patching, and pytest node scoring."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "fixtures" / "redundra-utils"
TASKS_DIR = REPO_ROOT / "benchmark" / "tasks"


def load_task(task_id: str) -> dict:
    with (TASKS_DIR / task_id / "task.yaml").open() as fh:
        return yaml.safe_load(fh)


def all_task_ids() -> list[str]:
    return sorted(p.name for p in TASKS_DIR.iterdir() if (p / "task.yaml").exists())


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@contextmanager
def fresh_checkout(base_sha: str) -> Iterator[Path]:
    """Yield a clean git worktree of the fixture at ``base_sha``."""
    tmp = Path(tempfile.mkdtemp(prefix="rbench-"))
    wt = tmp / "wt"
    res = _git(["worktree", "add", "--detach", "-q", str(wt), base_sha], FIXTURE)
    if res.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"worktree add failed: {res.stderr}")
    try:
        yield wt
    finally:
        _git(["worktree", "remove", "--force", str(wt)], FIXTURE)
        shutil.rmtree(tmp, ignore_errors=True)


def apply_patch(worktree: Path, patch_path: Path) -> bool:
    """Apply a unified diff to ``worktree``. Returns True on success."""
    text = patch_path.read_text()
    if not text.strip():
        return True
    res = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        return True
    # Fall back to a 3-way / lenient apply for prediction diffs that don't line
    # up perfectly (agents sometimes produce slightly fuzzy hunks).
    res2 = subprocess.run(
        ["git", "apply", "--3way", "--whitespace=nowarn", str(patch_path)],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    return res2.returncode == 0


def apply_patch_text(worktree: Path, diff_text: str) -> bool:
    if not diff_text.strip():
        return True
    tmp = worktree / ".rbench_pred.patch"
    tmp.write_text(diff_text)
    try:
        return apply_patch(worktree, tmp)
    finally:
        tmp.unlink(missing_ok=True)


_OUTCOME_RE = re.compile(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\s+(\S+)")


def run_pytest_nodes(worktree: Path, node_ids: list[str]) -> dict[str, str]:
    """Run the given pytest node ids; return {node_id: OUTCOME}.

    Nodes that never appear in the report (e.g. the test module failed to
    import because the agent never created it) are recorded as ``MISSING``.
    """
    if not node_ids:
        return {}
    res = subprocess.run(
        [
            "python3",
            "-m",
            "pytest",
            *node_ids,
            "-rA",
            "-p",
            "no:cacheprovider",
            "--no-header",
            "-q",
            "--tb=no",
        ],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    outcomes: dict[str, str] = {}
    for line in res.stdout.splitlines():
        m = _OUTCOME_RE.match(line.strip())
        if m:
            outcomes[m.group(2)] = m.group(1)
    # Normalise: pytest reports nodes with the rootdir-relative path, which
    # matches our `tests/...::name` ids. Anything we asked for but didn't see
    # is treated as a hard failure to import/collect.
    for nid in node_ids:
        outcomes.setdefault(nid, "MISSING")
    return outcomes
