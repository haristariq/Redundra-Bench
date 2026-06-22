import pytest

from redundra_utils.numeric import clamp, safe_div


def test_clamp_within_range():
    assert clamp(5, 0, 10) == 5


def test_clamp_above_and_below():
    assert clamp(15, 0, 10) == 10
    assert clamp(-3, 0, 10) == 0


def test_clamp_invalid_bounds():
    with pytest.raises(ValueError):
        clamp(1, 10, 0)


def test_safe_div_normal():
    assert safe_div(3, 4) == 0.75


def test_safe_div_zero_default():
    assert safe_div(1, 0) == 0.0


def test_safe_div_custom_default():
    assert safe_div(1, 0, default=-1) == -1
