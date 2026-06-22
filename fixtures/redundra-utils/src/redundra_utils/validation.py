"""Validation helpers."""

from __future__ import annotations

import re

__all__ = ["is_valid_email"]

# Deliberately pragmatic, not RFC-complete: one @, a dotted domain, no spaces.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str) -> bool:
    """Return ``True`` if ``value`` looks like a valid email address.

    >>> is_valid_email("a@b.com")
    True
    >>> is_valid_email("nope")
    False
    """
    return bool(_EMAIL_RE.match(value))
