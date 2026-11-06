"""
通知 API 路由（收件箱）
注意：固定子路径 /inbox /unread-count /mark-read /mark-unread 必须声明在动态路径 /{notification_id} 之前。
"""
from fastapi import APIRouter, Query
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.mail.schemas.notification_schema import MarkReadRequest, StarRequest
from base.plugins.mail.services.notification_service import NotificationService

notification_router = APIRouter(prefix="/notifications", tags=["消息-通知"])


# ==================== 固定子路径（必须在动态路径前） ====================


@notification_router.get("/inbox")
async def get_inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    is_read: bool = None,
    is_starred: bool = None,
    message_type: str = None,
    model: str = None,
    user_id: int = require_permission("mail:notification:view"),
):
    """获取当前用户的收件箱"""
    data = await NotificationService.get_inbox(
        user_id=user_id,
        page=page, page_size=page_size,
        is_read=is_read, is_starred=is_starred,
        message_type=message_type, model=model,
    )
    return success_response(data=data)


@notification_router.get("/unread-count")
async def get_unread_count(
    user_id: int = require_permission("mail:notification:view"),
):
    """获取未读通知数"""
    count = await NotificationService.get_unread_count(user_id)
    return success_response(data={"unread_count": count})


@notification_router.post("/mark-read")
async def mark_read(
    payload: MarkReadRequest,
    user_id: int = require_permission("mail:notification:view"),
):
    """标记已读（notification_ids 为空则标记全部已读）"""
    count = await NotificationService.mark_read(user_id, payload.notification_ids)
    return success_response(data={"updated": count}, msg=f"已标记 {count} 条为已读")


@notification_router.post("/mark-unread")
async def mark_unread(
    payload: MarkReadRequest,
    user_id: int = require_permission("mail:notification:view"),
):
    """标记未读"""
    count = await NotificationService.mark_unread(user_id, payload.notification_ids)
    return success_response(data={"updated": count}, msg=f"已标记 {count} 条为未读")


# ==================== 动态路径 ====================


@notification_router.post("/{notification_id}/star")
async def toggle_star(
    notification_id: int,
    payload: StarRequest = None,
    user_id: int = require_permission("mail:notification:view"),
):
    """切换/设置通知标星。

    请求体为空 → 切换标星状态
    请求体 {starred: true/false} → 显式设置
    """
    if payload is None:
        n = await NotificationService.toggle_starred(user_id, notification_id)
    else:
        n = await NotificationService.set_starred(user_id, notification_id, payload.starred)
    if not n:
        return fail_response(msg="通知不存在", code=404)
    return success_response(data=await n.to_dict(), msg="标星状态更新成功")
