"""Repository for the `tasks` table (follow-ups, reminders)."""
from __future__ import annotations

from app.db.supabase_client import get_supabase

TABLE = "tasks"


async def create(task: dict) -> dict:
    client = await get_supabase()
    res = await client.table(TABLE).insert(task).execute()
    return res.data[0]
