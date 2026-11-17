"""内容中心路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from base.common.authz import OwnerContext, require_owner, require_action
from base.common.response import success_response, fail_response
from base.plugins.contentops.schemas.content_schema import (
    ContentCreate, ContentUpdate, ContentListQuery, AdaptGenerateRequest, VersionConfirmRequest,
)
from base.plugins.contentops.services import content_service, adapt_service

content_router = APIRouter(prefix="/contents", tags=["内容中心"])


@content_router.post("", summary="创建源内容")
async def create_content(
    data: ContentCreate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:edit"),
):
    result = await content_service.ContentService.create(data, owner, creator_id=user_id)
    return success_response(data=result, msg="内容创建成功")


@content_router.get("", summary="内容列表")
async def list_content(
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=200),
    status: Optional[str] = None, keyword: Optional[str] = None,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:view"),
):
    q = ContentListQuery(page=page, page_size=page_size, status=status, keyword=keyword)
    return success_response(data=await content_service.ContentService.get_list(q, owner))


@content_router.get("/{item_id}", summary="内容详情（含成品版本）")
async def get_content(
    item_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:view"),
):
    try:
        return success_response(data=await content_service.ContentService.get_detail(item_id, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@content_router.put("/{item_id}", summary="编辑源内容")
async def update_content(
    item_id: int, data: ContentUpdate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:edit"),
):
    try:
        return success_response(data=await content_service.ContentService.update(item_id, data, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@content_router.delete("/{item_id}", summary="删除源内容")
async def delete_content(
    item_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:edit"),
):
    try:
        await content_service.ContentService.delete(item_id, owner)
        return success_response(msg="删除成功")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@content_router.put("/versions/{version_id}", summary="编辑成品版本")
async def update_version(
    version_id: int, payload: dict,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:edit"),
):
    try:
        return success_response(data=await content_service.ContentService.update_version(version_id, payload, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@content_router.post("/versions/{version_id}/rollback", summary="成品版本回退到父版本")
async def rollback_version(
    version_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:edit"),
):
    try:
        return success_response(data=await content_service.ContentService.rollback_version(version_id, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=400)


@content_router.post("/versions/{version_id}/confirm", summary="人工确认（导出唯一出口）")
async def confirm_version(
    version_id: int, data: VersionConfirmRequest,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:review:decide"),
):
    try:
        from base.plugins.contentops.services.review_service import ReviewService
        return success_response(data=await ReviewService.confirm_version(version_id, data.confirm, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=400)


@content_router.post("/{item_id}/media/bind", summary="把上传素材绑定到内容")
async def bind_media(
    item_id: int, payload: dict,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:content:edit"),
):
    try:
        from base.plugins.contentops.services.media_service import MediaService
        ids = payload.get("asset_ids") or []
        # 校验内容归属
        await content_service.ContentService.get_detail(item_id, owner)
        count = await MediaService.bind_to_content(ids, item_id, owner)
        return success_response(data={"bound": count}, msg="素材已绑定")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@content_router.post("/adapt/generate", summary="生成平台自适应成品")
async def generate_adapt(
    data: AdaptGenerateRequest,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:adapt:generate"),
):
    try:
        results = await adapt_service.AdaptService.generate(data, owner)
        return success_response(data={"items": results}, msg="自适应成品生成完成")
    except ValueError as e:
        return fail_response(msg=str(e), code=400)
