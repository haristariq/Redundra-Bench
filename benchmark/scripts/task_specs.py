"""Declarative specifications for every Redundra-Bench task.

Each task is a feature/refactor request against the `redundra-utils` fixture.
The *spec* here holds the gold (correct) solution and the hidden tests; the
authoring driver (`author_tasks.py`) turns each spec into a task directory
containing `task.yaml`, `gold.patch`, and `test.patch` by diffing the post-state
against the pinned base commit.

Task classes
------------
- ``positive``  : the natural, correct solution reuses an existing symbol
                  (``reuse_target``). Re-implementing it inline is a clone.
- ``negative``  : a *tempting* existing symbol (``tempting_symbol``) looks
                  applicable but is semantically wrong; the correct solution
                  writes new code. ``reuse_target`` is ``None``. Forcing reuse
                  here is a *false block*.
- ``extension`` : the correct solution extends/parameterizes an existing symbol
                  (``reuse_target``) rather than duplicating it.

Field reference
---------------
- ``prompt``           : the issue text shown to the agent. Never names the
                         reuse target or hints "reuse".
- ``reuse_target``     : dotted path the gold solution imports/calls (or None).
- ``tempting_symbol``  : for negatives, the look-alike symbol to watch for.
- ``gold_files``       : {relpath: full file content} for the gold solution.
- ``test_files``       : {relpath: full file content} for the hidden tests.
- ``fail_to_pass``     : test node ids that fail on base, pass after the fix.
- ``pass_to_pass``     : existing test node ids that must remain green.
- ``rationale``        : why this is a genuine reuse opportunity / false-block.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Full replacement contents for files that EXTENSION tasks modify in place.
# --------------------------------------------------------------------------- #

_TEXT_PY_EXT01 = '''"""Text-processing helpers.

