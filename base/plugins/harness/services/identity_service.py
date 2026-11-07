"""Harness 外部身份 → 本地用户映射服务"""
from typing import Any, Dict, Optional

from base.plugins.harness.models.harness import HarnessIdentity


class HarnessIdentityService:
    @classmethod
    async def resolve(
        cls, client_id: str, external_type: str, external_id: str
    ) -> Optional[HarnessIdentity]:
        identity = await HarnessIdentity.get_or_none(
            client_id=client_id, external_type=external_type, external_id=external_id
        )
        if identity is None or identity.status != "active":
            return None
        return identity

    @classmethod
    async def bind(
        cls,
        client_id: str,
        external_type: str,
        external_id: str,
        user_id: int,
        external_name: Optional[str] = None,
        owner_type: str = "usr",
        owner_id: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> HarnessIdentity:
        identity = await HarnessIdentity.get_or_none(
            client_id=client_id, external_type=external_type, external_id=external_id
        )
        if identity is None:
            return await HarnessIdentity.create(
                client_id=client_id,
                external_type=external_type,
                external_id=external_id,
                external_name=external_name,
                user_id=user_id,
                owner_type=owner_type,
                owner_id=owner_id or user_id,
                status="active",
                meta=meta,
            )
        identity.user_id = user_id
        identity.external_name = external_name or identity.external_name
        identity.owner_type = owner_type
        identity.owner_id = owner_id or user_id
        identity.meta = meta if meta is not None else identity.meta
        identity.status = "active"
        await identity.save()
        return identity

    @classmethod
    async def disable(cls, identity_id: int) -> bool:
        identity = await HarnessIdentity.get_or_none(id=identity_id)
        if identity is None:
            return False
        identity.status = "disabled"
        await identity.save()
        return True
