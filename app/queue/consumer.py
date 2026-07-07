"""Queue consumer — runs as a SEPARATE process from the web app.

Blocks on the `incoming_messages` queue, pops each payload, and dispatches it to
the message router (classify → extract → generate).
Start it with:  python -m app.queue.consumer
"""
from __future__ import annotations

import asyncio
import json

from app.core.message_router import route
from app.queue.redis_client import get_redis
from app.utils.logger import get_logger

logger = get_logger("consumer")

QUEUE_NAME = "incoming_messages"


async def handle(payload: dict) -> None:
    # One bad message must not kill the worker loop.
    try:
        await route(payload)
    except Exception:
        logger.exception("route_failed", extra={"wa_message_id": payload.get("id")})


async def run() -> None:
    r = get_redis()
    logger.info("consumer_start", extra={"queue": QUEUE_NAME})
    while True:
        item = await r.blpop(QUEUE_NAME, timeout=5)
        if item is None:
            continue  # timeout with nothing to do — loop again
        _key, raw = item
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("bad_payload", extra={"queue": QUEUE_NAME})
            continue
        await handle(payload)


if __name__ == "__main__":
    asyncio.run(run())
