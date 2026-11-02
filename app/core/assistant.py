"""The conversational assistant — "ask your business anything" (BOS-49).

When the business owner texts BusinessOS a free-form question ("aaj ki sales?",
"kiska udhaar baaki hai?"), the message router hands it here. We give an LLM a set
of read-only query tools over the owner's own data and let it pick, run, and phrase
the answer in Hindi/Hinglish — it never invents numbers, it queries them.

v1 tools: sales in a period, pending udhaar (the khata), recent orders. Stock/reorder
tools land with the item-catalog + derived-stock work (BOS-50/51).
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone
from string import Template

from app.ai.openai_client import complete_with_tools
from app.db.repositories import contact_repo, order_repo
from app.utils.logger import get_logger

logger = get_logger("assistant")

IST = timezone(timedelta(hours=5, minutes=30))
_SYSTEM = Template(
    (pathlib.Path(__file__).resolve().parent.parent / "ai" / "prompts" / "assistant.txt").read_text()
)


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def _period_range(period: str) -> tuple[str, str]:
    """Resolve a period keyword into [start, end) ISO timestamps (IST offset)."""
    now = datetime.now(IST)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "yesterday":
        start = today - timedelta(days=1)
        return start.isoformat(), today.isoformat()
    if period == "this_week":
        start = today - timedelta(days=today.weekday())  # Monday
    elif period == "this_month":
        start = today.replace(day=1)
    else:  # today (default)
        start = today
    return start.isoformat(), (now + timedelta(minutes=1)).isoformat()


# OpenAI tool specs (the model sees these to decide what to call).
TOOLS = [
    {"type": "function", "function": {
        "name": "sales_summary",
        "description": "Total sales to customers (count of orders + total ₹ value) in a period.",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "enum": ["today", "yesterday", "this_week", "this_month"]}},
            "required": ["period"]}}},
    {"type": "function", "function": {
        "name": "pending_udhaar",
        "description": "Who still owes money (unpaid customer orders / receivables) and how much.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "recent_orders",
        "description": "The most recent orders — what has been happening lately.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "how many orders, default 10"}}}}},
]


async def answer(business_id: str, question: str) -> str:
    """Answer an owner's free-form business question from their own data."""
    async def sales_summary(period: str = "today") -> dict:
        start, end = _period_range(period)
        s = await order_repo.summary_between(business_id, start, end, direction="sale")
        return {"period": period, "orders": s["orders"], "total_rupees": round(s["total_amount"])}

    async def pending_udhaar() -> dict:
        rows = await order_repo.outstanding_by_contact(business_id, direction="sale")
        out = []
        for r in rows:
            name = None
            if r.get("contact_id"):
                c = await contact_repo.get_by_id(r["contact_id"])
                name = (c or {}).get("name")
            out.append({"who": name or "Unknown", "amount_rupees": round(r["amount"]), "unpaid_orders": r["orders"]})
        out.sort(key=lambda x: x["amount_rupees"], reverse=True)
        return {"debtors": out, "total_pending_rupees": sum(x["amount_rupees"] for x in out)}

    async def recent_orders(limit: int = 10) -> dict:
        rows = await order_repo.recent(business_id, limit=min(int(limit or 10), 25))
        orders = []
        for o in rows:
            items = ", ".join(
                f"{(i.get('quantity') or '')} {i.get('unit') or ''} {i.get('description') or ''}".strip()
                for i in (o.get("items") or [])
            ) or "(no items)"
            orders.append({
                "order_number": o.get("order_number"), "direction": o.get("direction"),
                "items": items, "amount_rupees": o.get("total_amount"),
                "payment_status": o.get("payment_status"),
            })
        return {"orders": orders}

    impls = {"sales_summary": sales_summary, "pending_udhaar": pending_udhaar, "recent_orders": recent_orders}
    reply = await complete_with_tools(_SYSTEM.safe_substitute(today=_today_ist()), question, TOOLS, impls)
    logger.info("assistant_answered", extra={"chars": len(reply)})
    return reply
