"""Repository for the `payments` table."""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.supabase_client import get_supabase

TABLE = "payments"


async def create(payment: dict) -> dict:
    client = await get_supabase()
    res = await client.table(TABLE).insert(payment).execute()
    return res.data[0]


async def count_received_on(business_id: str, date_iso: str) -> int:
    """Count payments marked paid on a given date (for the daily summary)."""
    client = await get_supabase()
    rows = (
        await client.table(TABLE)
        .select("id")
        .eq("business_id", business_id)
        .eq("paid_date", date_iso)
        .execute()
    ).data
    return len(rows)


async def get_due_for_reminders(cutoff_date_iso: str) -> list:
    """Unpaid payments due on or before `cutoff` — the reminder candidates (all businesses)."""
    client = await get_supabase()
    return (
        await client.table(TABLE)
        .select("*")
        .in_("status", ["pending", "partial"])
        .lte("due_date", cutoff_date_iso)
        .order("due_date")
        .execute()
    ).data


async def mark_reminded(payment_id: str, reminder_count: int) -> None:
    client = await get_supabase()
    await client.table(TABLE).update({
        "reminder_count": (reminder_count or 0) + 1,
        "last_reminder_sent": datetime.now(timezone.utc).isoformat(),
    }).eq("id", payment_id).execute()
