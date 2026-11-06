from fastapi import APIRouter
from starlette.responses import JSONResponse
import asyncio
from typing import Dict, Any

router = APIRouter()


async def check_database() -> Dict[str, Any]:
    try:
        from tortoise import Tortoise
        if Tortoise.get_connection("default"):
            return {"status": "healthy", "message": "Database connection OK"}
        return {"status": "unhealthy", "message": "No database connection"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


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