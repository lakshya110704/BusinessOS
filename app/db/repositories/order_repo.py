"""Repository for the `orders` table."""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.supabase_client import get_supabase

TABLE = "orders"


async def create(order: dict) -> dict:
    """Insert an order row and return it."""
    client = await get_supabase()
    res = await client.table(TABLE).insert(order).execute()
    return res.data[0]


async def next_order_number(business_id: str) -> str:
    """Next per-business, per-year sequential number: ORD-YYYY-NNN.

    Counts this year's orders for the business and adds one. At Phase-1 volume the
    small race window is acceptable; a Postgres sequence would make it airtight.
    """
    client = await get_supabase()
    prefix = f"ORD-{datetime.now(timezone.utc).year}-"
    rows = (
        await client.table(TABLE)
        .select("order_number")
        .eq("business_id", business_id)
        .like("order_number", f"{prefix}%")
        .execute()
    ).data
    return f"{prefix}{len(rows) + 1:03d}"
