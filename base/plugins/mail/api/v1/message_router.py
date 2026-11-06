"""
消息 API 路由
注意：固定子路径 /thread 必须声明在动态路径 /{message_id} 之前，避免被参数解析。
"""
from fastapi import APIRouter, Query, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.mail.schemas.message_schema import MessageCreate, MessageUpdate
from base.plugins.mail.services.message_service import MessageService

message_router = APIRouter(prefix="/messages", tags=["消息-记录消息"])


# ==================== 固定子路径（必须在动态路径前） ====================


@message_router.get("/thread")
async def get_thread(
    model: str = Query(..., description="业务表名"),
    res_id: int = Query(..., description="业务记录ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: int = require_permission("mail:message:view"),
):
    """获取业务记录的消息线程（按时间升序）"""
    data = await MessageService.get_thread(model, res_id, page, page_size)
    return success_response(data=data)


# ==================== 动态路径 ====================


@message_router.post("")
async def post_message(
    payload: MessageCreate,
    user_id: int = require_permission("mail:message:post"),
):
    """发布消息（评论或通知）"""
    msg = await MessageService.post_message(
        model=payload.model,
        res_id=payload.res_id,
        body=payload.body,
        author_id=user_id,
        subtype_id=payload.subtype_id,
        subtype_code=payload.subtype_code,
        message_type=payload.message_type,
        subject=payload.subject,
        parent_id=payload.parent_id,
        attachment_ids=payload.attachment_ids,
        is_internal=payload.is_internal,
        record_name=payload.record_name,
        notify_followers=payload.notify_followers,
        extra_recipient_ids=payload.extra_recipient_ids,
    )
    return success_response(data=await msg.to_dict(include_author=True, include_subtype=True),
                             msg="消息发布成功")


@message_router.get("/{message_id}")
async def get_message(
    message_id: int,
    user_id: int = require_permission("mail:message:view"),
):
    """获取消息详情"""
    msg = await MessageService.get_message(message_id)
    if not msg:
        return fail_response(msg="消息不存在", code=404)
    return success_response(data=await msg.to_dict(include_author=True, include_subtype=True))


@message_router.put("/{message_id}")
async def update_message(
    message_id: int,
    payload: MessageUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """更新消息（仅作者或拥有 mail:message:manage 权限）"""
    # 检查是否拥有管理员权限
    from base.common.permissions import get_user_permissions_cached
    user_perms = await get_user_permissions_cached(user_id)
    is_admin = "*" in user_perms or "mail:message:manage" in user_perms

    try:
        msg = await MessageService.update_message(message_id, payload, user_id, is_admin=is_admin)
    except PermissionError as e:
        return fail_response(msg=str(e), code=403)
    if not msg:
        return fail_response(msg="消息不存在", code=404)
    return success_response(data=await msg.to_dict(include_author=True), msg="消息更新成功")


@message_router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """删除消息（仅作者或拥有 mail:message:manage 权限）"""
    from base.common.permissions import get_user_permissions_cached
    user_perms = await get_user_permissions_cached(user_id)
    is_admin = "*" in user_perms or "mail:message:manage" in user_perms

    try:
        success = await MessageService.delete_message(message_id, user_id, is_admin=is_admin)
    except PermissionError as e:
        return fail_response(msg=str(e), code=403)
    if not success:
        return fail_response(msg="消息不存在", code=404)
    return success_response(msg="消息删除成功")
