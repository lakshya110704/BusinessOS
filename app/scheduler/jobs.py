"""Scheduled jobs.

expire_confirmations() marks pending confirmations older than 24h as expired, so
a never-answered confirmation doesn't sit pending forever. Wire it to a scheduler
(APScheduler / cron) in LAK-21; it's a plain callable so it can also be run by hand.
"""
from __future__ import annotations

from app.db.repositories import pending_confirmation_repo as repo
from app.utils.logger import get_logger

logger = get_logger("scheduler")


async def expire_confirmations() -> int:
    count = await repo.expire_old()
    logger.info("expired_confirmations", extra={"count": count})
    return count
