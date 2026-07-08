"""Repository for the `contacts` table."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.db.supabase_client import get_supabase

TABLE = "contacts"


async def get_or_create(
    business_id: str,
    phone_number: Optional[str],
    name: Optional[str] = None,
    role: Optional[str] = None,
) -> Optional[dict]:
    """Return the contact for (business_id, phone_number), creating it if new.

    Returns None if there's no phone number (contacts.phone_number is NOT NULL).
    """
    if not phone_number:
        return None
    client = await get_supabase()
    existing = (
        await client.table(TABLE)
        .select("*")
        .eq("business_id", business_id)
        .eq("phone_number", phone_number)
        .limit(1)
        .execute()
    ).data
    if existing:
        return existing[0]

    row = {
        "business_id": business_id,
        "phone_number": phone_number,
        "name": name,
        "role": role,
        "last_contacted": datetime.now(timezone.utc).isoformat(),
    }
    try:
        return (await client.table(TABLE).insert(row).execute()).data[0]
    except Exception:
        # Lost a race on the UNIQUE(business_id, phone_number) constraint — re-fetch.
        again = (
            await client.table(TABLE)
            .select("*")
            .eq("business_id", business_id)
            .eq("phone_number", phone_number)
            .limit(1)
            .execute()
        ).data
        return again[0] if again else None


async def increment_stats(contact_id: str, orders_delta: int = 0, amount_delta: float = 0) -> None:
    """Bump total_orders / total_amount_transacted (read-modify-write; Phase-1 scale)."""
    client = await get_supabase()
    cur = (
        await client.table(TABLE)
        .select("total_orders,total_amount_transacted")
        .eq("id", contact_id)
        .limit(1)
        .execute()
    ).data
    if not cur:
        return
    total_orders = (cur[0].get("total_orders") or 0) + orders_delta
    total_amount = float(cur[0].get("total_amount_transacted") or 0) + float(amount_delta or 0)
    await client.table(TABLE).update({
        "total_orders": total_orders,
        "total_amount_transacted": total_amount,
        "last_contacted": datetime.now(timezone.utc).isoformat(),
    }).eq("id", contact_id).execute()
