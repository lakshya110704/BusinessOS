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
from app.core.action_generator import ProposedAction
from app.db.repositories import pending_confirmation_repo as repo
from app.utils.logger import get_logger
from app.whatsapp.sender import send_interactive

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
