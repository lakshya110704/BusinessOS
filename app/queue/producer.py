"""Push jobs onto a Redis list-backed queue.

The webhook calls `push("incoming_messages", payload)` and returns immediately;
the consumer (separate process) does the slow work. RPUSH appends to the tail;
the consumer BLPOPs from the head → FIFO order.
"""
from __future__ import annotations

import json
from typing import Any

from app.queue.redis_client import get_redis


async def push(queue_name: str, payload: dict[str, Any]) -> None:
    r = get_redis()
    await r.rpush(queue_name, json.dumps(payload))
