"""Repository for the `orders` table."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db.supabase_client import get_supabase

TABLE = "orders"


async def latest_unpaid_for_contact(business_id: str, contact_id: str) -> Optional[dict]:
    """Most recent order for a contact that isn't fully paid — the one a payment likely settles."""
    client = await get_supabase()
    res = (
        await client.table(TABLE)
        .select("*")
        .eq("business_id", business_id)
        .eq("contact_id", contact_id)
        .neq("payment_status", "paid")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    ).data
    return res[0] if res else None


async def set_payment_status(order_id: str, status: str) -> None:
    client = await get_supabase()
    await client.table(TABLE).update({"payment_status": status}).eq("id", order_id).execute()


async def create(order: dict) -> dict:
    """Insert an order row and return it."""
    client = await get_supabase()
    res = await client.table(TABLE).insert(order).execute()
    return res.data[0]


async def count_created_between(business_id: str, start_iso: str, end_iso: str) -> int:
    """Count orders created in [start, end) for a business (for the daily summary)."""
    client = await get_supabase()
    rows = (
        await client.table(TABLE)
        .select("id")
        .eq("business_id", business_id)
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
        .execute()
    ).data
    return len(rows)


async def get_recent_for_contact(business_id: str, contact_id: str, days: int = 30) -> list:
    """Orders for a contact within the last `days` (newest first) — read-only context."""
    client = await get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return (
        await client.table(TABLE)
        .select("*")
        .eq("business_id", business_id)
        .eq("contact_id", contact_id)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .execute()
    ).data


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


# --- Assistant query surface (read-only; powers "ask your business anything") ---

async def summary_between(
    business_id: str, start_iso: str, end_iso: str, direction: Optional[str] = None
) -> dict:
    """Count + total value of orders created in [start, end), optionally one direction
    ('sale' or 'purchase'). Used for "aaj/is hafte ki sales"."""
    client = await get_supabase()
    q = (
        client.table(TABLE)
        .select("total_amount")
        .eq("business_id", business_id)
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
    )
    if direction:
        q = q.eq("direction", direction)
    rows = (await q.execute()).data
    total = sum(float(r["total_amount"]) for r in rows if r.get("total_amount") is not None)
    return {"orders": len(rows), "total_amount": total}


async def outstanding_by_contact(business_id: str, direction: str = "sale") -> list:
    """Unpaid orders grouped by contact — the khata (who owes what). Default direction
    'sale' = receivables (customers who owe us)."""
    client = await get_supabase()
    rows = (
        await client.table(TABLE)
        .select("contact_id,total_amount")
        .eq("business_id", business_id)
        .eq("direction", direction)
        .neq("payment_status", "paid")
        .execute()
    ).data
    agg: dict = {}
    for r in rows:
        cid = r.get("contact_id")
        bucket = agg.setdefault(cid, {"contact_id": cid, "amount": 0.0, "orders": 0})
        bucket["orders"] += 1
        if r.get("total_amount") is not None:
            bucket["amount"] += float(r["total_amount"])
    return list(agg.values())


async def recent(business_id: str, limit: int = 10) -> list:
    """Most recent orders for a business (newest first), with their items."""
    client = await get_supabase()
    return (
        await client.table(TABLE)
        .select("order_number,contact_id,direction,items,total_amount,payment_status,created_at")
        .eq("business_id", business_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data
