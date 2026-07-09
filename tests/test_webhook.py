"""Webhook signature-verification + dedup tests (LAK-25).

Redis and the queue push are mocked, so these are pure/fast — they exercise the
security logic (HMAC) and the dedup branch without hitting Upstash.
"""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

TEST_SECRET = "test_secret_123"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(TEST_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _payload(wamid: str = "wamid.T1") -> bytes:
    return json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [
            {"from": "919876543210", "id": wamid, "type": "text", "text": {"body": "hi"}}
        ]}}]}],
    }).encode()


@pytest.fixture
def make_client(monkeypatch):
    """Returns a factory: make_client(dedup_is_new=True) -> (client, pushed_list)."""
    from app.config import settings
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", TEST_SECRET)

    import app.api.webhook as wh
    from app.main import app

    def _make(dedup_is_new: bool = True):
        class FakeRedis:
            async def set(self, *a, **k):
                return True if dedup_is_new else None  # SET NX: True=new, None=already exists

            async def delete(self, *a, **k):
                return 1

        monkeypatch.setattr(wh, "get_redis", lambda: FakeRedis())
        pushed = []

        async def fake_push(queue, payload):
            pushed.append(payload)

        monkeypatch.setattr(wh, "push", fake_push)
        return TestClient(app), pushed

    return _make


def test_valid_signature_returns_200_and_enqueues(make_client):
    client, pushed = make_client(dedup_is_new=True)
    body = _payload()
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _sign(body)})
    assert resp.status_code == 200
    assert resp.json()["enqueued"] == 1
    assert len(pushed) == 1


def test_invalid_signature_returns_403(make_client):
    client, pushed = make_client()
    body = _payload()
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=deadbeef"})
    assert resp.status_code == 403
    assert pushed == []


def test_missing_signature_returns_403(make_client):
    client, _ = make_client()
    resp = client.post("/webhook", content=_payload())
    assert resp.status_code == 403


def test_correct_signature_wrong_body_returns_403(make_client):
    client, _ = make_client()
    signed_body = _payload("wamid.ORIGINAL")
    signature = _sign(signed_body)
    tampered_body = _payload("wamid.TAMPERED")  # same signature, different bytes
    resp = client.post("/webhook", content=tampered_body, headers={"X-Hub-Signature-256": signature})
    assert resp.status_code == 403


def test_duplicate_message_id_not_reprocessed(make_client):
    client, pushed = make_client(dedup_is_new=False)  # Redis says this id was already seen
    body = _payload()
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _sign(body)})
    assert resp.status_code == 200
    assert resp.json()["enqueued"] == 0   # idempotent — skipped
    assert pushed == []
