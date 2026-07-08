"""Repository for the `payments` table."""
from __future__ import annotations

from app.db.supabase_client import get_supabase

TABLE = "payments"


async def create(payment: dict) -> dict:
    client = await get_supabase()
    res = await client.table(TABLE).insert(payment).execute()
    return res.data[0]
