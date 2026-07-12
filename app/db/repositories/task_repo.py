"""Repository for the `tasks` table (follow-ups, reminders)."""
from __future__ import annotations

from app.db.supabase_client import get_supabase

TABLE = "tasks"


async def create(task: dict) -> dict:
    client = await get_supabase()
    res = await client.table(TABLE).insert(task).execute()
    return res.data[0]


async def count_pending(business_id: str) -> int:
    """Count still-pending follow-ups for a business (for the daily summary)."""
    client = await get_supabase()
    rows = (
        await client.table(TABLE)
        .select("id")
        .eq("business_id", business_id)
        .eq("status", "pending")
        .execute()
    ).data
    return len(rows)
