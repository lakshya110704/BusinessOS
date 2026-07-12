"""Health check endpoint — Railway probes this path.

Reports dependency status. Supabase + Redis are critical (a failure → 503 so the
platform can react); the OpenAI key is reported but not treated as fatal. Each probe
does a lightweight round-trip, so keep the health-check interval reasonable.
"""
from fastapi import APIRouter, Response

from app.config import settings
from app.db.supabase_client import get_supabase
from app.queue.redis_client import get_redis

router = APIRouter()


async def _check_supabase() -> bool:
    try:
        client = await get_supabase()
        await client.table("businesses").select("id").limit(1).execute()
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    try:
        await get_redis().ping()
        return True
    except Exception:
        return False


@router.get("/health")
async def health(response: Response):
    checks = {
        "supabase": await _check_supabase(),
        "redis": await _check_redis(),
        "openai_key": bool(settings.OPENAI_API_KEY),
    }
    critical_ok = checks["supabase"] and checks["redis"]
    if not critical_ok:
        response.status_code = 503
    return {"status": "ok" if critical_ok else "degraded", "checks": checks}
