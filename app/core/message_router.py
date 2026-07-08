"""Message router — the glue the consumer calls for each queued message.

Takes a raw WhatsApp message dict (as the webhook enqueued it), runs the
understanding pipeline (classify → extract → generate), and returns a
ProposedAction. Sending the confirmation to the owner (LAK-18, via the sender)
plugs in where noted once Meta is live.

Only text messages run the pipeline today:
- voice/image/document → no parser yet (LAK-17+), skipped for now
- interactive/button    → owner replies to confirmations (LAK-19), handled separately
"""
from __future__ import annotations

from typing import Optional

from app.core.action_generator import ProposedAction, generate
from app.core.confirm_engine import handle_reply, send_confirmation
from app.core.entity_extractor import extract
from app.core.intent_classifier import classify
from app.db.repositories import business_repo
from app.parsers import voice_parser
from app.utils.logger import get_logger
from app.utils.phone import normalize_phone

logger = get_logger("router")


def _extract_reply_id(message: dict) -> Optional[str]:
    if message.get("type") == "interactive":
        button_reply = (message.get("interactive") or {}).get("button_reply") or {}
        return button_reply.get("id")
    if message.get("type") == "button":
        button = message.get("button") or {}
        return button.get("payload") or button.get("text")
    return None


async def _handle_owner_reply(message: dict, sender_raw: str) -> None:
    reply_id = _extract_reply_id(message)
    try:
        phone = normalize_phone(sender_raw)
    except ValueError:
        phone = None

    business = await business_repo.get_by_phone(phone) if phone else None
    if not business:
        logger.info("reply_from_unknown_sender")
        return

    outcome = await handle_reply(business["id"], phone, reply_id or "")
    logger.info("owner_reply_routed", extra={"outcome": outcome})


async def route(message: dict, phone_number_id: Optional[str] = None) -> Optional[ProposedAction]:
    mtype = message.get("type")
    sender_raw = message.get("from", "")

    # Owner tapped a confirmation button (1/2/3).
    if mtype in ("interactive", "button"):
        await _handle_owner_reply(message, sender_raw)
        return None

    # Get the message text — directly for text, via transcription for voice.
    if mtype == "text":
        text = (message.get("text") or {}).get("body", "")
    elif mtype == "audio":
        media_id = (message.get("audio") or {}).get("id")
        if not media_id:
            logger.info("audio_without_media_id")
            return None
        try:
            text = await voice_parser.parse(media_id)
        except Exception:
            logger.exception("voice_parse_failed", extra={"media_id": media_id})
            return None
    else:
        logger.info("skipped_unsupported_type", extra={"type": mtype})
        return None

    if not text or not text.strip():
        return None

    try:
        contact_phone = normalize_phone(sender_raw)
    except ValueError:
        contact_phone = None

    # LAK-15 will enrich contact + history here; empty context for now.
    intent = await classify(text)
    entities = await extract(text, intent=intent.intent)
    action = generate(intent, entities, context={"contact": {"phone": contact_phone}})
    logger.info(
        "routed",
        extra={"intent": intent.intent, "action": action.action_type, "escalate": action.escalate},
    )

    # Uncertain / no automated action → don't send a confirmation (LAK-15+ will
    # notify the owner to handle manually).
    if action.escalate or action.action_type == "escalate_to_owner":
        logger.info("escalated", extra={"intent": intent.intent})
        return action

    # Find which business this was sent to, then confirm with its owner.
    business = await business_repo.get_by_phone_number_id(phone_number_id) if phone_number_id else None
    if not business:
        logger.info("no_business_for_phone_number_id", extra={"phone_number_id": phone_number_id})
        return action

    await send_confirmation(business, action)
    return action
