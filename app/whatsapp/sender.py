"""High-level WhatsApp send helpers.

Each helper normalizes the recipient number first (Critical Rule #6), builds the
Cloud API payload for its message type, and delegates the HTTP to client.py.
Meta wants the recipient in international format WITHOUT the leading '+'.
"""
from __future__ import annotations

from typing import Optional

from app.utils.phone import normalize_phone
from app.whatsapp.client import send_message


def _wa_number(to: str) -> str:
    # normalize_phone → "+91XXXXXXXXXX"; Meta wants "91XXXXXXXXXX".
    return normalize_phone(to).lstrip("+")


async def send_text(to: str, text: str) -> dict:
    """Free-form session message (only allowed within 24h of the user's last message)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": _wa_number(to),
        "type": "text",
        "text": {"body": text},
    }
    return await send_message(payload)


async def send_interactive(to: str, body: str, buttons: list[tuple[str, str]]) -> dict:
    """Interactive reply-button message — used for the 1/2/3 confirmation.

    buttons: list of (id, title). Max 3; title max 20 chars (WhatsApp limits).
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": _wa_number(to),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": str(bid), "title": title}}
                    for bid, title in buttons[:3]
                ]
            },
        },
    }
    return await send_message(payload)


async def send_template(
    to: str,
    template_name: str,
    params: Optional[list] = None,
    language: str = "en",
) -> dict:
    """Pre-approved template message — required to (re)open a conversation after 24h."""
    components = []
    if params:
        components = [
            {"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in params]}
        ]
    payload = {
        "messaging_product": "whatsapp",
        "to": _wa_number(to),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components,
        },
    }
    return await send_message(payload)
