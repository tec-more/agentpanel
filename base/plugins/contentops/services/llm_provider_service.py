"""LLM 供应商配置服务（M4）。

- 仅境内节点：provider 命中海外黑名单直接拒绝（与 LLMAdapter 共用约束）；
- 归属隔离：平台级（owner NULL）全局可见 + 租户级覆盖；
- LLMProviderConfig 只是 contentops 侧的模型选择，凭证复用 llm 插件。
"""
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import LLMProviderConfig
from base.plugins.contentops.schemas.content_schema import LLMProviderCreate, LLMProviderUpdate
from base.plugins.contentops.services.llm_adapter import OVERSEAS_PROVIDERS


class LLMProviderService:
    """LLM 供应商配置 CRUD。"""

    @staticmethod
    def _assert_domestic(provider: str) -> None:
        if (provider or "").strip().lower() in OVERSEAS_PROVIDERS:
            raise ValueError(f"强制 region=domestic，已禁用海外 provider: {provider}")

    @staticmethod
    async def create(data: LLMProviderCreate, owner: Optional[OwnerContext]):
        LLMProviderService._assert_domestic(data.provider)
        cfg = await LLMProviderConfig.create(
            provider=data.provider, model=data.model, endpoint=data.endpoint,
            enabled=data.enabled, purpose=data.purpose,
            owner_type=owner.owner_type if owner else None,
            owner_id=owner.owner_id if owner else None,
        )
        return await cfg.to_dict()

    @staticmethod
    async def list_configs(purpose: Optional[str], owner: Optional[OwnerContext]):
        from tortoise.expressions import Q

        # 平台级全局 + 当前归属覆盖
        q = Q(owner_type__isnull=True) | Q(owner_id__isnull=True)
        if owner:
            q = q | Q(owner_type=owner.owner_type, owner_id=owner.owner_id)
        qs = LLMProviderConfig.filter(q)
        if purpose:
            qs = qs.filter(purpose=purpose)
        return [await c.to_dict() for c in await qs.order_by("-created_at")]

    @staticmethod
    async def update(cfg_id: int, data: LLMProviderUpdate, owner: Optional[OwnerContext]):
        cfg = await get_owned_or_404(LLMProviderConfig, cfg_id, owner, for_write=True) if owner else await LLMProviderConfig.get_or_none(id=cfg_id)
        if not cfg:
            raise ValueError("配置不存在或无权修改")
        payload = data.model_dump(exclude_unset=True)
        if "provider" in payload and payload["provider"]:
            LLMProviderService._assert_domestic(payload["provider"])
        for field, value in payload.items():
            setattr(cfg, field, value)
        await cfg.save()
        return await cfg.to_dict()

    @staticmethod
    async def delete(cfg_id: int, owner: Optional[OwnerContext]):
        cfg = await get_owned_or_404(LLMProviderConfig, cfg_id, owner, for_write=True) if owner else await LLMProviderConfig.get_or_none(id=cfg_id)
        if not cfg:
            raise ValueError("配置不存在或无权删除")
        await cfg.delete()
        return True
