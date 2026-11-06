"""
M9 配额看板 用户侧 API（双主体 cus/usr 均可访问）

溯源：docs/arch/04 §2.1 GET /v1/u/quota；T4 任务口径：用户侧挂载 /v1/customer/quota。

挂载说明：文件名以 _router 结尾，插件加载器优先注册（plugin_manager 排序规则），
确保 /v1/customer/quota 先于 customer.py 的 /{customer_id} 参数化路由命中，
不会被误解析为 customer_id="quota"。
鉴权复用 T2/M8 require_owner（typ/sub 同源）。
"""
from fastapi import APIRouter, Depends

from base.common.authz.context import OwnerContext, require_owner
from base.common.response import success_response
from base.common.quota.services.quota_service import QuotaService

quota_router = APIRouter(prefix="/quota", tags=["配额看板"])


@quota_router.get("", summary="当前主体配额看板（plan/period/items[limit/used/held]）")
async def get_quota_board(owner: OwnerContext = Depends(require_owner)):
    data = await QuotaService.board(owner)
    return success_response(data=data)
