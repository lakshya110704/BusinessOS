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

    Uses MAX(existing suffix) + 1 (not count), so deleting an order never causes a
    collision with a still-existing number. At Phase-1 volume the small concurrent
    race is acceptable; a Postgres sequence + UNIQUE(order_number) would make it airtight.
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
    highest = 0
    for row in rows:
        suffix = (row.get("order_number") or "").rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:03d}"
