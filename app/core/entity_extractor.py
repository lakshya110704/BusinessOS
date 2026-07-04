"""Entity extraction via GPT-4o mini.

extract() pulls structured business fields (quantity, amount, dates, vendor…)
out of a Hindi/Hinglish message. It injects today's date (IST) so the model can
resolve relative dates ("kal", "parso") to absolute ISO dates, and appends an
intent-specific refinement prompt for order vs payment messages.
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone
from string import Template
from typing import Optional

from pydantic import BaseModel, Field

from app.ai.openai_client import complete_json
from app.utils.logger import get_logger

logger = get_logger("entities")

IST = timezone(timedelta(hours=5, minutes=30))
_PROMPTS = pathlib.Path(__file__).resolve().parent.parent / "ai" / "prompts"
_BASE_TEMPLATE = Template((_PROMPTS / "entity_extractor.txt").read_text())
_ORDER_REFINEMENT = (_PROMPTS / "order_parser.txt").read_text()
_PAYMENT_REFINEMENT = (_PROMPTS / "payment_parser.txt").read_text()


class EntityResult(BaseModel):
    quantity: Optional[int] = None
    unit: Optional[str] = None
    sku: Optional[str] = None
    amount: Optional[float] = None
    delivery_date: Optional[str] = None
    payment_date: Optional[str] = None
    payment_terms: Optional[str] = None
    vendor_name: Optional[str] = None
    confidence: str = "LOW"
    ambiguities: list[str] = Field(default_factory=list)


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def _format_history(history: Optional[list]) -> str:
    if not history:
        return "(none)"
    return " | ".join(str(h) for h in history[-5:])


def _refinement_for(intent: str) -> str:
    if intent in ("order_placed", "order_inquiry"):
        return _ORDER_REFINEMENT
    if intent in ("payment_sent", "payment_request"):
        return _PAYMENT_REFINEMENT
    return ""


def _as_int(v) -> Optional[int]:
    if v in (None, "", "null"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_float(v) -> Optional[float]:
    if v in (None, "", "null"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def extract(
    message: str,
    intent: str,
    contact_history: Optional[list] = None,
) -> EntityResult:
    prompt = _BASE_TEMPLATE.safe_substitute(
        today=_today_ist(),
        message=message,
        intent=intent,
        contact_history=_format_history(contact_history),
    )
    refinement = _refinement_for(intent)
    if refinement:
        prompt = f"{prompt}\n\n{refinement}"

    data = await complete_json(prompt)
    # Accept either a flat object or one nested under "entities".
    flat = data.get("entities", data)

    result = EntityResult(
        quantity=_as_int(flat.get("quantity")),
        unit=flat.get("unit"),
        sku=flat.get("sku"),
        amount=_as_float(flat.get("amount")),
        delivery_date=flat.get("delivery_date"),
        payment_date=flat.get("payment_date"),
        payment_terms=flat.get("payment_terms"),
        vendor_name=flat.get("vendor_name"),
        confidence=str(data.get("confidence", flat.get("confidence", "LOW"))).upper(),
        ambiguities=data.get("ambiguities", flat.get("ambiguities", [])) or [],
    )
    logger.info(
        "extracted",
        extra={"intent": intent, "confidence": result.confidence, "ambiguities": len(result.ambiguities)},
    )
    return result
