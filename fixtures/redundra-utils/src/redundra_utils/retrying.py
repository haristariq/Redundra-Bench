"""Retry helper."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

__all__ = ["retry"]

T = TypeVar("T")


def retry(
    func: Callable[[], T],
    attempts: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    delay: float = 0.0,
) -> T:
    """Call ``func`` up to ``attempts`` times, retrying on ``exceptions``.

    Returns the first successful result. If every attempt raises one of
    ``exceptions``, the exception from the final attempt is re-raised. An
    exception not listed in ``exceptions`` propagates immediately.

    >>> calls = []
    >>> def flaky():
    ...     calls.append(1)
    ...     if len(calls) < 2:
    ...         raise ValueError("not yet")
    ...     return "ok"
    >>> retry(flaky, attempts=3)
    'ok'
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return func()
        except exceptions as exc:  # noqa: PERF203 - clarity over micro-perf
            last_exc = exc
            if attempt + 1 < attempts and delay:
                time.sleep(delay)
    assert last_exc is not None  # pragma: no cover - attempts >= 1 guarantees a try
    raise last_exc
