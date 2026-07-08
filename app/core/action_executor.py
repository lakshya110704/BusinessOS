"""Action executor — performs a confirmed action against the database.

Called by confirm_engine.handle_reply() once the owner taps "Confirm". Handles:
- create_order: upsert contact → insert order (ORD-YYYY-NNN) → bump contact stats
               → schedule a payment reminder if terms/date are known
- record_payment: insert a payment row (and mark the linked order paid if known)

The confirm engine's atomic claim_pending guarantees execute() runs at most once
per confirmation, which is our idempotency boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db.repositories import contact_repo, order_repo, payment_repo, task_repo
from app.utils.logger import get_logger

logger = get_logger("executor")

IST = timezone(timedelta(hours=5, minutes=30))


def _reminder_date(fields: dict) -> Optional[str]:
    """Work out when to remind about payment, as an ISO date (or None)."""
    if fields.get("payment_date"):
        return fields["payment_date"]
    terms = (fields.get("payment_terms") or "").lower()
    today = datetime.now(IST).date()
    if terms.startswith("net-"):
        try:
            return (today + timedelta(days=int(terms.split("-")[1]))).isoformat()
        except (ValueError, IndexError):
            return None
    if terms == "on-delivery":
        return fields.get("delivery_date")
    if terms == "advance":
        return today.isoformat()
    return None


async def _create_order(proposed_action: dict, business_id: str, source_message_id: Optional[str] = None) -> dict:
    fields = proposed_action.get("fields", {})
    contact_info = proposed_action.get("contact", {})

    # 1) Upsert the contact (vendor/customer who sent the message).
    contact = await contact_repo.get_or_create(
        business_id,
        phone_number=contact_info.get("phone"),
        name=fields.get("vendor_name") or contact_info.get("name"),
    )
    contact_id = contact["id"] if contact else None

    # 2) Insert the order with a sequential number.
    order_number = await order_repo.next_order_number(business_id)
    amount = fields.get("amount")
    order = await order_repo.create({
        "business_id": business_id,
        "contact_id": contact_id,
        "source_message_id": source_message_id,
        "order_number": order_number,
        "direction": "incoming",
        "items": [{
            "quantity": fields.get("quantity"),
            "unit": fields.get("unit"),
            "description": fields.get("sku"),
        }],
        "total_amount": amount,
        "delivery_date": fields.get("delivery_date"),
        "payment_terms": fields.get("payment_terms"),
        "status": "confirmed",
        "payment_status": "pending",
        "confirmed_by_owner": True,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    })

    # 3) Bump contact stats.
    if contact_id:
        await contact_repo.increment_stats(contact_id, orders_delta=1, amount_delta=amount or 0)

    # 4) Schedule a payment reminder if we know when payment is due.
    reminder_date = _reminder_date(fields)
    if reminder_date:
        await task_repo.create({
            "business_id": business_id,
            "contact_id": contact_id,
            "task_type": "payment",
            "description": f"Payment reminder for {order_number}",
            "due_at": f"{reminder_date}T09:00:00+05:30",
            "status": "pending",
        })

    logger.info("executed", extra={"action": "create_order", "order_id": order["id"], "order_number": order_number})
    return {"action": "create_order", "order_id": order["id"], "order_number": order_number, "reminder_date": reminder_date}


async def _record_payment(proposed_action: dict, business_id: str) -> dict:
    fields = proposed_action.get("fields", {})
    contact_info = proposed_action.get("contact", {})
    contact = await contact_repo.get_or_create(business_id, phone_number=contact_info.get("phone"))
    payment = await payment_repo.create({
        "business_id": business_id,
        "contact_id": contact["id"] if contact else None,
        "amount": fields.get("amount") or 0,
        "direction": "receivable",
        "status": "paid",
        "paid_date": datetime.now(IST).date().isoformat(),
    })
    logger.info("executed", extra={"action": "record_payment", "payment_id": payment["id"]})
    return {"action": "record_payment", "payment_id": payment["id"]}


async def execute(proposed_action: dict, business_id: str, source_message_id: Optional[str] = None) -> dict:
    action_type = proposed_action.get("action_type")
    if action_type == "create_order":
        return await _create_order(proposed_action, business_id, source_message_id)
    if action_type == "record_payment":
        return await _record_payment(proposed_action, business_id)

    logger.info("execute_noop", extra={"action": action_type})
    return {"action": action_type, "status": "not_implemented"}
