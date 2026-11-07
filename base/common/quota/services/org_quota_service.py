"""
P3 组织级配额服务（不依赖 agent 插件）

溯源：
- 01-需求与约束.md P3：组织维度配额，成员与客户用户共用同一套预占/结算账（不另起账本）
- quota_service：预占 quota_estimate → quota_reservation → quota_settle → usage_record 链路
- QuotaPlanBinding.bind_type=organization（bind_key=组织 ID）：组织套餐分配/调整/解绑
- QuotaAccount.owner_type=org：账户占用/预占/可用与成员拆分
- UsageRecord.member_id、QuotaReservation.meta.member_id：成员维度溯源

设计约束：
- 不新建并行账本：组织账户就是 QuotaAccount(owner_type="org")，计数/预占/结算全走 QuotaService
- 组织存在性校验复用 customer 插件模型；插件未启用时容错为空/不可用（不抛导入错误）
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from base.common.quota.models.binding import QuotaPlanBinding
from base.common.quota.models.quota import QuotaAccount, QuotaPlan, UsageRecord
from base.common.quota.models.reservation import QuotaReservation
from base.common.quota.services.plan_service import PlanService
from base.common.quota.services.quota_service import QuotaService, month_bounds

ACTIVE_HOLD_STATUSES = ("active", "partial")
ACCOUNT_STATUSES = ("active", "frozen")


class OrgQuotaError(Exception):
    """组织配额业务异常（code 供 API 映射 HTTP 状态）"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _customer_models():
    """惰性导入 customer 插件模型；插件未启用时返回 (None, None)。"""
    try:
        from base.plugins.customer.models.customer_organization import (
            CustomerOrganization,
            CustomerOrganizationMember,
        )
        return CustomerOrganization, CustomerOrganizationMember
    except Exception as e:  # pragma: no cover - 插件禁用场景
        logger.warning(f"[quota][org] customer 插件模型不可用: {e}")
        return None, None


def _ts(dt: Optional[datetime]) -> Optional[float]:
    """把 datetime 统一转 epoch 秒（兼容 use_tz 的 aware/naive）。"""
    if dt is None:
        return None
    try:
        return dt.timestamp()
    except Exception:
        return None


def _primary_amount(mapping: Optional[Dict[str, Any]]) -> float:
    """额度/用量主口径：优先 token，否则汇总数值型配额项。"""
    if not mapping:
        return 0.0
    if "token" in mapping:
        try:
            return float(mapping.get("token") or 0)
        except (TypeError, ValueError):
            return 0.0
    total = 0.0
    for value in mapping.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            total += float(value)
    return total


