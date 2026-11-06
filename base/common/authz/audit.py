"""
F8 越权审计与限流

溯源：
- docs/arch/04 §F8：越权 → 404（不暴露存在性）+ 审计(warn)；同主体 1 分钟 >10 次 → 限流 + 审计 alert
- docs/arch/05 §2.1 配套：越权尝试全量审计（warn）
- R-12：日志必带 trace_id/owner；审计复用现有 audit 通道（base.plugins.audit AuditLog）
- Redis 计数 key 规范：rl:{scene}:{identity}

降级（docs/arch/05 §1.1）：Redis 不可用时退化为进程内计数（单实例私有化部署可接受），
审计写入失败仅打日志，绝不阻断业务请求。
"""
import time
from typing import Dict, Optional, Tuple

from loguru import logger

from base.common.cache import RedisCache
from base.common.context import get_current_trace_id
from .constants import (
    RL_SCENE_AUTHZ_404,
    RL_WINDOW_SECONDS,
    RL_THRESHOLD,
    RL_BLOCK_SECONDS,
    rl_key,
    rl_block_key,
)

# 进程内降级计数器：{key: (count, expire_ts)}
_memory_counters: Dict[str, Tuple[int, float]] = {}
# 进程内降级封禁标记：{key: expire_ts}
_memory_blocks: Dict[str, float] = {}


async def _incr_counter(key: str, window_seconds: int) -> int:
    """窗口计数 +1（Redis INCR/EXPIRE；Redis 不可用退化进程内计数）"""
    if RedisCache.is_enabled():
        cache = await RedisCache.get_instance()
        # D2 修复：走封装方法（硬超时+熔断），失败返回 None 退化进程内计数
        count = await cache.incr(key, expire=window_seconds)
        if count is not None:
            return count
        logger.warning("[authz] Redis 计数失败，退化进程内计数")

    now = time.monotonic()
    count, expire_ts = _memory_counters.get(key, (0, 0.0))
    if now > expire_ts:
        count, expire_ts = 0, now + window_seconds
    count += 1
    _memory_counters[key] = (count, expire_ts)
    return count


async def _set_block(key: str, block_seconds: int) -> None:
    if RedisCache.is_enabled():
        cache = await RedisCache.get_instance()
        # D2 修复：走封装方法（硬超时+熔断）
        if await cache.set(key, "1", block_seconds):
            return
        logger.warning("[authz] Redis 封禁标记写入失败，退化进程内标记")
    _memory_blocks[key] = time.monotonic() + block_seconds


async def is_rate_limited(identity: str, scene: str = RL_SCENE_AUTHZ_404) -> bool:
    """限流闸门：主体是否处于越权限流封禁期"""
    key = rl_block_key(scene, identity)
    if RedisCache.is_enabled():
        try:
            cache = await RedisCache.get_instance()
            # D2 修复：走封装方法（硬超时+熔断），不直连 _client（死连接写路径会绕过 socket_timeout 挂起）
            return bool(await cache.exists(key))
        except Exception:
            pass
    expire_ts = _memory_blocks.get(key, 0.0)
    if time.monotonic() < expire_ts:
        return True
    _memory_blocks.pop(key, None)
    return False


async def _write_audit(
    *,
    level: str,
    operation: str,
    owner_identity: Optional[str],
    path: str,
    method: str,
    error_message: str,
    request_params: Optional[dict] = None,
) -> None:
    """审计落库（复用 audit 插件通道；失败仅记日志，不阻断请求）"""
    try:
        from base.plugins.audit.models.audit_log import AuditLog

        owner_type, owner_id = None, None
        if owner_identity and ":" in owner_identity:
            owner_type, owner_id = owner_identity.split(":", 1)

        await AuditLog.create(
            trace_id=get_current_trace_id(),
            user_id=int(owner_id) if owner_id and owner_id.isdigit() else None,
            username=owner_identity,
            module="authz",
            operation=operation,
            method=method,
            path=path[:500],
            request_params=request_params,
            status_code=404 if level == "warning" else 429,
            error_message=error_message,
            level=level,
        )
    except Exception as e:
        # 审计失败不阻断业务（05 §1.1 降级精神），但必须留有日志痕迹
        logger.error(f"[authz] 越权审计写入失败: {e}")


async def record_violation(
    owner_identity: Optional[str],
    *,
    path: str,
    method: str = "GET",
    resource_hint: Optional[str] = None,
    scene: str = RL_SCENE_AUTHZ_404,
) -> None:
    """
    记录一次 404 越权访问（L2 过滤器在"资源存在但归属不匹配"时调用）

    - 审计 warn（含 path/owner/trace_id，R-12）
    - 窗口计数 +1；超过阈值（1 分钟 >10 次）→ 限流封禁 + 审计 alert
    """
    identity = owner_identity or "anon"
    trace_id = get_current_trace_id()

    logger.warning(
        "[authz] 越权访问拒绝(404) identity={} path={} method={} resource={} trace_id={}",
        identity, path, method, resource_hint or "-", trace_id,
    )
    await _write_audit(
        level="warning",
        operation="authz.violation",
        owner_identity=identity,
        path=path,
        method=method,
        error_message=f"越权访问拒绝: resource={resource_hint or '-'}",
    )

    count = await _incr_counter(rl_key(scene, identity), RL_WINDOW_SECONDS)
    if count > RL_THRESHOLD:
        await _set_block(rl_block_key(scene, identity), RL_BLOCK_SECONDS)
        logger.error(
            "[authz] 高频越权限流触发 identity={} count={}/{}s trace_id={}",
            identity, count, RL_WINDOW_SECONDS, trace_id,
        )
        await _write_audit(
            level="critical",
            operation="authz.rate_limit_alert",
            owner_identity=identity,
            path=path,
            method=method,
            error_message=(
                f"同主体 {RL_WINDOW_SECONDS}s 内 404 越权 {count} 次（阈值 {RL_THRESHOLD}），"
                f"已限流封禁 {RL_BLOCK_SECONDS}s"
            ),
            request_params={"count": count, "window_seconds": RL_WINDOW_SECONDS},
        )


async def record_rate_limited_hit(
    owner_identity: Optional[str],
    *,
    path: str,
    method: str = "GET",
) -> None:
    """封禁期内的请求被 429 拒绝时留痕（info 级，避免封禁期刷 critical）"""
    logger.info(
        "[authz] 限流封禁中请求拒绝(429) identity={} path={} trace_id={}",
        owner_identity, path, get_current_trace_id(),
    )
