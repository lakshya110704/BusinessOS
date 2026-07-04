"""Async OpenAI client wrapper.

One place that knows how to talk to OpenAI: creates the client from settings,
lets the SDK retry transient errors (429/5xx), and exposes a JSON-mode helper
so callers get a parsed dict back instead of raw text.
"""
from __future__ import annotations

import json
from functools import lru_cache

from openai import AsyncOpenAI

from app.config import settings

DEFAULT_MODEL = "gpt-4o-mini"


@lru_cache(maxsize=1)
def get_openai() -> AsyncOpenAI:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY must be set in .env")
    # max_retries → SDK retries transient 429/5xx with backoff automatically.
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=3)


async def complete_json(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.0) -> dict:
    """Send a single-turn prompt and parse the model's JSON response.

    temperature=0 for deterministic classification; response_format forces the
    model to return valid JSON so we can json.loads() it safely.
    """
    client = get_openai()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)
