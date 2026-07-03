"""Queue consumer — runs as a SEPARATE process from the web app.

Blocks on the `incoming_messages` queue, pops each payload, and dispatches it.
Start it with:  python -m app.queue.consumer

Right now `handle()` just logs/prints the payload (LAK-7 done-when: "consumer
receives and prints it, no DB involved"). LAK-9+ will replace the stub with a
real dispatch into `message_router`.
"""
from __future__ import annotations

import asyncio
import json

from app.queue.redis_client import get_redis
from app.utils.logger import get_logger

logger = get_logger("consumer")

QUEUE_NAME = "incoming_messages"


async def handle(payload: dict) -> None:
    # TODO(LAK-9+): dispatch to app.core.message_router instead of printing.
    logger.info("consumed", extra={"queue": QUEUE_NAME, "fields": list(payload.keys())})
    print("CONSUMED:", payload)


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
