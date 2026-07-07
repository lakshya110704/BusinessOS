"""Repository for the `pending_confirmations` table.

All DB access for pending confirmations goes through here, so the rest of the app
never builds raw queries. Uses the async Supabase client.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db.supabase_client import get_supabase

TABLE = "pending_confirmations"


async def create(
    business_id: str,
    confirmation_type: str,
    proposed_action: dict,
    message_id: Optional[str] = None,
    expires_in_hours: int = 24,
) -> str:
    """Insert a pending confirmation (status=pending, expires in 24h). Returns its id."""
    client = await get_supabase()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()
    row = {
        "business_id": business_id,
        "message_id": message_id,
        "confirmation_type": confirmation_type,
        "proposed_action": proposed_action,
        "whatsapp_confirm_sent": True,
        "status": "pending",
        "expires_at": expires_at,
    }
    res = await client.table(TABLE).insert(row).execute()
    return res.data[0]["id"]


async def get_by_id(confirmation_id: str) -> Optional[dict]:
    client = await get_supabase()
    res = await client.table(TABLE).select("*").eq("id", confirmation_id).limit(1).execute()
    return res.data[0] if res.data else None


async def expire_old() -> int:
    """Mark still-pending confirmations past their expiry as expired. Returns count."""
    client = await get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    res = (
        await client.table(TABLE)
        .update({"status": "expired"})
        .eq("status", "pending")
        .lt("expires_at", now)
        .execute()
    )
    return len(res.data or [])
