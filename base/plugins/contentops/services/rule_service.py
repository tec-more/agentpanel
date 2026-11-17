"""规则库服务：合规规则 CRUD + 平台适配配置 CRUD。"""
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import ComplianceRule, PlatformRuleConfig
from base.plugins.contentops.schemas.content_schema import RuleCreate, RuleUpdate


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
