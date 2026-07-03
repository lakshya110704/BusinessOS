"""Supabase client wrapper.

Repositories call `get_supabase()` to get a ready-to-use async Supabase client,
instead of each module re-reading keys and re-connecting. The client is created
once (lazily) and reused — a single shared connection for the whole app.

Uses the SERVICE key (full access) — this runs server-side only, never in a
browser/client. See the RLS TODO in 001_initial.sql before that ever changes.
"""
from __future__ import annotations

from supabase import AsyncClient, acreate_client

from app.config import settings

_client: AsyncClient | None = None


async def get_supabase() -> AsyncClient:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
            )
        _client = await acreate_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
        )
    return _client
