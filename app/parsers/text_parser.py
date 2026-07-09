"""Text message parser — extract the body and normalize encoding.

Normalizes to Unicode NFC so Hindi/Hinglish combining characters are stored and
compared consistently (the same visual string can otherwise have two byte forms).
"""
from __future__ import annotations

import unicodedata


def parse(message: dict) -> str:
    body = (message.get("text") or {}).get("body", "") or ""
    return unicodedata.normalize("NFC", body).strip()
