"""发现应用目录（harness 插件）：USR 后台维护，CUS 客户端只读下发。

两条路由互不混用：
- /v1/harness/discover-apps        CUS JWT（底座 require_customer），仅启用项；
- /v1/harness/admin/discover-apps  USR JWT + 超管，后台管理全量项。

2026-11-26 从 customer 插件迁入 harness：CUS 守卫取自底座 base.common.authz，
不 import customer 插件内部服务；数据表仍为 customer_discover_app（不改名，
避免 openGauss 数据迁移）。
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from base.common.authz import require_customer
from base.common.response import success_response
from base.common.security import get_current_user_id
from base.plugins.harness.models.discover_app import CustomerDiscoverApp
from base.plugins.harness.schemas.discover_app import (
    DiscoverAppBase,
    DiscoverAppStatusUpdate,
    DiscoverAppUpdate,
)

# 装配器只取文件里首个 router 变量，因此用主 router 聚合两条子路由。
discover_app_router = APIRouter()
catalog_router = APIRouter(prefix="/discover-apps", tags=["Harness 发现应用"])
admin_discover_app_router = APIRouter(prefix="/admin/discover-apps", tags=["Harness 发现应用管理"])


def to_dict(item: CustomerDiscoverApp) -> dict[str, Any]:
    """只暴露客户端需要的展示字段，不泄漏任何服务端配置。"""
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "icon_text": item.icon_text,
        "icon_color": item.icon_color,
        "open_mode": item.open_mode,
        "target": item.target,
        "sort": item.sort,
        "is_active": item.is_active,
    }


async def require_admin(current_user_id: int = Depends(get_current_user_id)) -> int:
    """与系统设置一致：USR 超管才可维护应用目录。"""
    from base.core.users.services.user_service import UserService

    user = await UserService.get_by_id(current_user_id)
    if user is None or not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限执行此操作")
    return current_user_id


@catalog_router.get("", summary="[客户] 获取可见应用目录")
async def list_discover_apps(_owner=Depends(require_customer)):
    items = await CustomerDiscoverApp.filter(is_active=True).order_by("sort", "id").all()
    return success_response(data={"items": [to_dict(item) for item in items]})


@admin_discover_app_router.get("", summary="[后台] 应用目录列表")
async def admin_list_apps(_admin=Depends(require_admin)):
    items = await CustomerDiscoverApp.all().order_by("sort", "id")
    return success_response(data={"items": [to_dict(item) for item in items]})


@admin_discover_app_router.post("", summary="[后台] 新增应用")
async def admin_create_app(data: DiscoverAppBase, _admin=Depends(require_admin)):
    item = await CustomerDiscoverApp.create(**data.model_dump())
    return success_response(data=to_dict(item), msg="创建成功")


@admin_discover_app_router.put("/{app_id}", summary="[后台] 更新应用")
async def admin_update_app(app_id: int, data: DiscoverAppUpdate, _admin=Depends(require_admin)):
    item = await CustomerDiscoverApp.get_or_none(id=app_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="应用不存在")
    merged = to_dict(item)
    merged.update({key: value for key, value in data.model_dump(exclude_unset=True).items() if value is not None})
    try:
        validated = DiscoverAppBase(**merged)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    for key, value in validated.model_dump().items():
        setattr(item, key, value)
    await item.save()
    return success_response(data=to_dict(item), msg="更新成功")


@admin_discover_app_router.delete("/{app_id}", summary="[后台] 删除应用")
async def admin_delete_app(app_id: int, _admin=Depends(require_admin)):
    deleted = await CustomerDiscoverApp.filter(id=app_id).delete()
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="应用不存在")
    return success_response(msg="删除成功")


@admin_discover_app_router.patch("/{app_id}/status", summary="[后台] 启停应用")
async def admin_toggle_app(app_id: int, data: DiscoverAppStatusUpdate, _admin=Depends(require_admin)):
    item = await CustomerDiscoverApp.get_or_none(id=app_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="应用不存在")
    item.is_active = data.is_active
    await item.save(update_fields=["is_active"])
    return success_response(data=to_dict(item), msg="状态已更新")


discover_app_router.include_router(catalog_router)
discover_app_router.include_router(admin_discover_app_router)
