from fastapi import APIRouter
from starlette.responses import JSONResponse
import asyncio
from typing import Dict, Any

router = APIRouter()

# 探针超时：只要 2.5 秒仍无结果即判定 unhealthy，不做重试。
DB_PROBE_TIMEOUT_SECONDS = 2.5


def _db_alias() -> str:
    """数据库连接别名：与 Tortoise 配置的 default_connection 保持单一来源。"""
    from base.common.setting import TORTOISE_ORM
    return TORTOISE_ORM["apps"]["models"]["default_connection"]


async def check_database() -> Dict[str, Any]:
    alias = ""
    try:
        from tortoise import Tortoise
        alias = _db_alias()
        connection = Tortoise.get_connection(alias)
        if connection is None:
            return {"status": "unhealthy", "message": f"No database connection ({alias})"}
        rows = await asyncio.wait_for(
            connection.execute_query_dict("SELECT 1 AS ok"),
            timeout=DB_PROBE_TIMEOUT_SECONDS,
        )
        return {
            "status": "healthy",
            "message": f"Database connection OK ({alias}): SELECT 1 -> {rows}",
        }
    except asyncio.TimeoutError:
        return {
            "status": "unhealthy",
            "message": (
                f"Database probe timeout after {DB_PROBE_TIMEOUT_SECONDS}s "
                f"(alias={alias or 'unknown'})"
            ),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database probe failed (alias={alias or 'unknown'}): {type(e).__name__}: {e}",
        }


async def check_redis() -> Dict[str, Any]:
    from base.common.setting import settings
    if not settings.REDIS_ENABLED:
        return {"status": "skipped", "message": "Redis not enabled"}
    
    try:
        from redis.asyncio import Redis
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB
        )
        await redis.ping()
        await redis.close()
        return {"status": "healthy", "message": "Redis connection OK"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


async def check_qdrant() -> Dict[str, Any]:
    from base.common.setting import settings
    if not settings.QDRANT_ENABLED:
        return {"status": "skipped", "message": "Qdrant not enabled"}
    
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(
            url=settings.QDRANT_HOST,
            api_key=settings.QDRANT_API_KEY,
            timeout=settings.QDRANT_TIMEOUT
        )
        client.get_collections()
        return {"status": "healthy", "message": "Qdrant connection OK"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


@router.get("/health")
async def health_check():
    checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_qdrant()
    )
    
    overall_status = "healthy" if all(c["status"] in ["healthy", "skipped"] for c in checks) else "unhealthy"
    
    return JSONResponse({
        "status": overall_status,
        "checks": {
            "database": checks[0],
            "redis": checks[1],
            "qdrant": checks[2]
        },
        "timestamp": asyncio.get_event_loop().time()
    })


@router.get("/health/live")
async def liveness_check():
    return JSONResponse({"status": "alive"})


@router.get("/health/ready")
async def readiness_check():
    checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_qdrant()
    )
    
    ready = all(c["status"] in ["healthy", "skipped"] for c in checks)
    
    if ready:
        return JSONResponse({"status": "ready"}, status_code=200)
    else:
        return JSONResponse({"status": "not_ready", "checks": checks}, status_code=503)