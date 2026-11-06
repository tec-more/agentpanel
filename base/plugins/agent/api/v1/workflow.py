"""
工作流 API 路由（管理侧）

M3/T5 改造：
1. 全部端点接入 M8 归属过滤（RK-01 修复：require_owner + owned_queryset/get_owned_or_404）。
   usr 超管 data_scope=all 时保持既有全量可见行为，既有响应结构不变（只增不删）。
2. 新增 M3 端点：校验 / 草稿保存（乐观锁 409）/ 发布（Idempotency-Key 去重）/
   版本列表与快照 / 回滚 / 停用。

管理侧校验域为 admin：不做用户域节点类型/资源授权限制（保持后台画布兼容），
结构、图与类型错误照常报告；发布仍被阻断性错误拦截。
"""
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field

from base.common.authz import (
    OwnerContext,
    OwnedResourceNotFound,
    get_owned_or_404,
    owned_queryset,
    require_owner,
)
from base.common.response import fail_response, success_response

from ...models.workflow import Workflow, WorkflowExecution
from ...models.workflow_version import WorkflowVersion
from ...schemas.workflow import WorkflowCreate, WorkflowUpdate
from ...services.workflow_service import (
    DraftConflictError,
    ValidationBlockedError,
    WorkflowService,
    WorkflowStateError,
)
from ...services.graph_validator import DOMAIN_ADMIN

workflow_router = APIRouter(prefix="/workflows", tags=["工作流管理"])
workflow_execution_router = APIRouter(prefix="/workflow-executions", tags=["工作流执行记录"])


# ============================================================
# 请求模型
# ============================================================
class WorkflowSaveDraftRequest(BaseModel):
    graph_json: Dict[str, Any] = Field(..., description="Schema v2 图定义")
    draft_version: int = Field(..., description="草稿乐观锁版本号（读取时获得）")


class WorkflowValidateRequest(BaseModel):
    graph_json: Dict[str, Any] = Field(..., description="待校验的 Schema v2 图定义")


class WorkflowPublishRequest(BaseModel):
    description: str = Field("", max_length=200, description="发布说明（可选）")


class WorkflowRollbackRequest(BaseModel):
    version_no: int = Field(..., description="回滚目标版本号")


# ============================================================
# 异常 → HTTP 映射
# ============================================================
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


def _wf_payload(wf: Workflow) -> Dict[str, Any]:
    """既有响应结构（保持后台前端兼容），附加 M3 字段"""
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "status": wf.status,
        "definition": wf.definition,
        "created_at": wf.created_at,
        "updated_at": wf.updated_at,
        "node_count": len(wf.definition.get("nodes", [])) if wf.definition else 0,
        "edge_count": len(wf.definition.get("edges", [])) if wf.definition else 0,
        # M3 附加字段（不破坏既有结构）
        "schema_version": wf.schema_version,
        "draft_version": wf.draft_version,
        "current_version_id": wf.current_version_id,
        "owner_type": wf.owner_type,
        "owner_id": wf.owner_id,
        "visibility": wf.visibility,
    }


def _version_payload(v: WorkflowVersion) -> Dict[str, Any]:
    return {
        "id": v.id,
        "workflow_id": v.workflow_id,
        "version_no": v.version_no,
        "status": v.status,
        # BUG-T15-004：openGauss 空串即 NULL，序列化层兜底为空串保持契约
        "description": v.description or "",
        "resource_refs": v.resource_refs,
        "published_by_type": v.published_by_type,
        "published_by_id": v.published_by_id,
        "published_at": v.published_at,
        "created_at": v.created_at,
        "updated_at": v.updated_at,
    }


# ============================================================
# 既有端点（接入归属过滤，响应结构不变）
# ============================================================
@workflow_router.post("/", response_model=dict, summary="创建工作流")
async def create_workflow(
    body: WorkflowCreate,
    owner: OwnerContext = Depends(require_owner),
):
    workflow = await WorkflowService.create_workflow(body, owner=owner)
    return success_response(
        data={"id": workflow.id, "name": workflow.name}, msg="工作流创建成功"
    )


@workflow_router.get("/", response_model=dict, summary="获取工作流列表")
async def get_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
    owner: OwnerContext = Depends(require_owner),
):
    workflows = await WorkflowService.get_workflows(
        skip=skip, limit=limit, status=status, owner=owner
    )
    return success_response(data=[_wf_payload(w) for w in workflows])


@workflow_router.get("/{workflow_id}", response_model=dict, summary="获取工作流详情")
async def get_workflow(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        workflow = await WorkflowService.get_workflow_by_id(
            workflow_id, owner=owner, include_public=True
        )
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data=_wf_payload(workflow))


