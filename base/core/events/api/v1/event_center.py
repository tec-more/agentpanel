"""事件中心管理接口：订阅规则、订阅关系、事件发布与发布记录。

浏览器侧路径：/api/v1/event-center/*（/api 由 app_wrapper 统一剥离）。
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from base.common.response import ErrorResponse, SuccessResponse
from base.common.security import get_current_user_id
from base.core.events.models import EventSubscription
from base.core.events.registry import event_center
from base.core.events.service import EventCenterService

router = APIRouter(prefix="/v1/event-center", tags=["事件中心"])


async def require_admin(current_user_id: int = Depends(get_current_user_id)) -> int:
    from base.core.users.services.user_service import UserService

    user = await UserService.get_by_id(current_user_id)
    if not user or not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user_id


def _error(msg: str, code: int = status.HTTP_400_BAD_REQUEST):
    return ErrorResponse(msg=msg, status_code=code)


@router.get("/rules", summary="获取事件订阅与发布规则")
async def get_rules(admin: int = Depends(require_admin)):
    return SuccessResponse(data=event_center.rules())


@router.get("/subscriptions", summary="查询订阅关系")
async def list_subscriptions(
    event_name: str | None = Query(None),
    subscriber: str | None = Query(None),
    source: str | None = Query(None),
    admin: int = Depends(require_admin),
):
    data = await EventCenterService.list_subscriptions(event_name, subscriber, source)
    return SuccessResponse(data=data)


@router.post("/subscriptions", summary="新增自定义订阅")
async def create_subscription(data: dict = Body(...), admin: int = Depends(require_admin)):
    try:
        sub = await EventCenterService.create_subscription(data)
        return SuccessResponse(data=await sub.to_dict(), msg="订阅已创建")
    except ValueError as e:
        return _error(str(e))


@router.put("/subscriptions/{sub_id}", summary="修改订阅")
async def update_subscription(
    sub_id: int, data: dict = Body(...), admin: int = Depends(require_admin)
):
    sub = await EventSubscription.get_or_none(id=sub_id)
    if not sub:
        return _error("订阅不存在", status.HTTP_404_NOT_FOUND)
    try:
        updated = await EventCenterService.update_subscription(sub, data)
        return SuccessResponse(data=await updated.to_dict(), msg="订阅已更新")
    except ValueError as e:
        return _error(str(e))


@router.post("/subscriptions/{sub_id}/toggle", summary="启用/停用订阅")
async def toggle_subscription(sub_id: int, admin: int = Depends(require_admin)):
    sub = await EventSubscription.get_or_none(id=sub_id)
    if not sub:
        return _error("订阅不存在", status.HTTP_404_NOT_FOUND)
    if sub.is_system:
        return _error("声明式订阅由插件启停控制，请通过插件管理页操作")
    await event_center.set_enabled(sub, not sub.is_enabled)
    refreshed = await EventSubscription.get(id=sub_id)
    return SuccessResponse(data=await refreshed.to_dict(), msg="订阅状态已更新")


@router.delete("/subscriptions/{sub_id}", summary="删除自定义订阅")
async def delete_subscription(sub_id: int, admin: int = Depends(require_admin)):
    sub = await EventSubscription.get_or_none(id=sub_id)
    if not sub:
        return _error("订阅不存在", status.HTTP_404_NOT_FOUND)
    try:
        await EventCenterService.delete_subscription(sub)
        return SuccessResponse(msg="订阅已删除")
    except ValueError as e:
        return _error(str(e))


@router.post("/publish", summary="手动发布事件")
async def publish_event(data: dict = Body(...), admin: int = Depends(require_admin)):
    event_name = (data.get("event_name") or "").strip()
    payload = data.get("payload") or {}
    try:
        result = await event_center.publish(
            event_name,
            payload,
            idempotency_key=data.get("idempotency_key"),
            source_module="event-center/admin",
        )
        return SuccessResponse(data=result, msg="事件已发布")
    except ValueError as e:
        return _error(str(e))


@router.get("/records", summary="查询事件发布记录")
async def list_records(
    event_name: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin: int = Depends(require_admin),
):
    data = await EventCenterService.list_records(event_name, status_filter, page, page_size)
    return SuccessResponse(data=data)


@router.post("/records/{event_uuid}/replay", summary="重放失败事件")
async def replay_event(
    event_uuid: str, data: dict = Body(default={}), admin: int = Depends(require_admin)
):
    try:
        result = await EventCenterService.replay(event_uuid, data.get("reason", ""))
        return SuccessResponse(data=result, msg="事件已重放")
    except ValueError as e:
        return _error(str(e))


@router.get("/stats", summary="事件中心统计")
async def get_stats(admin: int = Depends(require_admin)):
    return SuccessResponse(data=await EventCenterService.stats())


@router.post("/sync", summary="重新同步插件声明订阅")
async def sync_declared(admin: int = Depends(require_admin)):
    await event_center.initialize()
    subs = await EventCenterService.list_subscriptions(source="declared")
    return SuccessResponse(data={"declared": len(subs)}, msg="声明订阅已同步")
