"""合规检测路由。"""
from fastapi import APIRouter, Depends

from base.common.authz import OwnerContext, require_owner
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.contentops.schemas.content_schema import ComplianceCheckRequest
from base.plugins.contentops.services.compliance_service import ComplianceEngine

compliance_router = APIRouter(prefix="/compliance", tags=["合规检测"])


@compliance_router.post("/check", summary="合规检测")
async def check(
    data: ComplianceCheckRequest,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:compliance:check"),
):
    if not data.content_id and not data.version_id:
        return fail_response(msg="content_id 与 version_id 至少提供一个", code=400)
    try:
        result = await ComplianceEngine.check_content(
            content_id=data.content_id, version_id=data.version_id,
            channels=data.channels, owner=owner,
        )
        return success_response(data=result, msg="检测完成")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)
