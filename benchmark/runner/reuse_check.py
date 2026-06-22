"""Reuse / clone analysis of a produced diff.

Implements the two behavioural primitives Redundra-Bench measures:

  * **reuse**  - did the diff *invoke* an existing symbol (import + call)?
  * **clone**  - did the diff instead *re-implement* that symbol's body
                 (a Type-3/Type-4 structural near-duplicate)?

The clone detector is intentionally simple and transparent: it compares a
normalised AST-node-type fingerprint of each function defined in the diff
against the fingerprint of the reference symbol's body, using a sequence-ratio
similarity. Its precision/recall is a known confounder (see BENCHMARK.md §F)
and should be reported alongside results, not treated as ground truth.
"""

from __future__ import annotations

import ast
import difflib
import importlib
import inspect
import re
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "fixtures" / "redundra-utils" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

CLONE_THRESHOLD = 0.75


# --------------------------------------------------------------------------- #
# Diff parsing
# --------------------------------------------------------------------------- #

_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")


def _changed_files(diff_text: str) -> list[str]:
    files = []
    for line in diff_text.splitlines():
        m = _DIFF_FILE_RE.match(line)
        if m and m.group(1) != "/dev/null":
            files.append(m.group(1))
    return files


def _added_lines_by_file(diff_text: str) -> dict[str, str]:
    """Return {path: text-of-added-lines} for each file in the diff."""
    result: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in diff_text.splitlines():
        m = _DIFF_FILE_RE.match(line)
        if m:
            if current is not None:
                result[current] = "\n".join(buf)
            current = m.group(1)
            buf = []
            continue
        if current is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            buf.append(line[1:])
    if current is not None:
        result[current] = "\n".join(buf)
    return result


def _is_test_path(path: str) -> bool:
    return "tests/" in path or Path(path).name.startswith("test_")


# --------------------------------------------------------------------------- #
# Reference symbol introspection
# --------------------------------------------------------------------------- #


def _split_symbol(dotted: str) -> tuple[str, str]:
    module, _, name = dotted.rpartition(".")
    return module, name


def _symbol_source(dotted: str) -> str | None:
    module, name = _split_symbol(dotted)
    try:
        mod = importlib.import_module(module)
        obj = getattr(mod, name)
        return inspect.getsource(obj)
    except Exception:
        return None


def _symbol_file(dotted: str) -> str | None:
    """Return the repo-relative file path that defines ``dotted``."""
    module, _ = _split_symbol(dotted)
    try:
        mod = importlib.import_module(module)
        path = Path(mod.__file__)
        return "src/" + str(path.relative_to(_SRC)).replace("\\", "/")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# AST fingerprints + similarity
# --------------------------------------------------------------------------- #

_SKIP_NODES = (ast.Load, ast.Store, ast.Del, ast.expr_context)


def _fingerprint(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, _SKIP_NODES):
            continue
        out.append(type(node).__name__)
    return out


