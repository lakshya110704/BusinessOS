"""FastAPI application entry point for BusinessOS."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, webhook
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("startup", extra={"event": "app_startup", "environment": settings.ENVIRONMENT})
    scheduler = None
    try:
        from app.scheduler.jobs import start_scheduler
        scheduler = start_scheduler()
    except Exception:
        logger.exception("scheduler_start_failed")
    yield
    # Shutdown
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    logger.info("shutdown", extra={"event": "app_shutdown"})


app = FastAPI(title="BusinessOS", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(webhook.router)


@app.get("/")
async def root():
    return {"service": "BusinessOS", "status": "running"}
