"""Health endpoint tests — dependency checks mocked (LAK-28)."""
from fastapi.testclient import TestClient

import app.api.health as health_module
from app.main import app


def test_health_ok_when_deps_up(monkeypatch):
    async def up():
        return True
    monkeypatch.setattr(health_module, "_check_supabase", up)
    monkeypatch.setattr(health_module, "_check_redis", up)
    monkeypatch.setattr(health_module.settings, "OPENAI_API_KEY", "sk-test")

    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"supabase": True, "redis": True, "openai_key": True}


def test_health_503_when_dependency_down(monkeypatch):
    async def up():
        return True
    async def down():
        return False
    monkeypatch.setattr(health_module, "_check_supabase", up)
    monkeypatch.setattr(health_module, "_check_redis", down)

    resp = TestClient(app).get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
    assert resp.json()["checks"]["redis"] is False
