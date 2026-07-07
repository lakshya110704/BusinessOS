"""Repository for the `orders` table."""
from __future__ import annotations

from app.db.supabase_client import get_supabase

TABLE = "orders"


async def create(order: dict) -> dict:
    """Insert an order row and return it."""
    client = await get_supabase()
    res = await client.table(TABLE).insert(order).execute()
    return res.data[0]