class OrgQuotaService:
    """组织配额账户 / 套餐分配 / 看板（全部 async）"""

    # ============================================================
    # 组织校验
    # ============================================================
    @classmethod
    async def get_organization(cls, org_id: int):
        CustomerOrganization, _ = _customer_models()
        if CustomerOrganization is None:
            raise OrgQuotaError("plugin_disabled", "customer 插件未启用，无法使用组织维度配额")
        org = await CustomerOrganization.get_or_none(id=org_id)
        if org is None:
            raise OrgQuotaError("not_found", f"组织不存在: {org_id}")
        return org

    @classmethod
    async def require_active_organization(cls, org_id: int):
        org = await cls.get_organization(org_id)
        if org.status != "active":
            raise OrgQuotaError("org_disabled", f"组织已停用: {org_id}")
        return org

    # ============================================================
    # 组织列表 / 详情
    # ============================================================
    @classmethod
    async def list_organizations(
        cls, page: int = 1, page_size: int = 20,
        status: Optional[str] = None, keyword: Optional[str] = None,
        plan_code: Optional[str] = None,
        has_stale_hold: Optional[bool] = None,
        near_limit: Optional[bool] = None,
        org_ids: Optional[List[int]] = None,
        near_limit_ratio: float = 0.8,
    ) -> Dict[str, Any]:
        CustomerOrganization, CustomerOrganizationMember = _customer_models()
        if CustomerOrganization is None:
            return {"total": 0, "page": page, "page_size": page_size, "items": []}

        query = CustomerOrganization.all()
        if org_ids is not None:
            query = query.filter(id__in=list(org_ids))
        if status:
            query = query.filter(status=status)
        if keyword:
            query = query.filter(name__icontains=keyword)

        # 高级筛选（套餐/超期预占/接近上限）需要全量计算后再分页
        advanced = bool(plan_code) or has_stale_hold is not None or bool(near_limit)
        if advanced:
            orgs = await query.order_by("id")
        else:
            total = await query.count()
            orgs = await query.offset((page - 1) * page_size).limit(page_size).order_by("id")
        org_ids_page = [o.id for o in orgs]
        if not org_ids_page:
            total = 0 if advanced else total
            return {"total": total, "page": page, "page_size": page_size, "items": []}

        # 套餐绑定（bind_key 为组织 ID 字符串）
        bindings = await QuotaPlanBinding.filter(
            bind_type=QuotaPlanBinding.BIND_TYPE_ORGANIZATION,
            bind_key__in=[str(i) for i in org_ids_page],
        ).prefetch_related("plan")
        bind_map = {b.bind_key: b for b in bindings}

        accounts = await QuotaAccount.filter(owner_type="org", owner_id__in=org_ids_page)
        acc_map = {a.owner_id: a for a in accounts}

        # 活跃成员数
        member_counts: Dict[int, int] = {}
        if CustomerOrganizationMember is not None:
            from tortoise.functions import Count
            rows = await CustomerOrganizationMember.filter(
                org_id__in=org_ids_page, status="active"
            ).group_by("org_id").annotate(n=Count("id")).values("org_id", "n")
            for r in rows:
                member_counts[int(r["org_id"])] = int(r.get("n") or 0)

        # 预占持有量（按 org 汇总），并识别超期预占
        held_map: Dict[int, float] = {}
        stale_count_map: Dict[int, int] = {}
        now_ts = datetime.now().timestamp()
        holds = await QuotaReservation.filter(
            owner_type="org", owner_id__in=org_ids_page, status__in=list(ACTIVE_HOLD_STATUSES)
        ).values("owner_id", "items", "expire_at")
        for h in holds:
            oid = int(h["owner_id"])
            held_map[oid] = held_map.get(oid, 0.0) + sum(
                float(v or 0) for v in (h["items"] or {}).values()
            )
            expire_ts = _ts(h.get("expire_at"))
            if expire_ts is not None and expire_ts <= now_ts:
                stale_count_map[oid] = stale_count_map.get(oid, 0) + 1

        items: List[Dict[str, Any]] = []
        for org in orgs:
            binding = bind_map.get(str(org.id))
            plan = binding.plan if binding else None
            acc = acc_map.get(org.id)
            used = _primary_amount((acc.used or {}) if acc else {})
            limit_total = _primary_amount((plan.quota_items or {}) if plan else {})
            held = held_map.get(org.id, 0.0)
            usage_ratio = (used + held) / limit_total if limit_total > 0 else 0.0
            item = {
                "org_id": org.id,
                "name": org.name,
                "status": org.status,
                "owner_customer_id": org.owner_customer_id,
                "member_count": member_counts.get(org.id, 0),
                "plan_id": plan.id if plan else None,
                "plan": plan.code if plan else None,
                "plan_name": plan.name if plan else None,
                "priority": binding.priority if binding else None,
                "account_status": acc.status if acc else "active",
                "used": acc.used if acc else {},
                "limit_total": limit_total,
                "used_total": used,
                "held_total": held,
                "available_total": max(limit_total - used - held, 0),
                "usage_ratio": round(usage_ratio, 4),
                "stale_hold_count": stale_count_map.get(org.id, 0),
                "has_stale_hold": stale_count_map.get(org.id, 0) > 0,
            }
            if plan_code and (not plan or plan.code != plan_code):
                continue
            if has_stale_hold is not None and item["has_stale_hold"] != bool(has_stale_hold):
                continue
            if near_limit and not (limit_total > 0 and usage_ratio >= near_limit_ratio):
                continue
            items.append(item)

        if advanced:
            total = len(items)
            items = items[(page - 1) * page_size: page * page_size]
        return {"total": total, "page": page, "page_size": page_size, "items": items}


    @classmethod
    async def _account_with_holds(cls, org_id: int) -> Dict[str, Any]:
        """账户看板以 DB 预占记录为准重算 held/available（不依赖进程内缓存）。"""
        base = await QuotaService.board(("org", org_id))
        holds = await QuotaReservation.filter(
            owner_type="org", owner_id=org_id, status__in=list(ACTIVE_HOLD_STATUSES)
        ).values("items")
        held_by_item: Dict[str, float] = {}
        for h in holds:
            for item, value in (h["items"] or {}).items():
                held_by_item[item] = held_by_item.get(item, 0.0) + float(value or 0)

        used_total = 0.0
        held_total = 0.0
        limit_total = 0.0
        for item in base.get("items") or []:
            if item.get("item") == "concurrency":
                continue
            limit = float(item.get("limit") or 0)
            used = float(item.get("used") or 0)
            held = held_by_item.get(item.get("item"), 0.0)
            item["held"] = held
            item["available"] = max(limit - used - held, 0)
            limit_total += limit
            used_total += used
            held_total += held
        base["limit_total"] = limit_total
        base["used_total"] = used_total
        base["held_total"] = held_total
        base["available_total"] = max(limit_total - used_total - held_total, 0)
        return base

    @classmethod
    async def available_plans(cls) -> List[Dict[str, Any]]:
        """组织可分配的套餐（scope=org/both 且启用）。"""
        plans = await QuotaPlan.filter(
            status="active", scope__in=["org", "both"]
        ).order_by("id")
        return [PlanService.plan_to_dict(plan) for plan in plans]

    @classmethod
    async def get_detail(cls, org_id: int) -> Dict[str, Any]:
        org = await cls.get_organization(org_id)
        binding = await QuotaPlanBinding.get_or_none(
            bind_type=QuotaPlanBinding.BIND_TYPE_ORGANIZATION, bind_key=str(org_id)
        )
        plan = None
        if binding:
            plan = await QuotaPlan.get_or_none(id=binding.plan_id)
        board = await cls._account_with_holds(org_id)
        CustomerOrganization, CustomerOrganizationMember = _customer_models()
        members: List[Dict[str, Any]] = []
        if CustomerOrganizationMember is not None:
            rows = await CustomerOrganizationMember.filter(
                org_id=org_id, status="active"
            ).prefetch_related("customer")
            for m in rows:
                members.append({
                    "member_id": m.customer_id,
                    "username": getattr(m.customer, "username", None),
                    "nickname": getattr(m.customer, "nickname", None),
                    "role": m.role,
                    "is_active": getattr(m.customer, "is_active", True),
                })
        return {
            "organization": {
                "org_id": org.id,
                "name": org.name,
                "status": org.status,
                "owner_customer_id": org.owner_customer_id,
                "member_count": len(members),
            },
            "plan": PlanService.plan_to_dict(plan) if plan else None,
            "binding": {
                "id": binding.id, "priority": binding.priority
            } if binding else None,
            "account": board,
            "members": members,
        }

    # ============================================================
    # 套餐分配 / 调整 / 解绑 / 停用
    # ============================================================
    @classmethod
    async def assign_plan(cls, org_id: int, plan_id: int, priority: int = 0) -> Dict[str, Any]:
        org = await cls.get_organization(org_id)
        try:
            binding = await PlanService.bind(
                QuotaPlanBinding.BIND_TYPE_ORGANIZATION, str(org_id), plan_id, priority
            )
        except ValueError as e:
            raise OrgQuotaError("invalid_plan", str(e))
        # 账户惰性刷新套餐指向（账户不存在时由首次预占创建）
        await QuotaAccount.filter(owner_type="org", owner_id=org_id).update(plan_id=plan_id)
        return {
            "org_id": org.id, "binding_id": binding.id,
            "plan_id": plan_id, "priority": binding.priority, "org_status": org.status,
        }

    @classmethod
    async def unbind_plan(cls, org_id: int) -> Dict[str, Any]:
        await cls.get_organization(org_id)
        binding = await QuotaPlanBinding.get_or_none(
            bind_type=QuotaPlanBinding.BIND_TYPE_ORGANIZATION, bind_key=str(org_id)
        )
        if binding is None:
            raise OrgQuotaError("not_found", f"组织未绑定套餐: {org_id}")
        await binding.delete()
        await QuotaAccount.filter(owner_type="org", owner_id=org_id).update(plan_id=None)
        return {"org_id": org_id, "binding_id": binding.id, "unbound": True}

    @classmethod
    async def set_account_status(cls, org_id: int, status_value: str) -> Dict[str, Any]:
        if status_value not in ACCOUNT_STATUSES:
            raise OrgQuotaError("invalid_status", f"非法账户状态: {status_value}，仅支持 active/frozen")
        org = await cls.get_organization(org_id)
        account = await QuotaService.ensure_account("org", org_id)
        account.status = status_value
        await account.save()
        # 停用即为 fail-closed：后续 quota_estimate 抛 QuotaError（前端/调用方按 42901 处理）
        return {
            "org_id": org.id, "org_status": org.status,
            "account_status": account.status,
        }

    # ============================================================
    # 组织看板（按组织 / 成员 / 来源 / usage_kind 拆分）
    # ============================================================
    @classmethod
    async def board(cls, org_id: int, days: int = 0) -> Dict[str, Any]:
        org = await cls.get_organization(org_id)
        base = await cls._account_with_holds(org_id)

        start, _ = month_bounds()
        if days and days > 0:
            start = datetime.now() - timedelta(days=days)

        records = await UsageRecord.filter(
            owner_type="org", owner_id=org_id, created_at__gte=start
        ).values(
            "member_id", "resource_type", "source", "usage_kind",
            "amount", "tokens_in", "tokens_out",
            "cache_read_tokens", "cache_write_tokens", "cost",
        )

        def _bucket(_key: Any = None) -> Dict[str, Any]:
            return {"used": 0.0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "records": 0}

        by_member: Dict[Any, Dict[str, Any]] = {}
        by_source: Dict[Any, Dict[str, Any]] = {}
        by_kind: Dict[Any, Dict[str, Any]] = {}
        by_resource: Dict[Any, Dict[str, Any]] = {}
        missing_member = 0
        for r in records:
            amount = float(r.get("amount") or 0)
            if not amount:
                amount = float(
                    int(r.get("tokens_in") or 0) + int(r.get("tokens_out") or 0)
                    + int(r.get("cache_read_tokens") or 0)
                    + int(r.get("cache_write_tokens") or 0)
                )
            buckets = (
                (by_member, r.get("member_id")),
                (by_source, r.get("source") or "unknown"),
                (by_kind, r.get("usage_kind") or "normal"),
                (by_resource, r.get("resource_type") or "unknown"),
            )
            for target, key in buckets:
                b = target.setdefault(key, _bucket())
                b["used"] += amount
                b["tokens_in"] += int(r.get("tokens_in") or 0)
                b["tokens_out"] += int(r.get("tokens_out") or 0)
                b["cost"] += float(r.get("cost") or 0)
                b["records"] += 1
            if r.get("member_id") is None:
                missing_member += 1

        # 成员活跃关系与名称
        CustomerOrganization, CustomerOrganizationMember = _customer_models()
        member_info: Dict[int, Dict[str, Any]] = {}
        active_member_ids: set = set()
        if CustomerOrganizationMember is not None:
            rows = await CustomerOrganizationMember.filter(
                org_id=org_id, status="active"
            ).prefetch_related("customer")
            for m in rows:
                active_member_ids.add(int(m.customer_id))
                member_info[int(m.customer_id)] = {
                    "member_id": int(m.customer_id),
                    "username": getattr(m.customer, "username", None),
                    "nickname": getattr(m.customer, "nickname", None),
                    "role": m.role,
                    "is_active": getattr(m.customer, "is_active", True),
                }

        # 预占（含超期）按成员拆分
        holds = await QuotaReservation.filter(
            owner_type="org", owner_id=org_id, status__in=list(ACTIVE_HOLD_STATUSES)
        ).order_by("expire_at")
        now_ts = datetime.now().timestamp()
        held_by_member: Dict[Any, float] = {}
        hold_items: List[Dict[str, Any]] = []
        stale_holds: List[Dict[str, Any]] = []
        for h in holds:
            member_id = (h.meta or {}).get("member_id")
            held_amount = sum(float(v or 0) for v in (h.items or {}).values())
            held_by_member[member_id] = held_by_member.get(member_id, 0.0) + held_amount
            expire_ts = _ts(h.expire_at)
            row = {
                "hold_id": h.hold_id,
                "member_id": member_id,
                "items": h.items or {},
                "used_items": h.used_items or {},
                "status": h.status,
                "source": h.source,
                "ref_type": h.ref_type,
                "ref_id": h.ref_id,
                "expire_at": h.expire_at.isoformat() if h.expire_at else None,
                "stale": bool(expire_ts is not None and expire_ts <= now_ts),
            }
            hold_items.append(row)
            if row["stale"]:
                stale_holds.append(row)

        by_member_rows = []
        for member_id, b in by_member.items():
            info = member_info.get(int(member_id)) if member_id is not None else None
            by_member_rows.append({
                "member_id": member_id,
                "username": (info or {}).get("username"),
                "nickname": (info or {}).get("nickname"),
                "role": (info or {}).get("role"),
                "member_active": (int(member_id) in active_member_ids) if member_id is not None else False,
                "member_enabled": (info or {}).get("is_active", True),
                **b,
                "held": held_by_member.get(member_id, 0.0),
            })
        # 仅有预占、无结算流水的成员也出现在名单里
        for member_id, held in held_by_member.items():
            if member_id in by_member:
                continue
            info = member_info.get(int(member_id)) if member_id is not None else None
            by_member_rows.append({
                "member_id": member_id,
                "username": (info or {}).get("username"),
                "nickname": (info or {}).get("nickname"),
                "role": (info or {}).get("role"),
                "member_active": (int(member_id) in active_member_ids) if member_id is not None else False,
                "member_enabled": (info or {}).get("is_active", True),
                **_bucket(None),
                "held": held,
            })
        by_member_rows.sort(key=lambda x: x["used"], reverse=True)

        anomalies: List[Dict[str, Any]] = []
        for row in stale_holds:
            anomalies.append({
                "type": "stale_hold",
                "hold_id": row["hold_id"],
                "member_id": row["member_id"],
                "expire_at": row["expire_at"],
                "items": row["items"],
            })
        for row in by_member_rows:
            if row["member_id"] is not None and not row["member_active"]:
                anomalies.append({
                    "type": "member_not_active",
                    "member_id": row["member_id"],
                    "used": row["used"],
                })
            elif row["member_id"] is not None and not row["member_enabled"]:
                anomalies.append({
                    "type": "member_disabled",
                    "member_id": row["member_id"],
                    "used": row["used"],
                })
        if missing_member:
            anomalies.append({
                "type": "usage_member_missing",
                "count": missing_member,
                "detail": "组织用量流水缺少 member_id，无法按成员拆分",
            })
        binding = await QuotaPlanBinding.get_or_none(
            bind_type=QuotaPlanBinding.BIND_TYPE_ORGANIZATION, bind_key=str(org_id)
        )
        account = await QuotaAccount.get_or_none(owner_type="org", owner_id=org_id)
        if binding is None and (base.get("plan") or (account and account.plan_id)):
            anomalies.append({
                "type": "plan_binding_missing",
                "detail": "账户仍指向套餐但组织绑定已解绑",
            })
        if base.get("status") != "active":
            anomalies.append({
                "type": "account_frozen",
                "detail": "配额账户已停用，预占/结算被 fail-closed 拒绝",
            })

        return {
            "organization": {
                "org_id": org.id,
                "name": org.name,
                "status": org.status,
                "owner_customer_id": org.owner_customer_id,
            },
            "account": base,
            "members": by_member_rows,
            "breakdown": {
                "by_member": by_member_rows,
                "by_source": [{"source": k, **v} for k, v in sorted(by_source.items(), key=lambda x: -x[1]["used"])],
                "by_usage_kind": [{"usage_kind": k, **v} for k, v in sorted(by_kind.items(), key=lambda x: -x[1]["used"])],
                "by_resource": [{"resource_type": k, **v} for k, v in sorted(by_resource.items(), key=lambda x: -x[1]["used"])],
            },
            "reservations": {
                "active_count": len(hold_items),
                "stale_count": len(stale_holds),
                "items": hold_items,
            },
            "anomalies": anomalies,
            "range_start": start.isoformat(),
        }
