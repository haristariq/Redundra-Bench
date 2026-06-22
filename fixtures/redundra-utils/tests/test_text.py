from redundra_utils.text import normalize_whitespace, slugify, truncate


def test_normalize_whitespace_collapses_and_strips():
    assert normalize_whitespace("  hello\t world\n") == "hello world"
    assert normalize_whitespace("a\n\n\nb") == "a b"
    assert normalize_whitespace("   ") == ""


def test_slugify_basic():
    assert slugify("  Hello, World!  ") == "hello-world"
    assert slugify("Foo --- Bar") == "foo-bar"
    assert slugify("already-a-slug") == "already-a-slug"


def test_slugify_strips_edge_hyphens():
    assert slugify("!!!edge!!!") == "edge"


def test_truncate_shorter_than_limit_unchanged():
    assert truncate("hi", 8) == "hi"


def test_truncate_appends_suffix_within_limit():
    out = truncate("hello world", 8)
    assert out == "hello w…"
    assert len(out) == 8


def test_truncate_tiny_limit():
    assert truncate("hello", 1) == "…"


def test_truncate_negative_limit_raises():
    import pytest

    with pytest.raises(ValueError):
        truncate("x", -1)