These are the kind of small, internal utilities a real project accumulates and
that an agent might re-implement from scratch instead of reusing.
"""

from __future__ import annotations

import re

__all__ = ["normalize_whitespace", "slugify", "truncate"]

_WHITESPACE_RE = re.compile(r"\\s+")
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace to a single space and strip the ends.

    >>> normalize_whitespace("  hello\\t world\\n")
    'hello world'
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def slugify(text: str) -> str:
    """Turn arbitrary text into a URL-safe slug.

    Lower-cases the input, collapses any run of non-alphanumeric characters to a
    single hyphen, and strips leading/trailing hyphens.

    >>> slugify("  Hello, World!  ")
    'hello-world'
    >>> slugify("Foo --- Bar")
    'foo-bar'
    """
    lowered = text.lower()
    hyphenated = _NON_SLUG_RE.sub("-", lowered)
    return hyphenated.strip("-")


def truncate(text: str, length: int, suffix: str = "\\u2026", whole_words: bool = False) -> str:
    """Truncate ``text`` to at most ``length`` characters.

    If truncation happens, ``suffix`` is appended and the total length never
    exceeds ``length``. If ``length`` is smaller than ``suffix`` the suffix
    itself is truncated.

    When ``whole_words`` is true and truncation happens mid-word, the result is
    trimmed back to the last word boundary so words are never cut in half.

    >>> truncate("hello world", 8)
    'hello w\\u2026'
    >>> truncate("hello world", 8, whole_words=True)
    'hello\\u2026'
    >>> truncate("hi", 8)
    'hi'
    """
    if length < 0:
        raise ValueError("length must be non-negative")
    if len(text) <= length:
        return text
    if length <= len(suffix):
        return suffix[:length]
    body = text[: length - len(suffix)]
    if whole_words and not text[length - len(suffix)].isspace():
        stripped = body.rstrip()
        if " " in stripped:
            body = stripped[: stripped.rfind(" ")].rstrip()
    return body + suffix
'''

_NUMERIC_PY_EXT02 = '''"""Numeric helpers."""

from __future__ import annotations

from typing import Optional, Union

__all__ = ["clamp", "safe_div"]

Number = Union[int, float]


def clamp(value: Number, lo: Number, hi: Number) -> Number:
    """Constrain ``value`` to the inclusive range ``[lo, hi]``.

    >>> clamp(15, 0, 10)
    10
    >>> clamp(-3, 0, 10)
    0
    >>> clamp(5, 0, 10)
    5
    """
    if lo > hi:
        raise ValueError("lo must not be greater than hi")
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def safe_div(
    numerator: Number,
    denominator: Number,
    default: Number = 0.0,
    ndigits: Optional[int] = None,
) -> Number:
    """Divide ``numerator`` by ``denominator``, returning ``default`` on zero.

    Avoids ``ZeroDivisionError`` for the common "rate / ratio" case. When
    ``ndigits`` is given, the result (including ``default``) is rounded to that
    many decimal places.

    >>> safe_div(3, 4)
    0.75
    >>> safe_div(1, 3, ndigits=2)
    0.33
    >>> safe_div(1, 0)
    0.0
    """
    if denominator == 0:
        result: Number = default
    else:
        result = numerator / denominator
    if ndigits is not None:
        return round(result, ndigits)
    return result
'''


TASKS: list[dict] = [
    # ----------------------------- POSITIVE ------------------------------ #
    {
        "id": "pos-01-url-path",
        "klass": "positive",
        "reuse_target": "redundra_utils.text.slugify",
        "tempting_symbol": None,
        "prompt": (
            "Add a helper that builds a clean URL path from a human page title.\n\n"
            "Create a new module `redundra_utils/webhelpers.py` exporting a function\n"
            "`make_url_path(title: str) -> str`. It must return the title as a URL\n"
            "path: a leading '/' followed by a lower-cased, hyphen-separated form of\n"
            "the title. Any run of non-alphanumeric characters becomes a single\n"
            "hyphen, and there must be no leading or trailing hyphen in the slug\n"
            "portion. Examples:\n"
            "  make_url_path('Hello, World!')  -> '/hello-world'\n"
            "  make_url_path('  Foo --- Bar ')  -> '/foo-bar'\n"
            "  make_url_path('!!!')             -> '/'\n"
        ),
        "gold_files": {
            "src/redundra_utils/webhelpers.py": (
                '"""Web helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from .text import slugify\n\n"
                '__all__ = ["make_url_path"]\n\n\n'
                "def make_url_path(title: str) -> str:\n"
                '    """Return ``title`` as a URL path (e.g. ``/hello-world``)."""\n'
                '    return "/" + slugify(title)\n'
            )
        },
        "test_files": {
            "tests/test_webhelpers.py": (
                "from redundra_utils.webhelpers import make_url_path\n\n\n"
                "def test_make_url_path_basic():\n"
                "    assert make_url_path('Hello, World!') == '/hello-world'\n\n\n"
                "def test_make_url_path_collapses_and_strips():\n"
                "    assert make_url_path('  Foo --- Bar ') == '/foo-bar'\n\n\n"
                "def test_make_url_path_empty_slug():\n"
                "    assert make_url_path('!!!') == '/'\n"
            )
        },
        "fail_to_pass": [
            "tests/test_webhelpers.py::test_make_url_path_basic",
            "tests/test_webhelpers.py::test_make_url_path_collapses_and_strips",
            "tests/test_webhelpers.py::test_make_url_path_empty_slug",
        ],
        "pass_to_pass": [
            "tests/test_text.py::test_slugify_basic",
            "tests/test_text.py::test_slugify_strips_edge_hyphens",
        ],
        "rationale": (
            "slugify already implements lower-case + non-alnum->hyphen + edge-strip. "
            "Re-implementing that regex inline is a textbook Type-3 clone."
        ),
    },
    {
        "id": "pos-02-batched-send",
        "klass": "positive",
        "reuse_target": "redundra_utils.collections_util.chunk",
        "tempting_symbol": None,
        "prompt": (
            "Add batched delivery for a notification queue.\n\n"
            "Create a new module `redundra_utils/notify.py` exporting\n"
            "`send_in_batches(items, size, sender) -> int`. It must split `items`\n"
            "into consecutive groups of at most `size` items (the last group may be\n"
            "smaller), call `sender(group)` once per group with a list, and return\n"
            "the number of groups sent. `size` must be a positive integer; raise\n"
            "ValueError otherwise. Order of items must be preserved.\n"
            "  send_in_batches([1,2,3,4,5], 2, sender) -> calls sender([1,2]),\n"
            "  sender([3,4]), sender([5]); returns 3.\n"
        ),
        "gold_files": {
            "src/redundra_utils/notify.py": (
                '"""Notification helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Any, Callable, Iterable\n\n"
                "from .collections_util import chunk\n\n"
                '__all__ = ["send_in_batches"]\n\n\n'
                "def send_in_batches(\n"
                "    items: Iterable[Any], size: int, sender: Callable[[list[Any]], Any]\n"
                ") -> int:\n"
                '    """Send ``items`` to ``sender`` in batches of ``size``; return batch count."""\n'
                "    count = 0\n"
                "    for batch in chunk(items, size):\n"
                "        sender(batch)\n"
                "        count += 1\n"
                "    return count\n"
            )
        },
        "test_files": {
            "tests/test_notify.py": (
                "import pytest\n\n"
                "from redundra_utils.notify import send_in_batches\n\n\n"
                "def test_send_in_batches_groups_and_counts():\n"
                "    seen = []\n"
                "    n = send_in_batches([1, 2, 3, 4, 5], 2, seen.append)\n"
                "    assert seen == [[1, 2], [3, 4], [5]]\n"
                "    assert n == 3\n\n\n"
                "def test_send_in_batches_exact_multiple():\n"
                "    seen = []\n"
                "    n = send_in_batches([1, 2, 3, 4], 2, seen.append)\n"
                "    assert seen == [[1, 2], [3, 4]]\n"
                "    assert n == 2\n\n\n"
                "def test_send_in_batches_invalid_size():\n"
                "    with pytest.raises(ValueError):\n"
                "        send_in_batches([1], 0, lambda b: None)\n"
            )
        },
        "fail_to_pass": [
            "tests/test_notify.py::test_send_in_batches_groups_and_counts",
            "tests/test_notify.py::test_send_in_batches_exact_multiple",
            "tests/test_notify.py::test_send_in_batches_invalid_size",
        ],
        "pass_to_pass": [
            "tests/test_collections_util.py::test_chunk_even_and_remainder",
            "tests/test_collections_util.py::test_chunk_invalid_size",
        ],
        "rationale": (
            "chunk already batches an iterable with the exact remainder + size-validation "
            "semantics required; an inline accumulator loop duplicates it."
        ),
    },
    {
        "id": "pos-03-comment-preview",
        "klass": "positive",
        "reuse_target": "redundra_utils.text.truncate",
        "tempting_symbol": None,
        "prompt": (
            "Add a one-line preview for long comment bodies.\n\n"
            "Create a new module `redundra_utils/display.py` exporting\n"
            "`comment_preview(body: str, width: int = 80) -> str`. The preview must\n"
            "be at most `width` characters. If the body is longer than `width`, it\n"
            "is shortened and a single-character ellipsis '\\u2026' is appended so the\n"
            "total length is exactly `width`. Bodies that already fit are returned\n"
            "unchanged.\n"
            "  comment_preview('hello world', 8) -> 'hello w\\u2026'\n"
            "  comment_preview('hi', 8)          -> 'hi'\n"
        ),
        "gold_files": {
            "src/redundra_utils/display.py": (
                '"""Display helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from .text import truncate\n\n"
                '__all__ = ["comment_preview"]\n\n\n'
                "def comment_preview(body: str, width: int = 80) -> str:\n"
                '    """Return a single-line preview of ``body`` at most ``width`` chars."""\n'
                "    return truncate(body, width)\n"
            )
        },
        "test_files": {
            "tests/test_display.py": (
                "from redundra_utils.display import comment_preview\n\n\n"
                "def test_comment_preview_truncates_with_ellipsis():\n"
                "    out = comment_preview('hello world', 8)\n"
                "    assert out == 'hello w\\u2026'\n"
                "    assert len(out) == 8\n\n\n"
                "def test_comment_preview_short_unchanged():\n"
                "    assert comment_preview('hi', 8) == 'hi'\n\n\n"
                "def test_comment_preview_default_width():\n"
                "    assert comment_preview('x' * 100)[-1] == '\\u2026'\n"
                "    assert len(comment_preview('x' * 100)) == 80\n"
            )
        },
        "fail_to_pass": [
            "tests/test_display.py::test_comment_preview_truncates_with_ellipsis",
            "tests/test_display.py::test_comment_preview_short_unchanged",
            "tests/test_display.py::test_comment_preview_default_width",
        ],
        "pass_to_pass": [
            "tests/test_text.py::test_truncate_appends_suffix_within_limit",
            "tests/test_text.py::test_truncate_shorter_than_limit_unchanged",
        ],
        "rationale": (
            "truncate already enforces the exact-width + ellipsis contract; re-deriving "
            "the slicing math inline is a clone."
        ),
    },
    {
        "id": "pos-04-load-settings",
        "klass": "positive",
        "reuse_target": "redundra_utils.collections_util.deep_merge",
        "tempting_symbol": None,
        "prompt": (
            "Add layered settings loading.\n\n"
            "Create a new module `redundra_utils/settings.py` exporting\n"
            "`load_settings(defaults: dict, user: dict) -> dict`. It returns a new\n"
            "settings dict where `user` values override `defaults`. When both sides\n"
            "hold a dict under the same key, the nested dicts must be merged\n"
            "recursively (not replaced). Inputs must not be mutated.\n"
            "  load_settings({'ui': {'theme': 'light', 'dpi': 96}},\n"
            "                {'ui': {'theme': 'dark'}})\n"
            "    -> {'ui': {'theme': 'dark', 'dpi': 96}}\n"
        ),
        "gold_files": {
            "src/redundra_utils/settings.py": (
                '"""Settings loading."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Any, Mapping\n\n"
                "from .collections_util import deep_merge\n\n"
                '__all__ = ["load_settings"]\n\n\n'
                "def load_settings(defaults: Mapping[str, Any], user: Mapping[str, Any]) -> dict:\n"
                '    """Return ``defaults`` with ``user`` layered on top (deep merge)."""\n'
                "    return deep_merge(defaults, user)\n"
            )
        },
        "test_files": {
            "tests/test_settings.py": (
                "from redundra_utils.settings import load_settings\n\n\n"
                "def test_load_settings_deep_merge():\n"
                "    out = load_settings(\n"
                "        {'ui': {'theme': 'light', 'dpi': 96}}, {'ui': {'theme': 'dark'}}\n"
                "    )\n"
                "    assert out == {'ui': {'theme': 'dark', 'dpi': 96}}\n\n\n"
                "def test_load_settings_does_not_mutate():\n"
                "    defaults = {'ui': {'dpi': 96}}\n"
                "    load_settings(defaults, {'ui': {'theme': 'dark'}})\n"
                "    assert defaults == {'ui': {'dpi': 96}}\n"
            )
        },
        "fail_to_pass": [
            "tests/test_settings.py::test_load_settings_deep_merge",
            "tests/test_settings.py::test_load_settings_does_not_mutate",
        ],
        "pass_to_pass": [
            "tests/test_collections_util.py::test_deep_merge_recursive",
            "tests/test_collections_util.py::test_deep_merge_does_not_mutate_inputs",
        ],
        "rationale": (
            "deep_merge already does non-mutating recursive merge; an inline recursive "
            "merge is a Type-3/4 clone."
        ),
    },
    {
        "id": "pos-05-completion-percentage",
        "klass": "positive",
        "reuse_target": "redundra_utils.numeric.safe_div",
        "tempting_symbol": None,
        "prompt": (
            "Add a progress percentage helper.\n\n"
            "Create a new module `redundra_utils/progress.py` exporting\n"
            "`completion_percentage(done: int, total: int) -> float`. It returns the\n"
            "percentage complete in the range 0..100. When `total` is 0 it must\n"
            "return 0.0 instead of raising.\n"
            "  completion_percentage(1, 4) -> 25.0\n"
            "  completion_percentage(0, 0) -> 0.0\n"
        ),
        "gold_files": {
            "src/redundra_utils/progress.py": (
                '"""Progress helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from .numeric import safe_div\n\n"
                '__all__ = ["completion_percentage"]\n\n\n'
                "def completion_percentage(done: int, total: int) -> float:\n"
                '    """Return percent complete in 0..100, or 0.0 when ``total`` is 0."""\n'
                "    return safe_div(done, total) * 100\n"
            )
        },
        "test_files": {
            "tests/test_progress.py": (
                "from redundra_utils.progress import completion_percentage\n\n\n"
                "def test_completion_percentage_basic():\n"
                "    assert completion_percentage(1, 4) == 25.0\n\n\n"
                "def test_completion_percentage_zero_total():\n"
                "    assert completion_percentage(0, 0) == 0.0\n"
            )
        },
        "fail_to_pass": [
            "tests/test_progress.py::test_completion_percentage_basic",
            "tests/test_progress.py::test_completion_percentage_zero_total",
        ],
        "pass_to_pass": [
            "tests/test_numeric.py::test_safe_div_normal",
            "tests/test_numeric.py::test_safe_div_zero_default",
        ],
        "rationale": (
            "safe_div already guards the divide-by-zero case the spec calls out; an "
            "inline `if total == 0` branch duplicates it."
        ),
    },
    {
        "id": "pos-06-set-brightness",
        "klass": "positive",
        "reuse_target": "redundra_utils.numeric.clamp",
        "tempting_symbol": None,
        "prompt": (
            "Add a brightness setter that guards its range.\n\n"
            "Create a new module `redundra_utils/device.py` exporting\n"
            "`set_brightness(level: int) -> int`. It must constrain `level` to the\n"
            "inclusive range 0..100 and return the constrained value (values below 0\n"
            "become 0, above 100 become 100).\n"
            "  set_brightness(150) -> 100\n"
            "  set_brightness(-5)  -> 0\n"
            "  set_brightness(50)  -> 50\n"
        ),
        "gold_files": {
            "src/redundra_utils/device.py": (
                '"""Device helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from .numeric import clamp\n\n"
                '__all__ = ["set_brightness"]\n\n\n'
                "def set_brightness(level: int) -> int:\n"
                '    """Return ``level`` constrained to the inclusive 0..100 range."""\n'
                "    return clamp(level, 0, 100)\n"
            )
        },
        "test_files": {
            "tests/test_device.py": (
                "from redundra_utils.device import set_brightness\n\n\n"
                "def test_set_brightness_clamps_high():\n"
                "    assert set_brightness(150) == 100\n\n\n"
                "def test_set_brightness_clamps_low():\n"
                "    assert set_brightness(-5) == 0\n\n\n"
                "def test_set_brightness_passthrough():\n"
                "    assert set_brightness(50) == 50\n"
            )
        },
        "fail_to_pass": [
            "tests/test_device.py::test_set_brightness_clamps_high",
            "tests/test_device.py::test_set_brightness_clamps_low",
            "tests/test_device.py::test_set_brightness_passthrough",
        ],
        "pass_to_pass": [
            "tests/test_numeric.py::test_clamp_within_range",
            "tests/test_numeric.py::test_clamp_above_and_below",
        ],
        "rationale": (
            "clamp is exactly range-constraining; `max(0, min(100, level))` inline is a clone."
        ),
    },
    {
        "id": "pos-07-fetch-with-retry",
        "klass": "positive",
        "reuse_target": "redundra_utils.retrying.retry",
        "tempting_symbol": None,
        "prompt": (
            "Add a retrying fetch wrapper.\n\n"
            "Create a new module `redundra_utils/fetcher.py` exporting\n"
            "`fetch_with_retry(fetcher, attempts: int = 3)`. It must call the\n"
            "zero-argument `fetcher` and return its result. If `fetcher` raises an\n"
            "Exception, it should be retried up to `attempts` total tries; if every\n"
            "attempt fails, the exception from the last attempt is re-raised.\n"
        ),
        "gold_files": {
            "src/redundra_utils/fetcher.py": (
                '"""Fetch helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Callable, TypeVar\n\n"
                "from .retrying import retry\n\n"
                '__all__ = ["fetch_with_retry"]\n\n'
                'T = TypeVar("T")\n\n\n'
                "def fetch_with_retry(fetcher: Callable[[], T], attempts: int = 3) -> T:\n"
                '    """Call ``fetcher`` with up to ``attempts`` retries on Exception."""\n'
                "    return retry(fetcher, attempts=attempts)\n"
            )
        },
        "test_files": {
            "tests/test_fetcher.py": (
                "import pytest\n\n"
                "from redundra_utils.fetcher import fetch_with_retry\n\n\n"
                "def test_fetch_with_retry_eventually_succeeds():\n"
                "    calls = []\n\n"
                "    def flaky():\n"
                "        calls.append(1)\n"
                "        if len(calls) < 2:\n"
                "            raise ValueError('nope')\n"
                "        return 'ok'\n\n"
                "    assert fetch_with_retry(flaky, attempts=3) == 'ok'\n"
                "    assert len(calls) == 2\n\n\n"
                "def test_fetch_with_retry_reraises_after_exhaustion():\n"
                "    def boom():\n"
                "        raise ValueError('always')\n\n"
                "    with pytest.raises(ValueError):\n"
                "        fetch_with_retry(boom, attempts=2)\n"
            )
        },
        "fail_to_pass": [
            "tests/test_fetcher.py::test_fetch_with_retry_eventually_succeeds",
            "tests/test_fetcher.py::test_fetch_with_retry_reraises_after_exhaustion",
        ],
        "pass_to_pass": [
            "tests/test_retrying.py::test_retry_eventually_succeeds",
            "tests/test_retrying.py::test_retry_exhausts_and_reraises",
        ],
        "rationale": (
            "retry already implements the attempt loop + last-exception re-raise; an inline "
            "for/try/except loop is a clone."
        ),
    },
    {
        "id": "pos-08-clean-display-name",
        "klass": "positive",
        "reuse_target": "redundra_utils.text.normalize_whitespace",
        "tempting_symbol": None,
        "prompt": (
            "Add display-name cleanup for user accounts.\n\n"
            "Create a new module `redundra_utils/accounts.py` exporting\n"
            "`clean_display_name(raw: str) -> str`. It must collapse every run of\n"
            "whitespace (spaces, tabs, newlines) to a single space and strip leading\n"
            "and trailing whitespace.\n"
            "  clean_display_name('  John\\t  Doe \\n') -> 'John Doe'\n"
        ),
        "gold_files": {
            "src/redundra_utils/accounts.py": (
                '"""Account helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "from .text import normalize_whitespace\n\n"
                '__all__ = ["clean_display_name"]\n\n\n'
                "def clean_display_name(raw: str) -> str:\n"
                '    """Return ``raw`` with whitespace collapsed and ends stripped."""\n'
                "    return normalize_whitespace(raw)\n"
            )
        },
        "test_files": {
            "tests/test_accounts.py": (
                "from redundra_utils.accounts import clean_display_name\n\n\n"
                "def test_clean_display_name_collapses():\n"
                "    assert clean_display_name('  John\\t  Doe \\n') == 'John Doe'\n\n\n"
                "def test_clean_display_name_already_clean():\n"
                "    assert clean_display_name('Jane Roe') == 'Jane Roe'\n"
            )
        },
        "fail_to_pass": [
            "tests/test_accounts.py::test_clean_display_name_collapses",
            "tests/test_accounts.py::test_clean_display_name_already_clean",
        ],
        "pass_to_pass": [
            "tests/test_text.py::test_normalize_whitespace_collapses_and_strips",
        ],
        "rationale": (
            "normalize_whitespace is exactly this; an inline `re.sub(r'\\s+', ' ', x).strip()` "
            "is a clone."
        ),
    },
    # ----------------------------- NEGATIVE ------------------------------ #
    {
        "id": "neg-01-clip-charset",
        "klass": "negative",
        "reuse_target": None,
        "tempting_symbol": "redundra_utils.numeric.clamp",
        "prompt": (
            "Add character-set filtering for sanitizing identifiers.\n\n"
            "Create a new module `redundra_utils/sanitize.py` exporting\n"
            "`clip_to_charset(text: str, allowed: str) -> str`. It must return a copy\n"
            "of `text` with every character that is NOT in `allowed` removed, "
            "preserving the order of the remaining characters.\n"
            "  clip_to_charset('a1b2c3', 'abc') -> 'abc'\n"
            "  clip_to_charset('hello!', 'helo') -> 'hello'\n"
        ),
        "gold_files": {
            "src/redundra_utils/sanitize.py": (
                '"""Sanitization helpers."""\n\n'
                "from __future__ import annotations\n\n"
                '__all__ = ["clip_to_charset"]\n\n\n'
                "def clip_to_charset(text: str, allowed: str) -> str:\n"
                '    """Return ``text`` with characters not in ``allowed`` removed."""\n'
                "    allowed_set = set(allowed)\n"
                '    return "".join(ch for ch in text if ch in allowed_set)\n'
            )
        },
        "test_files": {
            "tests/test_sanitize.py": (
                "from redundra_utils.sanitize import clip_to_charset\n\n\n"
                "def test_clip_to_charset_filters():\n"
                "    assert clip_to_charset('a1b2c3', 'abc') == 'abc'\n\n\n"
                "def test_clip_to_charset_preserves_order_and_dupes():\n"
                "    assert clip_to_charset('hello!', 'helo') == 'hello'\n\n\n"
                "def test_clip_to_charset_empty_allowed():\n"
                "    assert clip_to_charset('abc', '') == ''\n"
            )
        },
        "fail_to_pass": [
            "tests/test_sanitize.py::test_clip_to_charset_filters",
            "tests/test_sanitize.py::test_clip_to_charset_preserves_order_and_dupes",
            "tests/test_sanitize.py::test_clip_to_charset_empty_allowed",
        ],
        "pass_to_pass": [
            "tests/test_numeric.py::test_clamp_within_range",
        ],
        "rationale": (
            "'clip' looks like numeric.clamp, but clamp constrains a number to [lo,hi]; this "
            "filters characters. Forcing clamp here is a false block (and cannot pass tests)."
        ),
    },
    {
        "id": "neg-02-split-sections",
        "klass": "negative",
        "reuse_target": None,
        "tempting_symbol": "redundra_utils.collections_util.chunk",
        "prompt": (
            "Add document sectioning.\n\n"
            "Create a new module `redundra_utils/documents.py` exporting\n"
            "`split_sections(doc: str) -> list[str]`. A section is a run of text\n"
            "separated from the next by one or more blank lines (lines that are empty\n"
            "or whitespace-only). Return the list of sections with surrounding\n"
            "whitespace stripped from each, dropping any empty sections. Sections\n"
            "have variable length.\n"
            "  split_sections('a\\nb\\n\\nc') -> ['a\\nb', 'c']\n"
        ),
        "gold_files": {
            "src/redundra_utils/documents.py": (
                '"""Document helpers."""\n\n'
                "from __future__ import annotations\n\n"
                "import re\n\n"
                '__all__ = ["split_sections"]\n\n'
                '_BLANK_LINE_RE = re.compile(r"\\n\\s*\\n")\n\n\n'
                "def split_sections(doc: str) -> list[str]:\n"
                '    """Split ``doc`` into sections separated by blank lines."""\n'
                "    parts = _BLANK_LINE_RE.split(doc)\n"
                "    return [p.strip() for p in parts if p.strip()]\n"
            )
        },
        "test_files": {
            "tests/test_documents.py": (
                "from redundra_utils.documents import split_sections\n\n\n"
                "def test_split_sections_basic():\n"
                "    assert split_sections('a\\nb\\n\\nc') == ['a\\nb', 'c']\n\n\n"
                "def test_split_sections_multiple_blank_lines():\n"
                "    assert split_sections('one\\n\\n\\n\\ntwo') == ['one', 'two']\n\n\n"
                "def test_split_sections_drops_empty():\n"
                "    assert split_sections('\\n\\n  \\n\\nonly') == ['only']\n"
            )
        },
        "fail_to_pass": [
            "tests/test_documents.py::test_split_sections_basic",
            "tests/test_documents.py::test_split_sections_multiple_blank_lines",
            "tests/test_documents.py::test_split_sections_drops_empty",
        ],
        "pass_to_pass": [
            "tests/test_collections_util.py::test_chunk_even_and_remainder",
        ],
        "rationale": (
            "'split into groups' pattern-matches chunk, but chunk makes fixed-size groups; "
            "sections are variable and delimiter-driven. Forcing chunk is a false block."
        ),
    },
    {
        "id": "neg-03-shallow-override",
        "klass": "negative",
        "reuse_target": None,
        "tempting_symbol": "redundra_utils.collections_util.deep_merge",
        "prompt": (
            "Add a flat (shallow) config override.\n\n"
            "Create a new module `redundra_utils/config_flat.py` exporting\n"
            "`shallow_override(base: dict, override: dict) -> dict`. It must return a\n"
            "new dict where each top-level key present in `override` REPLACES the\n"
            "value in `base` wholesale. It must NOT merge nested dictionaries: if a\n"
            "key holds a dict on both sides, the override's dict replaces the base's\n"
            "dict entirely. Inputs must not be mutated.\n"
            "  shallow_override({'a': {'x': 1}}, {'a': {'y': 2}}) -> {'a': {'y': 2}}\n"
        ),
        "gold_files": {
            "src/redundra_utils/config_flat.py": (
                '"""Flat config override."""\n\n'
                "from __future__ import annotations\n\n"
                "from typing import Any, Mapping\n\n"
                '__all__ = ["shallow_override"]\n\n\n'
                "def shallow_override(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict:\n"
                '    """Return ``base`` with top-level keys replaced by ``override`` (no recursion)."""\n'
                "    return {**base, **override}\n"
            )
        },
        "test_files": {
            "tests/test_config_flat.py": (
                "from redundra_utils.config_flat import shallow_override\n\n\n"
                "def test_shallow_override_replaces_nested_wholesale():\n"
                "    # The key behavioural difference from a deep merge: nested dict is\n"
                "    # REPLACED, not merged.\n"
                "    assert shallow_override({'a': {'x': 1}}, {'a': {'y': 2}}) == {'a': {'y': 2}}\n\n\n"
                "def test_shallow_override_adds_and_overrides_top_level():\n"
                "    assert shallow_override({'a': 1, 'b': 2}, {'b': 3, 'c': 4}) == {\n"
                "        'a': 1, 'b': 3, 'c': 4\n"
                "    }\n\n\n"
                "def test_shallow_override_does_not_mutate():\n"
                "    base = {'a': {'x': 1}}\n"
                "    shallow_override(base, {'a': {'y': 2}})\n"
                "    assert base == {'a': {'x': 1}}\n"
            )
        },
        "fail_to_pass": [
            "tests/test_config_flat.py::test_shallow_override_replaces_nested_wholesale",
            "tests/test_config_flat.py::test_shallow_override_adds_and_overrides_top_level",
            "tests/test_config_flat.py::test_shallow_override_does_not_mutate",
        ],
        "pass_to_pass": [
            "tests/test_collections_util.py::test_deep_merge_recursive",
        ],
        "rationale": (
            "deep_merge is the obvious-looking reuse, but its recursive merge violates the "
            "no-merge-nested spec: deep_merge would yield {'a': {'x': 1, 'y': 2}} and fail "
            "the wholesale-replacement test. This is the canonical false-block trap."
        ),
    },
    # ---------------------------- EXTENSION ------------------------------ #
    {
        "id": "ext-01-truncate-whole-words",
        "klass": "extension",
        "reuse_target": "redundra_utils.text.truncate",
        "tempting_symbol": None,
        "prompt": (
            "Extend truncation so it can avoid cutting words in half.\n\n"
            "Add an optional keyword parameter `whole_words: bool = False` to the\n"
            "existing `redundra_utils.text.truncate` function. When `whole_words` is\n"
            "True and truncation would cut in the middle of a word, trim the result\n"
            "back to the previous word boundary before appending the suffix, so words\n"
            "are never split. Default (False) behaviour must be unchanged.\n"
            "  truncate('hello world foo', 10)                    -> 'hello wor\\u2026'\n"
            "  truncate('hello world foo', 10, whole_words=True)  -> 'hello\\u2026'\n"
        ),
        "gold_files": {"src/redundra_utils/text.py": _TEXT_PY_EXT01},
        "test_files": {
            "tests/test_text_words.py": (
                "from redundra_utils.text import truncate\n\n\n"
                "def test_truncate_whole_words_trims_to_boundary():\n"
                "    assert truncate('hello world foo', 10, whole_words=True) == 'hello\\u2026'\n\n\n"
                "def test_truncate_whole_words_default_still_cuts():\n"
                "    assert truncate('hello world foo', 10) == 'hello wor\\u2026'\n\n\n"
                "def test_truncate_whole_words_no_truncation_needed():\n"
                "    assert truncate('hi there', 20, whole_words=True) == 'hi there'\n"
            )
        },
        "fail_to_pass": [
            "tests/test_text_words.py::test_truncate_whole_words_trims_to_boundary",
            "tests/test_text_words.py::test_truncate_whole_words_default_still_cuts",
            "tests/test_text_words.py::test_truncate_whole_words_no_truncation_needed",
        ],
        "pass_to_pass": [
            "tests/test_text.py::test_truncate_appends_suffix_within_limit",
            "tests/test_text.py::test_truncate_shorter_than_limit_unchanged",
            "tests/test_text.py::test_truncate_tiny_limit",
            "tests/test_text.py::test_truncate_negative_limit_raises",
        ],
        "rationale": (
            "Correct answer extends truncate with a new param; duplicating a near-copy "
            "`truncate_words` alongside it is the anti-pattern this task detects."
        ),
    },
    {
        "id": "ext-02-safe-div-round",
        "klass": "extension",
        "reuse_target": "redundra_utils.numeric.safe_div",
        "tempting_symbol": None,
        "prompt": (
            "Extend safe division with optional rounding.\n\n"
            "Add an optional keyword parameter `ndigits: int | None = None` to the\n"
            "existing `redundra_utils.numeric.safe_div` function. When `ndigits` is\n"
            "not None, round the returned value (including the zero-denominator\n"
            "`default`) to that many decimal places using the built-in `round`.\n"
            "Default behaviour (ndigits=None) must be unchanged.\n"
            "  safe_div(1, 3, ndigits=2) -> 0.33\n"
            "  safe_div(3, 4)            -> 0.75\n"
        ),
        "gold_files": {"src/redundra_utils/numeric.py": _NUMERIC_PY_EXT02},
        "test_files": {
            "tests/test_numeric_round.py": (
                "from redundra_utils.numeric import safe_div\n\n\n"
                "def test_safe_div_rounds_when_ndigits_given():\n"
                "    assert safe_div(1, 3, ndigits=2) == 0.33\n\n\n"
                "def test_safe_div_rounds_default_on_zero():\n"
                "    assert safe_div(1, 0, default=1.0 / 3, ndigits=2) == 0.33\n\n\n"
                "def test_safe_div_unchanged_without_ndigits():\n"
                "    assert safe_div(3, 4) == 0.75\n"
            )
        },
        "fail_to_pass": [
            "tests/test_numeric_round.py::test_safe_div_rounds_when_ndigits_given",
            "tests/test_numeric_round.py::test_safe_div_rounds_default_on_zero",
            "tests/test_numeric_round.py::test_safe_div_unchanged_without_ndigits",
        ],
        "pass_to_pass": [
            "tests/test_numeric.py::test_safe_div_normal",
            "tests/test_numeric.py::test_safe_div_zero_default",
            "tests/test_numeric.py::test_safe_div_custom_default",
        ],
        "rationale": (
            "Correct answer adds a param to safe_div; a parallel `safe_div_rounded` clone is "
            "the anti-pattern."
        ),
    },
]


def by_id() -> dict[str, dict]:
    return {t["id"]: t for t in TASKS}
