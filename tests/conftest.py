"""Shared test fixtures."""
import json
import pathlib

import pytest

_FIXTURES = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "sample_messages.json").read_text()
)["fixtures"]


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
