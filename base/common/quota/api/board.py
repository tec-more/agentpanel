"""
M9 配额看板 API（后台侧）：GET /v1/quota

溯源：docs/arch/04 §2.1 GET /v1/u/quota（看板输出 plan/period/items[limit/used/held]）；
T4 任务口径：用户侧挂载 /v1/customer/quota（customer 插件），后台对应路由 /v1/quota（本路由）。
鉴权：require_owner（T2/M8 双主体上下文，typ/sub 同源）。
"""
from fastapi import APIRouter, Depends

from base.common.authz.context import OwnerContext, require_owner
from base.common.response import success_response
from base.common.quota.services.quota_service import QuotaService

quota_board_router = APIRouter(prefix="/v1/quota", tags=["配额看板"])


@quota_board_router.get("", summary="当前主体配额看板")
async def get_quota_board(owner: OwnerContext = Depends(require_owner)):
    data = await QuotaService.board(owner)
    return success_response(data=data)
