'''
Cloud health endpoint (P04).

GET /healthz proves the Cloud HTTP process is alive: it always returns 200 while the process
can serve a request. PostgreSQL/Redis reachability is additionally reported as informational
fields, per P04's instruction to keep this simple (not a full health-check framework) and to
stay Kubernetes liveness/readiness friendly -- a transient DB/Redis outage should not fail the
liveness probe and cause a restart loop that cannot fix an external dependency being down.
'''
import redis
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.cloud.config import (
    DB_CONFIG,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_USERNAME,
    REDIS_PASSWORD,
    REDIS_DB,
)
from src.common.logging_setup import get_logger

logger = get_logger("cloud_health")


def _check_postgres() -> str:
    '''Best-effort PostgreSQL reachability check. Never raises.'''
    try:
        session = DB_CONFIG.get_db_session()
        try:
            session.execute(text("SELECT 1"))
            return "ok"
        finally:
            session.close()
    except Exception:
        logger.error("postgres health check failed", exc_info=True)
        return "unreachable"


def _check_redis() -> str:
    '''Best-effort Redis reachability check. Never raises.'''
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            socket_connect_timeout=2,
        )
        client.ping()
        return "ok"
    except Exception:
        logger.error("redis health check failed", exc_info=True)
        return "unreachable"


async def healthz() -> JSONResponse:
    '''Kubernetes liveness/readiness endpoint for the Cloud server.'''
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "postgres": _check_postgres(),
            "redis": _check_redis(),
        },
    )
