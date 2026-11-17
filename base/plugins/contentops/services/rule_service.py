"""规则库服务：合规规则 CRUD + 灰度 + 词库批量导入 + 平台适配配置 CRUD。"""
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import ComplianceRule, PlatformRuleConfig
from base.plugins.contentops.schemas.content_schema import RuleCreate, RuleUpdate, RuleBulkImport


class RuleService:
    """规则库服务。"""

    # ---------- 合规规则 ----------
    @staticmethod
    async def create_rule(data: RuleCreate, owner: Optional[OwnerContext]):
        version = "1"
        rule = await ComplianceRule.create(
            layer=data.layer, type=data.type, pattern=data.pattern,
            risk_level=data.risk_level, action=data.action, basis=data.basis,
            suggestion=data.suggestion, category=data.category, platform=data.platform,
            enabled=data.enabled, source="tenant", version=version,
            status=getattr(data, "status", "active") or "active",
            rollout_percent=getattr(data, "rollout_percent", 100),
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
        )
        return await rule.to_dict()

    @staticmethod
    async def list_rules(layer: Optional[str], owner: Optional[OwnerContext]):
        qs = owned_queryset(ComplianceRule, owner) if owner else ComplianceRule.all()
        # 同时包含平台级全局规则（owner 为 NULL）
        from tortoise.expressions import Q
        if owner:
            qs = ComplianceRule.filter(Q(owner_type__isnull=True) | Q(owner_id=owner.owner_id, owner_type=owner.owner_type))
        if layer:
            qs = qs.filter(layer=layer)
        rows = await qs.order_by("-created_at")
        return [await r.to_dict() for r in rows]

    @staticmethod
    async def update_rule(rule_id: int, data: RuleUpdate, owner: Optional[OwnerContext]):
        rule = await get_owned_or_404(ComplianceRule, rule_id, owner, for_write=True) if owner else await ComplianceRule.get_or_none(id=rule_id)
        if not rule:
            raise ValueError("规则不存在或无权修改")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
        # 规则变更滚动版本
        try:
            rule.version = str(int(rule.version) + 1)
        except (ValueError, TypeError):
            rule.version = "2"
        await rule.save()
        return await rule.to_dict()

    @staticmethod
    async def delete_rule(rule_id: int, owner: Optional[OwnerContext]):
        rule = await get_owned_or_404(ComplianceRule, rule_id, owner, for_write=True) if owner else await ComplianceRule.get_or_none(id=rule_id)
        if not rule:
            raise ValueError("规则不存在或无权删除")
        await rule.delete()
        return True

    @staticmethod
    async def toggle_rule(rule_id: int, enabled: bool, owner: Optional[OwnerContext]):
        """规则启停（独立端点，不改变版本）。"""
        rule = await get_owned_or_404(ComplianceRule, rule_id, owner, for_write=True) if owner else await ComplianceRule.get_or_none(id=rule_id)
        if not rule:
            raise ValueError("规则不存在或无权操作")
        rule.enabled = enabled
        await rule.save(update_fields=["enabled", "updated_at"])
        return await rule.to_dict()

    @staticmethod
    async def bulk_import(data: RuleBulkImport, owner: Optional[OwnerContext]) -> dict:
        """开源词库批量导入：按归属去重后 bulk_create，返回导入/跳过计数。"""
        owner_type = owner.owner_type if owner else "usr"
        owner_id = owner.owner_id if owner else None
        words = [w.strip() for w in data.words if w and w.strip()]
        if not words:
            return {"created": 0, "skipped": 0, "total": 0}

        existing: set[str] = set()
        if data.dedupe:
            q = ComplianceRule.filter(pattern__in=words, owner_type=owner_type)
            if owner_id is not None:
                q = q.filter(owner_id=owner_id)
            else:
                q = q.filter(owner_id__isnull=True)
            existing = {r.pattern for r in await q}

        to_create = []
        seen: set[str] = set()
        for w in words:
            if w in existing or w in seen:
                continue
            seen.add(w)
            to_create.append(ComplianceRule(
                layer=data.layer, type=data.type, pattern=w,
                risk_level=data.risk_level, action=data.action,
                basis=data.basis, category=data.category, platform=data.platform,
                source=data.source, version="1", enabled=True,
                status="active", rollout_percent=100,
                owner_type=owner_type, owner_id=owner_id,
            ))
        if to_create:
            await ComplianceRule.bulk_create(to_create, batch_size=200)
        return {"created": len(to_create), "skipped": len(words) - len(to_create), "total": len(words)}

    # ---------- 平台适配配置 ----------
    @staticmethod
    async def list_platform_rules(platform: str, owner: Optional[OwnerContext]):
        rows = await PlatformRuleConfig.filter(platform=platform, enabled=True)
        return [await r.to_dict() for r in rows]

    @staticmethod
    async def set_platform_rule(platform: str, key: str, value: dict, owner: Optional[OwnerContext]):
        obj, _ = await PlatformRuleConfig.get_or_create(
            platform=platform, key=key,
            owner_type=owner.owner_type if owner else None,
            owner_id=owner.owner_id if owner else None,
            defaults={"value": value},
        )
        obj.value = value
        await obj.save()
        return await obj.to_dict()
