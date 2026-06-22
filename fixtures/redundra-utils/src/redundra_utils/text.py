"""Text-processing helpers.

These are the kind of small, internal utilities a real project accumulates and
that an agent might re-implement from scratch instead of reusing.
"""

from __future__ import annotations

import re

__all__ = ["normalize_whitespace", "slugify", "truncate"]

_WHITESPACE_RE = re.compile(r"\s+")
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


def truncate(text: str, length: int, suffix: str = "…") -> str:
    """Truncate ``text`` to at most ``length`` characters.

    If truncation happens, ``suffix`` is appended and the total length never
    exceeds ``length``. If ``length`` is smaller than ``suffix`` the suffix
    itself is truncated.

    >>> truncate("hello world", 8)
    'hello w…'
    >>> truncate("hi", 8)
    'hi'
    """
    if length < 0:
        raise ValueError("length must be non-negative")
    if len(text) <= length:
        return text
    if length <= len(suffix):
        return suffix[:length]
    return text[: length - len(suffix)] + suffix
