"""FastAPI application entry point for BusinessOS."""
from fastapi import FastAPI

from app.api import health, webhook

app = FastAPI(title="BusinessOS", version="0.1.0")

app.include_router(health.router)
app.include_router(webhook.router)


@app.get("/")
async def root():
    return {"service": "BusinessOS", "status": "running"}
