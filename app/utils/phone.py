"""Phone number normalization for Indian numbers.

Critical rule: normalize ALL formats to +91XXXXXXXXXX.
Accepts: +91XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX, XXXXXXXXXX (and with
spaces / dashes / parentheses mixed in).

Raises ValueError on anything that isn't a valid 10-digit Indian mobile —
callers (webhook receiver, sender, onboard script) should never persist or
send to an unvalidated number.
"""
from __future__ import annotations

import re


def normalize_phone(raw: str) -> str:
    """Normalize an Indian phone number to +91XXXXXXXXXX.

    Raises ValueError if the input is not a valid 10-digit Indian mobile.
    """
    if not raw or not raw.strip():
        raise ValueError("phone number is empty")

    digits = re.sub(r"\D", "", raw)

    # Strip country code / trunk prefix down to the core 10 digits.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 10:
        raise ValueError(
            f"invalid phone number {raw!r}: expected a 10-digit body, got {len(digits)} digits"
        )
    # Indian mobile numbers start 6-9.
    if digits[0] not in "6789":
        raise ValueError(
            f"invalid Indian mobile number {raw!r}: must start with 6-9"
        )

    return f"+91{digits}"
