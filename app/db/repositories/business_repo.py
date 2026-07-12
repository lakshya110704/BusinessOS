"""Repository for the `businesses` table."""
from __future__ import annotations

from typing import Optional

from app.db.supabase_client import get_supabase

TABLE = "businesses"


async def get_by_phone(phone_number: str) -> Optional[dict]:
    """Look up a business by its owner's WhatsApp number (normalized, e.g. +91XXXXXXXXXX)."""
    client = await get_supabase()
    res = await client.table(TABLE).select("*").eq("phone_number", phone_number).limit(1).execute()
    return res.data[0] if res.data else None


async def get_by_phone_number_id(phone_number_id: str) -> Optional[dict]:
    """Look up a business by the Meta phone_number_id its WhatsApp number maps to.

    Incoming webhooks carry this in metadata.phone_number_id — it's how we know
    which business (and therefore which owner) a message was sent to.
    """
    client = await get_supabase()
    res = (
        await client.table(TABLE)
        .select("*")
        .eq("whatsapp_phone_number_id", phone_number_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def get_by_id(business_id: str) -> Optional[dict]:
    client = await get_supabase()
    res = await client.table(TABLE).select("*").eq("id", business_id).limit(1).execute()
    return res.data[0] if res.data else None


async def get_active() -> list:
    """All active businesses (for scheduled jobs)."""
    client = await get_supabase()
    return (await client.table(TABLE).select("*").eq("is_active", True).execute()).data
