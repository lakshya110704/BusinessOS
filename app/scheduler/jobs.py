"""Scheduled jobs + the APScheduler that runs them.

- daily_summary          — 20:00 IST: WhatsApp each active owner their day's numbers.
- check_payment_reminders — 09:00 IST: remind owners about due/overdue payments.
- expire_confirmations    — hourly: mark stale pending confirmations expired.

The scheduler is started from the FastAPI lifespan hook (app/main.py). Each job is a
plain async callable, so it can also be run by hand or in a test.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db.repositories import (
    business_repo,
    contact_repo,
    daily_summary_repo,
    order_repo,
    payment_repo,
    pending_confirmation_repo,
    task_repo,
)
from app.utils.logger import get_logger
from app.whatsapp.sender import send_text

logger = get_logger("scheduler")
IST = pytz.timezone("Asia/Kolkata")


# --- expire old confirmations ------------------------------------------------

async def expire_confirmations() -> int:
    count = await pending_confirmation_repo.expire_old()
    logger.info("expired_confirmations", extra={"count": count})
    return count


# --- daily summary (LAK-21) --------------------------------------------------

def _summary_text(orders: int, payments: int, follow_ups: int) -> str:
    return (
        "📊 Aaj ka hisaab:\n"
        f"• Naye order: {orders}\n"
        f"• Payment aaye: {payments}\n"
        f"• Pending follow-up: {follow_ups}"
    )


async def daily_summary() -> int:
    if not settings.DAILY_SUMMARY_ENABLED:
        return 0
    today = datetime.now(IST).date()
    day_start = IST.localize(datetime.combine(today, time.min))
    day_end = day_start + timedelta(days=1)

    sent = 0
    for biz in await business_repo.get_active():
        orders = await order_repo.count_created_between(biz["id"], day_start.isoformat(), day_end.isoformat())
        payments = await payment_repo.count_received_on(biz["id"], today.isoformat())
        follow_ups = await task_repo.count_pending(biz["id"])
        text = _summary_text(orders, payments, follow_ups)

        await daily_summary_repo.upsert({
            "business_id": biz["id"],
            "summary_date": today.isoformat(),
            "orders_received": orders,
            "payments_received": payments,     # count (Phase 1)
            "pending_follow_ups": follow_ups,
            "summary_text": text,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })

        if biz.get("phone_number"):
            try:
                await send_text(biz["phone_number"], text)
                sent += 1
            except Exception:
                logger.error("summary_send_failed", extra={"business_id": biz["id"]})
    logger.info("daily_summary_done", extra={"sent": sent})
    return sent


# --- payment reminders (LAK-22) ----------------------------------------------

async def _reminder_text(payments: list, today: date) -> str:
    lines = ["💰 Payment reminder:"]
    for p in payments[:10]:
        name = "Unknown"
        if p.get("contact_id"):
            contact = await contact_repo.get_by_id(p["contact_id"])
            if contact and contact.get("name"):
                name = contact["name"]
        due = p.get("due_date")
        when = ""
        if due:
            days = (date.fromisoformat(due) - today).days
            when = f"{-days} din overdue" if days < 0 else ("aaj due" if days == 0 else f"{days} din baaki")
        lines.append(f"• {name}: ₹{p.get('amount')} — {when}")
    return "\n".join(lines)


async def check_payment_reminders() -> int:
    if not settings.PAYMENT_REMINDERS_ENABLED:
        return 0
    today = datetime.now(IST).date()
    cutoff = (today + timedelta(days=3)).isoformat()
    due = await payment_repo.get_due_for_reminders(cutoff)

    # Group by business, skipping payments already reminded today.
    by_business: dict = {}
    for p in due:
        last = p.get("last_reminder_sent")
        if last and last[:10] == today.isoformat():
            continue
        by_business.setdefault(p["business_id"], []).append(p)

    reminded = 0
    for business_id, payments in by_business.items():
        biz = await business_repo.get_by_id(business_id)
        if not biz or not biz.get("phone_number"):
            continue
        text = await _reminder_text(payments, today)
        try:
            await send_text(biz["phone_number"], text)
            for p in payments:
                await payment_repo.mark_reminded(p["id"], p.get("reminder_count", 0))
            reminded += 1
        except Exception:
            logger.error("reminder_send_failed", extra={"business_id": business_id})
    logger.info("payment_reminders_done", extra={"reminded": reminded})
    return reminded


# --- scheduler ---------------------------------------------------------------

def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)
    scheduler.add_job(daily_summary, CronTrigger(hour=20, minute=0), id="daily_summary", replace_existing=True)
    scheduler.add_job(check_payment_reminders, CronTrigger(hour=9, minute=0), id="payment_reminders", replace_existing=True)
    scheduler.add_job(expire_confirmations, CronTrigger(minute=0), id="expire_confirmations", replace_existing=True)
    scheduler.start()
    logger.info("scheduler_started", extra={"jobs": [j.id for j in scheduler.get_jobs()]})
    return scheduler
