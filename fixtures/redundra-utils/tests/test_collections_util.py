import pytest

from redundra_utils.collections_util import chunk, deep_merge


def test_chunk_even_and_remainder():
    assert list(chunk([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_chunk_exact_multiple():
    assert list(chunk([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]


def test_chunk_generator_input():
    assert list(chunk((i for i in range(3)), 5)) == [[0, 1, 2]]


def test_chunk_invalid_size():
    with pytest.raises(ValueError):
        list(chunk([1], 0))


def test_deep_merge_recursive():
    assert deep_merge({"a": {"x": 1}}, {"a": {"y": 2}}) == {"a": {"x": 1, "y": 2}}


def test_deep_merge_override_scalar():
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    deep_merge(base, {"a": {"y": 2}})
    assert base == {"a": {"x": 1}}
