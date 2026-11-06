from fastapi import APIRouter, Query
from typing import Optional
from base.plugins.subcontracting.schemas.subcontracting_schema import SubcontractingIssueCreate
from base.plugins.subcontracting.services.subcontracting_issue_service import SubcontractingIssueService

subcontracting_issue_router = APIRouter(prefix="/issues", tags=["委外-发料管理"])


@subcontracting_issue_router.post("/", summary="创建委外发料单")
async def create_issue(data: SubcontractingIssueCreate):
    try:
        issue = await SubcontractingIssueService.create_issue(data.dict())
        result = await issue.to_dict()
        from base.plugins.subcontracting.services.subcontracting_issue_service import ISSUE_STATUS_LABELS
        result["status_label"] = ISSUE_STATUS_LABELS.get(issue.status, issue.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_issue_router.get("/", summary="查询委外发料单列表")
async def get_issue_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    sc_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    return await SubcontractingIssueService.get_list(
        page=page, page_size=page_size, sc_code=sc_code, status=status
    )


@subcontracting_issue_router.get("/{issue_id}", summary="获取发料单详情")
async def get_issue(issue_id: int):
    issue = await SubcontractingIssueService.get_by_id(issue_id)
    if not issue:
        return {"error": "发料单不存在"}
    result = await issue.to_dict()
    from base.plugins.subcontracting.services.subcontracting_issue_service import ISSUE_STATUS_LABELS
    result["status_label"] = ISSUE_STATUS_LABELS.get(issue.status, issue.status)
    from base.plugins.subcontracting.models.subcontracting_issue import SubcontractingIssueLine
    lines = await SubcontractingIssueLine.filter(issue_id=issue.id).all()
    result["lines"] = [await l.to_dict() for l in lines]
    return result


@subcontracting_issue_router.post("/{issue_id}/generate-bom-lines", summary="按BOM生成发料明细")
async def generate_bom_lines(issue_id: int):
    try:
        lines = await SubcontractingIssueService.generate_bom_lines(issue_id)
        return {"lines": lines}
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_issue_router.put("/{issue_id}/confirm", summary="确认发料")
async def confirm_issue(issue_id: int, confirmer: Optional[str] = None):
    try:
        issue = await SubcontractingIssueService.confirm_issue(issue_id, confirmer=confirmer)
        result = await issue.to_dict()
        from base.plugins.subcontracting.services.subcontracting_issue_service import ISSUE_STATUS_LABELS
        result["status_label"] = ISSUE_STATUS_LABELS.get(issue.status, issue.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_issue_router.put("/{issue_id}/cancel", summary="取消发料单")
async def cancel_issue(issue_id: int):
    try:
        issue = await SubcontractingIssueService.cancel_issue(issue_id)
        result = await issue.to_dict()
        from base.plugins.subcontracting.services.subcontracting_issue_service import ISSUE_STATUS_LABELS
        result["status_label"] = ISSUE_STATUS_LABELS.get(issue.status, issue.status)
        return result
    except ValueError as e:
        return {"error": str(e)}