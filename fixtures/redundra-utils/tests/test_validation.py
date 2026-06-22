from redundra_utils.validation import is_valid_email


def test_valid_emails():
    assert is_valid_email("a@b.com")
    assert is_valid_email("first.last@example.co.uk")


def test_invalid_emails():
    assert not is_valid_email("nope")
    assert not is_valid_email("a@b")
    assert not is_valid_email("a b@c.com")
    assert not is_valid_email("two@@b.com")
