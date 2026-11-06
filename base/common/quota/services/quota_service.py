"""
M9 配额计量核心服务

溯源：
- docs/arch/03 §2.3 Redis key 设计（quota:/quota_hold:/conc:）与 §3.6（事实源/对账/崩溃恢复低估方向）
- docs/arch/04 F7 配额拦截流程、§6 quota_estimate/quota_settle 签名
- docs/arch/05 §1.1 Redis 降级（预检放行 + DB 原子条件更新兜底）、§1.2 幂等
- R-09：预占先于一切外部调用；结算幂等键 (execution_id,node_id,seq)

设计要点：
- 周期计数器拆两个 key：quota:（已结算 used）与 quota_held:（预占 held），
  预占判定 used+held+x<=limit；结算 held 转 used；释放 held 回退
- Redis 预占采用「先 INCRBYFLOAT 再读回校验、超限补偿回退」，单 item 原子，避免并发超发
- Redis 不可用时退化：DB 事务内 SELECT FOR UPDATE 校验并预扣（等价 UPDATE ... WHERE used+x<=limit
  的强校验语义，且兼容 openGauss/sqlite，遵守 R-06 红线）；预占登记在进程内（单实例私有化部署）
- 幂等：usage_record 按 (execution_id,node_id,seq) 存在性去重（seq 由调用方随节点递增；
  D1 已补 usage_record.seq 列与 UNIQUE(execution_id,node_id,seq) 硬约束；
  服务层先去重再增减计数，重复结算不会双计）
"""
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from loguru import logger
from tortoise.transactions import in_transaction

from base.common.cache import RedisCache
from base.common.quota.errors import QuotaError
from base.common.quota.metrics import inc_llm_tokens, inc_quota_reject
from base.common.quota.models.quota import QuotaAccount, UsageRecord

# 兜底 TTL：预占悬挂超过该时长由清理任务释放（AR-08）
HOLD_TTL_SECONDS = 3600
# 并发计数看门狗 TTL（§2.3：60s 兜底，崩溃自动释放）
CONC_WATCHDOG_SECONDS = 60
# 全局并发上限（§03-2.5 NFR：全局信号量 50）
GLOBAL_CONCURRENCY_LIMIT = 50

# 索引/集合 key
HOLD_INDEX_KEY = "quota_holds_index"
ACTIVE_OWNERS_KEY = "quota_active_owners"
CONC_GLOBAL_KEY = "conc:global"


def _now() -> datetime:
    return datetime.now()


def current_period(now: Optional[datetime] = None) -> str:
    """自然月周期标识，如 2026-11"""
    n = now or _now()
    return f"{n.year:04d}-{n.month:02d}"


def current_day_period(now: Optional[datetime] = None) -> str:
    """日周期标识（daily_* 配额项），如 2026-11-01"""
    n = now or _now()
    return f"{n.year:04d}-{n.month:02d}-{n.day:02d}"


def month_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """自然月起止 [start, end)"""
    n = now or _now()
    start = n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _is_daily_item(item: str) -> bool:
    return item.startswith("daily_")


def _normalize_owner(owner: Any) -> Tuple[str, int]:
    """支持 OwnerContext / (owner_type, owner_id) 元组 / dict"""
    if isinstance(owner, dict):
        return owner["owner_type"], int(owner["owner_id"])
    if isinstance(owner, (tuple, list)) and len(owner) == 2:
        return owner[0], int(owner[1])
    return owner.owner_type, int(owner.owner_id)


def _usage_item(resource_type: str) -> str:
    """usage_record.resource_type → 套餐配额项映射"""
    if resource_type in ("llm_token", "token", "tokens", "llm_tokens"):
        return "token"
    return resource_type


