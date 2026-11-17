"""客户门户 M5 回归：/me/* 自助端点 + /workspace/* 合规工作台 + CUS 越权防护。

运行：
    .venv/Scripts/python tests/regression_customer_portal.py

要点：
- 真实 DB；禁用本地不可达 Redis 走 DB 降级，避免 5s 超时。
- 测试数据 finally 清理。
- 核心断言（P0 越权）：USR token 访问 /me/* 一律 403；无 token 401；
  CUS token 只能读自己的数据（owner_id 强绑定），合规检测复用租户规则。
"""
import asyncio
import sys
import uuid
from datetime import timedelta
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
    from fastapi import FastAPI
    from tortoise import Tortoise

    from base.common.setting import TORTOISE_ORM
    from base.common.security import create_access_token
    from base.plugins.customer.models.customer import Customer
    from base.plugins.customer.api.v1.self_service_router import self_service_router
    from base.plugins.customer.api.v1.workspace_router import workspace_router

    # 禁用本地不可达 Redis
    import packages.common.cache as cm
    if cm._config is not None:
        cm._config.enabled = False
    cm.RedisCache._instance = None

    tag = uuid.uuid4().hex[:8]
    made = {"customers": []}

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        # 造两个客户（验证归属隔离）
        c1 = await Customer.create(
            username=f"portala_{tag}", email=f"portala_{tag}@x.com",
            password="x", nickname="客户A", is_active=True, is_verified=True)
        c2 = await Customer.create(
            username=f"portalb_{tag}", email=f"portalb_{tag}@x.com",
            password="x", nickname="客户B", is_active=True, is_verified=True)
        made["customers"] += [c1, c2]

        cus_token = create_access_token(
            data={"sub": str(c1.id), "typ": "cus", "email": c1.email},
            expires_delta=timedelta(hours=1))
        # 伪造一个 usr token（sub 指向系统用户，这里用 customer id 冒充，验证类型守卫）
        usr_token = create_access_token(
            data={"sub": str(c1.id), "typ": "usr"},
            expires_delta=timedelta(hours=1))

        # 用真实新路由挂载独立 app
        app = FastAPI()
        app.include_router(self_service_router, prefix="/v1/customer")
        app.include_router(workspace_router, prefix="/v1/customer")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as cl:
            H_CUS = {"Authorization": f"Bearer {cus_token}"}
            H_USR = {"Authorization": f"Bearer {usr_token}"}

            # --- 鉴权防线 ---
            r = await cl.get("/v1/customer/me/profile")
            ck("A1 无token 401", r.status_code == 401, f"s={r.status_code}")
            r = await cl.get("/v1/customer/me/profile", headers=H_USR)
            ck("A2 USR token 访问 /me 403", r.status_code == 403, f"s={r.status_code}")
            r = await cl.post("/v1/customer/workspace/compliance/check", headers=H_USR, json={"text": " test"})
            ck("A3 USR token 访问工作台 403", r.status_code == 403, f"s={r.status_code}")

            # --- 资料归属 ---
            r = await cl.get("/v1/customer/me/profile", headers=H_CUS)
            ck("A4 CUS token 200", r.status_code == 200, f"s={r.status_code}")
            body = r.json()
            data = body.get("data", body)
            ck("A5 资料是本人(owner绑定)", data.get("id") == c1.id, f"got={data.get('id')} want={c1.id}")
            ck("A6 资料不含敏感字段", "password" not in data and "openid" not in data)
            # 确认没有串到客户B
            ck("A7 未泄漏他人邮箱", data.get("email") != c2.email)

            # --- 其余自助端点可达 ---
            for path, label in [
                ("/v1/customer/me/membership", "会员"),
                ("/v1/customer/me/orders", "订单"),
                ("/v1/customer/me/payments", "支付"),
                ("/v1/customer/me/organizations", "组织"),
                ("/v1/customer/workspace/rules", "规则"),
            ]:
                r = await cl.get(path, headers=H_CUS)
                ck(f"B-{label} 200", r.status_code == 200, f"s={r.status_code}")

            # --- 合规自检 ---
            r = await cl.post(
                "/v1/customer/workspace/compliance/check", headers=H_CUS,
                json={"text": "这是一段正常内容，用于验证检测链路。", "channel": "text"})
            ck("C1 合规检测 200", r.status_code == 200, f"s={r.status_code}")
            cbody = r.json().get("data", r.json())
            ck("C2 返回判定字段", "verdict" in cbody and "hits" in cbody)
            ck("C3 正常文本判定 pass", cbody.get("verdict") in ("pass", "pass_hint"))

            # --- M6 可解释轨迹 ---
            ck("C2a 管道版本", cbody.get("pipeline_version") == "2.0-trace")
            trace = cbody.get("trace") or []
            ck("C2b 六步轨迹完整", len(trace) == 6, f"steps={len(trace)}")
            ck("C2c 步骤顺序正确", [s["step"] for s in trace] == [1, 2, 3, 4, 5, 6])
            ck("C2d 每步含过程方法字段", all(
                {"code", "name", "method", "status", "elapsed_ms", "detail"}.issubset(s)
                and s["method"] and s["detail"] for s in trace
            ))
            ck("C2e 语义层诚实标注跳过", trace[4]["code"] == "semantic" and trace[4]["status"] == "skipped")
            ck("C2f 聚合步给出判定原因", trace[5]["code"] == "aggregate" and cbody["verdict"] in trace[5]["detail"])

            # --- 幂等键回显 ---
            r = await cl.post(
                "/v1/customer/workspace/compliance/check",
                headers={**H_CUS, "Idempotency-Key": "m5-idem-1"},
                json={"text": "带幂等键"})
            ck("C4 幂等键回显", r.json().get("data", {}).get("idempotency_key") == "m5-idem-1")

    finally:
        try:
            for c in made["customers"]:
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
