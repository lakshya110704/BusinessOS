"""Simulate an inbound WhatsApp webhook POST against a locally running server.

Examples:
    # a vendor's order (from = the vendor's number)
    python scripts/test_webhook_local.py --type text --from 919888800002 --message "Ramesh bhai 50 piece bhejo kal tak"
    # the owner tapping "Confirm" (from = the owner's/business number)
    python scripts/test_webhook_local.py --type interactive --from 919318340858 --message 1
    python scripts/test_webhook_local.py --unsigned          # expect 403

--phone-number-id must match the onboarded business's whatsapp_phone_number_id so the
router can find it (defaults to WHATSAPP_PHONE_NUMBER_ID from .env).

Signs the payload with WHATSAPP_APP_SECRET (the same secret the server verifies
against), so a signed post returns 200 and an --unsigned post returns 403.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()


def build_payload(mtype: str, message: str, from_number: str, phone_number_id: str) -> dict:
    msg: dict = {
        "from": from_number,
        "id": f"wamid.TEST{uuid.uuid4().hex}",
        "timestamp": "1700000000",
        "type": mtype,
    }
    if mtype == "text":
        msg["text"] = {"body": message}
    elif mtype == "interactive":
        msg["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": message, "title": message},
        }
    elif mtype in ("audio", "image", "document"):
        msg[mtype] = {"id": f"MEDIA{uuid.uuid4().hex}", "mime_type": "application/octet-stream"}

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "919999999999",
                                "phone_number_id": phone_number_id,
                            },
                            "messages": [msg],
                        },
                    }
                ],
            }
        ],
    }


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/webhook")
    ap.add_argument("--type", default="text", choices=["text", "interactive", "audio", "image", "document"])
    ap.add_argument("--message", default="bhai 50 piece bhejo kal tak")
    ap.add_argument("--from", dest="from_number", default="919876543210", help="sender's WhatsApp number (no +)")
    ap.add_argument("--phone-number-id", default=os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "PHONE_NUMBER_ID"),
                    help="business's Meta phone_number_id (must match the onboarded business)")
    ap.add_argument("--unsigned", action="store_true", help="omit signature (should 403)")
    args = ap.parse_args()

    body = json.dumps(build_payload(args.type, args.message, args.from_number, args.phone_number_id)).encode()
    headers = {"Content-Type": "application/json"}
    if not args.unsigned:
        headers["X-Hub-Signature-256"] = sign(body, os.environ.get("WHATSAPP_APP_SECRET", ""))

    resp = httpx.post(args.url, content=body, headers=headers, timeout=10.0)
    print(f"status={resp.status_code} body={resp.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
