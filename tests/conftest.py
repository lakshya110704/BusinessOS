"""Shared test fixtures."""
import json
import pathlib

import pytest

_FIXTURES = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "sample_messages.json").read_text()
)["fixtures"]


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Each test that uses asyncio.run() gets its own event loop; the cached async
    Supabase/Redis clients bind to the first loop, so reset them before every test."""
    import app.db.supabase_client as sc
    import app.queue.redis_client as rc
    sc._client = None
    rc._redis = None
    yield


@pytest.fixture
def fixtures():
    return _FIXTURES


@pytest.fixture
def patch_json(monkeypatch):
    """Replace a module's `complete_json` with an async stub returning `response`.

    Usage: patch_json("app.core.intent_classifier.complete_json", {"intent": ...})
    """
    def _patch(target: str, response: dict):
        async def _fake(*args, **kwargs):
            return response
        monkeypatch.setattr(target, _fake)
    return _patch


@pytest.fixture
def mock_pipeline(monkeypatch):
    """Mock the OpenAI + WhatsApp boundaries for integration tests.

    Classifier → order_placed, extractor → a fixed order, confirm summary → canned text,
    and both WhatsApp sends are captured. Returns the `sends` list of (kind, to, body).
    """
    import datetime as _dt
    IST = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
    tomorrow = (_dt.datetime.now(IST).date() + _dt.timedelta(days=1)).isoformat()

    def _aret(resp):
        async def _f(*a, **k):
            return resp
        return _f

    monkeypatch.setattr("app.core.intent_classifier.complete_json",
                        _aret({"intent": "order_placed", "confidence": 0.95, "reasoning": "t"}))
    monkeypatch.setattr("app.core.entity_extractor.complete_json",
                        _aret({"quantity": 50, "unit": "piece", "delivery_date": tomorrow,
                               "payment_terms": "net-7", "vendor_name": "Ramesh", "confidence": "HIGH",
                               "ambiguities": []}))
    monkeypatch.setattr("app.core.confirm_engine.complete_json", _aret({"message": "📦 order aaya"}))

    sends = []

    async def _cap_interactive(to, body, buttons):
        sends.append(("interactive", to, body))

    async def _cap_text(to, text):
        sends.append(("text", to, text))

    monkeypatch.setattr("app.core.confirm_engine.send_interactive", _cap_interactive)
    monkeypatch.setattr("app.core.confirm_engine.send_text", _cap_text)
    return sends
