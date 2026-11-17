"""C1 整改回归：contentops 多租户 customer 功能码双轨鉴权（新文件）。

运行：
    .venv/Scripts/python tests/test_c1_authz_fix.py

分层：
- A 结构、B CUS 授权（真实 DB）、C USR RBAC 无回归、D HTTP 端到端。
- 禁用本地不可达 Redis，走 DB 降级，避免 5s 连接超时拖慢。
- 测试数据 finally 清理。
"""
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base.common.database  # noqa: F401  触发 openGauss 补丁

ROOT = Path(__file__).resolve().parent.parent
R = []


def ck(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


async def main():
    import httpx
    from fastapi import Depends, FastAPI
    from tortoise import Tortoise

    from base.common.setting import TORTOISE_ORM
    from base.common.security import create_access_token
    from base.common.authz import CONTENTOPS_ACTION_CODES, require_action, ResourceType
    from base.common.authz.context import OwnerContext, require_owner
    from base.common.authz.action_guard import _customer_authorize, _rbac_dependency
    from base.common.authz.service import ResourceGrantService, invalidate_customer_org_cache
    from base.common.authz.models.resource_grant import ResourceGrant
    from base.common.authz.filter import OwnedResourceNotFound
    from base.plugins.customer.models.customer import Customer
    from base.plugins.customer.models.customer_organization import (
        CustomerOrganization, CustomerOrganizationMember,
    )

    # 禁用本地不可达 Redis（宿主机连不到容器 6379），走 DB 降级；
    # 放在所有 import 之后，避免 base.common.cache 的 configure() 覆盖。
    import packages.common.cache as cm
    if cm._config is not None:
        cm._config.enabled = False
    cm.RedisCache._instance = None

    tag = uuid.uuid4().hex[:8]
    made = {"c": [], "o": [], "m": [], "g": []}
    chk = "contentops:compliance:check"
    edt = "contentops:content:edit"

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        # A 结构
        ck("A1 require_action 导出", callable(require_action))
        ck("A2 ResourceType 含 contentops_action", ResourceType.CONTENTOPS_ACTION.value == "contentops_action")
        ck("A3 权限码 12 个", len(CONTENTOPS_ACTION_CODES) == 12)
        m = json.loads((ROOT / "base/plugins/contentops/manifest.json").read_text(encoding="utf-8"))
        ck("A4 与 manifest 一致", {p["code"] for p in m["permissions"]} == set(CONTENTOPS_ACTION_CODES))
        vd = ROOT / "base/plugins/contentops/api/v1"
        fs = list(vd.glob("*.py"))
        ck("A5 无 require_permission 残留", not [f for f in fs if "require_permission" in f.read_text(encoding="utf-8")])
        # 核心 7 文件须全部用 require_action；M4 新增路由文件也用（>=7 即可，避免写死数量）
        core7 = ["content", "compliance", "review", "export", "ledger", "rules", "media"]
        ck("A6 核心7文件用 require_action", all(
            "require_action(" in (vd / f"{n}.py").read_text(encoding="utf-8") for n in core7
        ))
        import ast
        src = (ROOT / "base/common/authz/action_guard.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        # 只检测实际被引用的名字/属性，忽略 docstring 与注释文字
        used_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used_attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        ck("A7 CUS 分支不碰 get_current_user_id",
           "get_current_user_id" not in used_names and "get_current_user_id" not in used_attrs)

        # B CUS 授权（真实 DB）
        c1, c2, c3 = (
            await Customer.create(username=f"a_{tag}", nickname="授权", is_active=True),
            await Customer.create(username=f"b_{tag}", nickname="禁用", is_active=True),
            await Customer.create(username=f"c_{tag}", nickname="成员", is_active=True),
        )
        made["c"] += [c1, c2, c3]
        o1, o2, o3 = (OwnerContext(owner_type="cus", owner_id=c.id) for c in (c1, c2, c3))

        try:
            await _customer_authorize(o1, chk)
            ck("B1 未授权拒绝", False)
        except OwnedResourceNotFound:
            ck("B1 未授权拒绝(404)", True)

        made["g"].append(await ResourceGrantService.grant(("cus", c1.id), "contentops_action", chk, granted_by="reg"))
        ck("B2 授权放行返回 customer.id", await _customer_authorize(o1, chk) == c1.id)

        try:
            await _customer_authorize(o1, edt)
            ck("B3 跨码隔离", False)
        except OwnedResourceNotFound:
            ck("B3 跨码隔离(404)", True)

        made["g"].append(await ResourceGrantService.grant(("cus", c2.id), "contentops_action", chk, granted_by="reg"))
        c2.is_active = False
        await c2.save()
        try:
            await _customer_authorize(o2, chk)
            ck("B4 禁用主体拒绝", False)
        except OwnedResourceNotFound:
            ck("B4 禁用主体拒绝(404)", True)

        org = await CustomerOrganization.create(name=f"org_{tag}", owner_customer=c1, status="active")
        made["o"].append(org)
        made["m"].append(await CustomerOrganizationMember.create(org=org, customer=c3, role="member", status="active"))
        made["g"].append(await ResourceGrantService.grant(("org", org.id), "contentops_action", chk, granted_by="reg"))
        await invalidate_customer_org_cache(c3.id)
        ck("B5 org 继承授权", await _customer_authorize(o3, chk) == c3.id)

        # C USR RBAC 无回归
        import base.common.permissions as pm
        orig = pm.get_user_permissions_cached

        async def fake(uid):
            return {1: [chk], 2: ["x:y"], 3: ["*"]}.get(uid, [])

        pm.get_user_permissions_cached = fake
        try:
            dep = _rbac_dependency(chk)
            ck("C1 USR 有权限放行", await dep(OwnerContext(owner_type="usr", owner_id=1)) == 1)
            try:
                await dep(OwnerContext(owner_type="usr", owner_id=2))
                ck("C2 USR 无权限403", False)
            except Exception as e:
                ck("C2 USR 无权限403", getattr(e, "status_code", None) == 403)
            ck("C3 USR 超管通配", await dep(OwnerContext(owner_type="usr", owner_id=3)) == 3)
        finally:
            pm.get_user_permissions_cached = orig

        # D HTTP 端到端
        app = FastAPI()

        @app.post("/check")
        async def ep(owner=Depends(require_owner), user_id=require_action(chk)):
            return {"user_id": user_id, "owner_type": owner.owner_type}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as cl:
            t1 = create_access_token({"sub": str(c1.id), "typ": "cus"})
            r = await cl.post("/check", headers={"Authorization": f"Bearer {t1}"})
            ck("D1 授权 CUS 200", r.status_code == 200, f"s={r.status_code}")
            ck("D2 操作人=customer.id", r.status_code == 200 and r.json().get("user_id") == c1.id)

            c4 = await Customer.create(username=f"d_{tag}", nickname="无授权", is_active=True)
            made["c"].append(c4)
            t4 = create_access_token({"sub": str(c4.id), "typ": "cus"})
            r = await cl.post("/check", headers={"Authorization": f"Bearer {t4}"})
            ck("D3 未授权 CUS 404", r.status_code == 404, f"s={r.status_code}")

            r = await cl.post("/check")
            ck("D4 无 token 401", r.status_code == 401, f"s={r.status_code}")

            tb = create_access_token({"sub": str(c1.id), "typ": "ghost"})
            r = await cl.post("/check", headers={"Authorization": f"Bearer {tb}"})
            ck("D5 非法 typ 401", r.status_code == 401, f"s={r.status_code}")

    finally:
        try:
            for g in made["g"]:
                await ResourceGrant.filter(id=g.id).delete()
            for m in made["m"]:
                await CustomerOrganizationMember.filter(id=m.id).delete()
            for o in made["o"]:
                await CustomerOrganization.filter(id=o.id).delete()
            for c in made["c"]:
                await Customer.filter(id=c.id).delete()
            print("[cleanup] 完成")
        except Exception as e:
            print(f"[cleanup] 警告 {e}")
        finally:
            await Tortoise.close_connections()

    ok = sum(1 for _, v in R if v)
    print(f"\n===== {ok}/{len(R)} PASS =====")
    if ok != len(R):
        print("FAIL:", [n for n, v in R if not v])
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
