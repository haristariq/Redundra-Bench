import pytest

from redundra_utils.retrying import retry


def test_retry_succeeds_first_try():
    assert retry(lambda: "ok") == "ok"


def test_retry_eventually_succeeds():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("not yet")
        return "ok"

    assert retry(flaky, attempts=3) == "ok"
    assert len(calls) == 2


def test_retry_exhausts_and_reraises():
    def always_fail():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        retry(always_fail, attempts=2)


def test_retry_unlisted_exception_propagates_immediately():
    calls = []

    def boom():
        calls.append(1)
        raise KeyError("unexpected")

    with pytest.raises(KeyError):
        retry(boom, attempts=3, exceptions=(ValueError,))
    assert len(calls) == 1


def test_retry_invalid_attempts():
    with pytest.raises(ValueError):
        retry(lambda: 1, attempts=0)
