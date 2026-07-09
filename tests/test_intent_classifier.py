"""Intent classifier tests — mocked logic (always) + live accuracy eval (opt-in)."""
import asyncio
import os

import pytest

from app.core.intent_classifier import classify

requires_live = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_EVAL"),
    reason="set RUN_LIVE_EVAL=1 to run the live model accuracy eval (uses OpenAI)",
)


# --- Mocked logic tests (deterministic, no API) ------------------------------

def test_high_confidence_passes_through(patch_json):
    patch_json("app.core.intent_classifier.complete_json",
               {"intent": "order_placed", "confidence": 0.95, "reasoning": "x"})
    r = asyncio.run(classify("50 piece bhejo"))
    assert r.intent == "order_placed" and r.confidence == 0.95 and not r.escalate


def test_low_confidence_becomes_unknown_and_escalates(patch_json):
    patch_json("app.core.intent_classifier.complete_json",
               {"intent": "order_placed", "confidence": 0.5})
    r = asyncio.run(classify("kuch bhej do"))
    assert r.intent == "unknown" and r.escalate


def test_unrecognized_intent_escalates(patch_json):
    patch_json("app.core.intent_classifier.complete_json",
               {"intent": "banana", "confidence": 0.99})
    r = asyncio.run(classify("x"))
    assert r.intent == "unknown" and r.escalate


def test_missing_confidence_defaults_to_escalate(patch_json):
    patch_json("app.core.intent_classifier.complete_json", {"intent": "order_placed"})
    r = asyncio.run(classify("x"))
    assert r.intent == "unknown" and r.escalate


# --- Live accuracy eval (opt-in) ---------------------------------------------

@requires_live
def test_intent_accuracy_on_corpus(fixtures):
    unambiguous = [f for f in fixtures if not f["ambiguous"]]
    correct = sum(
        1 for f in unambiguous if asyncio.run(classify(f["message"])).intent == f["expected_intent"]
    )
    accuracy = correct / len(unambiguous)
    assert accuracy >= 0.90, f"intent accuracy {accuracy:.0%} on {len(unambiguous)} unambiguous fixtures"


@requires_live
def test_unknown_intent_messages_are_uncertain(fixtures):
    # Only messages whose INTENT is genuinely unclear (gibberish, emojis, links)
    # should come back uncertain. Entity-ambiguous orders have a clear intent and
    # are handled by the extractor instead (see test_entity_extractor).
    unknowns = [f for f in fixtures if f["expected_intent"] == "unknown"]
    uncertain = 0
    for f in unknowns:
        r = asyncio.run(classify(f["message"]))
        if r.intent == "unknown" or r.escalate or r.confidence < 0.70:
            uncertain += 1
    assert uncertain / len(unknowns) >= 0.80, f"only {uncertain}/{len(unknowns)} unknowns were uncertain"