def _funcs(source: str) -> list[ast.FunctionDef]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def _similarity(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _best_clone_score(added_source: str, reference_source: str) -> float:
    ref_funcs = _funcs(reference_source)
    if not ref_funcs:
        return 0.0
    ref_fp = _fingerprint(ref_funcs[0])
    best = 0.0
    for fn in _funcs(added_source):
        best = max(best, _similarity(_fingerprint(fn), ref_fp))
    return best


# --------------------------------------------------------------------------- #
# Import / call detection
# --------------------------------------------------------------------------- #


def _invokes_symbol(added_source: str, dotted: str) -> bool:
    """True if added code both brings ``name`` into scope and calls it."""
    module, name = _split_symbol(dotted)
    last_mod = module.rsplit(".", 1)[-1]  # e.g. "text"
    imported = False
    called = False

    try:
        tree = ast.parse(added_source)
        nodes = list(ast.walk(tree))
    except SyntaxError:
        nodes = []

    for node in nodes:
        if isinstance(node, ast.ImportFrom):
            mod = (node.module or "")
            if mod.endswith(last_mod) or mod.endswith(module):
                if any(a.name == name for a in node.names):
                    imported = True
        if isinstance(node, ast.Import):
            if any(a.name == module or a.name.endswith(last_mod) for a in node.names):
                imported = True
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == name:
                called = True
            if isinstance(f, ast.Attribute) and f.attr == name:
                called = True

    if nodes:
        return imported and called

    # Fallback for un-parseable (modified-file) diffs: textual heuristic.
    has_import = bool(
        re.search(rf"(from\s+[\w.]*{last_mod}\s+import\s+[^\n]*\b{name}\b)", added_source)
        or re.search(rf"import\s+{re.escape(module)}", added_source)
    )
    has_call = bool(re.search(rf"\b{name}\s*\(", added_source))
    return has_import and has_call


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def analyze_diff(
    diff_text: str,
    reuse_target: str | None,
    tempting_symbol: str | None,
    klass: str,
) -> dict:
    """Return a structured reuse/clone verdict for a diff.

    Keys:
      changed_code_files : non-test files touched
      reused             : invoked reuse_target (positive/extension)
      clone_score        : best structural similarity to the reference body
      duplicated         : added a near-duplicate of the reference instead of reusing
      modified_target_file : touched the file that defines reuse_target (extension)
      invoked_tempting   : invoked the tempting_symbol (negative false-block signal)
      expected_for_gold  : does this verdict match what the gold solution should show
      reason             : human-readable explanation
    """
    changed = _changed_files(diff_text)
    code_files = [f for f in changed if not _is_test_path(f) and f.endswith(".py")]
    added_by_file = _added_lines_by_file(diff_text)
    added_code = "\n".join(
        t for f, t in added_by_file.items() if not _is_test_path(f) and f.endswith(".py")
    )

    verdict: dict = {
        "changed_code_files": code_files,
        "reused": False,
        "clone_score": 0.0,
        "duplicated": False,
        "modified_target_file": False,
        "invoked_tempting": False,
        "expected_for_gold": False,
        "reason": "",
    }

    if reuse_target:
        verdict["reused"] = _invokes_symbol(added_code, reuse_target)
        ref_src = _symbol_source(reuse_target)
        if ref_src:
            verdict["clone_score"] = round(_best_clone_score(added_code, ref_src), 3)
        target_file = _symbol_file(reuse_target)
        verdict["modified_target_file"] = bool(target_file and target_file in code_files)

    if tempting_symbol:
        verdict["invoked_tempting"] = _invokes_symbol(added_code, tempting_symbol)
        ref_src = _symbol_source(tempting_symbol)
        if ref_src:
            verdict["clone_score"] = round(_best_clone_score(added_code, ref_src), 3)

    if klass == "positive":
        # Reuse if invoked; duplicate if a clone-quality body was added without reuse.
        verdict["duplicated"] = (verdict["clone_score"] >= CLONE_THRESHOLD) and not verdict["reused"]
        verdict["expected_for_gold"] = verdict["reused"] and not verdict["duplicated"]
        verdict["reason"] = (
            f"reused={verdict['reused']} clone_score={verdict['clone_score']} "
            f"duplicated={verdict['duplicated']}"
        )
    elif klass == "extension":
        verdict["duplicated"] = (verdict["clone_score"] >= CLONE_THRESHOLD) and not verdict[
            "modified_target_file"
        ]
        verdict["expected_for_gold"] = verdict["modified_target_file"] and not verdict["duplicated"]
        verdict["reason"] = (
            f"modified_target_file={verdict['modified_target_file']} "
            f"clone_score={verdict['clone_score']} duplicated={verdict['duplicated']}"
        )
    elif klass == "negative":
        verdict["expected_for_gold"] = not verdict["invoked_tempting"]
        verdict["reason"] = f"invoked_tempting={verdict['invoked_tempting']}"

    return verdict


def reuse_satisfied(verdict: dict, klass: str) -> bool:
    """Did the agent reuse correctly for a positive/extension task?"""
    if klass == "positive":
        return verdict["reused"] and not verdict["duplicated"]
    if klass == "extension":
        return verdict["modified_target_file"] and not verdict["duplicated"]
    return False
