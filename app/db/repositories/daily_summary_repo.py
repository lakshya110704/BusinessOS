"""Repository for the `daily_summaries` table."""
from __future__ import annotations

from app.db.supabase_client import get_supabase

TABLE = "daily_summaries"


async def upsert(row: dict) -> dict:
    """Insert or update a business's summary for a date (idempotent via UNIQUE(business_id, summary_date))."""
    client = await get_supabase()
    res = await client.table(TABLE).upsert(row, on_conflict="business_id,summary_date").execute()
    return res.data[0]