class QuotaService:
    """配额预占/结算/释放/并发/看板/对账（全部 async，R-08）"""

    # ---------------- Redis key ----------------
    @staticmethod
    def _used_key(ot: str, oid: int, item: str, period: str) -> str:
        return f"quota:{ot}:{oid}:{item}:{period}"

    @staticmethod
    def _held_key(ot: str, oid: int, item: str, period: str) -> str:
        return f"quota_held:{ot}:{oid}:{item}:{period}"

    @staticmethod
    def _hold_key(hold_id: str) -> str:
        return f"quota_hold:{hold_id}"

    @staticmethod
    def _conc_key(ot: str, oid: int) -> str:
        return f"conc:{ot}:{oid}"

    # ---------------- 基础设施 ----------------
    @staticmethod
    async def _redis():
        """获取可用 redis 客户端；不可用/异常返回 None（降级）

        必须先 get_instance() 触发惰性连接初始化（失败可重试），再判 is_enabled()；
        若先判 is_enabled() 则实例未创建时恒为 False，连接永远无法建立（BUG-OPS-001）。
        """
        try:
            cache = await RedisCache.get_instance()
            if RedisCache.is_enabled():
                return cache._client  # noqa: SLF001（项目现有用法，见 authz/audit.py）
            return None
        except Exception as e:
            logger.warning(f"[quota] Redis 不可用，进入降级路径: {e}")
            return None

    @staticmethod
    def _item_period(item: str, now: Optional[datetime] = None) -> str:
        return current_day_period(now) if _is_daily_item(item) else current_period(now)

    @staticmethod
    def _period_ttl(item: str, now: Optional[datetime] = None) -> int:
        """计数器 TTL：到周期末（月 → 下月 1 日；日 → 次日 0 点）"""
        n = now or _now()
        if _is_daily_item(item):
            end = (n + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            _, end = month_bounds(n)
        return max(int((end - n).total_seconds()), 1)

    # 进程内降级态（单实例私有化部署可接受；§05-1.1 容忍短暂超用，结算修正）
    _mem_holds: Dict[str, dict] = {}
    _mem_conc: Dict[str, int] = {}

    # ============================================================
    # 账户
    # ============================================================
    @classmethod
    async def ensure_account(cls, owner_type: str, owner_id: int) -> QuotaAccount:
        """
        定位或创建账户；自然月周期滚动（过期即重置 used，进入新周期）；
        绑定套餐变化时惰性刷新 account.plan。
        """
        from base.common.quota.services.plan_service import PlanService

        start, end = month_bounds()
        account = await QuotaAccount.get_or_none(owner_type=owner_type, owner_id=owner_id)
        if account is None:
            account = await QuotaAccount.create(
                owner_type=owner_type, owner_id=owner_id,
                period_start=start, period_end=end, used={},
            )
        else:
            # 部分后端（sqlite/PG 带时区配置）返回 aware datetime，比较前归一为 naive
            period_end = account.period_end
            if period_end is not None and period_end.tzinfo is not None:
                period_end = period_end.replace(tzinfo=None)
            if period_end is None or period_end <= _now():
                # 周期滚动：旧周期用量不再带回（usage_record 留痕对账）
                account.used = {}
                account.period_start = start
                account.period_end = end
                await account.save()

        plan = await PlanService.resolve_plan(owner_type, owner_id)
        if plan is not None and account.plan_id != plan.id:
            account.plan_id = plan.id
            await account.save()
        return account

    # ============================================================
    # 预估与预占（F7 前置拦截，R-09）
    # ============================================================
    @classmethod
    async def quota_estimate(
        cls,
        owner: Any,
        items: Dict[str, float],
        execution_id: Optional[int] = None,
    ) -> str:
        """
        预估并原子预占。

        Args:
            owner: OwnerContext 或 (owner_type, owner_id)
            items: 预估消耗 {配额项: 数量}，如 {"token": 12000, "kb_search": 2}
            execution_id: 关联执行实例（可空；hold_id 即 quota_hold:{hold_id} 的键后缀）

        Returns:
            hold_id（空字符串表示该主体未绑定套餐、不计量）

        Raises:
            QuotaError: 42901 语义，含 item/剩余/预计
        """
        from base.common.quota.services.plan_service import PlanService

        owner_type, owner_id = _normalize_owner(owner)
        plan = await PlanService.resolve_plan(owner_type, owner_id)
        if plan is None or plan.status != "active":
            return ""
        limits = plan.quota_items or {}
        requested = {
            k: float(v) for k, v in (items or {}).items()
            if k in limits and v and float(v) > 0
        }
        if not requested:
            return ""

        account = await cls.ensure_account(owner_type, owner_id)
        redis = await cls._redis()
        if redis is not None:
            try:
                return await cls._estimate_redis(redis, owner_type, owner_id, requested, limits, account, execution_id)
            except QuotaError:
                raise
            except Exception as e:
                logger.warning(f"[quota] Redis 预占失败，降级 DB 路径: {e}")
        return await cls._estimate_db(owner_type, owner_id, requested, limits, account, execution_id)

    @classmethod
    async def _estimate_redis(cls, redis, ot: str, oid: int, requested: Dict[str, float],
                              limits: Dict[str, Any], account: QuotaAccount,
                              execution_id: Optional[int]) -> str:
        held_keys: List[Tuple[str, str, float]] = []  # (item, held_key, amount)
        try:
            for item, amount in requested.items():
                period = cls._item_period(item)
                used_key = cls._used_key(ot, oid, item, period)
                held_key = cls._held_key(ot, oid, item, period)
                ttl = cls._period_ttl(item)
                # 崩溃恢复（§3.6）：used 计数缺失时以 PG 落盘值重建（低估方向，PG 为分钟级滞后）
                if not await redis.exists(used_key):
                    seed = float((account.used or {}).get(item, 0))
                    await redis.set(used_key, seed, ex=ttl)
                used = float(await redis.get(used_key) or 0)
                new_held = float(await redis.incrbyfloat(held_key, amount))
                await redis.expire(held_key, ttl)
                limit = float(limits.get(item, 0))
                if used + new_held > limit:
                    await redis.incrbyfloat(held_key, -amount)  # 补偿回退
                    remaining = max(limit - used - (new_held - amount), 0)
                    inc_quota_reject(item)
                    raise QuotaError(item=item, remaining=remaining, estimated=amount)
                held_keys.append((item, held_key, amount))
        except QuotaError:
            raise

        hold_id = str(execution_id) if execution_id else f"qh_{uuid.uuid4().hex[:16]}"
        expire_at = time.time() + HOLD_TTL_SECONDS
        await redis.hset(cls._hold_key(hold_id), mapping={
            "owner_type": ot,
            "owner_id": str(oid),
            "items": json.dumps({item: amount for item, _, amount in held_keys}),
            "expire_at": str(expire_at),
        })
        await redis.expire(cls._hold_key(hold_id), HOLD_TTL_SECONDS)
        await redis.zadd(HOLD_INDEX_KEY, {hold_id: expire_at})
        await redis.sadd(ACTIVE_OWNERS_KEY, f"{ot}:{oid}")
        return hold_id

    @classmethod
    async def _estimate_db(cls, ot: str, oid: int, requested: Dict[str, float],
                           limits: Dict[str, Any], account: QuotaAccount,
                           execution_id: Optional[int]) -> str:
        """降级：DB 事务内强校验 + 预扣（§05-1.1），预占登记进程内"""
        async with in_transaction() as conn:
            acc = await QuotaAccount.filter(id=account.id).select_for_update().using_db(conn).first()
            used = dict(acc.used or {})
            for item, amount in requested.items():
                limit = float(limits.get(item, 0))
                current = float(used.get(item, 0))
                if current + amount > limit:
                    inc_quota_reject(item)
                    raise QuotaError(item=item, remaining=max(limit - current, 0), estimated=amount)
            for item, amount in requested.items():
                used[item] = float(used.get(item, 0)) + amount
            acc.used = used
            await acc.save(using_db=conn)

        hold_id = str(execution_id) if execution_id else f"qh_{uuid.uuid4().hex[:16]}"
        cls._mem_holds[hold_id] = {
            "owner_type": ot, "owner_id": oid,
            "items": dict(requested),  # 已预扣量（结算时按真实用量修正差额）
            "charged": dict(requested),
            "expire_at": time.time() + HOLD_TTL_SECONDS,
            "db": True,
        }
        return hold_id

    # ============================================================
    # 结算（幂等）
    # ============================================================
    @classmethod
    async def quota_settle(
        cls,
        hold_id: Optional[str],
        usage: List[Dict[str, Any]],
        owner: Any = None,
    ) -> Dict[str, Any]:
        """
        结算真实用量：预占转正式、释放差额；usage_record 幂等写入。

        Args:
            hold_id: quota_estimate 返回值（可为空字符串表示不计量主体）
            usage: [{execution_id, node_id, seq, resource_type/item, amount,
                     tokens_in, tokens_out, cost, model?}]
            owner: hold_id 为空时提供主体（否则无法记账）

        幂等：同一 (execution_id,node_id,seq) 重复结算仅首次生效（§05-1.2，R-09）。
        支持同一 hold 多次结算（每节点结算）：held 按真实用量逐步转正式，
        剩余预占由 quota_release 或悬挂清理任务兜底释放。
        """
        entries = [u for u in (usage or []) if float(u.get("amount", 0) or 0) != 0
                   or u.get("tokens_in") or u.get("tokens_out")]
        hold = await cls._load_hold(hold_id) if hold_id else None

        if hold is not None:
            ot, oid = hold["owner_type"], int(hold["owner_id"])
        elif owner is not None:
            ot, oid = _normalize_owner(owner)
        elif hold_id:
            return {"settled": 0, "skipped": 0, "missing_hold": True}
        else:
            return {"settled": 0, "skipped": 0}

        # ---- 幂等去重：先查已落库流水（D1：键对齐为 execution_id,node_id,seq）----
        fresh: List[Dict[str, Any]] = []
        skipped = 0
        if entries:
            dedup_keys = {
                (u.get("execution_id"), u.get("node_id"), int(u.get("seq") or 0))
                for u in entries
                if u.get("execution_id") is not None and u.get("node_id") is not None
            }
            existing = set()
            if dedup_keys:
                exec_ids = {k[0] for k in dedup_keys}
                node_ids = {k[1] for k in dedup_keys}
                records = await UsageRecord.filter(
                    execution_id__in=exec_ids, node_id__in=node_ids
                ).all()
                existing = {(r.execution_id, r.node_id, r.seq) for r in records}
            for u in entries:
                key = (u.get("execution_id"), u.get("node_id"), int(u.get("seq") or 0))
                if u.get("execution_id") is not None and u.get("node_id") is not None and key in existing:
                    skipped += 1
                    continue
                fresh.append(u)

        if not fresh:
            # 全部重复：仅可能仍需释放已空预占
            if hold is not None and not any(hold["items"].values()):
                await cls._drop_hold(hold_id, hold)
            return {"settled": 0, "skipped": skipped}

        # ---- 真实用量按配额项聚合 ----
        real: Dict[str, float] = {}
        for u in fresh:
            item = _usage_item(u.get("resource_type") or u.get("item") or "")
            if not item:
                continue
            amount = float(u.get("amount", 0) or 0) or float(
                (u.get("tokens_in") or 0) + (u.get("tokens_out") or 0)
            )
            real[item] = real.get(item, 0.0) + amount

        # ---- 计数：held 转 used / 直接 used ----
        if hold is not None and hold.get("db"):
            await cls._settle_db_counters(ot, oid, hold, real)
        else:
            redis = await cls._redis()
            if redis is not None:
                try:
                    await cls._settle_redis_counters(redis, ot, oid, hold, real)
                except Exception as e:
                    logger.warning(f"[quota] Redis 结算计数失败，落 DB: {e}")
                    await cls._settle_db_counters_direct(ot, oid, real)
            else:
                await cls._settle_db_counters_direct(ot, oid, real)

        # ---- 流水落库 ----
        written = 0
        for u in fresh:
            await UsageRecord.create(
                owner_type=ot,
                owner_id=oid,
                execution_id=u.get("execution_id"),
                node_id=u.get("node_id"),
                seq=int(u.get("seq") or 0),
                resource_type=u.get("resource_type") or u.get("item") or "unknown",
                amount=float(u.get("amount", 0) or 0),
                tokens_in=int(u.get("tokens_in") or 0),
                tokens_out=int(u.get("tokens_out") or 0),
                cost=u.get("cost") or 0,
            )
            written += 1
            inc_llm_tokens(ot, u.get("model") or "unknown",
                           int(u.get("tokens_in") or 0), int(u.get("tokens_out") or 0))

        # ---- 预占收尾 ----
        if hold is not None:
            if any(v > 0 for v in hold["items"].values()):
                await cls._store_hold(hold_id, hold)
            else:
                await cls._drop_hold(hold_id, hold)

        return {"settled": written, "skipped": skipped}

    @classmethod
    async def _settle_redis_counters(cls, redis, ot: str, oid: int,
                                     hold: Optional[dict], real: Dict[str, float]) -> None:
        for item, amount in real.items():
            period = cls._item_period(item)
            used_key = cls._used_key(ot, oid, item, period)
            ttl = cls._period_ttl(item)
            if not await redis.exists(used_key):
                await redis.set(used_key, 0, ex=ttl)
            await redis.incrbyfloat(used_key, amount)
            await redis.expire(used_key, ttl)
            held_take = 0.0
            if hold is not None:
                held_take = min(amount, float(hold["items"].get(item, 0)))
                if held_take > 0:
                    hold["items"][item] = float(hold["items"][item]) - held_take
                    await redis.incrbyfloat(cls._held_key(ot, oid, item, period), -held_take)
        await redis.sadd(ACTIVE_OWNERS_KEY, f"{ot}:{oid}")

    @classmethod
    async def _settle_db_counters(cls, ot: str, oid: int, hold: dict, real: Dict[str, float]) -> None:
        """降级路径结算：预扣转真实（real - 已预扣部分 = 差额修正）"""
        account = await cls.ensure_account(ot, oid)
        async with in_transaction() as conn:
            acc = await QuotaAccount.filter(id=account.id).select_for_update().using_db(conn).first()
            used = dict(acc.used or {})
            for item, amount in real.items():
                take = min(amount, float(hold["items"].get(item, 0)))
                hold["items"][item] = float(hold["items"].get(item, 0)) - take
                # 预占时已把预估值计入 used，这里只补真实超出预估的差额
                delta = amount - take
                if delta:
                    used[item] = float(used.get(item, 0)) + delta
            acc.used = used
            await acc.save(using_db=conn)

    @classmethod
    async def _settle_db_counters_direct(cls, ot: str, oid: int, real: Dict[str, float]) -> None:
        """无预占（hold 丢失/降级无登记）直接落 DB used"""
        account = await cls.ensure_account(ot, oid)
        async with in_transaction() as conn:
            acc = await QuotaAccount.filter(id=account.id).select_for_update().using_db(conn).first()
            used = dict(acc.used or {})
            for item, amount in real.items():
                used[item] = float(used.get(item, 0)) + amount
            acc.used = used
            await acc.save(using_db=conn)

    # ============================================================
    # 释放（异常路径）
    # ============================================================
    @classmethod
    async def quota_release(cls, hold_id: Optional[str]) -> bool:
        """释放预占剩余量（异常/取消路径）。幂等：重复释放为无操作。"""
        if not hold_id:
            return False
        hold = await cls._load_hold(hold_id)
        if hold is None:
            return False
        ot, oid = hold["owner_type"], int(hold["owner_id"])
        if hold.get("db"):
            account = await cls.ensure_account(ot, oid)
            async with in_transaction() as conn:
                acc = await QuotaAccount.filter(id=account.id).select_for_update().using_db(conn).first()
                used = dict(acc.used or {})
                for item, amount in hold["items"].items():
                    if amount:
                        used[item] = max(float(used.get(item, 0)) - float(amount), 0)
                        hold["items"][item] = 0.0
                acc.used = used
                await acc.save(using_db=conn)
        else:
            redis = await cls._redis()
            if redis is not None:
                for item, amount in hold["items"].items():
                    if amount:
                        await redis.incrbyfloat(
                            cls._held_key(ot, oid, item, cls._item_period(item)), -float(amount)
                        )
                        hold["items"][item] = 0.0
        await cls._drop_hold(hold_id, hold)
        return True

    # ============================================================
    # 预占存取
    # ============================================================
    @classmethod
    async def _load_hold(cls, hold_id: str) -> Optional[dict]:
        if hold_id in cls._mem_holds:
            return cls._mem_holds[hold_id]
        redis = await cls._redis()
        if redis is None:
            return None
        try:
            data = await redis.hgetall(cls._hold_key(hold_id))
            if not data:
                return None
            return {
                "owner_type": data["owner_type"],
                "owner_id": int(data["owner_id"]),
                "items": {k: float(v) for k, v in json.loads(data.get("items") or "{}").items()},
                "expire_at": float(data.get("expire_at", 0)),
                "db": False,
            }
        except Exception as e:
            logger.warning(f"[quota] 读取预占失败 {hold_id}: {e}")
            return None

    @classmethod
    async def _store_hold(cls, hold_id: str, hold: dict) -> None:
        if hold.get("db"):
            cls._mem_holds[hold_id] = hold
            return
        redis = await cls._redis()
        if redis is None:
            return
        try:
            await redis.hset(cls._hold_key(hold_id), mapping={
                "owner_type": hold["owner_type"],
                "owner_id": str(hold["owner_id"]),
                "items": json.dumps(hold["items"]),
                "expire_at": str(hold["expire_at"]),
            })
            await redis.expire(cls._hold_key(hold_id), HOLD_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"[quota] 更新预占失败 {hold_id}: {e}")

    @classmethod
    async def _drop_hold(cls, hold_id: str, hold: dict) -> None:
        cls._mem_holds.pop(hold_id, None)
        redis = await cls._redis()
        if redis is None:
            return
        try:
            await redis.delete(cls._hold_key(hold_id))
            await redis.zrem(HOLD_INDEX_KEY, hold_id)
        except Exception as e:
            logger.warning(f"[quota] 删除预占失败 {hold_id}: {e}")

    # ============================================================
    # 并发计数（conc: 带看门狗 TTL）
    # ============================================================
    @classmethod
    async def acquire_concurrency(cls, owner: Any, limit: int,
                                  global_limit: int = GLOBAL_CONCURRENCY_LIMIT) -> bool:
        """
        占用一个并发槽（超限抛 QuotaError(item=concurrency)）。
        看门狗：key TTL 60s，进程崩溃自动释放；运行中应周期性 heartbeat_concurrency。
        """
        ot, oid = _normalize_owner(owner)
        redis = await cls._redis()
        if redis is not None:
            try:
                n = await redis.incr(cls._conc_key(ot, oid))
                await redis.expire(cls._conc_key(ot, oid), CONC_WATCHDOG_SECONDS)
                g = await redis.incr(CONC_GLOBAL_KEY)
                await redis.expire(CONC_GLOBAL_KEY, CONC_WATCHDOG_SECONDS)
                if n > int(limit) or g > int(global_limit):
                    await redis.decr(cls._conc_key(ot, oid))
                    await redis.decr(CONC_GLOBAL_KEY)
                    inc_quota_reject("concurrency")
                    raise QuotaError(
                        item="concurrency",
                        remaining=max(int(limit) - (n - 1), 0),
                        estimated=1,
                        message="并发运行数已达上限，请稍后重试",
                    )
                return True
            except QuotaError:
                raise
            except Exception as e:
                logger.warning(f"[quota] Redis 并发计数失败，退化进程内: {e}")
        # 降级：进程内计数
        key = f"{ot}:{oid}"
        n = cls._mem_conc.get(key, 0) + 1
        g = cls._mem_conc.get("__global__", 0) + 1
        if n > int(limit) or g > int(global_limit):
            inc_quota_reject("concurrency")
            raise QuotaError(item="concurrency", remaining=max(int(limit) - (n - 1), 0),
                             estimated=1, message="并发运行数已达上限，请稍后重试")
        cls._mem_conc[key] = n
        cls._mem_conc["__global__"] = g
        return True

    @classmethod
    async def release_concurrency(cls, owner: Any) -> None:
        ot, oid = _normalize_owner(owner)
        redis = await cls._redis()
        if redis is not None:
            try:
                for key in (cls._conc_key(ot, oid), CONC_GLOBAL_KEY):
                    val = await redis.decr(key)
                    if val < 0:
                        await redis.set(key, 0, ex=CONC_WATCHDOG_SECONDS)
                    await redis.expire(key, CONC_WATCHDOG_SECONDS)
                return
            except Exception as e:
                logger.warning(f"[quota] Redis 并发释放失败，退化进程内: {e}")
        key = f"{ot}:{oid}"
        cls._mem_conc[key] = max(cls._mem_conc.get(key, 0) - 1, 0)
        cls._mem_conc["__global__"] = max(cls._mem_conc.get("__global__", 0) - 1, 0)

    @classmethod
    async def heartbeat_concurrency(cls, owner: Any) -> None:
        """看门狗续期（运行中长任务周期调用）"""
        ot, oid = _normalize_owner(owner)
        redis = await cls._redis()
        if redis is None:
            return
        try:
            await redis.expire(cls._conc_key(ot, oid), CONC_WATCHDOG_SECONDS)
            await redis.expire(CONC_GLOBAL_KEY, CONC_WATCHDOG_SECONDS)
        except Exception:
            pass

    @classmethod
    async def current_concurrency(cls, ot: str, oid: int) -> int:
        redis = await cls._redis()
        if redis is not None:
            try:
                return int(await redis.get(cls._conc_key(ot, oid)) or 0)
            except Exception:
                pass
        return cls._mem_conc.get(f"{ot}:{oid}", 0)

    # ============================================================
    # 看板
    # ============================================================
    @classmethod
    async def board(cls, owner: Any) -> Dict[str, Any]:
        """
        配额看板（docs/arch/04 §2.3 GET /v1/u/quota 输出形态）：
        {plan, period, items: [{item, limit, used, held}]}
        """
        from base.common.quota.services.plan_service import PlanService

        ot, oid = _normalize_owner(owner)
        plan = await PlanService.resolve_plan(ot, oid)
        account = await cls.ensure_account(ot, oid)
        redis = await cls._redis()
        items: List[Dict[str, Any]] = []
        limits = (plan.quota_items if plan else {}) or {}
        for item, limit in limits.items():
            period = cls._item_period(item)
            used = float((account.used or {}).get(item, 0))
            held = 0.0
            if item == "concurrency":
                used = float(await cls.current_concurrency(ot, oid))
            elif redis is not None:
                try:
                    used = float(await redis.get(cls._used_key(ot, oid, item, period)) or used)
                    held = float(await redis.get(cls._held_key(ot, oid, item, period)) or 0)
                except Exception:
                    pass
            else:
                # 降级：进程内预占合计
                held = sum(
                    float(h["items"].get(item, 0))
                    for h in cls._mem_holds.values()
                    if h["owner_type"] == ot and int(h["owner_id"]) == oid
                )
            items.append({
                "item": item,
                "limit": limit,
                "used": used,
                "held": held,
            })
        return {
            "plan": plan.code if plan else None,
            "plan_name": plan.name if plan else None,
            "period": current_period(),
            "period_start": account.period_start.isoformat() if account.period_start else None,
            "period_end": account.period_end.isoformat() if account.period_end else None,
            "items": items,
        }

    # ============================================================
    # 对账与清理（定时任务）
    # ============================================================
    @classmethod
    async def reconcile_active_accounts(cls) -> int:
        """
        活跃账户对账落盘（§3.6：Redis → PG used，每分钟）；
        顺带完成周期滚动。返回对账账户数。Redis 不可用时仅做滚动。
        """
        redis = await cls._redis()
        owners: List[str] = []
        if redis is not None:
            try:
                owners = list(await redis.smembers(ACTIVE_OWNERS_KEY) or [])
            except Exception as e:
                logger.warning(f"[quota] 对账读取活跃账户失败: {e}")
        count = 0
        for ident in owners:
            ot, _, oid = ident.partition(":")
            try:
                account = await cls.ensure_account(ot, int(oid))
                if redis is not None:
                    period = current_period()
                    pattern = cls._used_key(ot, int(oid), "*", period)
                    used = dict(account.used or {})
                    async for key in redis.scan_iter(match=pattern):
                        item = key.split(":")[3]
                        used[item] = float(await redis.get(key) or 0)
                    account.used = used
                    await account.save()
                count += 1
            except Exception as e:
                logger.error(f"[quota] 对账失败 {ident}: {e}")
        return count

    @classmethod
    async def cleanup_stale_holds(cls, now_ts: Optional[float] = None) -> int:
        """
        悬挂预占清理（AR-08）：超 TTL 未结算的 hold 释放（Redis 索引 + 进程内登记）。
        hold hash 已被 Redis TTL 删除的，仅清索引（计数器 held 泄漏由对账/周期滚动兜底，
        方向为保守多计，符合安全侧）。
        """
        ts = now_ts or time.time()
        released = 0
        # 进程内降级登记
        for hold_id in list(cls._mem_holds.keys()):
            hold = cls._mem_holds.get(hold_id)
            if hold and float(hold.get("expire_at", 0)) <= ts:
                if await cls.quota_release(hold_id):
                    released += 1
        redis = await cls._redis()
        if redis is None:
            return released
        try:
            stale_ids = await redis.zrangebyscore(HOLD_INDEX_KEY, "-inf", ts)
            for hold_id in stale_ids:
                try:
                    if await cls.quota_release(hold_id):
                        released += 1
                    else:
                        await redis.zrem(HOLD_INDEX_KEY, hold_id)
                except Exception as e:
                    logger.error(f"[quota] 清理悬挂预占失败 {hold_id}: {e}")
        except Exception as e:
            logger.warning(f"[quota] 扫描悬挂预占失败: {e}")
        return released
