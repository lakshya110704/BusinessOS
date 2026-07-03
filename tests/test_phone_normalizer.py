"""Unit tests for the Indian phone normalizer (LAK-11)."""
import pytest

from app.utils.phone import normalize_phone


@pytest.mark.parametrize(
    "raw",
    [
        "+919876543210",       # already normalized
        "919876543210",        # country code, no +
        "09876543210",         # trunk prefix
        "9876543210",          # bare 10-digit
        "+91 98765-43210",     # spaces + dashes
        "(+91) 98765 43210",   # parentheses
    ],
)
def test_all_formats_normalize(raw):
    assert normalize_phone(raw) == "+919876543210"


@pytest.mark.parametrize(
    "bad",
    [
        "",                 # empty
        "   ",              # whitespace only
        "12345",            # too short
        "123456789012345",  # too long
        "5876543210",       # invalid leading digit (5)
        "abcd",             # no digits
    ],
)
def test_invalid_raises_valueerror(bad):
    with pytest.raises(ValueError):
        normalize_phone(bad)
