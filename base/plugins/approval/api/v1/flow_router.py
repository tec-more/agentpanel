"""
审批流程规则 API 路由（流程本身即审批规则）
"""
from typing import Optional
from fastapi import APIRouter, Query, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.approval.schemas.flow_schema import FlowCreate, FlowUpdate, FlowListQuery
from base.plugins.approval.services.flow_service import FlowService

flow_router = APIRouter(prefix="/flow-rules", tags=["审批流程规则"])


# ==================== 前端审批检测 API（无需权限，页面级调用） ====================

@flow_router.get("/check-for-model")
async def check_approval_for_model(
    model: str = Query(..., description="业务模型标识"),
    action: Optional[str] = Query(None, description="动作 create/update/delete，不传则返回该模型所有匹配流程"),
):
    """前端调用：检测当前模型是否配置了审批规则。

    返回该模型所有启用的流程规则及其匹配的动作/methods，
    前端据此决定是否显示「提交审批」按钮以及支持哪些操作走审批。
    无需权限，任何登录用户均可调用。
    """
    from base.plugins.approval.models.approval_flow import ApprovalFlow

    flows = await ApprovalFlow.filter(is_active=True, model=model).order_by("-priority").all()
    result = []
    for flow in flows:
        actions = []
        if flow.action:
            actions.append(flow.action)
        else:
            # 未指定 action，表示匹配全部动作
            methods = flow.methods or ["POST", "PUT", "DELETE"]
            m_to_a = {"POST": "create", "PUT": "update", "DELETE": "delete"}
            actions = [m_to_a[m] for m in methods if m in m_to_a]

        if action and action not in actions:
            continue

        result.append({
            "flow_id": flow.id,
            "flow_name": flow.name,
            "flow_code": flow.code,
            "actions": actions,
            "methods": flow.methods,
            "priority": flow.priority,
            "business_type": flow.business_type,
            "form_config": flow.form_config,
        })

    return success_response(data={
        "model": model,
        "require_approval": len(result) > 0,
        "flows": result,
    })


@flow_router.post("/submit-for-approval")
async def submit_for_approval(
    payload: dict,
    user_id: int = Depends(get_current_user_id),
):
    """前端调用：直接提交审批（创建实例）。

    请求体：
        model: 业务模型标识
        action: create/update/delete
        data: 业务数据载荷
        business_id: 业务对象 ID（update/delete）
        title: 审批标题（可选）

    审批模块负责：校验规则 → 创建实例 → 返回实例 ID。
    """
    from base.plugins.approval.services.approval_gate import gate_write

    model = payload.get("model")
    action = payload.get("action")
    business_data = payload.get("data")
    business_id = payload.get("business_id")
    title = payload.get("title")

    if not model or not action:
        return fail_response(msg="缺少 model 或 action 参数")

    try:
        await gate_write(
            model=model,
            action=action,
            payload=business_data,
            business_id=business_id,
            applicant_id=user_id,
            title=title,
        )
        # gate_write 命中时抛 NeedApprovalError → 异常处理器返回 40001
        # 未命中时静默放行 → 此处返回无需审批
        return success_response(data={"require_approval": False}, msg="该操作无需审批，直接执行即可")
    except Exception as e:
        # NeedApprovalError 由异常处理器处理，这里兜底其他错误
        from base.plugins.approval.services.approval_gate import NeedApprovalError
        if isinstance(e, NeedApprovalError):
            raise  # 让异常处理器处理
        return fail_response(msg=str(e))


# ==================== 审批上下文 API（无需权限，页面级调用） ====================


@flow_router.get("/context")
async def get_approval_context(
    model: str = Query(..., description="业务模型标识"),
    business_id: int = Query(None, description="业务对象 ID（详情页传入）"),
    user_id: int = Depends(get_current_user_id),
):
    """获取审批上下文：合并流程规则、实例状态、当前用户的审批任务。

    返回数据前端可直接用于判断显示哪些审批按钮：
    - has_flow: 模型是否有启用的审批流程
    - flows: 匹配的流程列表（含各动作支持情况）
    - instance: 现有审批实例（详情页传入 business_id 时返回）
    - pending_tasks: 当前用户在实例上的待处理任务
    - can_submit: 可提交审批（有流程 且 无进行中实例 或 有创建动作的流程）
    - can_approve: 当前用户是某个待处理任务的审批人
    - can_cancel: 当前用户是实例申请人且实例未完结
    - can_create / can_update / can_delete: 各动作是否有匹配流程
    """
    data = await FlowService.build_approval_context(model, business_id, user_id)
    return success_response(data=data)


