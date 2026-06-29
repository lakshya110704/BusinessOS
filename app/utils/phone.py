"""Phone number normalization for Indian numbers.

Critical rule: normalize ALL formats to +91XXXXXXXXXX.
Accepts: +91XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX, XXXXXXXXXX (and with
spaces / dashes / parentheses mixed in).
"""
from __future__ import annotations

import re


def normalize_indian_phone(raw: str) -> str | None:
    """Return the number as +91XXXXXXXXXX, or None if it isn't a valid 10-digit Indian mobile."""
    if not raw:
        return None

    digits = re.sub(r"\D", "", raw)

    # Strip country code / trunk prefix down to the core 10 digits.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 10:
        return None
    # Indian mobile numbers start 6-9.
    if digits[0] not in "6789":
        return None

    return f"+91{digits}"
