"""taskiq beat / worker 探活脚本（compose healthcheck 调用）。

用法：
    python base/common/taskiq_app/health.py beat
    python base/common/taskiq_app/health.py worker
退出码 0 = 健康，1 = 不健康。

beat：PG 可达 + Redis 心跳键 `ap:taskiq:beat:heartbeat` 未过期。
worker：RabbitMQ 可达 + Redis 心跳键 `ap:taskiq:worker:heartbeat` 未过期。

taskiq 不提供 HTTP 端口 / `inspect ping` 等价物（R15），故用轻量脚本。
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

# 让脚本既能被 `python <path>/health.py` 直接运行，也能被包导入：
# 把项目根加入 sys.path，使 `base.common.taskiq_app.config` 等绝对导入可解析。
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from loguru import logger  # noqa: E402

from base.common.taskiq_app.config import settings  # noqa: E402

_HEARTBEAT_THRESHOLD = 30.0


def _heartbeat_age(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return time.time() - float(raw)
    except (TypeError, ValueError):
        return None


async def _check_pg() -> bool:
    if not settings.db_url:
        logger.error("TASKIQ_DB_URL 未配置，PG 检查跳过（判不健康）")
        return False
    try:
        import asyncpg

        conn = await asyncio.wait_for(asyncpg.connect(settings.db_url), timeout=5)
        await conn.close()
        return True
    except Exception as exc:
        logger.error(f"PG 不可达: {exc}")
        return False


async def _check_mq() -> bool:
    if not settings.broker_url:
        logger.error("TASKIQ_BROKER_URL 未配置，MQ 检查跳过（判不健康）")
        return False
    try:
        from aio_pika import connect_robust

        conn = await asyncio.wait_for(connect_robust(settings.broker_url), timeout=5)
        await conn.close()
        return True
    except Exception as exc:
        logger.error(f"RabbitMQ 不可达: {exc}")
        return False


async def _check_redis_heartbeat(key: str) -> bool:
    try:
        from base.common.cache import RedisCache

        rc = await RedisCache.get_instance()
        val = await rc.get(key)
        age = _heartbeat_age(val)
        if age is None:
            logger.error(f"心跳键 {key} 不存在")
            return False
        if age > _HEARTBEAT_THRESHOLD:
            logger.error(f"心跳键 {key} 过期 age={age:.1f}s")
            return False
        return True
    except Exception as exc:
        logger.error(f"Redis 心跳检查失败: {exc}")
        return False


async def _main(mode: str) -> bool:
    if mode == "beat":
        pg = await _check_pg()
        hb = await _check_redis_heartbeat(f"{settings.redis_key_prefix}beat:heartbeat")
        return pg and hb
    if mode == "worker":
        mq = await _check_mq()
        hb = await _check_redis_heartbeat(f"{settings.redis_key_prefix}worker:heartbeat")
        return mq and hb
    logger.error(f"未知模式 {mode!r}（应为 beat / worker）")
    return False


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "beat"
    ok = asyncio.run(_main(mode))
    sys.exit(0 if ok else 1)
