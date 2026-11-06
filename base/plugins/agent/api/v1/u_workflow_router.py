"""
用户侧工作流 API（cus 主体）

溯源：docs/arch/04 §2.1 用户侧工作流 API 清单、PRD §7.1 归属隔离。

与管理侧（workflow.py）的差异：
1. 校验域为 user：10 类开放节点白名单、code 节点拒绝（R-10）、http 域名白名单、
   资源引用授权（E-110）全部生效。
2. 归属强制过滤：全部读写经 owned_queryset/get_owned_or_404（M8），交叉访问 404。
3. 列表附加校验摘要（PRD §7.3：画布页问题面板数据源）。

路由前缀：/u/workflows（本文件以 _router 结尾，先于 workflow.py 的参数路由加载，
避免 /workflows/{workflow_id} 误吞——加载顺序见 api/v1/__init__.py）。
"""
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field

from base.common.authz import OwnerContext, OwnedResourceNotFound, require_owner
from base.common.response import success_response

from ...models.workflow import Workflow
from ...services.workflow_service import (
    DraftConflictError,
    ValidationBlockedError,
    WorkflowService,
    WorkflowStateError,
)
from ...services.graph_validator import DOMAIN_USER

router = APIRouter(prefix="/u/workflows", tags=["用户侧工作流"])


# ============================================================
# 请求模型
# ============================================================
class UserWorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="工作流名称")
    description: str = Field("", max_length=500, description="描述")
    graph_json: Optional[Dict[str, Any]] = Field(None, description="初始图（缺省生成 start→end 骨架）")
    template_id: Optional[int] = Field(None, description="从模板复制（模板工作流 ID）")


class UserWorkflowSaveDraftRequest(BaseModel):
    graph_json: Dict[str, Any] = Field(..., description="Schema v2 图定义")
    draft_version: int = Field(..., description="草稿乐观锁版本号")


class UserWorkflowValidateRequest(BaseModel):
    graph_json: Dict[str, Any] = Field(..., description="待校验图")


class UserWorkflowPublishRequest(BaseModel):
    description: str = Field("", max_length=200, description="发布说明（可选）")


class UserWorkflowRollbackRequest(BaseModel):
    version_no: int = Field(..., description="回滚目标版本号")


def _raise_http(exc: Exception):
    if isinstance(exc, DraftConflictError):
        raise HTTPException(
            status_code=409,
            detail={
                "code": 40901,
                "msg": "草稿已被他人（或另一会话）修改，请刷新后重试",
                "current_draft_version": exc.current_version,
            },
        )
    if isinstance(exc, ValidationBlockedError):
        raise HTTPException(
            status_code=422,
            detail={"code": 42200, "msg": "校验未通过，操作被阻断", "issues": exc.issues},
        )
    if isinstance(exc, WorkflowStateError):
        raise HTTPException(status_code=409, detail={"code": 40900, "msg": str(exc)})
    if isinstance(exc, OwnedResourceNotFound):
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    raise exc


def _list_payload(wf: Workflow) -> Dict[str, Any]:
    definition = wf.definition or {}
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "status": wf.status,
        "schema_version": wf.schema_version,
        "draft_version": wf.draft_version,
        "current_version_id": wf.current_version_id,
        "node_count": len(definition.get("nodes", [])),
        "created_at": wf.created_at,
        "updated_at": wf.updated_at,
    }


