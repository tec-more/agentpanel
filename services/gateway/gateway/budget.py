"""网关额度预检与流式看门狗（共享存储：Redis 优先、DB 兜底）

设计要点：
- 预检与扣减必须是跨进程共享的：Redis 用单个 Lua 脚本完成“双校验 + 预占”，
  Redis 不可用时用 DB 事务 + 行锁（quota_account / harness_gateway_budget）；
- 进程内不保存任何额度或并发计数，避免多副本各算一份；
- 已发给 provider 的 token 无法收回，截断只限制超支幅度，不承诺零超支；
- 本模块只负责额度与并发，不写 usage_record（记账仍由 gateway.service 负责）。
"""
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from tortoise.transactions import in_transaction

from packages.agentpanel_common.cache import RedisCache
from .runtime import gateway_config
from packages.agentpanel_common.quota.metrics import inc_gateway_quota_reject, inc_gateway_quota_truncate
from packages.agentpanel_common.models.quota import QuotaAccount
from packages.agentpanel_common.quota.services.plan_service import PlanService
from packages.agentpanel_common.quota.services.quota_service import (
    ACTIVE_OWNERS_KEY,
    QuotaService,
    current_period,
    month_bounds,
)

CONC_WATCHDOG_SECONDS = 60
LEASE_KEY_TTL_FALLBACK = 86400

# Redis 预检：租约预算与租户配额双校验，超限不写入任何计数。
# KEYS: lease hash / owner used / owner held
# ARGV: lease budget(0=不限) / owner limit(0=不限) / reserve / ttl
# 返回: {ok, reason(0/1=lease/2=owner), used, reserved, limit}
_LUA_GRANT = """
local lb = tonumber(ARGV[1])
local ol = tonumber(ARGV[2])
local amt = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local lused = tonumber(redis.call('HGET', KEYS[1], 'used') or '0')
local lres = tonumber(redis.call('HGET', KEYS[1], 'reserved') or '0')
local oused = tonumber(redis.call('GET', KEYS[2]) or '0')
local oheld = tonumber(redis.call('GET', KEYS[3]) or '0')
if lb > 0 and (lused + lres + amt) > lb then
  return {0, 1, lused, lres, lb}
end
if ol > 0 and (oused + oheld + amt) > ol then
  return {0, 2, oused, oheld, ol}
end
redis.call('HINCRBYFLOAT', KEYS[1], 'reserved', amt)
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('INCRBYFLOAT', KEYS[3], amt)
redis.call('EXPIRE', KEYS[3], ttl)
return {1, 0, lused, lres + amt, lb}
"""

# 结算：reserved → used，held → used，并累计请求/截断计数
# ARGV: reserved / actual / ttl / inc_requests(1/0) / truncated(1/0) / over_budget(1/0) / owner marker
_LUA_SETTLE = """
local res = tonumber(ARGV[1])
local act = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local lres = math.max(tonumber(redis.call('HGET', KEYS[1], 'reserved') or '0') - res, 0)
local lused = tonumber(redis.call('HGET', KEYS[1], 'used') or '0') + act
redis.call('HSET', KEYS[1], 'reserved', tostring(lres))
redis.call('HSET', KEYS[1], 'used', tostring(lused))
if tonumber(ARGV[4]) == 1 then redis.call('HINCRBY', KEYS[1], 'requests', 1) end
if tonumber(ARGV[5]) == 1 then redis.call('HINCRBY', KEYS[1], 'truncated', 1) end
if tonumber(ARGV[6]) == 1 then redis.call('HINCRBY', KEYS[1], 'over_budget', 1) end
redis.call('EXPIRE', KEYS[1], ttl)
local oheld = math.max(tonumber(redis.call('GET', KEYS[3]) or '0') - res, 0)
redis.call('SET', KEYS[3], tostring(oheld), 'EX', ttl)
local oused = tonumber(redis.call('GET', KEYS[2]) or '0') + act
redis.call('SET', KEYS[2], tostring(oused), 'EX', ttl)
redis.call('SADD', 'quota_active_owners', ARGV[7])
return {lused, lres, oused}
"""

# 释放：预占回退（异常/上游失败路径）
_LUA_RELEASE = """
local res = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local lres = math.max(tonumber(redis.call('HGET', KEYS[1], 'reserved') or '0') - res, 0)
redis.call('HSET', KEYS[1], 'reserved', tostring(lres))
redis.call('EXPIRE', KEYS[1], ttl)
local oheld = math.max(tonumber(redis.call('GET', KEYS[3]) or '0') - res, 0)
redis.call('SET', KEYS[3], tostring(oheld), 'EX', ttl)
return {lres, oheld}
"""


