"""Action generator — decide WHAT to propose from intent + entities.

Pure logic (no API): maps a classified intent + extracted entities into a
ProposedAction the confirm engine can render into a WhatsApp message. Anything
uncertain routes to escalate_to_owner rather than acting (Critical Rules #5, #8).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.core.entity_extractor import EntityResult
from app.core.intent_classifier import CONFIDENCE_THRESHOLD, IntentResult
from app.utils.logger import get_logger

logger = get_logger("action")

# Action types
CREATE_ORDER = "create_order"
RECORD_PAYMENT = "record_payment"
SCHEDULE_PAYMENT_REMINDER = "schedule_payment_reminder"
SEND_ACKNOWLEDGEMENT = "send_acknowledgement"
ESCALATE_TO_OWNER = "escalate_to_owner"

# intent → action for the confident, mappable cases
_INTENT_ACTION = {
    "order_placed": CREATE_ORDER,
    "payment_sent": RECORD_PAYMENT,
    "payment_request": SCHEDULE_PAYMENT_REMINDER,
    "greeting": SEND_ACKNOWLEDGEMENT,
}


class ProposedAction(BaseModel):
    action_type: str
    intent: str
    confidence: float
    escalate: bool = False
    reason: str = ""
    contact: dict = Field(default_factory=dict)   # name / phone / role
    fields: dict = Field(default_factory=dict)    # entity fields for this action


def _entity_fields(entities: EntityResult) -> dict:
    fields = {
        key: value
        for key, value in {
            "quantity": entities.quantity,
            "unit": entities.unit,
            "sku": entities.sku,
            "amount": entities.amount,
            "delivery_date": entities.delivery_date,
            "payment_date": entities.payment_date,
            "payment_terms": entities.payment_terms,
            "vendor_name": entities.vendor_name,
        }.items()
        if value is not None
    }
    if entities.ambiguities:
        fields["ambiguities"] = entities.ambiguities
    return fields


def generate(
    intent_result: IntentResult,
    entity_result: EntityResult,
    context: Optional[dict] = None,
) -> ProposedAction:
    context = context or {}
    contact = context.get("contact", {})
    intent = intent_result.intent
    confidence = intent_result.confidence
    fields = _entity_fields(entity_result)

    # Uncertain → never act, escalate to the owner.
    if intent_result.escalate or confidence < CONFIDENCE_THRESHOLD or intent == "unknown":
        action = ProposedAction(
            action_type=ESCALATE_TO_OWNER, intent=intent, confidence=confidence,
            escalate=True, reason="low_confidence", contact=contact, fields=fields,
        )
        logger.info("proposed", extra={"action": action.action_type, "intent": intent, "confidence": confidence})
        return action

    # Confident, mappable intents; anything else (order_inquiry, delivery_update,
    # complaint, …) needs a human in Phase 1 → escalate.
    action_type = _INTENT_ACTION.get(intent, ESCALATE_TO_OWNER)
    action = ProposedAction(
        action_type=action_type,
        intent=intent,
        confidence=confidence,
        escalate=(action_type == ESCALATE_TO_OWNER),
        reason="" if action_type != ESCALATE_TO_OWNER else "no_automated_action_for_intent",
        contact=contact,
        fields=fields,
    )
    logger.info("proposed", extra={"action": action.action_type, "intent": intent, "confidence": confidence})
    return action
