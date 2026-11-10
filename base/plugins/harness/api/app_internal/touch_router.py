"""app 内部接口：供 独立服务上报客户端活跃时间（服务凭据保护）

- 表归属：`harness_client` 属于 app，只有 app 写；
- 独立服务只调用本接口，不直接写表；
- 失败/客户端不存在按 best-effort 处理，不抛业务错误；
- 不在 `api/v1` 下，避免被插件路由前缀 `/v1/harness` 包裹；由 start.py 手动挂载到根路径。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from base.common.response import success_response
from base.plugins.harness.models.harness import HarnessClient
from base.plugins.harness.services import service_auth

app_touch_router = APIRouter(prefix="/internal/v1/harness", tags=["Harness-内部"], include_in_schema=False)


async def _require_service(request: Request):
    try:
        return await service_auth.authenticate(request, ("clients:touch",))
    except service_auth.ServiceAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.status_code, "msg": exc.message, "data": exc.to_dict()},
        )


@app_touch_router.post("/clients/{client_id}/touch", summary="上报客户端最近活跃时间")
async def touch_client(client_id: str, _identity=Depends(_require_service)):
    updated = await HarnessClient.filter(client_id=client_id).update(last_used_at=datetime.now())
    return success_response(
        data={"client_id": client_id, "updated": bool(updated)},
        msg="已更新" if updated else "客户端不存在或无需更新",
        success=True,
    )
