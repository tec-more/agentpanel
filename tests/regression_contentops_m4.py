"""ContentOps M4 回归：规则灰度 / LLM配置 / 词库导入 / 对外API Key 鉴权闭环。

运行：
    .venv/Scripts/python tests/regression_contentops_m4.py

要点：
- 真实 DB；禁用本地不可达 Redis 走 DB / 进程内降级，避免 5s 超时。
- 测试数据 finally 清理（API Key / 规则 / customer）。
- 分层：A 灰度计算、B 词库导入、C LLM配置境内约束、D API Key 签发校验、
  E 对外端点 HTTP 端到端（无 key 401 / scope 不足 403 / 合法 key 200）。
"""
import asyncio
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
    from base.common.authz.context import OwnerContext
    from base.plugins.contentops.services.compliance_service import ComplianceEngine
    from base.plugins.contentops.services.api_key_service import (
        ContentopsApiKeyService, hash_secret, OPENAPI_SCOPES,
    )
    from base.plugins.contentops.services.openapi_auth import require_openapi_scope
    from base.plugins.contentops.services.llm_provider_service import LLMProviderService
    from base.plugins.contentops.services.rule_service import RuleService
    from base.plugins.contentops.schemas.content_schema import RuleBulkImport, LLMProviderCreate
    from base.plugins.contentops.models import (
        ComplianceRule, ContentopsApiKey, LLMProviderConfig,
    )
    from base.plugins.customer.models.customer import Customer

    # 禁用本地不可达 Redis（与 authz 回归一致，避免 5s 连接超时）
    import packages.common.cache as cm
    if cm._config is not None:
        cm._config.enabled = False
    cm.RedisCache._instance = None

    tag = uuid.uuid4().hex[:8]
    made = {"cust": [], "rules": [], "keys": [], "llm": []}

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        cust = await Customer.create(username=f"m4_{tag}", nickname="M4租户", is_active=True)
        made["cust"].append(cust)
        owner = OwnerContext(owner_type="cus", owner_id=cust.id)

        # A 灰度确定性分桶
        class FakeRule:
            def __init__(self, rid, status, pct):
                self.id, self.status, self.rollout_percent = rid, status, pct

        ck("A1 active 恒生效", ComplianceEngine._in_rollout(FakeRule(1, "active", 0), owner))
        ck("A2 draft 不生效", not ComplianceEngine._in_rollout(FakeRule(1, "draft", 100), owner))
        ck("A3 archived 不生效", not ComplianceEngine._in_rollout(FakeRule(1, "archived", 100), owner))
        ck("A4 gray 0% 不生效", not ComplianceEngine._in_rollout(FakeRule(1, "gray", 0), owner))
        ck("A5 gray 100% 生效", ComplianceEngine._in_rollout(FakeRule(1, "gray", 100), owner))
        # 单调性：pct 越大越易生效（bucket < pct 的必然性质）
        results = [ComplianceEngine._in_rollout(FakeRule(7, "gray", p), owner) for p in range(0, 101)]
        ck("A6 gray 单调不递减", all(not (results[i] and not results[i + 1]) for i in range(100)))
        ck("A7 gray 确定性", ComplianceEngine._in_rollout(FakeRule(7, "gray", 50), owner) == ComplianceEngine._in_rollout(FakeRule(7, "gray", 50), owner))

        # B 开源词库批量导入 + 去重
        bulk = RuleBulkImport(layer="L1", words=["绝对", "最佳", "第一品牌", "绝对"], dedupe=True)
        res = await RuleService.bulk_import(bulk, owner)
        ck("B1 词库导入 created=3", res["created"] == 3, str(res))
        ck("B2 词库去重 skipped=1", res["skipped"] == 1, str(res))
        imported = await ComplianceRule.filter(owner_type="cus", owner_id=cust.id, source="opensource")
        made["rules"] += list(imported)
        ck("B3 规则落库带灰度字段", all((r.status == "active" and r.rollout_percent == 100) for r in imported))
        res2 = await RuleService.bulk_import(bulk, owner)
        ck("B4 重复导入全跳过", res2["created"] == 0 and res2["skipped"] == 4, str(res2))

        # B5 启停
        one = imported[0]
        toggled = await RuleService.toggle_rule(one.id, False, owner)
        ck("B5 规则启停", toggled["enabled"] is False)

        # C LLM 配置境内约束
        try:
            await LLMProviderService.create(LLMProviderCreate(provider="openai", model="gpt-4"), owner)
            ck("C1 海外provider拒绝", False)
        except ValueError:
            ck("C1 海外provider拒绝", True)
        cfg = await LLMProviderService.create(LLMProviderCreate(provider="deepseek", model="deepseek-chat"), owner)
        made["llm"].append(await LLMProviderConfig.get(id=cfg["id"]))
        ck("C2 境内provider放行", cfg["provider"] == "deepseek")

        # D API Key 签发 / 校验 / 哈希存储
        rec, secret = await ContentopsApiKeyService.issue("m4-key", cust.id, scopes=["compliance:check"])
        made["keys"].append(rec)
        ck("D1 secret 明文前缀", secret.startswith("csk_"))
        ck("D2 DB 只存哈希", rec.secret_hash == hash_secret(secret) and rec.secret_hash != secret)
        ck("D3 合法校验通过", (await ContentopsApiKeyService.verify(rec.key_id, secret)) is not None)
        ck("D4 错误 secret 拒绝", (await ContentopsApiKeyService.verify(rec.key_id, "wrong")) is None)
        ck("D5 scope 白名单过滤", set(rec.scopes) <= set(OPENAPI_SCOPES))

        # E 对外端点 HTTP 端到端
        app = FastAPI()

        @app.post("/openapi/compliance/check")
        async def chk(ctx=Depends(require_openapi_scope("compliance:check"))):
            return {"key_id": ctx["key_id"], "owner_type": ctx["owner"].owner_type, "owner_id": ctx["owner"].owner_id}

        @app.get("/openapi/rules")
        async def rules(ctx=Depends(require_openapi_scope("rules:read"))):
            return {"key_id": ctx["key_id"]}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as cl:
            r = await cl.post("/openapi/compliance/check")
            ck("E1 无凭据 401", r.status_code == 401, f"s={r.status_code}")
            r = await cl.post("/openapi/compliance/check", headers={"X-ContentOps-Key-Id": rec.key_id, "X-ContentOps-Secret": "bad"})
            ck("E2 错误secret 401", r.status_code == 401, f"s={r.status_code}")
            r = await cl.get("/openapi/rules", headers={"X-ContentOps-Key-Id": rec.key_id, "X-ContentOps-Secret": secret})
            ck("E3 scope不足 403", r.status_code == 403, f"s={r.status_code}")
            r = await cl.post("/openapi/compliance/check", headers={"X-ContentOps-Key-Id": rec.key_id, "X-ContentOps-Secret": secret})
            ck("E4 合法key 200", r.status_code == 200, f"s={r.status_code}")
            ck("E5 owner 绑定正确", r.status_code == 200 and r.json().get("owner_id") == cust.id and r.json().get("owner_type") == "cus")
            # Bearer 复合格式
            r = await cl.post("/openapi/compliance/check", headers={"Authorization": f"Bearer {rec.key_id}.{secret}"})
            ck("E6 Bearer复合格式 200", r.status_code == 200, f"s={r.status_code}")
            # 吊销后拒绝
            await ContentopsApiKeyService.revoke(rec.key_id)
            r = await cl.post("/openapi/compliance/check", headers={"X-ContentOps-Key-Id": rec.key_id, "X-ContentOps-Secret": secret})
            ck("E7 吊销后 401", r.status_code == 401, f"s={r.status_code}")

    finally:
        try:
            for r in made["rules"]:
                await ComplianceRule.filter(id=r.id).delete()
            for c in made["llm"]:
                await LLMProviderConfig.filter(id=c.id).delete()
            for k in made["keys"]:
                await ContentopsApiKey.filter(id=k.id).delete()
            for c in made["cust"]:
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
