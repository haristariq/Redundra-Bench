"""Functional scoring: apply hidden tests + a prediction, run FAIL/PASS sets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from _common import (
    TASKS_DIR,
    apply_patch,
    apply_patch_text,
    fresh_checkout,
    run_pytest_nodes,
)


@dataclass
class ScoreResult:
    task_id: str
    prediction_applied: bool
    fail_to_pass: dict[str, str] = field(default_factory=dict)
    pass_to_pass: dict[str, str] = field(default_factory=dict)

    @property
    def f2p_ok(self) -> bool:
        return bool(self.fail_to_pass) and all(
            v == "PASSED" for v in self.fail_to_pass.values()
        )

    @property
    def p2p_ok(self) -> bool:
        return all(v == "PASSED" for v in self.pass_to_pass.values())

    @property
    def functional_success(self) -> bool:
        return self.prediction_applied and self.f2p_ok and self.p2p_ok

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "prediction_applied": self.prediction_applied,
            "functional_success": self.functional_success,
            "f2p_ok": self.f2p_ok,
            "p2p_ok": self.p2p_ok,
            "fail_to_pass": self.fail_to_pass,
            "pass_to_pass": self.pass_to_pass,
        }


def score(
    task: dict,
    prediction_patch: Optional[str] = None,
    prediction_patch_path: Optional[Path] = None,
) -> ScoreResult:
    """Score a prediction (diff text or file) against a task.

    Pass neither prediction argument to score the *empty* prediction (used to
    confirm FAIL_TO_PASS tests genuinely fail on base).
    """
    task_dir = TASKS_DIR / task["id"]
    with fresh_checkout(task["base_ref"]) as wt:
        # Hidden tests are always applied (they define the FAIL_TO_PASS set).
        if not apply_patch(wt, task_dir / "test.patch"):
            raise RuntimeError(f"{task['id']}: test.patch failed to apply")

        if prediction_patch_path is not None:
            applied = apply_patch(wt, prediction_patch_path)
        elif prediction_patch is not None:
            applied = apply_patch_text(wt, prediction_patch)
        else:
            applied = False  # empty prediction (base-fails sanity check)

        # Always run the node sets and report outcomes. If the prediction
        # failed to apply, the new code isn't present, so FAIL_TO_PASS nodes
        # will surface as MISSING/FAILED - which is the correct verdict.
        f2p = run_pytest_nodes(wt, task["fail_to_pass"])
        p2p = run_pytest_nodes(wt, task["pass_to_pass"])

    return ScoreResult(
        task_id=task["id"],
        prediction_applied=applied,
        fail_to_pass=f2p,
        pass_to_pass=p2p,
    )
