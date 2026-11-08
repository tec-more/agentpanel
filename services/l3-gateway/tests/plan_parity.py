"""套餐双解析器对拍（spec §13.6，D-P3-2=B 硬门槛）。

同一份 fixture 下，分别用：
- L2 ORM 解析器 `base/common/quota/services/plan_resolver.py`
- 网关只读 SQL 解析器 `services/l3-gateway/app/plan_resolver.py`
调用共享 `PlanService.resolve_plan`，逐字段比较；任一分支不一致即以非 0 退出。

用法（本地库，需 DB_*/REDIS_* 环境变量）：
    .venv\\Scripts\\python.exe services\\l3-gateway\\tests\\plan_parity.py
fixture 全部以 `p3parity_` 前缀构造，结束时清理。
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, ROOT)

from tortoise import Tortoise

from packages.agentpanel_common.config import load_l3_common
from packages.agentpanel_common.db import build_tortoise_orm, shared_model_modules, stabilize_shared_model_fields
from packages.agentpanel_common.quota.services import plan_service

from base.common.quota.services.plan_resolver import L2PlanResolver
from app.plan_resolver import SqlPlanResolver

PREFIX = "p3parity_"

EXTRA_MODEL_MODULES = [
    "base.plugins.customer.models.customer",
    "base.plugins.customer.models.membership",
    "base.plugins.customer.models.customer_membership",
    "base.core.users.models.users",
    "base.core.users.models.rbac",
]

failures: List[str] = []
checks: List[str] = []


def check(name: str, left: Any, right: Any) -> None:
    if left == right:
        checks.append(f"PASS {name}: {json.dumps(left, ensure_ascii=False, default=str)}")
    else:
        failures.append(
            f"FAIL {name}\n  L2  = {json.dumps(left, ensure_ascii=False, default=str)}"
            f"\n  GW  = {json.dumps(right, ensure_ascii=False, default=str)}"
        )


async def main() -> int:
    cfg = load_l3_common(source="gateway")
    await Tortoise.init(
        config=build_tortoise_orm(cfg.db, shared_model_modules() + EXTRA_MODEL_MODULES)
    )
    stabilize_shared_model_fields()
    conn = Tortoise.get_connection("postgres")

    async def q(sql: str, params: Optional[list] = None) -> List[Dict[str, Any]]:
        return await conn.execute_query_dict(sql, params or [])

    created = {
        "plan": [], "binding": [], "level": [], "membership": [],
        "customer": [], "user": [], "role": [],
    }

    async def new_plan(code: str, status: str = "active", scope: str = "both",
                       items: Optional[dict] = None) -> int:
        rows = await q(
            "INSERT INTO quota_plan (code,name,scope,quota_items,status) "
            "VALUES ($1,$2,$3,$4::jsonb,$5) RETURNING id",
            [PREFIX + code, PREFIX + code, scope,
             json.dumps(items or {"token": 100}), status],
        )
        created["plan"].append(rows[0]["id"])
        return rows[0]["id"]

    async def new_binding(bind_type: str, bind_key: str, plan_id: int, priority: int = 0) -> None:
        rows = await q(
            "INSERT INTO quota_plan_binding (bind_type,bind_key,priority,plan_id) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            [bind_type, bind_key, priority, plan_id],
        )
        created["binding"].append(rows[0]["id"])

    async def new_customer() -> int:
        rows = await q("INSERT INTO customer DEFAULT VALUES RETURNING id")
        created["customer"].append(rows[0]["id"])
        return rows[0]["id"]

    async def new_level(level_type: str) -> int:
        rows = await q(
            "INSERT INTO customer_membership_level (level_type,name,price,features) "
            "VALUES ($1,$2,0,'{}'::jsonb) RETURNING id",
            [level_type, PREFIX + level_type],
        )
        created["level"].append(rows[0]["id"])
        return rows[0]["id"]

    async def new_membership(customer_id: int, level_id: Optional[int],
                             expire_time: Optional[str] = None) -> int:
        expire_dt = datetime.fromisoformat(expire_time) if expire_time else None
        rows = await q(
            "INSERT INTO customer_membership (customer_id,membership_level_id,expire_time,is_active) "
            "VALUES ($1,$2,$3,true) RETURNING id",
            [customer_id, level_id, expire_dt],
        )
        created["membership"].append(rows[0]["id"])
        return rows[0]["id"]

    async def new_user(tag: str) -> int:
        rows = await q(
            "INSERT INTO \"user\" (username,email,is_active) VALUES ($1,$2,true) RETURNING id",
            [PREFIX + tag, PREFIX + tag + "@example.local"],
        )
        created["user"].append(rows[0]["id"])
        return rows[0]["id"]

    async def new_role(tag: str, is_active: bool = True) -> int:
        rows = await q(
            "INSERT INTO role (name,code,is_active) VALUES ($1,$2,$3) RETURNING id",
            [PREFIX + tag, PREFIX + tag, is_active],
        )
        created["role"].append(rows[0]["id"])
        return rows[0]["id"]

    async def link(user_id: int, role_id: int) -> None:
        await q("INSERT INTO user_role (user_id,role_id) VALUES ($1,$2)", [user_id, role_id])

    def snapshot(plan: Any) -> Optional[Dict[str, Any]]:
        if plan is None:
            return None
        return {
            "id": plan.id,
            "code": plan.code,
            "name": plan.name,
            "scope": plan.scope,
            "status": plan.status,
            "quota_items": plan.quota_items,
        }

    async def compare_plan(name: str, owner_type: str, owner_id: int) -> None:
        plan_service.configure(L2PlanResolver())
        left = snapshot(await plan_service.PlanService.resolve_plan(owner_type, owner_id))
        plan_service.configure(SqlPlanResolver())
        right = snapshot(await plan_service.PlanService.resolve_plan(owner_type, owner_id))
        check(name, left, right)

    async def compare_keys(name: str, customer_id: Optional[int] = None,
                           user_id: Optional[int] = None) -> None:
        l2, sql = L2PlanResolver(), SqlPlanResolver()
        if customer_id is not None:
            check(f"{name}/customer_level", await l2.customer_level_type(customer_id),
                  await sql.customer_level_type(customer_id))
        if user_id is not None:
            check(f"{name}/user_roles",
                  sorted(await l2.user_role_codes(user_id)),
                  sorted(await sql.user_role_codes(user_id)))

    try:
        # ---------- P1 无绑定 ----------
        await compare_plan("P1 无绑定(org)", "org", 99999999)

        # ---------- P4 组织套餐 ----------
        plan_org = await new_plan("org", scope="org")
        await new_binding("organization", "90000001", plan_org, priority=1)
        await compare_plan("P4 组织套餐", "org", 90000001)

        # ---------- P5/P6/P7/P8/P14 客户等级 ----------
        level_vip = await new_level("vip")
        level_svip = await new_level("svip")
        plan_vip = await new_plan("vip", scope="cus")
        plan_regular = await new_plan("regular", scope="cus")
        await new_binding("membership_level", "vip", plan_vip, priority=2)
        await new_binding("membership_level", "regular", plan_regular, priority=0)
        await new_binding("membership_level", "svip", plan_vip, priority=2)

        cust_active = await new_customer()
        await new_membership(cust_active, level_vip, "2099-01-01T00:00:00+00:00")
        await compare_keys("P5 客户等级键", customer_id=cust_active)
        await compare_plan("P5 客户等级套餐", "cus", cust_active)

        cust_expired = await new_customer()
        await new_membership(cust_expired, level_svip, "2020-01-01T00:00:00+00:00")
        await compare_keys("P6 过期会员键", customer_id=cust_expired)
        await compare_plan("P6 过期回落 regular", "cus", cust_expired)

        cust_none = await new_customer()
        await compare_keys("P7 无会员记录键", customer_id=cust_none)
        await compare_plan("P7 无会员记录回落 regular", "cus", cust_none)

        cust_null_level = await new_customer()
        await new_membership(cust_null_level, None, None)
        await compare_keys("P8 等级为空键", customer_id=cust_null_level)
        await compare_plan("P8 等级为空回落 regular", "cus", cust_null_level)

        cust_naive = await new_customer()
        await new_membership(cust_naive, level_vip, "2025-01-01T00:00:00+00:00")
        await compare_keys("P14 过期时间键", customer_id=cust_naive)
        await compare_plan("P14 过期时间一致", "cus", cust_naive)

        # ---------- P13 客户不存在 ----------
        await compare_keys("P13 客户不存在键", customer_id=88888888)
        await compare_plan("P13 客户不存在", "cus", 88888888)

        # ---------- P2/P3/P9/P10/P11 角色套餐 ----------
        role_low = await new_role("role_low")
        role_high = await new_role("role_high")
        role_inactive = await new_role("role_inactive", is_active=False)
        plan_role_low = await new_plan("role_low", scope="usr")
        plan_role_high = await new_plan("role_high", scope="usr")
        plan_role_inactive = await new_plan("role_inactive", scope="usr")
        plan_tie_small = await new_plan("tie_small", scope="usr")
        plan_tie_large = await new_plan("tie_large", scope="usr")
        await new_binding("role", PREFIX + "role_low", plan_role_low, priority=1)
        await new_binding("role", PREFIX + "role_high", plan_role_high, priority=5)
        await new_binding("role", PREFIX + "role_inactive", plan_role_inactive, priority=9)
        await new_binding("role", PREFIX + "tie_small", plan_tie_small, priority=3)
        await new_binding("role", PREFIX + "tie_large", plan_tie_large, priority=3)

        user_multi = await new_user("user_multi")
        await link(user_multi, role_low)
        await link(user_multi, role_high)
        await link(user_multi, role_inactive)
        await compare_keys("P9/P10 用户角色键", user_id=user_multi)
        await compare_plan("P2 多角色取高优先级", "usr", user_multi)

        role_tie_a = await new_role("tie_a")
        role_tie_b = await new_role("tie_b")
        await new_binding("role", PREFIX + "tie_a", plan_tie_small, priority=3)
        await new_binding("role", PREFIX + "tie_b", plan_tie_large, priority=3)
        user_tie = await new_user("user_tie")
        await link(user_tie, role_tie_a)
        await link(user_tie, role_tie_b)
        await compare_plan("P3 priority 并列取 plan_id 大者", "usr", user_tie)

        await compare_keys("P11 用户不存在键", user_id=77777777)
        await compare_plan("P11 用户不存在", "usr", 77777777)

        # ---------- P12 绑定套餐 disabled ----------
        plan_disabled = await new_plan("disabled", status="disabled", scope="org")
        await new_binding("organization", "90000002", plan_disabled, priority=1)
        await compare_plan("P12 套餐 disabled", "org", 90000002)
    finally:
        # 清理（按依赖倒序）；直接按收集的 id 删除
        try:
            if created["binding"]:
                await q("DELETE FROM quota_plan_binding WHERE id = ANY($1::bigint[])",
                        [created["binding"]])
            if created["membership"]:
                await q("DELETE FROM customer_membership WHERE id = ANY($1::bigint[])",
                        [created["membership"]])
            if created["user"]:
                await q("DELETE FROM user_role WHERE user_id = ANY($1::bigint[])",
                        [created["user"]])
            if created["plan"]:
                await q("DELETE FROM quota_plan WHERE id = ANY($1::bigint[])",
                        [created["plan"]])
            if created["level"]:
                await q("DELETE FROM customer_membership_level WHERE id = ANY($1::bigint[])",
                        [created["level"]])
            if created["customer"]:
                await q("DELETE FROM customer WHERE id = ANY($1::bigint[])",
                        [created["customer"]])
            if created["user"]:
                await q('DELETE FROM "user" WHERE id = ANY($1::bigint[])',
                        [created["user"]])
            if created["role"]:
                await q("DELETE FROM role WHERE id = ANY($1::bigint[])",
                        [created["role"]])
        finally:
            await Tortoise.close_connections()

    for line in checks:
        print(line)
    for line in failures:
        print(line)
    print(f"\n结果：{len(checks)} 通过 / {len(failures)} 失败")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
