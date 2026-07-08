"""Low-level async HTTP client for the Meta WhatsApp Cloud API.

Everything outbound goes through send_message(): it attaches auth, enforces the
80 msg/s cap, and retries transient failures (429 / 5xx) with exponential
backoff. Higher-level helpers live in sender.py.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("wa_client")

# Graph API version — bump when Meta deprecates. Kept as a constant so there's
# one place to change it.
GRAPH_API_VERSION = "v21.0"
MAX_PER_SECOND = 80
_MIN_INTERVAL = 1.0 / MAX_PER_SECOND
MAX_RETRIES = 4
REQUEST_TIMEOUT = 10.0


class _RateLimiter:
    """Serializes sends to at most MAX_PER_SECOND by spacing them _MIN_INTERVAL apart."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delta = time.monotonic() - self._last
            if delta < self._min_interval:
                await asyncio.sleep(self._min_interval - delta)
            self._last = time.monotonic()


_rate_limiter = _RateLimiter(_MIN_INTERVAL)


def _messages_url() -> str:
    return (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}"
        f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )


async def send_message(payload: dict) -> dict:
    """POST a message payload to the Cloud API. Returns Meta's JSON response.

    Raises httpx.HTTPStatusError on a non-retryable 4xx, or after exhausting
    retries on 429/5xx.
    """
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID must be set in .env"
        )

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    url = _messages_url()
    backoff = 1.0

    for attempt in range(1, MAX_RETRIES + 1):
        await _rate_limiter.wait()
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)

        # Retryable: rate-limited or server error.
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == MAX_RETRIES:
                logger.error("wa_send_exhausted", extra={"status": resp.status_code})
                resp.raise_for_status()
            logger.info("wa_retry", extra={"status": resp.status_code, "attempt": attempt})
            await asyncio.sleep(backoff)
            backoff *= 2
            continue

        # Non-retryable client error → surface it (with Meta's error body logged).
        if resp.status_code >= 400:
            logger.error("wa_send_failed", extra={"status": resp.status_code, "body": resp.text})
            resp.raise_for_status()

        data = resp.json()
        message_id = (data.get("messages") or [{}])[0].get("id")
        logger.info("wa_sent", extra={"wa_message_id": message_id})
        return data

    return {}  # unreachable — loop either returns or raises


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}


async def get_media_url(media_id: str) -> str:
    """Resolve a WhatsApp media_id to its (temporary) download URL."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json()["url"]


async def download_media(url: str) -> bytes:
    """Download media bytes from a Meta media URL (requires the access token)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        return resp.content
