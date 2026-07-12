"""Integration test: text order → confirm → owner reply "1" → order in DB (LAK-26).

Drives route() (what the queue consumer calls) with real Supabase + Redis but mocked
OpenAI + WhatsApp. Skipped unless both SUPABASE_URL and UPSTASH_REDIS_URL are set.
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

OWNER = "+919999900001"
VENDOR = "919888800002"


async def _cleanup(client, business_id):
    for table in ["pending_confirmations", "tasks", "orders", "messages", "contacts", "businesses"]:
        col = "id" if table == "businesses" else "business_id"
        await client.table(table).delete().eq(col, business_id).execute()


@requires_infra
def test_text_order_flow(mock_pipeline):
    async def flow():
        client = await get_supabase()
        pnid = f"PNID{uuid.uuid4().hex[:8]}"
        biz = (await client.table("businesses").insert({
            "owner_name": "Owner", "phone_number": OWNER, "whatsapp_phone_number_id": pnid,
            "business_name": "Test", "is_active": True,
        }).execute()).data[0]
        bid = biz["id"]
        try:
            # 1) A vendor sends an order to the business.
            order_msg = {"from": VENDOR, "id": f"wamid.{uuid.uuid4().hex}", "type": "text",
                         "text": {"body": "50 piece bhejo kal tak"}}
            await route(order_msg, pnid)

            msgs = (await client.table("messages").select("*").eq("business_id", bid).execute()).data
            assert len(msgs) == 1
            assert msgs[0]["raw_content"] == "50 piece bhejo kal tak"
            assert msgs[0]["intent"] == "order_placed"

            pend = (await client.table("pending_confirmations").select("*").eq("business_id", bid).execute()).data
            assert len(pend) == 1 and pend[0]["status"] == "pending"
            assert pend[0]["proposed_action"]["action_type"] == "create_order"
            assert any(s[0] == "interactive" for s in mock_pipeline)   # confirmation sent

            # 2) Owner replies "1" (tap Confirm).
            mock_pipeline.clear()
            reply = {"from": OWNER.lstrip("+"), "id": f"wamid.{uuid.uuid4().hex}", "type": "interactive",
                     "interactive": {"type": "button_reply", "button_reply": {"id": "1", "title": "Confirm"}}}
            await route(reply, pnid)

            orders = (await client.table("orders").select("*").eq("business_id", bid).execute()).data
            assert len(orders) == 1
            assert orders[0]["status"] == "confirmed"
            assert orders[0]["source_message_id"] == msgs[0]["id"]     # linked to its message

            conf = (await client.table("pending_confirmations").select("status").eq("id", pend[0]["id"]).execute()).data[0]
            assert conf["status"] == "confirmed"
            assert any(s[0] == "text" and "Order logged" in s[2] for s in mock_pipeline)
        finally:
            await _cleanup(client, bid)

    asyncio.run(flow())
