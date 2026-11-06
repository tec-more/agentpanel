"""
M11 身份关联 管理侧 API

溯源：docs/arch/04-核心流程与接口契约.md §2.2 POST /v1/identity-links/admin-bind。

挂载：customer 插件 route_prefix=/v1/customer（项目插件路由习惯），
最终路径 /v1/customer/identity-links/*；仅超级管理员可操作。
"""
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from base.common.permissions import require_superuser
from base.common.response import success_response, fail_response
from base.plugins.customer.services.identity_service import (
    IdentityError,
    IdentityService,
)

identity_admin_router = APIRouter(prefix="/identity-links", tags=["身份关联管理"])


class AdminBindSchema(BaseModel):
    """管理员手动绑定请求"""
    customer_id: int = Field(..., gt=0, description="客户主体 ID")
    user_id: int = Field(..., gt=0, description="后台用户主体 ID")


@identity_admin_router.post("/admin-bind", summary="管理员手动绑定双身份")
async def admin_bind(
    data: AdminBindSchema,
    admin_id: int = require_superuser(),
):
    """管理员手动绑定客户与后台用户（跳过验证，全量审计）"""
    try:
        result = await IdentityService.admin_bind(admin_id, data.customer_id, data.user_id)
        return success_response(data=result, msg="绑定成功")
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)


@identity_admin_router.get("", summary="查询身份关联记录")
async def list_identity_links(
    customer_id: Optional[int] = Query(None, gt=0, description="按客户过滤"),
    user_id: Optional[int] = Query(None, gt=0, description="按后台用户过滤"),
    status: Optional[str] = Query(None, description="按状态过滤: prompted/linked/dismissed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_id: int = require_superuser(),
):
    """关联记录分页查询"""
    data = await IdentityService.list_links(
        customer_id=customer_id, user_id=user_id, status=status,
        page=page, page_size=page_size,
    )
    return success_response(data=data)
