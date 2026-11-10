"""配额计量核心服务（共享实现，P3 D-P3-2=B）。

语义与 app 历史实现一致；差异仅在 import 路径（共享 cache / 共享模型 / 共享配额域）。
"""
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from loguru import logger
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from ...cache import RedisCache
from ...domain.quota_errors import QuotaError, QuotaReservationConflict
from ..metrics import inc_llm_tokens, inc_quota_reject
from ...models.quota import QuotaAccount, UsageRecord
from ...models.reservation import QuotaReservation

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

# 同一 hold 的预占/结算/释放串行化（单实例部署；跨进程仍由 hold_id 唯一约束兜底）。
# 条带锁避免按 hold 数量无限增长。
_HOLD_LOCK_STRIPES = 64
_hold_locks: Optional[List[asyncio.Lock]] = None


def _hold_lock(hold_id: str) -> asyncio.Lock:
    global _hold_locks
    if _hold_locks is None:
        _hold_locks = [asyncio.Lock() for _ in range(_HOLD_LOCK_STRIPES)]
    return _hold_locks[hash(str(hold_id)) % _HOLD_LOCK_STRIPES]


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


def new_hold_id(prefix: str = "qh") -> str:
    """生成预占键；调用方可传入确定性键（如 harness:hr:xxx），禁止用 str(execution_id)。"""
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def default_idem_key(usage: Dict[str, Any]) -> Optional[str]:
    """确定性幂等键。

    优先使用调用方显式 idem_key；Harness 路径固定为
    harness:{run_id}:{node_id}:{seq}；旧执行路径为 exec:{execution_id}:{node_id}:{seq}。
    无稳定三元组时返回 None（回退旧去重逻辑）。
    """
    explicit = usage.get("idem_key")
    if explicit:
        return str(explicit)[:180]
    run_id = usage.get("run_id")
    node_id = usage.get("node_id")
    seq = int(usage.get("seq") or 0)
    if node_id is None:
        return None
    if run_id is not None:
        return f"harness:{run_id}:{node_id}:{seq}"[:180]
    execution_id = usage.get("execution_id")
    if execution_id is not None:
        return f"exec:{execution_id}:{node_id}:{seq}"[:180]
    return None


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
        from .plan_service import PlanService

        start, end = month_bounds()
        account = await QuotaAccount.get_or_none(owner_type=owner_type, owner_id=owner_id)
        if account is None:
            try:
                account = await QuotaAccount.create(
                    owner_type=owner_type, owner_id=owner_id,
                    period_start=start, period_end=end, used={},
                )
            except IntegrityError:
                # 并发首建：唯一约束兜底，回读已存在的账户
                account = await QuotaAccount.get_or_none(
                    owner_type=owner_type, owner_id=owner_id
                )
                if account is None:
                    raise
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
                await account.save(update_fields=["used", "period_start", "period_end"])

        plan = await PlanService.resolve_plan(owner_type, owner_id)
        if plan is not None and account.plan_id != plan.id:
            account.plan_id = plan.id
            # 只写 plan_id：避免用陈旧快照覆盖并发预扣/结算写回的 used
            await account.save(update_fields=["plan_id"])
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
        hold_id: Optional[str] = None,
        source: str = "agent",
        ref_type: Optional[str] = None,
        ref_id: Optional[str] = None,
        member_id: Optional[int] = None,
    ) -> str:
        """
        预估并原子预占（DB 持久化 + Redis 实时计数）。

        Args:
            owner: OwnerContext 或 (owner_type, owner_id)
            items: 预估消耗 {配额项: 数量}，如 {"token": 12000, "kb_search": 2}
            execution_id: 关联执行实例（兼容旧调用）
            hold_id: 调用方显式指定的预占键；**禁止**再以 str(execution_id) 作为默认值。
                      Harness 建议用 f"harness:{run_no}"，保证同 run 多步共享且不覆盖。
            source/ref_type/ref_id: 预占来源与业务引用，写入 quota_reservation 供对账。
            member_id: 组织配额按成员拆分维度（P3）；可为空。

        Returns:
            hold_id（空字符串表示该主体未绑定套餐、不计量）

        Raises:
            QuotaError: 42901 语义，含 item/剩余/预计
        """
        from .plan_service import PlanService

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

        hold_id = hold_id or new_hold_id("qh")
        account = await cls.ensure_account(owner_type, owner_id)
        if account.status != "active":
            raise QuotaError(item="account", remaining=0, estimated=0, message="配额账户已停用")

        # 同一 hold_id 的预占只允许发生一次：先读 DB 事实源，存在即返回首次结果；
        # 并发/跨进程由 quota_reservation.hold_id 唯一约束兜底（见 _claim_reservation）。
        async with _hold_lock(hold_id):
            existing = await QuotaReservation.get_or_none(hold_id=hold_id)
            if existing is not None:
                if existing.status in ("active", "partial"):
                    return hold_id
                raise QuotaReservationConflict(hold_id, existing.status)

            redis = await cls._redis()
            if redis is not None:
                try:
                    return await cls._estimate_redis(
                        redis, owner_type, owner_id, requested, limits, account,
                        execution_id, hold_id=hold_id, source=source,
                        ref_type=ref_type, ref_id=ref_id, plan_id=plan.id,
                        member_id=member_id,
                    )
                except (QuotaError, QuotaReservationConflict):
                    raise
                except Exception as e:
                    logger.warning(f"[quota] Redis 预占失败，降级 DB 路径: {e}")
            return await cls._estimate_db(
                owner_type, owner_id, requested, limits, account, execution_id,
                hold_id=hold_id, source=source, ref_type=ref_type, ref_id=ref_id,
                plan_id=plan.id, member_id=member_id,
            )

    @classmethod
    async def _estimate_redis(cls, redis, ot: str, oid: int, requested: Dict[str, float],
                              limits: Dict[str, Any], account: QuotaAccount,
                              execution_id: Optional[int], *,
                              hold_id: str, source: str = "agent",
                              ref_type: Optional[str] = None, ref_id: Optional[str] = None,
                              plan_id: Optional[int] = None,
                              member_id: Optional[int] = None) -> str:
        # 幂等闸门：先用 quota_reservation.hold_id 唯一约束抢占（status=pending）。
        # 同一 hold_id 第二次调用：已 active/partial 直接返回首次结果；仍 pending 明确报冲突。
        expire_at = time.time() + HOLD_TTL_SECONDS
        row, created = await cls._claim_reservation(
            hold_id, ot, oid, requested, execution_id,
            source=source, ref_type=ref_type, ref_id=ref_id,
            plan_id=plan_id, expire_at=expire_at, counter_mode="redis",
            member_id=member_id,
        )
        if not created:
            if row.status in ("active", "partial"):
                return hold_id
            raise QuotaReservationConflict(hold_id, row.status)

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

            await redis.hset(cls._hold_key(hold_id), mapping={
                "owner_type": ot,
                "owner_id": str(oid),
                "items": json.dumps({item: amount for item, _, amount in held_keys}),
                "expire_at": str(expire_at),
            })
            await redis.expire(cls._hold_key(hold_id), HOLD_TTL_SECONDS)
            await redis.zadd(HOLD_INDEX_KEY, {hold_id: expire_at})
            await redis.sadd(ACTIVE_OWNERS_KEY, f"{ot}:{oid}")

            # 计数成功后置为 active；失败则整体补偿并删除 pending 行，允许重试
            await cls._activate_reservation(row, requested)
        except Exception:
            for item, held_key, amount in held_keys:
                try:
                    await redis.incrbyfloat(held_key, -float(amount))
                except Exception:
                    pass
            try:
                await redis.delete(cls._hold_key(hold_id))
                await redis.zrem(HOLD_INDEX_KEY, hold_id)
            except Exception:
                pass
            await cls._delete_pending(hold_id)
            raise
        return hold_id

    @classmethod
    async def _estimate_db(cls, ot: str, oid: int, requested: Dict[str, float],
                           limits: Dict[str, Any], account: QuotaAccount,
                           execution_id: Optional[int], *,
                           hold_id: str, source: str = "agent",
                           ref_type: Optional[str] = None, ref_id: Optional[str] = None,
                           plan_id: Optional[int] = None,
                           member_id: Optional[int] = None) -> str:
        """降级：DB 事务内强校验 + 预扣（§05-1.1），预占登记同时落库"""
        expire_at = time.time() + HOLD_TTL_SECONDS
        row, created = await cls._claim_reservation(
            hold_id, ot, oid, requested, execution_id,
            source=source, ref_type=ref_type, ref_id=ref_id,
            plan_id=plan_id, expire_at=expire_at, counter_mode="db",
            member_id=member_id,
        )
        if not created:
            if row.status in ("active", "partial"):
                return hold_id
            raise QuotaReservationConflict(hold_id, row.status)

        try:
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
                # 与本事务同提交：要么预扣+active 一起生效，要么都不生效
                await QuotaReservation.filter(id=row.id, status="pending").using_db(conn).update(
                    status="active", items=dict(requested), original_items=dict(requested)
                )
        except Exception:
            await cls._delete_pending(hold_id)
            raise

        cls._mem_holds[hold_id] = {
            "owner_type": ot, "owner_id": oid,
            "items": dict(requested),  # 已预扣量（结算时按真实用量修正差额）
            "charged": dict(requested),
            "used_items": {},
            "expire_at": expire_at,
            "db": True,
            "persisted": True,
        }
        return hold_id

    @classmethod
    async def _claim_reservation(
        cls, hold_id: str, ot: str, oid: int, requested: Dict[str, float],
        execution_id: Optional[int], *, source: str, ref_type: Optional[str],
        ref_id: Optional[str], plan_id: Optional[int], expire_at: Optional[float],
        counter_mode: str = "redis",
        member_id: Optional[int] = None,
    ) -> Tuple[QuotaReservation, bool]:
        """用 quota_reservation.hold_id 唯一约束抢占预占权。

        返回 (row, created)：
        - created=True：本次调用新建 pending 行，继续做实际预扣；
        - created=False：已有行（并发调用或重复调用），由调用方判断 active/partial 复用还是报冲突。
        """
        kwargs = dict(
            hold_id=hold_id,
            owner_type=ot,
            owner_id=oid,
            plan_id=plan_id,
            period=current_period(),
            items=dict(requested),
            original_items=dict(requested),
            used_items={},
            status="pending",
            counter_mode=counter_mode,
            source=source,
            ref_type=ref_type,
            ref_id=ref_id,
            execution_id=execution_id,
            expire_at=datetime.fromtimestamp(expire_at, tz=timezone.utc) if expire_at else None,
            meta={"member_id": member_id} if member_id else None,
        )
        try:
            return await QuotaReservation.create(**kwargs), True
        except IntegrityError:
            existing = await QuotaReservation.get_or_none(hold_id=hold_id)
            if existing is None:
                raise
            return existing, False

    @classmethod
    async def _activate_reservation(cls, row: QuotaReservation, requested: Dict[str, float]) -> None:
        """pending → active；仅当仍是 pending 时生效（避免覆盖并发失败清理）。"""
        await QuotaReservation.filter(id=row.id, status="pending").update(
            status="active", items=dict(requested), original_items=dict(requested)
        )

    @classmethod
    async def _delete_pending(cls, hold_id: str) -> None:
        """预扣失败时删除 pending 行，允许同一 hold_id 重试。"""
        await QuotaReservation.filter(hold_id=hold_id, status="pending").delete()

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

        # 已落库预占：走行锁 + 唯一 idem_key 的强幂等路径（并发重复只成功一次）
        if hold_id:
            async with _hold_lock(hold_id):
                row = await QuotaReservation.get_or_none(hold_id=hold_id)
                if row is not None:
                    if row.status not in ("active", "partial"):
                        return {"settled": 0, "skipped": len(entries), "missing_hold": True}
                    return await cls._settle_reserved(row, entries)

        # ---- 无登记行：保持既有语义（历史 Redis-only 预占 / 无预占 owner 路径）----
        hold = await cls._load_hold(hold_id) if hold_id else None

        if hold is not None:
            ot, oid = hold["owner_type"], int(hold["owner_id"])
            hold_member_id = hold.get("member_id")
        elif owner is not None:
            ot, oid = _normalize_owner(owner)
            hold_member_id = None
        elif hold_id:
            return {"settled": 0, "skipped": 0, "missing_hold": True}
        else:
            return {"settled": 0, "skipped": 0}

        fresh, skipped = await cls._dedupe_entries(entries)
        if not fresh:
            # 全部重复：仅可能仍需释放已空预占
            if hold is not None and not any(float(v) > 0 for v in hold["items"].values()):
                await cls._drop_hold(hold_id, hold)
            return {"settled": 0, "skipped": skipped}

        real = cls._aggregate_real(fresh)

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

        # ---- 流水落库（idem_key 确定性去重；source 单独留痕，禁止跨来源混算）----
        written = 0
        for u in fresh:
            await cls._create_usage_record(u, ot, oid, hold_member_id)
            written += 1

        # ---- 预占收尾（同步更新 quota_reservation，DB 为对账事实源）----
        if hold is not None:
            used_items = dict(hold.get("used_items") or {})
            for item, amount in real.items():
                used_items[item] = float(used_items.get(item, 0)) + float(amount)
            hold["used_items"] = used_items
            if any(float(v) > 0 for v in hold["items"].values()):
                await cls._store_hold(hold_id, hold, status="partial")
            else:
                await cls._drop_hold(hold_id, hold, status="settled")

        return {"settled": written, "skipped": skipped}

    @classmethod
    async def _settle_reserved(cls, row: QuotaReservation, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """已落库预占的结算：行锁串行化 → 唯一 idem_key 抢占用流水 → 再改计数。

        先落流水再改计数：并发/重试只会“少计”（由对账发现），不会双计。
        """
        ot, oid = row.owner_type, int(row.owner_id)
        hold_member_id = (row.meta or {}).get("member_id")
        is_db = (row.counter_mode or "redis") == "db"
        account = await cls.ensure_account(ot, oid) if is_db else None

        async with in_transaction() as conn:
            locked = await QuotaReservation.filter(id=row.id).select_for_update().using_db(conn).first()
            if locked is None or locked.status not in ("active", "partial"):
                return {"settled": 0, "skipped": len(entries), "missing_hold": True}
            hold = cls._hold_from_row(locked)
            fresh, skipped = await cls._dedupe_entries(entries, conn)
            if not fresh:
                if not any(float(v) > 0 for v in hold["items"].values()):
                    await cls._persist_hold_state(conn, locked, hold, "settled")
                return {"settled": 0, "skipped": skipped}

            written = 0
            for u in fresh:
                await cls._create_usage_record(u, ot, oid, hold_member_id, using_db=conn)
                written += 1
            real = cls._aggregate_real(fresh)

            # 预占扣减：held 转 used，记录本次实际消耗的预占量
            deltas: Dict[str, Tuple[float, float]] = {}
            for item, amount in real.items():
                take = min(float(amount), float(hold["items"].get(item, 0)))
                hold["items"][item] = float(hold["items"].get(item, 0)) - take
                deltas[item] = (float(amount), float(take))
            used_items = dict(hold.get("used_items") or {})
            for item, amount in real.items():
                used_items[item] = float(used_items.get(item, 0)) + float(amount)
            hold["used_items"] = used_items

            if is_db and account is not None:
                acc = await QuotaAccount.filter(id=account.id).select_for_update().using_db(conn).first()
                used = dict(acc.used or {})
                for item, (amount, take) in deltas.items():
                    delta = amount - take  # 预占时已计入 used，只补超出部分
                    if delta:
                        used[item] = float(used.get(item, 0)) + delta
                acc.used = used
                await acc.save(using_db=conn)

            status = "partial" if any(float(v) > 0 for v in hold["items"].values()) else "settled"
            await cls._persist_hold_state(conn, locked, hold, status)

        # 事务提交后再更新 Redis 实时计数（redis 模式）；失败不影响 DB 事实源
        if not is_db:
            await cls._apply_redis_settle(row.hold_id, ot, oid, hold, deltas, status)
        if status == "partial":
            cls._mem_holds[row.hold_id] = hold
        else:
            cls._mem_holds.pop(row.hold_id, None)
        return {"settled": written, "skipped": skipped}

    @classmethod
    async def _dedupe_entries(cls, entries: List[Dict[str, Any]], conn=None) -> Tuple[List[Dict[str, Any]], int]:
        """确定性 idem_key 优先，旧路径回退 (execution_id,node_id,seq)。conn 用于行锁事务内复用。"""
        fresh: List[Dict[str, Any]] = []
        skipped = 0
        if not entries:
            return fresh, skipped

        idem_keys = {k for u in entries if (k := default_idem_key(u))}
        existing_idem: set = set()
        if idem_keys:
            q = UsageRecord.filter(idem_key__in=list(idem_keys))
            if conn is not None:
                q = q.using_db(conn)
            existing_idem = set(await q.values_list("idem_key", flat=True))

        dedup_keys = {
            (u.get("execution_id"), u.get("node_id"), int(u.get("seq") or 0))
            for u in entries
            if u.get("execution_id") is not None and u.get("node_id") is not None
        }
        existing = set()
        if dedup_keys:
            exec_ids = {k[0] for k in dedup_keys}
            node_ids = {k[1] for k in dedup_keys}
            q = UsageRecord.filter(execution_id__in=exec_ids, node_id__in=node_ids)
            if conn is not None:
                q = q.using_db(conn)
            for r in await q.all():
                existing.add((r.execution_id, r.node_id, r.seq))

        for u in entries:
            ik = default_idem_key(u)
            key = (u.get("execution_id"), u.get("node_id"), int(u.get("seq") or 0))
            if ik and ik in existing_idem:
                skipped += 1
                continue
            if u.get("execution_id") is not None and u.get("node_id") is not None and key in existing:
                skipped += 1
                continue
            fresh.append(u)
        return fresh, skipped

    @staticmethod
    def _aggregate_real(entries: List[Dict[str, Any]]) -> Dict[str, float]:
        real: Dict[str, float] = {}
        for u in entries:
            item = _usage_item(u.get("resource_type") or u.get("item") or "")
            if not item:
                continue
            amount = float(u.get("amount", 0) or 0) or float(
                (u.get("tokens_in") or 0) + (u.get("tokens_out") or 0)
                + (u.get("cache_read_tokens") or 0) + (u.get("cache_write_tokens") or 0)
            )
            real[item] = real.get(item, 0.0) + amount
        return real

    @staticmethod
    def _hold_from_row(row: QuotaReservation) -> dict:
        return {
            "owner_type": row.owner_type,
            "owner_id": int(row.owner_id),
            "items": {k: float(v) for k, v in (row.items or {}).items()},
            "used_items": {k: float(v) for k, v in (row.used_items or {}).items()},
            "expire_at": row.expire_at.timestamp() if row.expire_at else 0.0,
            "db": (row.counter_mode or "redis") == "db",
            "persisted": True,
            "member_id": (row.meta or {}).get("member_id"),
        }

    @classmethod
    async def _create_usage_record(cls, u: Dict[str, Any], ot: str, oid: int,
                                   hold_member_id: Optional[int] = None, using_db=None) -> None:
        price_snapshot = u.get("price_snapshot")
        raw_member = u.get("member_id")
        if raw_member is None:
            raw_member = hold_member_id
        kwargs = dict(
            owner_type=ot,
            owner_id=oid,
            member_id=int(raw_member) if raw_member else None,
            execution_id=u.get("execution_id"),
            node_id=u.get("node_id"),
            seq=int(u.get("seq") or 0),
            resource_type=u.get("resource_type") or u.get("item") or "unknown",
            amount=float(u.get("amount", 0) or 0),
            tokens_in=int(u.get("tokens_in") or 0),
            tokens_out=int(u.get("tokens_out") or 0),
            cost=u.get("cost") or 0,
            source=str(u.get("source") or "provider"),
            gateway_key=u.get("gateway_key"),
            usage_kind=str(u.get("usage_kind") or "normal"),
            idem_key=default_idem_key(u),
            session_ref=u.get("session_ref"),
            model=u.get("model"),
            provider=u.get("provider"),
            cache_read_tokens=int(u.get("cache_read_tokens") or 0),
            cache_write_tokens=int(u.get("cache_write_tokens") or 0),
            reasoning_tokens=int(u.get("reasoning_tokens") or 0),
            currency=str(u.get("currency") or "CNY"),
            price_snapshot=price_snapshot,
            raw_seq=int(u.get("raw_seq") or 0),
        )
        if using_db is not None:
            kwargs["using_db"] = using_db
        await UsageRecord.create(**kwargs)
        inc_llm_tokens(ot, u.get("model") or "unknown",
                       int(u.get("tokens_in") or 0), int(u.get("tokens_out") or 0))

    @classmethod
    async def _persist_hold_state(cls, conn, row: QuotaReservation, hold: dict, status: str) -> None:
        await QuotaReservation.filter(id=row.id, status__in=["active", "partial"]).using_db(conn).update(
            items=hold.get("items") or {},
            used_items=hold.get("used_items") or {},
            status=status,
            settled_at=_now() if status == "settled" else None,
            updated_at=_now(),
        )

    @classmethod
    async def _apply_redis_settle(cls, hold_id: str, ot: str, oid: int, hold: dict,
                                  deltas: Dict[str, Tuple[float, float]], status: str) -> None:
        """事务提交后更新 Redis 实时计数；held 扣减做非负钳制。"""
        redis = await cls._redis()
        if redis is None:
            return
        try:
            for item, (amount, take) in deltas.items():
                period = cls._item_period(item)
                used_key = cls._used_key(ot, oid, item, period)
                ttl = cls._period_ttl(item)
                if not await redis.exists(used_key):
                    await redis.set(used_key, 0, ex=ttl)
                await redis.incrbyfloat(used_key, amount)
                await redis.expire(used_key, ttl)
                if take > 0:
                    held_key = cls._held_key(ot, oid, item, period)
                    current = float(await redis.get(held_key) or 0)
                    dec = min(current, take)
                    if dec > 0:
                        await redis.incrbyfloat(held_key, -dec)
            await redis.sadd(ACTIVE_OWNERS_KEY, f"{ot}:{oid}")
            if status == "partial":
                await redis.hset(cls._hold_key(hold_id), mapping={
                    "owner_type": ot,
                    "owner_id": str(oid),
                    "items": json.dumps(hold.get("items") or {}),
                    "expire_at": str(hold.get("expire_at") or 0),
                })
            else:
                await redis.delete(cls._hold_key(hold_id))
                await redis.zrem(HOLD_INDEX_KEY, hold_id)
        except Exception as e:
            logger.warning(f"[quota] 结算后更新 Redis 计数失败 {hold_id}: {e}")

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
        async with _hold_lock(hold_id):
            row = await QuotaReservation.get_or_none(hold_id=hold_id)
            if row is not None:
                if row.status not in ("active", "partial"):
                    return False
                return await cls._release_reserved(row)

            # 历史 Redis-only 预占：保持既有语义
            hold = await cls._load_hold(hold_id)
            if hold is None:
                return False
            ot, oid = hold["owner_type"], int(hold["owner_id"])
            redis = await cls._redis()
            if redis is not None:
                for item, amount in hold["items"].items():
                    if amount:
                        held_key = cls._held_key(ot, oid, item, cls._item_period(item))
                        current = float(await redis.get(held_key) or 0)
                        dec = min(current, float(amount))  # 非负钳制
                        if dec > 0:
                            await redis.incrbyfloat(held_key, -dec)
                        hold["items"][item] = 0.0
            await cls._drop_hold(hold_id, hold, status="released")
            return True

    @classmethod
    async def _release_reserved(cls, row: QuotaReservation) -> bool:
        """已落库预占的释放：行锁内条件更新，重复/释放后再结算均为确定行为。"""
        ot, oid = row.owner_type, int(row.owner_id)
        is_db = (row.counter_mode or "redis") == "db"
        account = await cls.ensure_account(ot, oid) if is_db else None

        async with in_transaction() as conn:
            locked = await QuotaReservation.filter(id=row.id).select_for_update().using_db(conn).first()
            if locked is None or locked.status not in ("active", "partial"):
                return False
            hold = cls._hold_from_row(locked)
            if is_db and account is not None:
                acc = await QuotaAccount.filter(id=account.id).select_for_update().using_db(conn).first()
                used = dict(acc.used or {})
                for item, amount in hold["items"].items():
                    if amount:
                        used[item] = max(float(used.get(item, 0)) - float(amount), 0)
                acc.used = used
                await acc.save(using_db=conn)
            await QuotaReservation.filter(id=row.id).using_db(conn).update(
                items={},
                used_items=hold.get("used_items") or {},
                status="released",
                released_at=_now(),
                updated_at=_now(),
            )

        if not is_db:
            redis = await cls._redis()
            if redis is not None:
                try:
                    for item, amount in hold["items"].items():
                        if amount:
                            held_key = cls._held_key(ot, oid, item, cls._item_period(item))
                            current = float(await redis.get(held_key) or 0)
                            dec = min(current, float(amount))  # 非负钳制
                            if dec > 0:
                                await redis.incrbyfloat(held_key, -dec)
                    await redis.delete(cls._hold_key(row.hold_id))
                    await redis.zrem(HOLD_INDEX_KEY, row.hold_id)
                except Exception as e:
                    logger.warning(f"[quota] 释放后更新 Redis 计数失败 {row.hold_id}: {e}")
        cls._mem_holds.pop(row.hold_id, None)
        return True

    # ============================================================
    # 预占存取
    # ============================================================
    @classmethod
    async def _load_hold(cls, hold_id: str) -> Optional[dict]:
        """读取预占：进程缓存 → DB(reservation) → Redis（兼容历史未落库预占）。"""
        if hold_id in cls._mem_holds:
            return cls._mem_holds[hold_id]

        # 1) DB 事实源（进程重启/Redis 失联后仍可结算与释放）
        try:
            row = await QuotaReservation.get_or_none(hold_id=hold_id)
        except Exception as e:
            logger.warning(f"[quota] 读取预占登记失败 {hold_id}: {e}")
            row = None
        if row is not None:
            if row.status not in ("active", "partial"):
                return None
            return {
                "owner_type": row.owner_type,
                "owner_id": int(row.owner_id),
                "items": {k: float(v) for k, v in (row.items or {}).items()},
                "used_items": {k: float(v) for k, v in (row.used_items or {}).items()},
                "expire_at": row.expire_at.timestamp() if row.expire_at else 0.0,
                "db": row.counter_mode == "db",
                "persisted": True,
                "member_id": (row.meta or {}).get("member_id"),
            }

        # 2) Redis 回退（历史数据）
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
                "member_id": None,
            }
        except Exception as e:
            logger.warning(f"[quota] 读取预占失败 {hold_id}: {e}")
            return None

    @classmethod
    async def _store_hold(cls, hold_id: str, hold: dict, status: str = "partial") -> None:
        if hold.get("db"):
            cls._mem_holds[hold_id] = hold
        else:
            redis = await cls._redis()
            if redis is not None:
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

        # DB 持久化：DB 为对账事实源（Redis 仅做实时计数）
        try:
            await QuotaReservation.filter(hold_id=hold_id).update(
                items=hold.get("items") or {},
                used_items=hold.get("used_items") or {},
                status=status,
                updated_at=_now(),
            )
        except Exception as e:
            logger.warning(f"[quota] 更新预占登记失败 {hold_id}: {e}")

    @classmethod
    async def _drop_hold(cls, hold_id: str, hold: dict, status: str = "settled") -> None:
        cls._mem_holds.pop(hold_id, None)
        redis = await cls._redis()
        if redis is not None:
            try:
                await redis.delete(cls._hold_key(hold_id))
                await redis.zrem(HOLD_INDEX_KEY, hold_id)
            except Exception as e:
                logger.warning(f"[quota] 删除预占失败 {hold_id}: {e}")

        now = _now()
        try:
            await QuotaReservation.filter(hold_id=hold_id).update(
                items={},
                used_items=hold.get("used_items") or {},
                status=status,
                settled_at=now if status == "settled" else None,
                released_at=now if status == "released" else None,
                updated_at=now,
            )
        except Exception as e:
            logger.warning(f"[quota] 结束预占登记失败 {hold_id}: {e}")

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
        from .plan_service import PlanService

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
                "available": max(float(limit) - used - held, 0),
            })
        return {
            "owner_type": ot,
            "owner_id": oid,
            "status": account.status,
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
    async def reconcile_active_accounts(cls) -> Dict[str, Any]:
        """
        活跃账户对账落盘（§3.6：Redis → PG used，每分钟）；
        顺带完成周期滚动。Redis 不可用时仅做滚动。

        逐条容错：单条标识无法解析或落盘失败时跳过该条并计入异常清单，
        不中断整批；异常清单保留原始标识、失败原因与批次号。
        返回 {batch_no, total, processed, skipped, anomalies}。
        """
        batch_no = f"qrc{_now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4]}"
        redis = await cls._redis()
        owners: List[str] = []
        if redis is not None:
            try:
                owners = list(await redis.smembers(ACTIVE_OWNERS_KEY) or [])
            except Exception as e:
                logger.warning(f"[quota] 对账读取活跃账户失败: {e}")
        processed = 0
        anomalies: List[Dict[str, Any]] = []

        def _skip(ident: str, reason: str, exc: Optional[Exception] = None) -> None:
            anomaly = {
                "batch_no": batch_no,
                "hold_id": ident,
                "reason": reason,
                "error": str(exc) if exc else None,
            }
            anomalies.append(anomaly)
            detail = f"[quota] 对账跳过 batch={batch_no} hold_id={ident} reason={reason}"
            if exc is not None:
                detail += f" error={exc}"
            logger.warning(detail)

        for ident in owners:
            ot, sep, raw_oid = ident.partition(":")
            if not sep or not ot or not raw_oid:
                _skip(ident, "标识格式不符，应为 owner_type:owner_id")
                continue
            try:
                oid = int(raw_oid)
            except (TypeError, ValueError) as e:
                _skip(ident, f"owner_id 无法解析为整数: {raw_oid!r}", e)
                continue
            try:
                account = await cls.ensure_account(ot, oid)
                if redis is not None:
                    period = current_period()
                    pattern = cls._used_key(ot, oid, "*", period)
                    used = dict(account.used or {})
                    async for key in redis.scan_iter(match=pattern):
                        item = key.split(":")[3]
                        used[item] = float(await redis.get(key) or 0)
                    account.used = used
                    await account.save()
                processed += 1
            except Exception as e:
                _skip(ident, "对账落盘失败", e)
        if anomalies:
            logger.warning(
                f"[quota] 对账完成 batch={batch_no} 处理 {processed} 条 / 跳过 {len(anomalies)} 条"
            )
        return {
            "batch_no": batch_no,
            "total": len(owners),
            "processed": processed,
            "skipped": len(anomalies),
            "anomalies": anomalies,
        }

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
        # DB 事实源兜底：pending（预扣中断）与 active/partial（超期未结算）
        try:
            for row in await QuotaReservation.filter(status__in=["pending", "active", "partial"]).all():
                exp = row.expire_at
                if exp is None:
                    continue
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp.timestamp() > ts:
                    continue
                if row.status == "pending":
                    if (row.counter_mode or "redis") != "db":
                        redis_h = await cls._redis()
                        if redis_h is not None:
                            try:
                                for item, amount in (row.items or {}).items():
                                    held_key = cls._held_key(
                                        row.owner_type, int(row.owner_id), item, cls._item_period(item)
                                    )
                                    current = float(await redis_h.get(held_key) or 0)
                                    dec = min(current, float(amount))
                                    if dec > 0:
                                        await redis_h.incrbyfloat(held_key, -dec)
                                await redis_h.delete(cls._hold_key(row.hold_id))
                                await redis_h.zrem(HOLD_INDEX_KEY, row.hold_id)
                            except Exception as e:
                                logger.warning(f"[quota] 清理 pending 预占计数失败 {row.hold_id}: {e}")
                    await QuotaReservation.filter(id=row.id, status="pending").delete()
                    released += 1
                else:
                    try:
                        if await cls.quota_release(row.hold_id):
                            released += 1
                    except Exception as e:
                        logger.error(f"[quota] 清理 DB 悬挂预占失败 {row.hold_id}: {e}")
        except Exception as e:
            logger.warning(f"[quota] 扫描 DB 悬挂预占失败: {e}")

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
