"""Async Redis (Upstash) connection — shared by the queue and the context cache.

Uses the native Redis protocol via redis-py's asyncio client (not Upstash's REST
API) because the consumer relies on BLPOP, a blocking pop the REST API can't do
efficiently. The client is created once (lazily) and reused.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from redis.asyncio import Redis, from_url

from app.config import settings

_redis: Optional[Redis] = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        if not settings.UPSTASH_REDIS_URL:
            raise RuntimeError("UPSTASH_REDIS_URL must be set in .env")
        # decode_responses=True → we get str back, not bytes.
        _redis = from_url(settings.UPSTASH_REDIS_URL, decode_responses=True)
    return _redis


# --- Conversation context cache (24h TTL) ------------------------------------
# Avoids a DB hit for recent conversation context on every incoming message.

async def set_context(phone_number: str, context: dict[str, Any], ttl: int = 86400) -> None:
    r = get_redis()
    await r.set(f"{phone_number}:context", json.dumps(context), ex=ttl)


async def get_context(phone_number: str) -> Optional[dict[str, Any]]:
    r = get_redis()
    raw = await r.get(f"{phone_number}:context")
    return json.loads(raw) if raw else None
