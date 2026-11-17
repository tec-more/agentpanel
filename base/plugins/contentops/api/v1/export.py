"""成品导出路由。"""
from fastapi import APIRouter, Depends

from fastapi.responses import FileResponse

from base.common.authz import OwnerContext, require_owner, require_action
from base.common.response import success_response, fail_response
from base.plugins.contentops.schemas.content_schema import ExportRequest
from base.plugins.contentops.services.export_service import ExportService

export_router = APIRouter(prefix="/exports", tags=["成品导出"])


@export_router.post("", summary="打包导出（生成导出快照）")
async def create_export(
    data: ExportRequest,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:export:create"),
):
    try:
        result = await ExportService.create_export(
            data.content_id, data.platform_version_ids, owner, creator_id=user_id,
        )
        return success_response(data=result, msg="导出完成")
    except ValueError as e:
        return fail_response(msg=str(e), code=400)


@export_router.get("", summary="导出记录列表")
async def list_exports(
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:export:view"),
):
    return success_response(data={"items": await ExportService.list_exports(owner)})


@export_router.get("/{package_id}/download", summary="下载导出 ZIP")
async def download(
    package_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:export:view"),
):
    try:
        path = await ExportService.get_download_path(package_id, owner)
        return FileResponse(path, filename=f"contentops_export_{package_id}.zip", media_type="application/zip")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)
