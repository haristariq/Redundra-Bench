"""Numeric helpers."""

from __future__ import annotations

from typing import Union

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


def safe_div(numerator: Number, denominator: Number, default: Number = 0.0) -> Number:
    """Divide ``numerator`` by ``denominator``, returning ``default`` on zero.

    Avoids ``ZeroDivisionError`` for the common "rate / ratio" case.

    >>> safe_div(3, 4)
    0.75
    >>> safe_div(1, 0)
    0.0
    >>> safe_div(1, 0, default=-1)
    -1
    """
    if denominator == 0:
        return default
    return numerator / denominator
