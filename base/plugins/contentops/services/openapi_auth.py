"""ContentOps 对外 OpenAPI 鉴权依赖（M4，fail-closed）。

校验链：Key ID/secret 提取 → 状态/过期 → SHA-256 常量时间比对 → IP 白名单
→ scope 校验 → RPM 限流（Redis，降级进程内计数）→ 审计留痕。

与登录态路由物理隔离：本依赖不读 JWT、不走 require_owner；
外部调用绑定的 CUS 租户归属由 API Key 记录提供，构造 OwnerContext 供归属过滤复用。
"""
import time
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status
from loguru import logger

from base.common.authz.context import OwnerContext
from base.common.cache import RedisCache
from base.common.context import get_current_trace_id
from base.plugins.contentops.models import ContentopsApiKey
from base.plugins.contentops.services.api_key_service import (
    ContentopsApiKeyService,
)

# 进程内限流降级计数（Redis 不可用时）
_mem_counters: Dict[str, Tuple[int, float]] = {}

RL_WINDOW = 60  # 秒


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _extract_credentials(request: Request) -> Tuple[str, str]:
    """支持 X-ContentOps-Key-Id/X-ContentOps-Secret 与 Bearer <key_id>.<secret>。"""
    kid = request.headers.get("X-ContentOps-Key-Id")
    secret = request.headers.get("X-ContentOps-Secret")
    if kid and secret:
        return kid, secret
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if token and "." in token:
        return token.split(".", 1)
    return "", ""


async def _rate_limit_ok(record: ContentopsApiKey) -> bool:
    """RPM 限流：0=不限；Redis INCR 优先，失败退化进程内。"""
    limit = record.rate_limit_rpm or 0
    if limit <= 0:
        return True
    key = f"rl:contentops_openapi:{record.key_id}"
    if RedisCache.is_enabled():
        try:
            cache = await RedisCache.get_instance()
            count = await cache.incr(key, expire=RL_WINDOW)
            if count is not None:
                return count <= limit
            logger.warning("[contentops-openapi] Redis 计数失败，退化进程内限流")
        except Exception as e:
            logger.warning(f"[contentops-openapi] Redis 限流异常: {e}")
    now = time.monotonic()
    count, expire_ts = _mem_counters.get(key, (0, 0.0))
    if now > expire_ts:
        count, expire_ts = 0, now + RL_WINDOW
    count += 1
    _mem_counters[key] = (count, expire_ts)
    return count <= limit


async def _audit(
    record: Optional[ContentopsApiKey],
    request: Request,
    outcome: str,
    detail: str,
) -> None:
    """审计留痕（复用 audit 插件通道；失败仅记日志，绝不阻断）。"""
    try:
        from base.common.plugin_symbol import resolve_plugin_symbol
        AuditLog = resolve_plugin_symbol("base.plugins.audit.models.audit_log.AuditLog")
        key_id = record.key_id if record else (_extract_credentials(request)[0] or "anon")
        await AuditLog.create(
            trace_id=get_current_trace_id(),
            username=f"apikey:{key_id}",
            module="contentops_openapi",
            operation=f"contentops.openapi.{outcome}",
            method=request.method,
            path=request.url.path[:500],
            status_code=401 if outcome == "auth_reject" else (429 if outcome == "rate_limit" else 200),
            error_message=detail,
            level="warning" if outcome in ("auth_reject", "rate_limit") else "info",
        )
    except Exception as e:
        logger.error(f"[contentops-openapi] 审计写入失败: {e}")


def require_openapi_scope(required: str):
    """构造带 scope 校验的对外鉴权依赖（工厂函数）。

    用法：
        @router.post("/compliance/check")
        async def ep(ctx=Depends(require_openapi_scope("compliance:check"))): ...
    """
    async def dependency(request: Request) -> Dict[str, object]:
        key_id, secret = _extract_credentials(request)
        record = None
        if key_id and secret:
            record = await ContentopsApiKeyService.verify(key_id, secret)

        if record is None:
            await _audit(None, request, "auth_reject", "无效 API Key 凭据")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的 API Key 凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )

        allowed_ips = record.allowed_ips or []
        if allowed_ips and _client_ip(request) not in allowed_ips:
            await _audit(record, request, "auth_reject", "来源 IP 不在白名单")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="来源 IP 不在白名单")

        if required not in (record.scopes or []):
            await _audit(record, request, "auth_reject", f"缺少 scope: {required}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API Key 无此权限")

        if not await _rate_limit_ok(record):
            await _audit(record, request, "rate_limit", f"超过 {record.rate_limit_rpm} RPM")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求频率超限",
            )

        await ContentopsApiKeyService.touch(record)
        # 外部调用绑定 CUS 归属，供归属过滤复用（平台级 + 本租户）
        owner = OwnerContext(owner_type=record.owner_type, owner_id=record.owner_id)
        request.state.contentops_api_key = record
        return {"api_key": record, "owner": owner, "key_id": record.key_id}

    return dependency


# 默认依赖别名（兼容直接 Depends 使用）
require_contentops_api_key = require_openapi_scope
