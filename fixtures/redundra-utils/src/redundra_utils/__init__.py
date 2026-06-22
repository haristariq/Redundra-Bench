"""redundra_utils - a small, utility-rich library used as a benchmark fixture.

The package intentionally bundles general-purpose helpers (text, collections,
numeric, retry, validation) so that feature tasks can be authored whose natural
solution is to *reuse* one of these helpers rather than re-implement it.
"""

from __future__ import annotations

from .collections_util import chunk, deep_merge
from .numeric import clamp, safe_div
from .retrying import retry
from .text import normalize_whitespace, slugify, truncate
from .validation import is_valid_email

__version__ = "0.1.0"

__all__ = [
    "chunk",
    "deep_merge",
    "clamp",
    "safe_div",
    "retry",
    "normalize_whitespace",
    "slugify",
    "truncate",
    "is_valid_email",
]
