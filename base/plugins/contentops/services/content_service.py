"""内容中心服务：源内容/成品版本 CRUD + diff 回退。"""
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import ContentItem, ContentVersion
from base.plugins.contentops.schemas.content_schema import ContentCreate, ContentUpdate


class ContentService:
    """内容中心服务（归属隔离）。"""

    @staticmethod
    async def create(data: ContentCreate, owner: Optional[OwnerContext], creator_id: Optional[int] = None):
        item = await ContentItem.create(
            title=data.title, body=data.body, summary=data.summary,
            media=data.media, topics=data.topics, cover=data.cover,
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
            creator_id=creator_id,
        )
        return await item.to_dict()

    @staticmethod
    async def get_list(query, owner: Optional[OwnerContext]):
        qs = owned_queryset(ContentItem, owner) if owner else ContentItem.all()
        if query.status:
            qs = qs.filter(status=query.status)
        if query.keyword:
            from tortoise.expressions import Q
            qs = qs.filter(Q(title__icontains=query.keyword) | Q(summary__icontains=query.keyword))
        total = await qs.count()
        rows = await qs.offset((query.page - 1) * query.page_size).limit(query.page_size)
        return {
            "total": total, "page": query.page, "page_size": query.page_size,
            "items": [await r.to_dict() for r in rows],
        }

    @staticmethod
    async def get_detail(item_id: int, owner: Optional[OwnerContext]):
        item = await get_owned_or_404(ContentItem, item_id, owner) if owner else await ContentItem.get_or_none(id=item_id)
        if not item:
            raise ValueError("内容不存在")
        d = await item.to_dict()
        versions = await ContentVersion.filter(content_id=item.id).order_by("-created_at")
        d["versions"] = [await v.to_dict() for v in versions]
        return d

    @staticmethod
    async def update(item_id: int, data: ContentUpdate, owner: Optional[OwnerContext]):
        item = await get_owned_or_404(ContentItem, item_id, owner, for_write=True) if owner else await ContentItem.get_or_none(id=item_id)
        if not item:
            raise ValueError("内容不存在或无权修改")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await item.save()
        return await item.to_dict()

    @staticmethod
    async def delete(item_id: int, owner: Optional[OwnerContext]):
        item = await get_owned_or_404(ContentItem, item_id, owner, for_write=True) if owner else await ContentItem.get_or_none(id=item_id)
        if not item:
            raise ValueError("内容不存在或无权删除")
        await ContentVersion.filter(content_id=item.id).delete()
        await item.delete()
        return True

    # ---------- 成品版本 ----------
    @staticmethod
    async def create_version(
        content_id: int, platform: str, payload: dict, owner: Optional[OwnerContext],
        is_adapted: bool = False, parent_id: int = None, diff: list = None, rule_version: str = None,
    ):
        ver = await ContentVersion.create(
            content_id=content_id, platform=platform, payload=payload,
            is_adapted=is_adapted, parent_id=parent_id, diff=diff or [],
            rule_version=rule_version,
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
        )
        return await ver.to_dict()

    @staticmethod
    async def update_version(version_id: int, payload: dict, owner: Optional[OwnerContext]):
        ver = await get_owned_or_404(ContentVersion, version_id, owner, for_write=True) if owner else await ContentVersion.get_or_none(id=version_id)
        if not ver:
            raise ValueError("成品版本不存在或无权修改")
        ver.payload = payload
        await ver.save()
        return await ver.to_dict()

    @staticmethod
    async def rollback_version(version_id: int, owner: Optional[OwnerContext]):
        """回退到父版本：把 parent 的 payload 复制为当前版本的新内容。"""
        ver = await get_owned_or_404(ContentVersion, version_id, owner, for_write=True) if owner else await ContentVersion.get_or_none(id=version_id)
        if not ver or not ver.parent_id:
            raise ValueError("无可回退的父版本")
        parent = await ContentVersion.get_or_none(id=ver.parent_id)
        if not parent:
            raise ValueError("父版本不存在")
        ver.payload = parent.payload
        ver.diff = []
        await ver.save()
        return await ver.to_dict()
