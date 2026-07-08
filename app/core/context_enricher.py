"""Context enricher — assembles relationship context before classification.

enrich() pulls the last few messages (Redis cache → DB fallback), the contact's
record (role, reliability, terms), and their recent orders, so the classifier and
extractor can reason with history instead of treating every message cold. A new /
unknown contact returns sensible empty defaults.

All reads here are read-only and idempotent.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.db.repositories import contact_repo, message_repo, order_repo
from app.queue.redis_client import get_context, set_context
from app.utils.logger import get_logger

logger = get_logger("enricher")

HISTORY_LIMIT = 5
HISTORY_CACHE_TTL = 300  # 5 min — history is a hint, minor staleness is fine


class EnrichedContext(BaseModel):
    is_known: bool = False
    contact: dict = Field(default_factory=dict)
    history: list = Field(default_factory=list)
    recent_orders: list = Field(default_factory=list)


async def _history(business_id: str, contact_id: str) -> list:
    # Redis cache first, fall back to DB and repopulate.
    cache_key = f"contact:{contact_id}"
    cached = await get_context(cache_key)
    if cached and "history" in cached:
        return cached["history"]
    messages = await message_repo.get_recent(business_id, contact_id, HISTORY_LIMIT)
    history = [
        (m.get("raw_content") or m.get("voice_transcript") or "").strip()
        for m in messages
        if (m.get("raw_content") or m.get("voice_transcript"))
    ]
    await set_context(cache_key, {"history": history}, ttl=HISTORY_CACHE_TTL)
    return history


async def enrich(business_id: str, contact_id: Optional[str]) -> EnrichedContext:
    if not contact_id:
        return EnrichedContext(is_known=False)

    contact = await contact_repo.get_by_id(contact_id)
    if not contact:
        return EnrichedContext(is_known=False)

    history = await _history(business_id, contact_id)
    orders = await order_repo.get_recent_for_contact(business_id, contact_id, days=30)

    context = EnrichedContext(
        is_known=True,
        contact={
            "name": contact.get("name"),
            "role": contact.get("role"),
            "reliability_score": contact.get("reliability_score"),
            "typical_order_size": contact.get("typical_order_size"),
            "payment_terms_days": contact.get("payment_terms_days"),
        },
        history=history,
        recent_orders=[
            {"order_number": o.get("order_number"), "total_amount": o.get("total_amount"), "created_at": o.get("created_at")}
            for o in orders
        ],
    )
    logger.info(
        "enriched",
        extra={"is_known": True, "history": len(history), "recent_orders": len(orders)},
    )
    return context
