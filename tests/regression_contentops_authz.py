"""C1 整改回归：contentops 多租户 customer 功能码双轨鉴权。

运行（项目根目录，激活 venv）：
    .venv/Scripts/python tests/regression_contentops_authz.py

验证分层：
- A. 结构：路由全部改用 require_action、权限码全集一致、管理端资源类型已扩展
- B. CUS 分支（真实 DB）：未授权 404 / 授权放行 / org 继承 / 主体禁用 / 跨权限码隔离
- C. USR 分支：RBAC 403/200/超管通配不回归（mock get_user_permissions_cached，不改真库 RBAC）
- D. HTTP 端到端：401 / 404 / 200 完整链路（TestClient + 真实 JWT）

测试数据在 finally 中清理（客户/组织/成员/授权），不污染真库。
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 导入 database 触发 openGauss 补丁（必须在连库前）
import base.common.database  # noqa: F401

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


async def main():
    import json
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from base.common.security import create_access_token
    from base.common.authz.constants import CONTENTOPS_ACTION_CODES, ResourceType
    from base.common.authz.context import OwnerContext, require_owner
    from base.common.authz.action_guard import (
        require_action, _customer_authorize, _rbac_dependency,
    )
    from base.common.authz.service import ResourceGrantService
    from base.common.authz.models.resource_grant import ResourceGrant
    from base.common.authz.filter import OwnedResourceNotFound
    from base.plugins.customer.models.customer import Customer
    from tortoise import Tortoise

    tag = uuid.uuid4().hex[:8]
    created = {"customers": [], "orgs": [], "members": [], "grants": []}
    code_check = "contentops:compliance:check"
    code_edit = "contentops:content:edit"

    from base.common.setting import TORTOISE_ORM
    from tortoise import Tortoise

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        # ---------- A. 结构 ----------
        import base.common.authz as authz
        check("A1 authz 导出 require_action", hasattr(authz, "require_action"))
        check("A2 ResourceType 含 contentops_action",
              ResourceType.CONTENTOPS_ACTION.value == "contentops_action")
        check("A3 权限码全集 12 个", len(CONTENTOPS_ACTION_CODES) == 12)

        manifest = json.loads(
            (Path(__file__).resolve().parent.parent / "base/plugins/contentops/manifest.json").read_text(encoding="utf-8")
        )
        manifest_codes = {p["code"] for p in manifest["permissions"]}
        check("A4 权限码与 manifest 一致", manifest_codes == set(CONTENTOPS_ACTION_CODES),
              f"manifest={len(manifest_codes)} codes={len(CONTENTOPS_ACTION_CODES)}")

        vdir = Path(__file__).resolve().parent.parent / "base/plugins/contentops/api/v1"
        route_files = list(vdir.glob("*.py"))
        bad = [f.name for f in route_files
               if "require_permission" in f.read_text(encoding="utf-8")]
        check("A5 路由无残留 require_permission", not bad, f"残留={bad}")
        files_with_action = [f.name for f in route_files
                             if "require_action(" in f.read_text(encoding="utf-8")]
        check("A6 7 个路由文件均用 require_action", len(files_with_action) == 7,
              f"{files_with_action}")

        # ---------- B. CUS 分支（真实 DB） ----------
        c1 = await Customer.create(username=f"c1a_{tag}", nickname="授权客户", is_active=True)
        c2 = await Customer.create(username=f"c1b_{tag}", nickname="禁用客户", is_active=True)
        c3 = await Customer.create(username=f"c1c_{tag}", nickname="组织成员客户", is_active=True)
        created["customers"] += [c1, c2, c3]

        o1_ctx = OwnerContext(owner_type="cus", owner_id=c1.id)
        o2_ctx = OwnerContext(owner_type="cus", owner_id=c2.id)
        o3_ctx = OwnerContext(owner_type="cus", owner_id=c3.id)

        # 未授权 → 拒绝
        try:
            await _customer_authorize(o1_ctx, code_check)
            check("B1 CUS 未授权被拒", False)
        except OwnedResourceNotFound:
            check("B1 CUS 未授权被拒(404)", True)

        # 授权后放行，返回 customer.id
        g = await ResourceGrantService.grant(("cus", c1.id), "contentops_action", code_check,
                                              granted_by="regression")
        created["grants"].append(g)
        uid = await _customer_authorize(o1_ctx, code_check)
        check("B2 CUS 授权后放行且返回 customer.id", uid == c1.id, f"{uid}=={c1.id}")

        # 跨权限码隔离：授权了 check 不等于有 edit
        try:
            await _customer_authorize(o1_ctx, code_edit)
            check("B3 跨权限码不串权", False)
        except OwnedResourceNotFound:
            check("B3 跨权限码不串权(404)", True)

        # 主体禁用 → 不放行
        g2 = await ResourceGrantService.grant(("cus", c2.id), "contentops_action", code_check,
                                               granted_by="regression")
        created["grants"].append(g2)
        c2.is_active = False
        await c2.save()
        try:
            await _customer_authorize(o2_ctx, code_check)
            check("B4 禁用主体不放行", False)
        except OwnedResourceNotFound:
            check("B4 禁用主体不放行(404)", True)

        # org 继承：组织被授权，成员客户无需自身授权即可访问
        from base.plugins.customer.models.customer_organization import (
            CustomerOrganization, CustomerOrganizationMember,
        )
        org = await CustomerOrganization.create(name=f"c1org_{tag}", owner_customer=c1, status="active")
        created["orgs"].append(org)
        member = await CustomerOrganizationMember.create(org=org, customer=c3, role="member", status="active")
        created["members"].append(member)
        g3 = await ResourceGrantService.grant(("org", org.id), "contentops_action", code_check,
                                               granted_by="regression")
        created["grants"].append(g3)
        # 清缓存确保继承即时生效
        from base.common.authz.service import invalidate_customer_org_cache
        await invalidate_customer_org_cache(c3.id)
        uid3 = await _customer_authorize(o3_ctx, code_check)
        check("B5 CUS 通过 org 继承获得授权", uid3 == c3.id, f"{uid3}=={c3.id}")

        # ---------- C. USR 分支（mock RBAC，不改库） ----------
        import base.common.permissions as perms_mod
        orig_get = perms_mod.get_user_permissions_cached
        usr_ctx = OwnerContext(owner_type="usr", owner_id=999001)

        async def fake_perms(uid):
            return {
                999001: [code_check],          # 有 check 权限
                999002: ["other:perm"],        # 无目标权限
                999003: ["*"],                 # 超管通配
            }.get(uid, [])

        perms_mod.get_user_permissions_cached = fake_perms
        try:
            dep = _rbac_dependency(code_check)
            uid_ok = await dep(OwnerContext(owner_type="usr", owner_id=999001))
            check("C1 USR 有权限放行且返回 user.id", uid_ok == 999001)
            try:
                await dep(OwnerContext(owner_type="usr", owner_id=999002))
                check("C2 USR 无权限 403", False)
            except Exception as e:
                check("C2 USR 无权限 403", getattr(e, "status_code", None) == 403,
                      f"status={getattr(e,'status_code',None)}")
            uid_super = await dep(OwnerContext(owner_type="usr", owner_id=999003))
            check("C3 USR 超管通配放行", uid_super == 999003)
        finally:
            perms_mod.get_user_permissions_cached = orig_get

            # ---------- D. HTTP 端到端 ----------
            app = FastAPI()

            @app.post("/check")
            async def check_endpoint(
                owner=Depends(require_owner),
                user_id=require_action(code_check),
            ):
                return {"user_id": user_id, "owner_type": owner.owner_type}

            # 全程异步 ASGI 客户端：避免 TestClient 在 lifespan 异步上下文内
            # 再起事件循环导致 anyio BlockingPortal 跨 loop 冲突。
            import httpx

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                # 授权客户 token
                tok_c1 = create_access_token({"sub": str(c1.id), "typ": "cus"})
                r_ok = await client.post("/check", headers={"Authorization": f"Bearer {tok_c1}"})
                check("D1 CUS 授权 HTTP 200", r_ok.status_code == 200, f"status={r_ok.status_code}")
                check("D2 CUS 返回操作人=customer.id",
                      r_ok.status_code == 200 and r_ok.json().get("user_id") == c1.id)

                # 无授权客户 token（c3 只有 org 的 check 授权 -> 有权限；用新客户 c4 无授权）
                c4 = await Customer.create(username=f"c1d_{tag}", nickname="无授权客户", is_active=True)
                created["customers"].append(c4)
                tok_c4 = create_access_token({"sub": str(c4.id), "typ": "cus"})
                r_404 = await client.post("/check", headers={"Authorization": f"Bearer {tok_c4}"})
                check("D3 CUS 未授权 HTTP 404（不暴露功能存在性）", r_404.status_code == 404,
                      f"status={r_404.status_code}")

                # 无 token → 401
                r_401 = await client.post("/check")
                check("D4 无 token HTTP 401", r_401.status_code == 401, f"status={r_401.status_code}")

                # 非法 typ token → 401（R-04）
                tok_bad = create_access_token({"sub": str(c1.id), "typ": "ghost"})
                r_bad = await client.post("/check", headers={"Authorization": f"Bearer {tok_bad}"})
                check("D5 非法 typ token HTTP 401", r_bad.status_code == 401, f"status={r_bad.status_code}")

    finally:
        # ---------- 清理 ----------
        try:
            for g in created["grants"]:
                await ResourceGrant.filter(id=g.id).delete()
            for m in created["members"]:
                await CustomerOrganizationMember.filter(id=m.id).delete()
            for o in created["orgs"]:
                await CustomerOrganization.filter(id=o.id).delete()
            for c in created["customers"]:
                await Customer.filter(id=c.id).delete()
            print("[cleanup] 测试数据已清理")
        except Exception as e:
            print(f"[cleanup] 警告：清理未完成 {e}")

    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"\n===== 结果：{passed}/{total} PASS =====")
    if passed != total:
        print("失败项：", [n for n, ok in results if not ok])
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
