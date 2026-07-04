"""Intent classification via GPT-4o mini.

classify() formats the §6.1 prompt with contact + conversation context, calls
the model in JSON mode, and enforces the confidence gate: anything below 0.70
(or an unrecognized intent) becomes `unknown` and is flagged for owner
escalation rather than acted on (Critical Rule #8).
"""
from __future__ import annotations

import pathlib
from string import Template
from typing import Optional

from pydantic import BaseModel

from app.ai.openai_client import complete_json
from app.utils.logger import get_logger

logger = get_logger("intent")

VALID_INTENTS = {
    "order_placed", "order_inquiry", "payment_sent", "payment_request",
    "delivery_update", "complaint", "greeting", "unknown",
}
CONFIDENCE_THRESHOLD = 0.70

_PROMPT_PATH = pathlib.Path(__file__).resolve().parent.parent / "ai" / "prompts" / "intent_classifier.txt"
_PROMPT_TEMPLATE = Template(_PROMPT_PATH.read_text())


class IntentResult(BaseModel):
    intent: str
    confidence: float
    reasoning: str = ""
    escalate: bool = False


def _format_history(history: Optional[list]) -> str:
    if not history:
        return "(none)"
    # Keep the last 5, oldest→newest. Each item is a short text string.
    return " | ".join(str(h) for h in history[-5:])


async def classify(
    message: str,
    contact: Optional[dict] = None,
    history: Optional[list] = None,
) -> IntentResult:
    contact = contact or {}
    prompt = _PROMPT_TEMPLATE.safe_substitute(
        business_vertical=contact.get("business_vertical", "unknown"),
        contact_name=contact.get("name", "Unknown"),
        contact_role=contact.get("role", "unknown"),
        history=_format_history(history),
        message=message,
    )

    data = await complete_json(prompt)
    intent = data.get("intent", "unknown")
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    reasoning = data.get("reasoning", "")

    escalate = False
    if intent not in VALID_INTENTS or confidence < CONFIDENCE_THRESHOLD:
        # Too unsure (or garbage intent) → don't guess; escalate to the owner.
        escalate = True
        intent = "unknown"

    logger.info("classified", extra={"intent": intent, "confidence": confidence, "escalate": escalate})
    return IntentResult(intent=intent, confidence=confidence, reasoning=reasoning, escalate=escalate)
