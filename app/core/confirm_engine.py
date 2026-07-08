"""Confirm-before-act engine — the core trust bridge.

send_confirmation() turns a ProposedAction into a Hindi WhatsApp message with
tappable 1/2/3 buttons, sends it to the business owner, and records a
pending_confirmations row so the reply handler (LAK-19) can match the answer.

The AI never executes an action without this step in Phase 1 (Critical Rule #5).
"""
from __future__ import annotations

import pathlib
from string import Template
from typing import Optional

from app.ai.openai_client import complete_json
from app.core.action_executor import execute
from app.core.action_generator import ProposedAction
from app.db.repositories import pending_confirmation_repo as repo
from app.utils.logger import get_logger
from app.whatsapp.sender import send_interactive, send_text

logger = get_logger("confirm")

_PROMPT = Template(
    (pathlib.Path(__file__).resolve().parent.parent / "ai" / "prompts" / "summary_generator.txt").read_text()
)

# WhatsApp reply buttons — id is what comes back when the owner taps (LAK-19 maps it).
_BUTTONS = [("1", "Confirm"), ("2", "Edit"), ("3", "Skip")]

_CONFIRMATION_TYPE = {
    "create_order": "order",
    "record_payment": "payment",
    "schedule_payment_reminder": "payment",
}


def _details(action: ProposedAction) -> str:
    f = action.fields
    lines = []
    if f.get("quantity"):
        lines.append(f"Quantity: {f['quantity']} {f.get('unit', '')}".strip())
    if f.get("amount"):
        lines.append(f"Amount: ₹{f['amount']}")
    if f.get("delivery_date"):
        lines.append(f"Delivery: {f['delivery_date']}")
    if f.get("payment_terms"):
        lines.append(f"Payment: {f['payment_terms']}")
    if f.get("vendor_name"):
        lines.append(f"Contact: {f['vendor_name']}")
    return "\n".join(lines) or "(no details extracted)"


async def _generate_message(action: ProposedAction) -> str:
    prompt = _PROMPT.safe_substitute(
        action_type=action.action_type,
        contact_name=action.fields.get("vendor_name") or action.contact.get("name", "Unknown"),
        details=_details(action),
    )
    data = await complete_json(prompt)
    return data.get("message", "").strip() or _details(action)


async def send_confirmation(
    business: dict,
    proposed_action: ProposedAction,
    source_message_id: Optional[str] = None,
) -> str:
    """Send the owner a confirmation and record it. Returns the pending_confirmation id.

    `business` must have `id` (UUID) and `phone_number` (owner's WhatsApp).
    """
    owner_phone = business.get("phone_number") or business.get("owner_phone")
    if not owner_phone:
        raise ValueError("business is missing an owner phone_number")

    body = await _generate_message(proposed_action)

    # Send first, then persist — so whatsapp_confirm_sent=True reflects reality.
    await send_interactive(owner_phone, body, _BUTTONS)

    confirmation_id = await repo.create(
        business_id=business["id"],
        confirmation_type=_CONFIRMATION_TYPE.get(proposed_action.action_type, proposed_action.action_type),
        proposed_action=proposed_action.model_dump(),
        message_id=source_message_id,
    )
    logger.info(
        "confirmation_sent",
        extra={"confirmation_id": confirmation_id, "action": proposed_action.action_type},
    )
    return confirmation_id


async def handle_reply(business_id: str, owner_phone: str, reply_value: str) -> str:
    """Process an owner's tap (1/2/3) on the latest pending confirmation.

    1 → confirmed + execute the action; 2 → edited; 3 → ignored;
    anything else → re-send the confirmation. Returns the outcome string.
    """
    pending = await repo.get_latest_pending(business_id)
    if not pending:
        await send_text(owner_phone, "Koi pending confirmation nahi hai.")
        return "no_pending"

    confirmation_id = pending["id"]

    if reply_value == "1":
        # Atomically claim pending→confirmed; only the winner executes (no dup orders).
        if not await repo.claim_pending(confirmation_id, "confirmed"):
            logger.info("reply_already_handled", extra={"confirmation_id": confirmation_id})
            return "already_handled"
        result = await execute(pending["proposed_action"], business_id)
        order_number = result.get("order_number")
        reminder_date = result.get("reminder_date")
        message = f"✅ Order logged.{f' ({order_number})' if order_number else ''}"
        if reminder_date:
            message += f" Payment reminder set for {reminder_date}."
        await send_text(owner_phone, message)
        logger.info("reply_handled", extra={"confirmation_id": confirmation_id, "reply": "1", "outcome": "confirmed"})
        return "confirmed"

    if reply_value == "2":
        if not await repo.claim_pending(confirmation_id, "edited"):
            return "already_handled"
        await send_text(owner_phone, "✏️ Theek hai — sahi details bhej dijiye.")
        logger.info("reply_handled", extra={"confirmation_id": confirmation_id, "reply": "2", "outcome": "edited"})
        return "edited"

    if reply_value == "3":
        if not await repo.claim_pending(confirmation_id, "ignored"):
            return "already_handled"
        await send_text(owner_phone, "👍 Theek hai, ignore kar diya.")
        logger.info("reply_handled", extra={"confirmation_id": confirmation_id, "reply": "3", "outcome": "ignored"})
        return "ignored"

    # Unknown reply → re-send the confirmation buttons.
    action = ProposedAction(**pending["proposed_action"])
    body = await _generate_message(action)
    await send_interactive(owner_phone, body, _BUTTONS)
    logger.info("reply_unknown_resend", extra={"confirmation_id": confirmation_id, "reply": reply_value})
    return "resent"
