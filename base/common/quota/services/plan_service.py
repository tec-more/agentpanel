"""
M9 套餐服务：QuotaPlan CRUD、绑定关系管理、主体套餐解析

溯源：
- docs/arch/02 §4.2 / PRD §7.3：客户按会员等级（MembershipLevel.level_type）、
  后台用户按角色（Role.code）双向映射到同一配额项集合（Q-D / C-17）
- quota.py QuotaPlan docstring：映射关系由服务层维护，不在套餐表建 FK
- docs/arch/06 §1.1：MembershipLevel/Role → QuotaPlan 单向映射

解析规则：
- cus：有效 CustomerMembership（is_active 且未过期）→ membership_level.level_type
  → 绑定；无会员记录时按 "regular" 兜底
- usr：用户全部激活角色 code → 绑定集合，priority 大者优先，并列取 plan_id 大者
- 未命中绑定：返回 None（不计量不拦截，看板 plan=null）
"""
from typing import Any, Dict, List, Optional

from loguru import logger

from base.common.quota.models.binding import QuotaPlanBinding
from base.common.quota.models.quota import QuotaPlan


class PlanService:
    """套餐定义与绑定（全部 async）"""

    # ============================================================
    # 套餐 CRUD
    # ============================================================
    @staticmethod
    async def create_plan(data: Dict[str, Any]) -> QuotaPlan:
        existing = await QuotaPlan.get_or_none(code=data["code"])
        if existing:
            raise ValueError(f"套餐编码已存在: {data['code']}")
        return await QuotaPlan.create(
            code=data["code"],
            name=data["name"],
            scope=data.get("scope", "both"),
            quota_items=data.get("quota_items") or {},
            status=data.get("status", "active"),
        )

    @staticmethod
    async def update_plan(plan_id: int, data: Dict[str, Any]) -> Optional[QuotaPlan]:
        plan = await QuotaPlan.get_or_none(id=plan_id)
        if plan is None:
            return None
        if "code" in data and data["code"] != plan.code:
            dup = await QuotaPlan.get_or_none(code=data["code"])
            if dup:
                raise ValueError(f"套餐编码已存在: {data['code']}")
            plan.code = data["code"]
        for field in ("name", "scope", "quota_items", "status"):
            if field in data:
                setattr(plan, field, data[field])
        await plan.save()
        return plan

    @staticmethod
    async def delete_plan(plan_id: int) -> bool:
        plan = await QuotaPlan.get_or_none(id=plan_id)
        if plan is None:
            return False
        await plan.delete()  # 绑定经 FK CASCADE 清理；账户 plan_id 置 NULL（SET_NULL）
        return True

    @staticmethod
    async def get_plan(plan_id: int) -> Optional[QuotaPlan]:
        return await QuotaPlan.get_or_none(id=plan_id)

    @staticmethod
    async def list_plans(page: int = 1, page_size: int = 20,
                         status: Optional[str] = None,
                         scope: Optional[str] = None) -> Dict[str, Any]:
        query = QuotaPlan.all()
        if status:
            query = query.filter(status=status)
        if scope:
            query = query.filter(scope=scope)
        total = await query.count()
        plans = await query.offset((page - 1) * page_size).limit(page_size).order_by("id")
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [PlanService.plan_to_dict(p) for p in plans],
        }

    @staticmethod
    def plan_to_dict(plan: QuotaPlan) -> Dict[str, Any]:
        return {
            "id": plan.id,
            "code": plan.code,
            "name": plan.name,
            "scope": plan.scope,
            "quota_items": plan.quota_items or {},
            "status": plan.status,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }

    # ============================================================
    # 绑定关系管理
    # ============================================================
    @staticmethod
    async def bind(bind_type: str, bind_key: str, plan_id: int, priority: int = 0) -> QuotaPlanBinding:
        if bind_type not in (QuotaPlanBinding.BIND_TYPE_MEMBERSHIP_LEVEL, QuotaPlanBinding.BIND_TYPE_ROLE):
            raise ValueError(f"非法绑定类型: {bind_type}")
        plan = await QuotaPlan.get_or_none(id=plan_id)
        if plan is None:
            raise ValueError(f"套餐不存在: {plan_id}")
        binding = await QuotaPlanBinding.get_or_none(bind_type=bind_type, bind_key=bind_key)
        if binding:
            # 幂等：重复绑定更新指向与优先级
            binding.plan_id = plan_id
            binding.priority = priority
            await binding.save()
            return binding
        return await QuotaPlanBinding.create(
            bind_type=bind_type, bind_key=bind_key, plan_id=plan_id, priority=priority
        )

    @staticmethod
    async def unbind(binding_id: int) -> bool:
        binding = await QuotaPlanBinding.get_or_none(id=binding_id)
        if binding is None:
            return False
        await binding.delete()
        return True

    @staticmethod
    async def list_bindings(bind_type: Optional[str] = None) -> List[Dict[str, Any]]:
        query = QuotaPlanBinding.all()
        if bind_type:
            query = query.filter(bind_type=bind_type)
        bindings = await query.order_by("bind_type", "bind_key")
        return [
            {
                "id": b.id,
                "bind_type": b.bind_type,
                "bind_key": b.bind_key,
                "plan_id": b.plan_id,
                "priority": b.priority,
            }
            for b in bindings
        ]

    # ============================================================
    # 主体套餐解析
    # ============================================================
    @staticmethod
    async def resolve_plan(owner_type: str, owner_id: int) -> Optional[QuotaPlan]:
        if owner_type == "cus":
            bind_key = await PlanService._customer_level_type(owner_id)
            bind_type = QuotaPlanBinding.BIND_TYPE_MEMBERSHIP_LEVEL
            keys = [bind_key] if bind_key else []
        elif owner_type == "usr":
            keys = await PlanService._user_role_codes(owner_id)
            bind_type = QuotaPlanBinding.BIND_TYPE_ROLE
        else:
            return None
        if not keys:
            return None
        bindings = await QuotaPlanBinding.filter(
            bind_type=bind_type, bind_key__in=keys
        ).order_by("-priority", "-plan_id").prefetch_related("plan")
        for binding in bindings:
            plan = binding.plan
            if plan and plan.status == "active":
                return plan
        return None

    @staticmethod
    async def _customer_level_type(customer_id: int) -> Optional[str]:
        """客户当前有效会员等级 level_type；无记录按 regular 兜底"""
        try:
            from base.plugins.customer.models.customer_membership import CustomerMembership
            membership = await CustomerMembership.filter(
                customer_id=customer_id, is_active=True
            ).select_related("membership_level").first()
            if membership is None:
                return "regular"
            if membership.is_expired:
                return "regular"
            if membership.membership_level and membership.membership_level.level_type:
                level_type = membership.membership_level.level_type
                return getattr(level_type, "value", level_type)
            return "regular"
        except Exception as e:
            logger.warning(f"[quota] 解析客户会员等级失败 customer_id={customer_id}: {e}")
            return None

    @staticmethod
    async def _user_role_codes(user_id: int) -> List[str]:
        """后台用户激活角色 code 集合"""
        try:
            from base.core.users.models.users import User
            user = await User.get_or_none(id=user_id).prefetch_related("roles")
            if user is None:
                return []
            return [r.code for r in user.roles if r.is_active]
        except Exception as e:
            logger.warning(f"[quota] 解析用户角色失败 user_id={user_id}: {e}")
            return []
