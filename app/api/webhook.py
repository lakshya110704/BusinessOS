"""Meta WhatsApp Cloud API webhook.

Two endpoints:
- GET  /webhook  → one-time verification handshake with Meta.
- POST /webhook  → receives every incoming message. MUST return 200 in <1s,
                   so we verify the signature, then hand off to async processing.

Critical rules honored here:
- Always validate the X-Hub-Signature-256 signature (anyone can POST here).
- Respond fast; do not block on AI work inside the request.
- Never log raw message content.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response

from app.config import settings

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    """Meta calls this once to verify the endpoint. Echo back the challenge."""
    if (
        hub_mode == "subscribe"
        and settings.WHATSAPP_VERIFY_TOKEN
        and hmac.compare_digest(hub_verify_token, settings.WHATSAPP_VERIFY_TOKEN)
    ):
        # hub.challenge must be returned as a raw integer/string body.
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


def _verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Validate the SHA-256 HMAC Meta sends in X-Hub-Signature-256."""
    if not signature_header or not settings.WHATSAPP_APP_SECRET:
        return False
    expected = (
        "sha256="
        + hmac.new(
            settings.WHATSAPP_APP_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)


@router.post("/webhook")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None),
):
    body = await request.body()

    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()

    # TODO(Day 2): push to Redis queue and process async.
    # background_tasks.enqueue(...)
    _ = payload  # placeholder until the queue consumer lands

    # Return 200 immediately — Meta retries aggressively otherwise.
    return {"status": "ok"}