@flow_router.get("/context-by-route")
async def get_context_by_route(
    route: str = Query(..., description="当前前端路由路径，如 /panel/purchase/order/123"),
    business_id: int = Query(None, description="业务对象 ID（详情页传入）"),
    user_id: int = Depends(get_current_user_id),
):
    """全局审批组件按当前前端路由反查命中的审批流程，返回审批上下文。

    无需权限（页面级调用，与 /context 一致）。
    后台在流程规则的 route_patterns 中配置适用的路由模式（支持 :id 参数段），
    本接口据此匹配，命中则返回 has_flow=True 及完整上下文，未命中返回 has_flow=False。
    """
    data = await FlowService.get_context_by_route(route, business_id, user_id)
    return success_response(data=data)


# ==================== 流程规则管理 API（需权限） ====================


@flow_router.get("/models")
async def get_available_models(
    user_id: int = require_permission("approval:flowrule:view"),
):
    """获取所有可用的业务模型（用于流程规则配置）"""
    models = FlowService.get_available_models()
    return success_response(data=models)


@flow_router.get("/actions")
async def get_model_actions(
    model: str = Query(..., description="业务模型标识"),
    user_id: int = require_permission("approval:flowrule:view"),
):
    """根据业务模型获取可配置的执行动作"""
    actions = FlowService.get_model_actions(model)
    return success_response(data=actions)


@flow_router.post("/check")
async def check_approval_required(
    payload: dict,
    user_id: int = require_permission("approval:flowrule:view"),
):
    """根据业务模型和方法检查是否需要审批（基于模型匹配）"""
    model = payload.get("model")
    method = payload.get("method", "POST")
    if not model:
        return fail_response(msg="缺少 model 参数")
    result = await FlowService.check_approval_required_by_model(model, method)
    return success_response(data=result)


@flow_router.post("")
async def create_flow(
    flow_data: FlowCreate,
    user_id: int = require_permission("approval:flowrule:manage"),
):
    """创建审批流程规则"""
    try:
        flow = await FlowService.create_flow(flow_data)
        return success_response(data=await flow.to_dict(), msg="流程创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@flow_router.post("/validate")
async def validate_flow(
    flow_data: FlowCreate,
    user_id: int = require_permission("approval:flowrule:view"),
):
    """校验流程配置结构（不落库），供前端实时校验使用"""
    errors = FlowService.validate_flow_config(flow_data.flow_config)
    if errors:
        return success_response(data={"valid": False, "errors": errors})
    return success_response(data={"valid": True, "errors": []})


@flow_router.get("")
async def get_flow_list(
    page: int = 1,
    page_size: int = 10,
    name: str = None,
    business_type: str = None,
    model: str = None,
    action: str = None,
    is_active: bool = None,
    user_id: int = require_permission("approval:flowrule:view"),
):
    """获取审批流程规则列表"""
    query = FlowListQuery(
        page=page,
        page_size=page_size,
        name=name,
        business_type=business_type,
        model=model,
        action=action,
        is_active=is_active
    )
    result = await FlowService.get_flow_list(query)
    return success_response(data=result)


@flow_router.get("/{flow_id}")
async def get_flow_detail(
    flow_id: int,
    user_id: int = require_permission("approval:flowrule:view"),
):
    """获取审批流程规则详情"""
    flow = await FlowService.get_flow(flow_id)
    if not flow:
        return fail_response(msg="流程不存在", code=404)
    return success_response(data=await flow.to_dict())


@flow_router.put("/{flow_id}")
async def update_flow(
    flow_id: int,
    flow_data: FlowUpdate,
    user_id: int = require_permission("approval:flowrule:manage"),
):
    """更新审批流程规则"""
    try:
        flow = await FlowService.update_flow(flow_id, flow_data)
        if not flow:
            return fail_response(msg="流程不存在", code=404)
        return success_response(data=await flow.to_dict(), msg="流程更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@flow_router.delete("/{flow_id}")
async def delete_flow(
    flow_id: int,
    user_id: int = require_permission("approval:flowrule:manage"),
):
    """删除审批流程规则"""
    try:
        success = await FlowService.delete_flow(flow_id)
        if not success:
            return fail_response(msg="流程不存在", code=404)
        return success_response(msg="流程删除成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@flow_router.post("/{flow_id}/toggle")
async def toggle_flow_status(
    flow_id: int,
    is_active: bool,
    user_id: int = require_permission("approval:flowrule:manage"),
):
    """切换流程规则启用状态"""
    flow = await FlowService.toggle_flow_status(flow_id, is_active)
    if not flow:
        return fail_response(msg="流程不存在", code=404)
    return success_response(data=await flow.to_dict(), msg="状态更新成功")


@flow_router.get("/business-type/{business_type}")
async def get_flow_by_business_type(
    business_type: str,
    user_id: int = require_permission("approval:flowrule:view"),
):
    """根据业务类型获取启用的流程规则"""
    flow = await FlowService.get_flow_by_business_type(business_type)
    if not flow:
        return success_response(data=None, msg="未找到对应流程")
    return success_response(data=await flow.to_dict())
