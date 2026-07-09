"""Entity extractor tests — mocked coercion/logic (always) + live date-resolution (opt-in)."""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

from app.core.entity_extractor import _BASE_TEMPLATE, _today_ist, extract

requires_live = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_EVAL"),
    reason="set RUN_LIVE_EVAL=1 to run the live extractor eval (uses OpenAI)",
)


# --- Mocked logic tests (deterministic, no API) ------------------------------

def test_type_coercion(patch_json):
    patch_json("app.core.entity_extractor.complete_json",
               {"quantity": "50", "unit": "piece", "amount": "20000", "payment_terms": "net-7",
                "confidence": "high", "ambiguities": []})
    r = asyncio.run(extract("x", intent="order_placed"))
    assert r.quantity == 50 and isinstance(r.quantity, int)
    assert r.amount == 20000.0 and isinstance(r.amount, float)
    assert r.payment_terms == "net-7"
    assert r.confidence == "HIGH"          # upper-cased


def test_null_and_missing_fields(patch_json):
    patch_json("app.core.entity_extractor.complete_json",
               {"quantity": None, "unit": None, "amount": "null"})
    r = asyncio.run(extract("x", intent="order_placed"))
    assert r.quantity is None and r.unit is None and r.amount is None


def test_accepts_nested_entities_shape(patch_json):
    patch_json("app.core.entity_extractor.complete_json",
               {"entities": {"quantity": 10, "unit": "box"}, "confidence": "MEDIUM", "ambiguities": []})
    r = asyncio.run(extract("x", intent="order_placed"))
    assert r.quantity == 10 and r.unit == "box"


def test_garbage_numbers_coerce_to_none(patch_json):
    patch_json("app.core.entity_extractor.complete_json",
               {"quantity": "kuch", "amount": "bahut"})
    r = asyncio.run(extract("x", intent="order_placed"))
    assert r.quantity is None and r.amount is None


def test_prompt_injects_todays_date():
    # The extractor must give the model today's date so it can resolve "kal" etc.
    prompt = _BASE_TEMPLATE.safe_substitute(
        today=_today_ist(), message="x", intent="order_placed", contact_history="(none)"
    )
    assert _today_ist() in prompt


# --- Live eval (opt-in) ------------------------------------------------------

@requires_live
def test_relative_date_resolves_to_tomorrow(fixtures):
    IST = timezone(timedelta(hours=5, minutes=30))
    tomorrow = (datetime.now(IST).date() + timedelta(days=1)).isoformat()
    f = next(x for x in fixtures
             if x.get("relative_date") == "kal" and x["expected_intent"] == "order_placed" and not x["ambiguous"])
    r = asyncio.run(extract(f["message"], intent="order_placed"))
    assert r.delivery_date == tomorrow


@requires_live
def test_extracts_quantity_and_unit(fixtures):
    f = next(x for x in fixtures
             if x["expected_intent"] == "order_placed" and x["expected_entities"].get("quantity") and not x["ambiguous"])
    r = asyncio.run(extract(f["message"], intent="order_placed"))
    assert r.quantity == f["expected_entities"]["quantity"]


@requires_live
def test_entity_ambiguous_orders_are_flagged(fixtures):
    # An order with a clear intent but a missing/vague quantity should surface as
    # ambiguous at the extractor: null quantity OR a recorded ambiguity.
    amb_orders = [x for x in fixtures if x["ambiguous"] and x["expected_intent"] == "order_placed"]
    flagged = 0
    for f in amb_orders:
        r = asyncio.run(extract(f["message"], intent="order_placed"))
        if r.quantity is None or r.ambiguities or r.confidence != "HIGH":
            flagged += 1
    assert flagged / len(amb_orders) >= 0.80, f"only {flagged}/{len(amb_orders)} ambiguous orders were flagged"
