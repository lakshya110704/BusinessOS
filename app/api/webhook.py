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

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import ValidationError

from app.config import settings
from app.queue.producer import push
from app.queue.redis_client import get_redis
from app.utils.logger import get_logger
from app.whatsapp.message_types import WebhookPayload

router = APIRouter()
logger = get_logger("webhook")

QUEUE_NAME = "incoming_messages"
DEDUP_TTL_SECONDS = 86400  # 24h — Meta won't resend a message id beyond this window


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
    x_hub_signature_256: Optional[str] = Header(default=None),
):
    # 1) Signature check FIRST — before any parsing (Critical rule).
    body = await request.body()
    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 2) Parse into typed models. The signature already proved this is really
    #    Meta, so an unparsable/unexpected payload is our modelling gap, not an
    #    attack — log it and still 200, or Meta will retry the same bad payload
    #    forever.
    try:
        payload = WebhookPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        logger.error("unparsable_payload", extra={"error": type(exc).__name__})
        return {"status": "ok", "enqueued": 0}

    # 3) Extract → dedup → enqueue. No DB and no AI work here: keep it <1s.
    #    We carry phone_number_id (which business the message was sent to) so the
    #    consumer can route the confirmation to the right owner.
    redis = get_redis()
    enqueued = 0
    for entry in payload.entry:
        for change in entry.changes:
            phone_number_id = change.value.metadata.phone_number_id if change.value.metadata else None
            for message in (change.value.messages or []):
                # Dedup via Redis SET NX: first writer wins, duplicates are skipped.
                is_new = await redis.set(f"dedup:{message.id}", "1", nx=True, ex=DEDUP_TTL_SECONDS)
                if not is_new:
                    logger.info("duplicate_skipped", extra={"wa_message_id": message.id})
                    continue
                item = {"message": message.model_dump(by_alias=True), "phone_number_id": phone_number_id}
                try:
                    # We log ids/types only — never the message body (Critical rule #1).
                    await push(QUEUE_NAME, item)
                except Exception:
                    # Release the dedup claim so Meta's retry can reprocess, then fail.
                    await redis.delete(f"dedup:{message.id}")
                    logger.error("enqueue_failed", extra={"wa_message_id": message.id})
                    raise
                logger.info("enqueued", extra={"wa_message_id": message.id, "type": message.type})
                enqueued += 1

    # 4) Ack immediately — Meta retries aggressively otherwise.
    return {"status": "ok", "enqueued": enqueued}
