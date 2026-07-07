"""Action executor — performs a confirmed action against the database.

Called by confirm_engine.handle_reply() once the owner taps "Confirm". Only the
create_order path is implemented here (enough for the confirm loop); the rest
(record_payment, schedule_payment_reminder, contact upsert, sequential order
numbers) is completed in LAK-20.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from app.db.repositories import order_repo
from app.utils.logger import get_logger

logger = get_logger("executor")


def _order_number() -> str:
    # LAK-20 will replace this with a sequential ORD-YYYY-NNN counter.
    return f"ORD-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}"


async def execute(proposed_action: dict, business_id: str, contact_id: Optional[str] = None) -> dict:
    action_type = proposed_action.get("action_type")
    fields = proposed_action.get("fields", {})

    if action_type == "create_order":
        order = await order_repo.create({
            "business_id": business_id,
            "contact_id": contact_id,
            "order_number": _order_number(),
            "direction": "incoming",
            "items": [{
                "quantity": fields.get("quantity"),
                "unit": fields.get("unit"),
                "description": fields.get("sku"),
            }],
            "total_amount": fields.get("amount"),
            "delivery_date": fields.get("delivery_date"),
            "payment_terms": fields.get("payment_terms"),
            "status": "confirmed",
            "payment_status": "pending",
            "confirmed_by_owner": True,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("executed", extra={"action": action_type, "order_id": order["id"]})
        return {"action": action_type, "order_id": order["id"], "order_number": order["order_number"]}

    # TODO(LAK-20): record_payment, schedule_payment_reminder.
    logger.info("execute_noop", extra={"action": action_type})
    return {"action": action_type, "status": "not_implemented"}