@workflow_router.put("/{workflow_id}", response_model=dict, summary="更新工作流")
async def update_workflow(
    workflow_id: int,
    body: WorkflowUpdate,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        workflow = await WorkflowService.update_workflow(workflow_id, body, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(
        data={"id": workflow.id, "name": workflow.name}, msg="工作流更新成功"
    )


@workflow_router.delete("/{workflow_id}", response_model=dict, summary="删除工作流")
async def delete_workflow(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        success = await WorkflowService.delete_workflow(workflow_id, owner=owner)
    except (OwnedResourceNotFound, WorkflowStateError) as e:
        _raise_http(e)
    if success:
        return success_response(msg="工作流删除成功")
    return fail_response(msg="工作流删除失败", code=500)


# ============================================================
# M3 新增端点：校验 / 草稿 / 发布 / 版本 / 回滚 / 停用
# ============================================================
@workflow_router.post("/{workflow_id}/validate", response_model=dict, summary="校验工作流图")
async def validate_workflow_graph(
    workflow_id: int,
    body: WorkflowValidateRequest,
    owner: OwnerContext = Depends(require_owner),
):
    """管理侧全量校验（admin 域：不拦截节点类型/资源授权，仅报告结构与图错误）"""
    try:
        await get_owned_or_404(Workflow, workflow_id, owner, include_public=True)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    issues = await WorkflowService.validate_graph_for(
        owner, body.graph_json, domain=DOMAIN_ADMIN
    )
    return success_response(data=WorkflowService.validation_summary(issues))


@workflow_router.put("/{workflow_id}/draft", response_model=dict, summary="保存工作流草稿")
async def save_workflow_draft(
    workflow_id: int,
    body: WorkflowSaveDraftRequest,
    owner: OwnerContext = Depends(require_owner),
):
    """保存草稿（乐观锁）：冲突 40901；校验错误不阻断保存但随响应返回"""
    try:
        fresh, issues = await WorkflowService.save_draft(
            workflow_id, body.graph_json, body.draft_version,
            owner=owner, domain=DOMAIN_ADMIN,
        )
    except (OwnedResourceNotFound, DraftConflictError) as e:
        _raise_http(e)
    return success_response(data={
        "id": fresh.id,
        "draft_version": fresh.draft_version,
        "updated_at": fresh.updated_at,
        "validation": WorkflowService.validation_summary(issues),
    }, msg="草稿已保存")


@workflow_router.post("/{workflow_id}/publish", response_model=dict, summary="发布工作流")
async def publish_workflow(
    workflow_id: int,
    body: Optional[WorkflowPublishRequest] = None,
    owner: OwnerContext = Depends(require_owner),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """发布：Idempotency-Key 24h 去重；阻断性校验错误（E-1xx）→ 422 拒绝"""
    try:
        result = await WorkflowService.publish_workflow(
            workflow_id, owner=owner,
            idempotency_key=idempotency_key, domain=DOMAIN_ADMIN,
            description=(body.description if body else ""),
        )
    except (OwnedResourceNotFound, DraftConflictError, ValidationBlockedError, WorkflowStateError) as e:
        _raise_http(e)
    return success_response(data=result, msg="发布成功")


@workflow_router.get("/{workflow_id}/versions", response_model=dict, summary="版本列表")
async def list_workflow_versions(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        versions = await WorkflowService.list_versions(workflow_id, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data=[_version_payload(v) for v in versions])


@workflow_router.get(
    "/{workflow_id}/versions/{version_no}",
    response_model=dict,
    summary="版本快照（只读）",
)
async def get_workflow_version(
    workflow_id: int,
    version_no: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        v = await WorkflowService.get_version_snapshot(workflow_id, version_no, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    data = _version_payload(v)
    data["graph_json"] = v.graph_json  # 快照完整图（只读）
    return success_response(data=data)


@workflow_router.post("/{workflow_id}/rollback", response_model=dict, summary="回滚到历史版本")
async def rollback_workflow(
    workflow_id: int,
    body: WorkflowRollbackRequest,
    owner: OwnerContext = Depends(require_owner),
):
    """回滚＝以旧版本图生成新版本（历史版本不可变）"""
    try:
        result = await WorkflowService.rollback_workflow(
            workflow_id, body.version_no, owner=owner, domain=DOMAIN_ADMIN
        )
    except (OwnedResourceNotFound, ValidationBlockedError, WorkflowStateError) as e:
        _raise_http(e)
    return success_response(data=result, msg="回滚成功")


@workflow_router.post("/{workflow_id}/disable", response_model=dict, summary="停用工作流")
async def disable_workflow(
    workflow_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        wf = await WorkflowService.disable_workflow(workflow_id, owner=owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data={"id": wf.id, "status": wf.status}, msg="已停用")


# ============================================================
# 执行相关（归属过滤；引擎执行为 T6 范围，此处仅保留既有直接执行入口）
# ============================================================
@workflow_router.post("/{workflow_id}/execute", response_model=dict, summary="执行工作流")
async def execute_workflow(
    workflow_id: int,
    input_data: Dict[str, Any],
    owner: OwnerContext = Depends(require_owner),
):
    try:
        await get_owned_or_404(Workflow, workflow_id, owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    execution = await WorkflowService.execute_workflow_direct(workflow_id, input_data)
    return success_response(
        data={
            "execution_id": execution.id,
            "status": execution.status,
            "output_data": execution.output_data,
        },
        msg="工作流执行完成",
    )


@workflow_execution_router.get("/", response_model=dict, summary="获取工作流执行列表")
async def get_workflow_executions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    workflow_id: Optional[int] = None,
    status: Optional[str] = None,
    owner: OwnerContext = Depends(require_owner),
):
    query = owned_queryset(WorkflowExecution, owner, include_public=False)
    if workflow_id:
        query = query.filter(workflow_id=workflow_id)
    if status:
        query = query.filter(status=status)

    executions = await query.offset(skip).limit(limit).order_by("-created_at")
    return success_response(data=[
        {
            "id": e.id,
            "workflow_id": e.workflow_id,
            "status": e.status,
            "input_data": e.input_data,
            "output_data": e.output_data,
            "error_message": e.error_message,
            "started_at": e.started_at,
            "completed_at": e.completed_at,
            "created_at": e.created_at,
        }
        for e in executions
    ])


@workflow_execution_router.get(
    "/{execution_id}",
    response_model=dict,
    summary="获取工作流执行详情",
)
async def get_workflow_execution(
    execution_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        execution = await get_owned_or_404(
            WorkflowExecution, execution_id, owner, include_public=False
        )
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data={
        "id": execution.id,
        "workflow_id": execution.workflow_id,
        "status": execution.status,
        "input_data": execution.input_data,
        "output_data": execution.output_data,
        "error_message": execution.error_message,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "created_at": execution.created_at,
    })