# ============================================================
# 列表 / 新建 / 详情
# ============================================================
@router.get("", response_model=dict, summary="我的工作流列表")
async def list_my_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    owner: OwnerContext = Depends(require_owner),
):
    """BUG-T15-005 修复：契约统一为 {items,total,page,page_size}，参数 page/page_size/keyword 对齐前端"""
    skip = (page - 1) * page_size
    workflows = await WorkflowService.get_workflows(
        skip=skip, limit=page_size, name=keyword or "", status=status or "", owner=owner
    )
    total = await WorkflowService.count_workflows(name=keyword or "", status=status or "", owner=owner)
    return success_response(data={
        "items": [_list_payload(w) for w in workflows],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("", response_model=dict, summary="新建工作流（可选从模板复制）")
async def create_my_workflow(
    body: UserWorkflowCreateRequest,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        wf, issues = await WorkflowService.create_user_workflow(
            owner,
            name=body.name,
            description=body.description,
            graph_json=body.graph_json,
            template_id=body.template_id,
        )
    except (OwnedResourceNotFound, WorkflowStateError) as e:
        _raise_http(e)
    data = _list_payload(wf)
    data["validation"] = WorkflowService.validation_summary(issues)
    return success_response(data=data, msg="工作流创建成功")


@router.get("/{workflow_id}", response_model=dict, summary="工作流详情（含校验结果）")
async def get_my_workflow(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        result = await WorkflowService.get_user_workflow_detail(workflow_id, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data=result)


# ============================================================
# 草稿 / 校验 / 发布
# ============================================================
@router.put("/{workflow_id}/draft", response_model=dict, summary="保存草稿（乐观锁）")
async def save_my_draft(
    workflow_id: int,
    body: UserWorkflowSaveDraftRequest,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        fresh, issues = await WorkflowService.save_draft(
            workflow_id, body.graph_json, body.draft_version,
            owner=owner, domain=DOMAIN_USER,
        )
    except (OwnedResourceNotFound, DraftConflictError) as e:
        _raise_http(e)
    return success_response(data={
        "id": fresh.id,
        "draft_version": fresh.draft_version,
        "updated_at": fresh.updated_at,
        "validation": WorkflowService.validation_summary(issues),
    }, msg="草稿已保存")


@router.post("/{workflow_id}/validate", response_model=dict, summary="校验工作流图")
async def validate_my_workflow(
    workflow_id: int,
    body: UserWorkflowValidateRequest,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        result = await WorkflowService.validate_user_workflow(
            workflow_id, body.graph_json, owner=owner
        )
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data=result)


@router.post("/{workflow_id}/publish", response_model=dict, summary="发布工作流")
async def publish_my_workflow(
    workflow_id: int,
    body: Optional[UserWorkflowPublishRequest] = None,
    owner: OwnerContext = Depends(require_owner),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    try:
        result = await WorkflowService.publish_workflow(
            workflow_id, owner=owner,
            idempotency_key=idempotency_key, domain=DOMAIN_USER,
            description=(body.description if body else ""),
        )
    except (OwnedResourceNotFound, DraftConflictError, ValidationBlockedError, WorkflowStateError) as e:
        _raise_http(e)
    return success_response(data=result, msg="发布成功")


# ============================================================
# 版本 / 回滚 / 停用 / 删除
# ============================================================
@router.get("/{workflow_id}/versions", response_model=dict, summary="版本列表")
async def list_my_versions(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        versions = await WorkflowService.list_versions(workflow_id, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data=[
        {
            "id": v.id,
            "version_no": v.version_no,
            "status": v.status,
            # BUG-T15-004：openGauss 空串即 NULL，序列化层兜底为空串保持契约
            "description": v.description or "",
            "resource_refs": v.resource_refs,
            "published_at": v.published_at,
            "created_at": v.created_at,
        }
        for v in versions
    ])


@router.get(
    "/{workflow_id}/versions/{version_no}",
    response_model=dict,
    summary="版本快照（只读）",
)
async def get_my_version_snapshot(
    workflow_id: int,
    version_no: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        v = await WorkflowService.get_version_snapshot(workflow_id, version_no, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data={
        "id": v.id,
        "version_no": v.version_no,
        "status": v.status,
        # BUG-T15-004：openGauss 空串即 NULL，序列化层兜底为空串保持契约
        "description": v.description or "",
        "resource_refs": v.resource_refs,
        "graph_json": v.graph_json,
        "published_at": v.published_at,
        "created_at": v.created_at,
    })


@router.post("/{workflow_id}/rollback", response_model=dict, summary="回滚到历史版本")
async def rollback_my_workflow(
    workflow_id: int,
    body: UserWorkflowRollbackRequest,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        result = await WorkflowService.rollback_workflow(
            workflow_id, body.version_no, owner=owner, domain=DOMAIN_USER
        )
    except (OwnedResourceNotFound, ValidationBlockedError, WorkflowStateError) as e:
        _raise_http(e)
    return success_response(data=result, msg="回滚成功")


@router.post("/{workflow_id}/disable", response_model=dict, summary="停用工作流")
async def disable_my_workflow(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        wf = await WorkflowService.disable_workflow(workflow_id, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data={"id": wf.id, "status": wf.status}, msg="已停用")


@router.delete("/{workflow_id}", response_model=dict, summary="删除工作流")
async def delete_my_workflow(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    """删除（软删）：存在生效发布态需先停用（B5）"""
    try:
        success = await WorkflowService.delete_workflow(workflow_id, owner=owner)
    except (OwnedResourceNotFound, WorkflowStateError) as e:
        _raise_http(e)
    if success:
        return success_response(msg="工作流删除成功")
    raise HTTPException(status_code=500, detail="删除失败")
