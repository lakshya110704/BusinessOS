"""Repository for the `messages` table — the stored record of every message.

This is the base of the memory graph (§1.5): raw text / voice transcript, plus the
AI's intent + entities, kept per business+contact. Access is server-side only
(service key); RLS must enforce per-business isolation before any client access.
"""
from __future__ import annotations

from typing import Optional

from app.db.supabase_client import get_supabase

TABLE = "messages"


async def create(message: dict) -> dict:
    """Insert a message row. Idempotent on whatsapp_message_id (Meta can resend)."""
    client = await get_supabase()
    try:
        return (await client.table(TABLE).insert(message).execute()).data[0]
    except Exception:
        wamid = message.get("whatsapp_message_id")
        if wamid:
            existing = (
                await client.table(TABLE).select("*").eq("whatsapp_message_id", wamid).limit(1).execute()
            ).data
            if existing:
                return existing[0]
        raise


async def update_analysis(
    message_id: str,
    intent: Optional[str] = None,
    entities: Optional[dict] = None,
    confidence: Optional[float] = None,
    processed_content: Optional[str] = None,
) -> None:
    """Attach the AI results to an already-stored message."""
    patch = {}
    if intent is not None:
        patch["intent"] = intent
    if entities is not None:
        patch["entities"] = entities
    if confidence is not None:
        patch["confidence_score"] = confidence
    if processed_content is not None:
        patch["processed_content"] = processed_content
    if not patch:
        return
    client = await get_supabase()
    await client.table(TABLE).update(patch).eq("id", message_id).execute()


async def get_recent(business_id: str, contact_id: Optional[str] = None, limit: int = 5) -> list:
    """Most recent messages for a business (optionally one contact) — for context (LAK-15)."""
    client = await get_supabase()
    query = client.table(TABLE).select("*").eq("business_id", business_id)
    if contact_id:
        query = query.eq("contact_id", contact_id)
    return (await query.order("created_at", desc=True).limit(limit).execute()).data
