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


async def get_latest_pending(business_id: str) -> Optional[dict]:
    """Most recent still-pending confirmation for a business (what a reply refers to)."""
    client = await get_supabase()
    res = (
        await client.table(TABLE)
        .select("*")
        .eq("business_id", business_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def update_status(confirmation_id: str, status: str) -> None:
    client = await get_supabase()
    await client.table(TABLE).update({"status": status}).eq("id", confirmation_id).execute()


async def claim_pending(confirmation_id: str, status: str) -> bool:
    """Atomically move a confirmation from `pending` to `status`.

    The `.eq("status", "pending")` makes this a conditional update: only the first
    caller flips it and gets rows back; a concurrent second tap gets 0 rows and
    must NOT execute the action (guards against duplicate orders).
    """
    client = await get_supabase()
    res = (
        await client.table(TABLE)
        .update({"status": status})
        .eq("id", confirmation_id)
        .eq("status", "pending")
        .execute()
    )
    return bool(res.data)


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
