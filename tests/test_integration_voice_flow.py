"""Integration test: voice note → transcript → order flow (LAK-27).

Mocks Whisper (voice_parser.parse) + OpenAI + WhatsApp; real Supabase + Redis. Asserts
the transcript is stored in messages.voice_transcript and the pipeline produces an order.
"""
import asyncio
import uuid

import pytest

from app.config import settings
from app.core.message_router import route
from app.db.supabase_client import get_supabase

requires_infra = pytest.mark.skipif(
    not (settings.SUPABASE_URL and settings.UPSTASH_REDIS_URL),
    reason="integration test needs real Supabase + Redis creds in .env",
)

OWNER = "+919999900003"
VENDOR = "919888800004"
TRANSCRIPT = "रमेश भाई पचास पीस भेजो कल तक"


async def _cleanup(client, business_id):
    for table in ["pending_confirmations", "tasks", "orders", "messages", "contacts", "businesses"]:
        col = "id" if table == "businesses" else "business_id"
        await client.table(table).delete().eq(col, business_id).execute()


@requires_infra
def test_voice_order_flow(mock_pipeline, monkeypatch):
    async def fake_parse(media_id, media_url=None):
        return TRANSCRIPT
    monkeypatch.setattr("app.core.message_router.voice_parser.parse", fake_parse)

    async def flow():
        client = await get_supabase()
        pnid = f"PNID{uuid.uuid4().hex[:8]}"
        biz = (await client.table("businesses").insert({
            "owner_name": "Owner", "phone_number": OWNER, "whatsapp_phone_number_id": pnid,
            "business_name": "Test", "is_active": True,
        }).execute()).data[0]
        bid = biz["id"]
        try:
            voice_msg = {"from": VENDOR, "id": f"wamid.{uuid.uuid4().hex}", "type": "audio",
                         "audio": {"id": "MEDIA123"}}
            await route(voice_msg, pnid)

            msgs = (await client.table("messages").select("*").eq("business_id", bid).execute()).data
            assert len(msgs) == 1
            assert msgs[0]["message_type"] == "voice"
            assert msgs[0]["voice_transcript"] == TRANSCRIPT   # transcript stored in DB
            assert msgs[0]["raw_content"] is None              # not stored as raw text
            assert msgs[0]["intent"] == "order_placed"

            pend = (await client.table("pending_confirmations").select("*").eq("business_id", bid).execute()).data
            assert len(pend) == 1
            assert any(s[0] == "interactive" for s in mock_pipeline)   # confirmation sent
        finally:
            await _cleanup(client, bid)

    asyncio.run(flow())
