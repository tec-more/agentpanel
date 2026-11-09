"""L3 编排健康探针（与 L2 `/health/health` 同形，依赖来自环境变量配置）。"""
import asyncio
from typing import Any, Dict

from fastapi import APIRouter
from starlette.responses import JSONResponse

from packages.common.config import L3CommonConfig

router = APIRouter()

DB_PROBE_TIMEOUT_SECONDS = 2.5
DB_ALIAS = "postgres"

_common_config: L3CommonConfig | None = None


def init_health(config: L3CommonConfig) -> None:
    global _common_config
    _common_config = config


async def check_database() -> Dict[str, Any]:
    alias = DB_ALIAS
    try:
        from tortoise import Tortoise

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
    if _common_config is None:
        return {"status": "unhealthy", "message": "Redis config not initialized"}
    redis_cfg = _common_config.redis
    if not redis_cfg.enabled:
        return {"status": "skipped", "message": "Redis not enabled"}
    try:
        from redis.asyncio import Redis

        redis = Redis(
            host=redis_cfg.host,
            port=redis_cfg.port,
            password=redis_cfg.password,
            db=redis_cfg.db,
        )
        await redis.ping()
        await redis.aclose()
        return {"status": "healthy", "message": "Redis connection OK"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


async def check_qdrant() -> Dict[str, Any]:
    """编排服务不使用向量库；保留该子项以维持响应契约形状。"""
    return {"status": "skipped", "message": "Qdrant not used by l3-orchestration"}


@router.get("/health")
async def health_check():
    checks = await asyncio.gather(check_database(), check_redis(), check_qdrant())
    overall_status = (
        "healthy" if all(c["status"] in ["healthy", "skipped"] for c in checks) else "unhealthy"
    )
    return JSONResponse(
        {
            "status": overall_status,
            "checks": {
                "database": checks[0],
                "redis": checks[1],
                "qdrant": checks[2],
            },
            "timestamp": asyncio.get_event_loop().time(),
        }
    )


@router.get("/health/live")
async def liveness_check():
    return JSONResponse({"status": "alive"})


@router.get("/health/ready")
async def readiness_check():
    checks = await asyncio.gather(check_database(), check_redis(), check_qdrant())
    ready = all(c["status"] in ["healthy", "skipped"] for c in checks)
    if ready:
        return JSONResponse({"status": "ready"}, status_code=200)
    return JSONResponse({"status": "not_ready", "checks": checks}, status_code=503)