class GatewayQuotaError(Exception):
    """入口预检拒绝（携带可直接返回客户端的错误码与上下文）"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail or {}


@dataclass
class BudgetGrant:
    """一次请求的额度授权（预占量 + 输出上限 + 并发槽）"""

    lease_id: str
    owner_type: Optional[str]
    owner_id: Optional[int]
    prompt_tokens: int
    output_allowance: int
    reserved_tokens: int
    limit_tokens: int
    budget_tokens: float
    owner_limit: float
    backend: str
    concurrency_held: bool = False
    unlimited: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OwnerQuota:
    owner_type: Optional[str]
    owner_id: Optional[int]
    limit: float
    period: str
    used_seed: float
    status: str = "active"


def _to_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _chars(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(_chars(item) for item in value)
    if isinstance(value, dict):
        return sum(_chars(value.get(key)) for key in ("content", "text", "arguments"))
    return 0


def estimate_prompt_tokens(body: Dict[str, Any]) -> int:
    """按字符估算输入 token（宁高不低，避免低估导致超支）。"""
    ratio = max(float(gateway_config().get("estimate_chars_per_token") or 2.0), 0.5)
    chars = 0
    messages = body.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict):
                chars += _chars(message.get("content"))
                chars += _chars(message.get("tool_calls"))
    chars += _chars(body.get("prompt"))
    return max(int(math.ceil(chars / ratio)), 0)


def request_output_limit(body: Dict[str, Any], cap: int) -> int:
    """请求声明的输出上限（未声明时取配置上限）。"""
    raw = body.get("max_completion_tokens")
    if raw is None:
        raw = body.get("max_tokens")
    if raw is None:
        return cap
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return cap
    if value <= 0:
        return cap
    return min(value, cap)


def apply_request_caps(body: Dict[str, Any], grant: BudgetGrant) -> Dict[str, Any]:
    """把请求输出上限夹紧到本次额度允许量（provider 侧同步受限）。"""
    value = int(grant.output_allowance)
    if "max_completion_tokens" in body:
        body["max_completion_tokens"] = min(int(body.get("max_completion_tokens") or value), value)
    if "max_tokens" in body or "max_completion_tokens" not in body:
        body["max_tokens"] = min(int(body.get("max_tokens") or value), value)
    return body


def estimate_completion_tokens(chars: int) -> int:
    ratio = max(float(gateway_config().get("estimate_chars_per_token") or 2.0), 0.5)
    return int(math.ceil(max(chars, 0) / ratio))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_stale(value: Optional[datetime], seconds: int) -> bool:
    """DB 时间戳过期判断；统一按 UTC 比较，避免 use_tz 下永远判定过期。"""
    if value is None:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).total_seconds() > seconds


def _lease_budget(lease: Any) -> float:
    meta = getattr(lease, "meta", None) or {}
    value = meta.get("budget_tokens")
    if value is None:
        value = gateway_config().get("lease_budget_tokens") or 0
    try:
        return max(float(value or 0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _owner_key_parts(lease: Any) -> tuple[Optional[str], Optional[int]]:
    owner_type = getattr(lease, "owner_type", None)
    owner_id = getattr(lease, "owner_id", None)
    if not owner_type or owner_id is None:
        return None, None
    return str(owner_type), int(owner_id)


def _period_ttl(period: str) -> int:
    now = _now()
    start, end = month_bounds(now)
    if period != current_period(now):
        return max(int((end - now).total_seconds()), 1)
    return max(int((end - now).total_seconds()), 1)


class GatewayBudgetService:
    """入口预检 / 原子预占 / 结算 / 快照 / 自动吊销"""

    # ---------------- Redis 基础设施 ----------------
    @staticmethod
    def _lease_key(lease_id: str) -> str:
        return f"gw:budget:lease:{lease_id}"

    @staticmethod
    def _conc_key(owner_type: str, owner_id: int) -> str:
        return f"gw:conc:{owner_type}:{owner_id}"

    @staticmethod
    async def _redis():
        try:
            cache = await RedisCache.get_instance()
            if RedisCache.is_enabled():
                return cache._client  # noqa: SLF001（项目既有用法）
            return None
        except Exception as exc:
            logger.warning(f"[gateway-budget] Redis 不可用，走 DB 兜底: {exc}")
            return None

    @staticmethod
    def _used_key(owner_type: str, owner_id: int, period: str) -> str:
        return QuotaService._used_key(owner_type, owner_id, "token", period)

    @staticmethod
    def _held_key(owner_type: str, owner_id: int, period: str) -> str:
        return QuotaService._held_key(owner_type, owner_id, "token", period)

    @classmethod
    def _owner_keys(cls, owner_type: Optional[str], owner_id: Optional[int],
                    period: str, lease_id: str) -> tuple[str, str]:
        """无配额主体时用租约私有 key，避免不同租约互相干扰。"""
        if owner_type is None:
            key = f"gw:none:{lease_id}"
            return key, key
        return cls._used_key(owner_type, owner_id, period), cls._held_key(owner_type, owner_id, period)

    # ---------------- 租户配额解析 ----------------
    @classmethod
    async def _resolve_owner(cls, lease: Any, *, ensure: bool = True) -> OwnerQuota:
        owner_type, owner_id = _owner_key_parts(lease)
        period = current_period()
        if owner_type is None:
            return OwnerQuota(None, None, 0.0, period, 0.0)
        plan = await PlanService.resolve_plan(owner_type, owner_id)
        limit = 0.0
        if plan is not None:
            limit = max(float((plan.quota_items or {}).get("token", 0) or 0), 0.0)
        if ensure:
            account = await QuotaService.ensure_account(owner_type, owner_id)
        else:
            account = await QuotaAccount.get_or_none(owner_type=owner_type, owner_id=owner_id)
        status = getattr(account, "status", "active") or "active"
        used_seed = float(((account.used if account else {}) or {}).get("token", 0) or 0)
        return OwnerQuota(owner_type, owner_id, limit, period, used_seed, status)

    # ---------------- 预检入口 ----------------
    @classmethod
    async def grant(cls, lease: Any, body: Dict[str, Any]) -> BudgetGrant:
        cfg = gateway_config()
        prompt = estimate_prompt_tokens(body)
        cap = int(cfg.get("max_output_tokens_per_request") or 4096)
        requested = request_output_limit(body, cap)
        min_allow = int(cfg.get("min_output_allowance_tokens") or 1)
        budget = _lease_budget(lease)
        owner = await cls._resolve_owner(lease)
        if owner.status != "active":
            raise GatewayQuotaError(
                403,
                "quota.account_frozen",
                "配额账户已停用，网关拒绝转发",
                {"lease_id": lease.lease_id, "owner_type": owner.owner_type, "owner_id": owner.owner_id},
            )

        redis = await cls._redis()
        if redis is not None:
            try:
                return await cls._grant_redis(
                    redis, lease, owner, budget, prompt, cap, requested, min_allow
                )
            except GatewayQuotaError:
                raise
            except Exception as exc:
                logger.warning(f"[gateway-budget] Redis 预检异常，降级 DB: {exc}")
        return await cls._grant_db(lease, owner, budget, prompt, cap, requested, min_allow)

    @classmethod
    def _remaining(cls, budget: float, used: float, reserved: float,
                   owner_limit: float, owner_used: float, owner_held: float) -> Optional[float]:
        remaining: Optional[float] = None
        if budget > 0:
            remaining = budget - used - reserved
        if owner_limit > 0:
            owner_remaining = owner_limit - owner_used - owner_held
            remaining = owner_remaining if remaining is None else min(remaining, owner_remaining)
        return remaining

    @classmethod
    def _deny(cls, lease: Any, reason: str, remaining: float, requested: float, budget: float,
              owner: OwnerQuota) -> GatewayQuotaError:
        if reason == "lease":
            return GatewayQuotaError(
                402,
                "quota.lease_budget_exhausted",
                "租约 token 预算不足，网关拒绝转发",
                {
                    "lease_id": lease.lease_id,
                    "resource": "token",
                    "remaining": max(remaining, 0),
                    "requested": requested,
                    "budget_tokens": budget,
                },
            )
        return GatewayQuotaError(
            402,
            "quota.balance_insufficient",
            "租户/组织账户余额不足，网关拒绝转发",
            {
                "lease_id": lease.lease_id,
                "resource": "token",
                "remaining": max(remaining, 0),
                "requested": requested,
                "owner_type": owner.owner_type,
                "owner_id": owner.owner_id,
                "owner_limit": owner.limit,
            },
        )

    @classmethod
    async def _grant_redis(cls, redis, lease, owner: OwnerQuota, budget: float,
                           prompt: int, cap: int, requested: int, min_allow: int) -> BudgetGrant:
        cfg = gateway_config()
        ttl = int(cfg.get("gateway_quota_ttl_seconds") or LEASE_KEY_TTL_FALLBACK)
        lease_key = cls._lease_key(lease.lease_id)
        if not await redis.exists(lease_key):
            await redis.hset(lease_key, mapping={
                "budget": str(budget),
                "used": "0",
                "reserved": "0",
                "requests": "0",
                "rejected": "0",
                "truncated": "0",
                "over_budget": "0",
            })
            await redis.expire(lease_key, ttl)
        elif budget > 0:
            await redis.hset(lease_key, "budget", str(budget))

        owner_used = 0.0
        owner_held = 0.0
        used_key, held_key = cls._owner_keys(owner.owner_type, owner.owner_id, owner.period, lease.lease_id)
        if owner.owner_type is not None:
            if not await redis.exists(used_key):
                await redis.set(used_key, owner.used_seed, ex=_period_ttl(owner.period))
            owner_used = _to_num(await redis.get(used_key))
            owner_held = _to_num(await redis.get(held_key))

        lease_used = _to_num(await redis.hget(lease_key, "used"))
        lease_reserved = _to_num(await redis.hget(lease_key, "reserved"))
        remaining = cls._remaining(
            budget, lease_used, lease_reserved, owner.limit, owner_used, owner_held
        )
        allowance = min(cap, requested)
        if remaining is not None:
            allowance = min(allowance, max(int(remaining - prompt), 0))
        if allowance < min_allow:
            reason = "lease" if budget > 0 and (budget - lease_used - lease_reserved) <= prompt else "owner"
            raise cls._deny(
                lease, reason, remaining if remaining is not None else 0,
                prompt + min_allow, budget, owner,
            )
        reserve = float(prompt + allowance)

        for _ in range(2):
            reply = await redis.eval(
                _LUA_GRANT, 3,
                lease_key,
                used_key,
                held_key,
                str(budget), str(owner.limit), str(reserve), str(ttl),
            )
            ok = int(_to_num(reply[0]))
            if ok:
                grant = BudgetGrant(
                    lease_id=lease.lease_id,
                    owner_type=owner.owner_type,
                    owner_id=owner.owner_id,
                    prompt_tokens=prompt,
                    output_allowance=allowance,
                    reserved_tokens=int(round(reserve)),
                    limit_tokens=prompt + allowance,
                    budget_tokens=budget,
                    owner_limit=owner.limit,
                    backend="redis",
                    unlimited=remaining is None,
                )
                try:
                    grant.concurrency_held = await cls._acquire_concurrency(owner)
                except GatewayQuotaError:
                    await cls._release_redis(redis, grant, lease_key, used_key, held_key, ttl)
                    raise
                return grant

            reason_code = int(_to_num(reply[1]))
            limit_value = _to_num(reply[4])
            used_value = _to_num(reply[2])
            held_value = _to_num(reply[3])
            if reason_code == 1:
                remaining = limit_value - used_value - held_value
                reason = "lease"
            else:
                remaining = limit_value - used_value - held_value
                reason = "owner"
            new_allowance = min(cap, requested, max(int(remaining - prompt), 0))
            if new_allowance < min_allow:
                raise cls._deny(lease, reason, remaining, prompt + min_allow, budget, owner)
            allowance = new_allowance
            reserve = float(prompt + allowance)

        raise cls._deny(lease, "lease" if budget > 0 else "owner", 0, prompt + min_allow, budget, owner)

    @classmethod
    async def _grant_db(cls, lease, owner: OwnerQuota, budget: float, prompt: int, cap: int,
                        requested: int, min_allow: int) -> BudgetGrant:
        from packages.agentpanel_common.models.harness import HarnessGatewayBudget

        allowance = min(cap, requested)
        try:
            async with in_transaction() as conn:
                row = await HarnessGatewayBudget.filter(
                    lease_id=lease.lease_id
                ).using_db(conn).first()
                if row is None:
                    row = await HarnessGatewayBudget.create(
                        lease_id=lease.lease_id,
                        owner_type=owner.owner_type,
                        owner_id=owner.owner_id,
                        budget_tokens=budget,
                        used_tokens=0,
                        reserved_tokens=0,
                        using_db=conn,
                    )
                else:
                    row = await HarnessGatewayBudget.filter(
                        id=row.id
                    ).using_db(conn).select_for_update().first()
                if budget > 0 and abs(float(row.budget_tokens or 0) - budget) > 0.001:
                    row.budget_tokens = budget
                lease_remaining = (
                    budget - float(row.used_tokens or 0) - float(row.reserved_tokens or 0)
                    if budget > 0 else None
                )
                owner_remaining = None
                account = None
                used: Dict[str, Any] = {}
                current = 0.0
                if owner.owner_type is not None:
                    account = await QuotaAccount.filter(
                        owner_type=owner.owner_type, owner_id=owner.owner_id
                    ).using_db(conn).select_for_update().first()
                    used = dict(account.used or {}) if account else {}
                    current = float(used.get("token", 0) or 0)
                    if owner.limit > 0:
                        owner_remaining = owner.limit - current

                remaining = lease_remaining
                if owner_remaining is not None:
                    remaining = owner_remaining if remaining is None else min(remaining, owner_remaining)
                if remaining is not None:
                    allowed = int(remaining - prompt)
                    if allowed < min_allow:
                        deny_reason = "lease" if (
                            budget > 0 and (lease_remaining or 0) <= prompt
                        ) else "owner"
                        raise cls._deny(
                            lease, deny_reason, remaining, prompt + min_allow, budget, owner
                        )
                    allowance = min(allowance, allowed)

                reserve = float(prompt + allowance)
                row.used_tokens = float(row.used_tokens or 0) + reserve
                row.reserved_tokens = float(row.reserved_tokens or 0) + reserve
                row.budget_tokens = budget
                await row.save(using_db=conn)
                if owner.owner_type is not None and account is not None:
                    used["token"] = current + reserve
                    account.used = used
                    await account.save(using_db=conn)

                grant = BudgetGrant(
                    lease_id=lease.lease_id,
                    owner_type=owner.owner_type,
                    owner_id=owner.owner_id,
                    prompt_tokens=prompt,
                    output_allowance=allowance,
                    reserved_tokens=int(round(reserve)),
                    limit_tokens=prompt + allowance,
                    budget_tokens=budget,
                    owner_limit=owner.limit,
                    backend="db",
                    unlimited=remaining is None,
                )
        except GatewayQuotaError:
            raise
        except Exception as exc:
            logger.error(f"[gateway-budget] DB 预检失败 lease={lease.lease_id}: {exc}")
            raise GatewayQuotaError(503, "quota.store_unavailable", "额度存储暂不可用，请稍后重试", {"error": str(exc)})

        try:
            grant.concurrency_held = await cls._acquire_concurrency(owner)
        except GatewayQuotaError:
            await cls._release_db(lease, grant, use_reservation=True)
            raise
        return grant

    # ---------------- 结算 / 释放 ----------------
    @classmethod
    async def settle(cls, lease, grant: Optional[BudgetGrant], *, usage: Optional[Dict[str, Any]] = None,
                     estimated_completion: int = 0, truncated: bool = False,
                     over_budget: bool = False) -> Optional[Dict[str, Any]]:
        if grant is None:
            return None
        usage = usage or {}
        prompt = int(usage.get("prompt_tokens") or grant.prompt_tokens)
        completion = int(usage.get("completion_tokens") or estimated_completion)
        actual = float(usage.get("total_tokens") or (prompt + completion))
        result: Optional[Dict[str, Any]] = None

        if grant.backend == "redis":
            redis = await cls._redis()
            if redis is not None:
                try:
                    result = await cls._settle_redis(redis, lease, grant, actual, truncated, over_budget)
                except Exception as exc:
                    logger.warning(f"[gateway-budget] Redis 结算失败，落 DB 修正: {exc}")
                    result = await cls._settle_db(
                        lease, grant, actual, truncated, over_budget, use_reservation=False
                    )
            else:
                result = await cls._settle_db(
                    lease, grant, actual, truncated, over_budget, use_reservation=False
                )
        else:
            result = await cls._settle_db(
                lease, grant, actual, truncated, over_budget, use_reservation=True
            )

        await cls._release_concurrency(grant)

        if truncated:
            await cls.maybe_auto_revoke(lease, "stream_truncated")
        elif result:
            if grant.budget_tokens > 0 and float(result.get("lease_used", 0)) >= grant.budget_tokens:
                await cls.maybe_auto_revoke(lease, "lease_budget_exhausted")
            elif grant.owner_limit > 0 and float(result.get("owner_used", 0)) >= grant.owner_limit:
                await cls.maybe_auto_revoke(lease, "balance_insufficient")
        return result

    @classmethod
    async def release(cls, lease, grant: Optional[BudgetGrant]) -> None:
        if grant is None:
            return
        if grant.backend == "redis":
            redis = await cls._redis()
            if redis is not None:
                try:
                    await cls._release_redis(
                        redis, grant, cls._lease_key(lease.lease_id),
                        *cls._owner_keys(grant.owner_type, grant.owner_id, current_period(), lease.lease_id),
                        int(gateway_config().get("gateway_quota_ttl_seconds") or LEASE_KEY_TTL_FALLBACK),
                    )
                except Exception as exc:
                    logger.warning(f"[gateway-budget] Redis 释放失败，落 DB 修正: {exc}")
                    await cls._release_db(lease, grant, use_reservation=False)
            else:
                await cls._release_db(lease, grant, use_reservation=False)
        else:
            await cls._release_db(lease, grant, use_reservation=True)
        await cls._release_concurrency(grant)

    @classmethod
    async def _settle_redis(cls, redis, lease, grant: BudgetGrant, actual: float,
                            truncated: bool, over_budget: bool) -> Dict[str, Any]:
        ttl = int(gateway_config().get("gateway_quota_ttl_seconds") or LEASE_KEY_TTL_FALLBACK)
        lease_key = cls._lease_key(lease.lease_id)
        used_key, held_key = cls._owner_keys(
            grant.owner_type, grant.owner_id, current_period(), lease.lease_id
        )
        owner_marker = f"{grant.owner_type}:{grant.owner_id}" if grant.owner_type is not None else f"none:{lease.lease_id}"
        reply = await redis.eval(
            _LUA_SETTLE, 3,
            lease_key, used_key, held_key,
            str(grant.reserved_tokens), str(actual), str(ttl),
            "1", "1" if truncated else "0", "1" if over_budget else "0",
            owner_marker,
        )
        return {
            "lease_used": _to_num(reply[0]),
            "lease_reserved": _to_num(reply[1]),
            "owner_used": _to_num(reply[2]),
            "actual_tokens": actual,
        }

    @classmethod
    async def _settle_db(cls, lease, grant: BudgetGrant, actual: float, truncated: bool,
                         over_budget: bool, *, use_reservation: bool) -> Dict[str, Any]:
        from packages.agentpanel_common.models.harness import HarnessGatewayBudget

        async with in_transaction() as conn:
            row = await HarnessGatewayBudget.filter(
                lease_id=lease.lease_id
            ).using_db(conn).select_for_update().first()
            if row is None:
                row = await HarnessGatewayBudget.create(
                    lease_id=lease.lease_id,
                    owner_type=grant.owner_type,
                    owner_id=grant.owner_id,
                    budget_tokens=grant.budget_tokens,
                    using_db=conn,
                )
            reserved = float(grant.reserved_tokens) if use_reservation else 0.0
            row.reserved_tokens = max(float(row.reserved_tokens or 0) - reserved, 0)
            row.used_tokens = float(row.used_tokens or 0) + actual - reserved
            row.request_count = int(row.request_count or 0) + 1
            if truncated:
                row.truncated_count = int(row.truncated_count or 0) + 1
            if over_budget:
                row.over_budget_count = int(row.over_budget_count or 0) + 1
            row.last_settled_at = _now()
            if grant.budget_tokens > 0 and row.used_tokens >= grant.budget_tokens:
                row.status = "exhausted"
            await row.save(using_db=conn)

            owner_used = 0.0
            if grant.owner_type is not None:
                account = await QuotaAccount.filter(
                    owner_type=grant.owner_type, owner_id=grant.owner_id
                ).using_db(conn).select_for_update().first()
                if account is not None:
                    used = dict(account.used or {})
                    current = float(used.get("token", 0) or 0)
                    used["token"] = max(current + actual - reserved, 0)
                    account.used = used
                    await account.save(using_db=conn)
                    owner_used = used["token"]
            return {
                "lease_used": float(row.used_tokens),
                "lease_reserved": float(row.reserved_tokens),
                "owner_used": owner_used,
                "actual_tokens": actual,
            }

    @classmethod
    async def _release_redis(cls, redis, grant: BudgetGrant, lease_key: str,
                             used_key: str, held_key: str, ttl: int) -> None:
        await redis.eval(
            _LUA_RELEASE, 3,
            lease_key,
            used_key,
            held_key,
            str(grant.reserved_tokens), str(ttl),
        )

    @classmethod
    async def _release_db(cls, lease, grant: BudgetGrant, *, use_reservation: bool) -> None:
        from packages.agentpanel_common.models.harness import HarnessGatewayBudget

        reserved = float(grant.reserved_tokens) if use_reservation else 0.0
        try:
            async with in_transaction() as conn:
                row = await HarnessGatewayBudget.filter(
                    lease_id=lease.lease_id
                ).using_db(conn).select_for_update().first()
                if row is not None:
                    row.reserved_tokens = max(float(row.reserved_tokens or 0) - reserved, 0)
                    row.used_tokens = max(float(row.used_tokens or 0) - reserved, 0)
                    await row.save(using_db=conn)
                if grant.owner_type is not None and reserved:
                    account = await QuotaAccount.filter(
                        owner_type=grant.owner_type, owner_id=grant.owner_id
                    ).using_db(conn).select_for_update().first()
                    if account is not None:
                        used = dict(account.used or {})
                        used["token"] = max(float(used.get("token", 0) or 0) - reserved, 0)
                        account.used = used
                        await account.save(using_db=conn)
        except Exception as exc:
            logger.warning(f"[gateway-budget] DB 释放失败 lease={lease.lease_id}: {exc}")

    # ---------------- 并发槽 ----------------
    @classmethod
    async def _acquire_concurrency(cls, owner: OwnerQuota) -> bool:
        if owner.owner_type is None:
            return False
        limit = int(gateway_config().get("max_concurrent_requests_per_owner") or 8)
        if limit <= 0:
            return False
        redis = await cls._redis()
        if redis is not None:
            try:
                key = cls._conc_key(owner.owner_type, owner.owner_id)
                value = int(await redis.incr(key))
                await redis.expire(key, CONC_WATCHDOG_SECONDS)
                if value > limit:
                    await redis.decr(key)
                    inc_gateway_quota_reject("concurrency")
                    raise GatewayQuotaError(
                        429,
                        "quota.concurrency_limit",
                        "单租户并发请求数已达上限，请稍后重试",
                        {"owner_type": owner.owner_type, "owner_id": owner.owner_id, "limit": limit},
                    )
                return True
            except GatewayQuotaError:
                raise
            except Exception as exc:
                logger.warning(f"[gateway-budget] Redis 并发计数失败，降级 DB: {exc}")

        from packages.agentpanel_common.models.harness import HarnessGatewayConcurrency

        try:
            async with in_transaction() as conn:
                row = await HarnessGatewayConcurrency.filter(
                    owner_type=owner.owner_type, owner_id=owner.owner_id
                ).using_db(conn).first()
                if row is None:
                    row = await HarnessGatewayConcurrency.create(
                        owner_type=owner.owner_type, owner_id=owner.owner_id, inflight=0,
                        using_db=conn,
                    )
                else:
                    row = await HarnessGatewayConcurrency.filter(
                        id=row.id
                    ).using_db(conn).select_for_update().first()
                updated = row.updated_at
                if _is_stale(updated, CONC_WATCHDOG_SECONDS):
                    row.inflight = 0
                if int(row.inflight or 0) + 1 > limit:
                    inc_gateway_quota_reject("concurrency")
                    raise GatewayQuotaError(
                        429,
                        "quota.concurrency_limit",
                        "单租户并发请求数已达上限，请稍后重试",
                        {"owner_type": owner.owner_type, "owner_id": owner.owner_id, "limit": limit},
                    )
                row.inflight = int(row.inflight or 0) + 1
                await row.save(using_db=conn)
            return True
        except GatewayQuotaError:
            raise
        except Exception as exc:
            logger.error(f"[gateway-budget] DB 并发计数失败: {exc}")
            raise GatewayQuotaError(503, "quota.store_unavailable", "额度存储暂不可用，请稍后重试", {"error": str(exc)})

    @classmethod
    async def _release_concurrency(cls, grant: BudgetGrant) -> None:
        owner_type, owner_id = grant.owner_type, grant.owner_id
        if owner_type is None:
            return
        redis = await cls._redis()
        if redis is not None:
            try:
                key = cls._conc_key(owner_type, owner_id)
                value = int(await redis.decr(key))
                if value < 0:
                    await redis.set(key, 0, ex=CONC_WATCHDOG_SECONDS)
                else:
                    await redis.expire(key, CONC_WATCHDOG_SECONDS)
                return
            except Exception as exc:
                logger.warning(f"[gateway-budget] Redis 并发释放失败，降级 DB: {exc}")

        from packages.agentpanel_common.models.harness import HarnessGatewayConcurrency

        try:
            async with in_transaction() as conn:
                row = await HarnessGatewayConcurrency.filter(
                    owner_type=owner_type, owner_id=owner_id
                ).using_db(conn).select_for_update().first()
                if row is not None:
                    row.inflight = max(int(row.inflight or 0) - 1, 0)
                    await row.save(using_db=conn)
        except Exception as exc:
            logger.warning(f"[gateway-budget] DB 并发释放失败: {exc}")

    # ---------------- 计数 / 审计联动 ----------------
    @classmethod
    async def record_reject(cls, lease, reason: str) -> None:
        inc_gateway_quota_reject(reason)
        redis = await cls._redis()
        if redis is not None:
            try:
                key = cls._lease_key(lease.lease_id)
                await redis.hincrby(key, "rejected", 1)
                return
            except Exception as exc:
                logger.warning(f"[gateway-budget] Redis 拒绝计数失败，落 DB: {exc}")
        from packages.agentpanel_common.models.harness import HarnessGatewayBudget

        try:
            async with in_transaction() as conn:
                row = await HarnessGatewayBudget.filter(
                    lease_id=lease.lease_id
                ).using_db(conn).select_for_update().first()
                if row is None:
                    row = await HarnessGatewayBudget.create(
                        lease_id=lease.lease_id,
                        owner_type=getattr(lease, "owner_type", None),
                        owner_id=getattr(lease, "owner_id", None),
                        budget_tokens=_lease_budget(lease),
                        using_db=conn,
                    )
                row.rejected_count = int(row.rejected_count or 0) + 1
                await row.save(using_db=conn)
        except Exception as exc:
            logger.warning(f"[gateway-budget] DB 拒绝计数失败 lease={lease.lease_id}: {exc}")

    @classmethod
    def record_truncate(cls, reason: str) -> None:
        """截断的持久化计数由 settle 完成，这里只落 Prometheus 指标。"""
        inc_gateway_quota_truncate(reason)

    @classmethod
    async def maybe_auto_revoke(cls, lease, reason: str) -> None:
        if not bool(gateway_config().get("auto_revoke_on_exhausted", True)):
            return
        if getattr(lease, "status", None) != "active":
            return
        try:
            from .constants import GATEWAY_EVENT_SOURCE
            from .lease_revoke import revoke_lease_internal

            await revoke_lease_internal(
                lease.lease_id,
                reason=reason,
                actor_type="system",
                actor_id="gateway-budget",
                event_source=GATEWAY_EVENT_SOURCE,
            )
        except Exception as exc:
            logger.warning(f"[gateway-budget] 自动吊销失败 lease={lease.lease_id}: {exc}")

    # ---------------- 快照 / 看板 ----------------
    @classmethod
    async def snapshot(cls, lease, owner: Optional[OwnerQuota] = None) -> Dict[str, Any]:
        budget = _lease_budget(lease)
        if owner is None:
            try:
                owner = await cls._resolve_owner(lease, ensure=False)
            except Exception:
                owner = OwnerQuota(*_owner_key_parts(lease), 0.0, current_period(), 0.0)
        period = owner.period
        redis = await cls._redis()
        if redis is not None:
            try:
                lease_key = cls._lease_key(lease.lease_id)
                data = await redis.hgetall(lease_key)
                used = _to_num(data.get("used"))
                reserved = _to_num(data.get("reserved"))
                requests = int(_to_num(data.get("requests")))
                rejected = int(_to_num(data.get("rejected")))
                truncated = int(_to_num(data.get("truncated")))
                over_budget = int(_to_num(data.get("over_budget")))
                owner_used = owner_held = 0.0
                if owner.owner_type is not None:
                    owner_used = _to_num(await redis.get(cls._used_key(owner.owner_type, owner.owner_id, period)))
                    owner_held = _to_num(await redis.get(cls._held_key(owner.owner_type, owner.owner_id, period)))
                return cls._build_snapshot(
                    lease, budget, used, reserved, requests, rejected, truncated,
                    over_budget, owner, owner_used, owner_held,
                )
            except Exception as exc:
                logger.warning(f"[gateway-budget] Redis 快照失败，落 DB: {exc}")

        from packages.agentpanel_common.models.harness import HarnessGatewayBudget

        row = await HarnessGatewayBudget.get_or_none(lease_id=lease.lease_id)
        account = await QuotaAccount.get_or_none(
            owner_type=owner.owner_type, owner_id=owner.owner_id
        ) if owner.owner_type is not None else None
        used = max(float(row.used_tokens or 0) - float(row.reserved_tokens or 0), 0) if row else 0.0
        reserved = float(row.reserved_tokens or 0) if row else 0.0
        owner_used = float(((account.used if account else {}) or {}).get("token", 0) or 0)
        return cls._build_snapshot(
            lease, budget, used, reserved,
            int(row.request_count or 0) if row else 0,
            int(row.rejected_count or 0) if row else 0,
            int(row.truncated_count or 0) if row else 0,
            int(row.over_budget_count or 0) if row else 0,
            owner, owner_used, 0.0,
        )

    @staticmethod
    def _build_snapshot(lease, budget, used, reserved, requests, rejected, truncated,
                        over_budget, owner, owner_used, owner_held) -> Dict[str, Any]:
        lease_remaining = max(budget - used - reserved, 0) if budget > 0 else None
        owner_remaining = max(owner.limit - owner_used - owner_held, 0) if owner.limit > 0 else None
        if lease_remaining is not None and owner_remaining is not None:
            remaining = min(lease_remaining, owner_remaining)
        else:
            remaining = lease_remaining if lease_remaining is not None else owner_remaining
        avg = (used / requests) if requests > 0 else 0.0
        estimated = int(remaining / max(avg, 1.0)) if remaining is not None else None
        exhausted = bool(remaining is not None and remaining <= 0)
        return {
            "lease_id": lease.lease_id,
            "client_id": getattr(lease, "client_id", None),
            "owner_type": owner.owner_type,
            "owner_id": owner.owner_id,
            "session_no": getattr(lease, "session_no", None),
            "run_no": getattr(lease, "run_no", None),
            "status": getattr(lease, "status", None),
            "expires_at": getattr(lease, "expires_at", None).isoformat()
            if getattr(lease, "expires_at", None) else None,
            "budget_tokens": budget if budget > 0 else None,
            "owner_limit": owner.limit if owner.limit > 0 else None,
            "used_tokens": round(used, 2),
            "reserved_tokens": round(reserved, 2),
            "remaining_tokens": round(remaining, 2) if remaining is not None else None,
            "request_count": requests,
            "rejected_count": rejected,
            "truncated_count": truncated,
            "over_budget_count": over_budget,
            "avg_tokens_per_request": round(avg, 2),
            "estimated_requests": estimated,
            "exhausted": exhausted,
        }

    @classmethod
    async def list_dashboard(cls, *, client_id: Optional[str] = None,
                             owner_type: Optional[str] = None,
                             owner_id: Optional[int] = None,
                             active_only: bool = True, limit: int = 50) -> Dict[str, Any]:
        from packages.agentpanel_common.models.harness import HarnessGatewayLease

        query = HarnessGatewayLease.all()
        if client_id:
            query = query.filter(client_id=client_id)
        if owner_type:
            query = query.filter(owner_type=owner_type)
        if owner_id is not None:
            query = query.filter(owner_id=owner_id)
        if active_only:
            query = query.filter(status="active")
        leases = await query.order_by("-id").limit(int(limit))
        items = [await cls.snapshot(lease) for lease in leases]
        summary = cls._summarize_items(items)
        return {"summary": summary, "items": items}

    @staticmethod
    def _summarize_items(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "leases": len(items),
            "active_leases": sum(1 for item in items if item.get("status") == "active"),
            "exhausted_leases": sum(1 for item in items if item.get("exhausted")),
            "rejected_count": sum(int(item.get("rejected_count") or 0) for item in items),
            "truncated_count": sum(int(item.get("truncated_count") or 0) for item in items),
            "over_budget_count": sum(int(item.get("over_budget_count") or 0) for item in items),
            "used_tokens": round(sum(float(item.get("used_tokens") or 0) for item in items), 2),
            "remaining_tokens": round(
                sum(float(item.get("remaining_tokens") or 0)
                    for item in items if item.get("remaining_tokens") is not None), 2
            ),
        }

    @classmethod
    async def summary(cls, limit: int = 20) -> Dict[str, Any]:
        data = await cls.list_dashboard(active_only=True, limit=limit)
        return data["summary"]
