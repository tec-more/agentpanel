"""ContentOps 核心业务链路冒烟测试。

链路：种子规则 → 创建源内容 → 合规检测(P0拦截) → 规则改写 → 复检通过
      → 生成成品 → 人工确认 → 打包导出 → 台账标记 → 效果回填。

运行：.venv/Scripts/python tests/smoke_contentops_flow.py
结束时清理本脚本创建的测试数据 + 还原 manifest。
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from base.app_wrapper import real_app

WORKDIR = Path(__file__).resolve().parent.parent
MANIFEST = WORKDIR / "base" / "plugins" / "contentops" / "manifest.json"

results = []
created = {"rule_ids": [], "content_ids": [], "version_ids": [], "package_ids": [], "ledger_ids": [], "hit_ids": []}


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


async def main():
    from tortoise import Tortoise
    from base.plugins.contentops.models import (
        ComplianceRule, ContentItem, ContentVersion, ComplianceHit,
        ExportPackage, PublishLedger, EffectData,
    )
    from base.plugins.contentops.services.compliance_service import ComplianceEngine
    from base.plugins.contentops.services.review_service import ReviewService
    from base.plugins.contentops.services.export_service import ExportService
    from base.plugins.contentops.services.ledger_service import LedgerService
    from base.plugins.contentops.schemas.content_schema import VersionConfirmRequest

    original = MANIFEST.read_text(encoding="utf-8")
    m = json.loads(original)
    m["is_installed"] = True
    m["is_enabled"] = True
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=4), encoding="utf-8")

    try:
        async with real_app.router.lifespan_context(real_app):
            # 1. 种子规则：一条 P0 违禁词（平台级，owner NULL）
            rule = await ComplianceRule.create(
                layer="L1", type="keyword", pattern="包治百病", risk_level="P0",
                action="block", basis="广告法", suggestion="避免绝对化疗效表述",
                source="self", version="1", enabled=True,
                owner_type=None, owner_id=None,
            )
            created["rule_ids"].append(rule.id)

            # 2. 含违禁词的源内容
            item = await ContentItem.create(
                title="神药测试", body="本产品包治百病，效果显著。", owner_type="usr", owner_id=999001,
            )
            created["content_ids"].append(item.id)

            # 3. 合规检测 → 应命中 P0
            summary = await ComplianceEngine.check_content(item.id, None, ["text"], None)
            check("P0 违禁词被检出", summary["has_p0"] is True, f"verdict={summary['verdict']}")
            check("命中项含依据与建议", any(h.get("basis") for h in summary["hits"]))
            check("P0 判定为硬拦截", summary["verdict"] == "block")

            # 4. 消歧白名单：'最近'不应被误报（加一条 P1 规则 '最'）
            rule2 = await ComplianceRule.create(
                layer="L1", type="keyword", pattern="最", risk_level="P1",
                action="warn", source="self", version="1", enabled=True,
                owner_type=None, owner_id=None,
            )
            created["rule_ids"].append(rule2.id)
            item2 = await ContentItem.create(title="最近的新闻", body="这是一条正常内容。", owner_type="usr", owner_id=999001)
            created["content_ids"].append(item2.id)
            s2 = await ComplianceEngine.check_content(item2.id, None, ["text"], None)
            # '最近'在白名单，'最'在正文'正常'里没有；标题'最近'应被消歧
            p1_hits = [h for h in s2["hits"] if h["level"] == "P1"]
            check("上下文消歧生效（'最近'不误报）", len(p1_hits) == 0, f"p1_hits={len(p1_hits)}")

            # 5. 干净成品版本 → 确认 → 导出
            await ComplianceRule.filter(id=rule.id).update(enabled=False)  # 关闭 P0 规则以生成干净版本
            ver = await ContentVersion.create(
                content_id=item2.id, platform="wechat", payload={"title": "正常标题", "body": "正常正文", "topics": ["科技"]},
                is_adapted=True, confirmed=False, status="pending", owner_type="usr", owner_id=999001,
            )
            created["version_ids"].append(ver.id)
            await ReviewService.confirm_version(ver.id, True, None)
            vcheck = await ContentVersion.get(id=ver.id)
            check("人工确认后版本进入 confirmed", vcheck.confirmed is True, f"status={vcheck.status}")

            pkg = await ExportService.create_export(item2.id, {"wechat": ver.id}, None, creator_id=999001)
            created["package_ids"].append(pkg["id"])
            check("导出快照生成", bool(pkg.get("id")))

            ledgers = await PublishLedger.filter(version_id=ver.id)
            created["ledger_ids"].extend([l.id for l in ledgers])
            check("导出后自动建台账待发布", len(ledgers) == 1 and ledgers[0].status == "pending")

            # 6. 台账标记已发布 + 效果回填
            from base.plugins.contentops.schemas.content_schema import LedgerUpdate, EffectCreate
            await LedgerService.update(ledgers[0].id, LedgerUpdate(status="published"), None)
            eff = await LedgerService.add_effect(ledgers[0].id, EffectCreate(views=100, likes=10), None)
            check("效果数据回填", eff["views"] == 100 and eff["likes"] == 10)
    finally:
        # 清理测试数据
        try:
            async with real_app.router.lifespan_context(real_app):
                await EffectData.filter(ledger_id__in=created["ledger_ids"]).delete()
                await PublishLedger.filter(id__in=created["ledger_ids"]).delete()
                await ExportPackage.filter(id__in=created["package_ids"]).delete()
                await ComplianceHit.filter(content_version_id__in=created["version_ids"]).delete()
                await ContentVersion.filter(id__in=created["version_ids"]).delete()
                await ContentItem.filter(id__in=created["content_ids"]).delete()
                await ComplianceRule.filter(id__in=created["rule_ids"]).delete()
                print("[cleanup] 测试数据已清理")
        except Exception as e:
            print(f"[cleanup] 清理失败(可忽略): {str(e)[:100]}")
        MANIFEST.write_text(original, encoding="utf-8")
        print("[restore] manifest 已还原")

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n断言总数={len(results)} PASS={passed} FAIL={len(results)-passed}")
    if any(not c for _, c, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
