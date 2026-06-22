"""Collection helpers."""

from __future__ import annotations

from typing import Any, Iterable, Iterator, Mapping

__all__ = ["chunk", "deep_merge"]


def chunk(iterable: Iterable[Any], size: int) -> Iterator[list[Any]]:
    """Yield successive lists of up to ``size`` items from ``iterable``.

    The final chunk may be shorter than ``size``. Works on any iterable, not
    just sequences.

    >>> list(chunk([1, 2, 3, 4, 5], 2))
    [[1, 2], [3, 4], [5]]
    """
    if size <= 0:
        raise ValueError("size must be a positive integer")
    batch: list[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base``, returning a new dict.

    When both sides hold a mapping under the same key, the mappings are merged
    recursively. Otherwise the value from ``override`` wins. Neither input is
    mutated.

    >>> deep_merge({"a": {"x": 1}}, {"a": {"y": 2}})
    {'a': {'x': 1, 'y': 2}}
    """
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = value
    return result
