"""Harness 三档审批策略管理与评估（fail-closed）"""
from fastapi import APIRouter, Depends, Query, Request

from base.common.permissions import require_superuser
from base.common.response import success_response, fail_response
from base.plugins.harness.models.harness import HarnessActionPolicy
from base.plugins.harness.schemas.harness import ActionEvaluate, PolicyCreate, PolicyRuleUpsert
from base.plugins.harness.services.audit_service import HarnessAuditService
from base.plugins.harness.services.orchestration_proxy import (
    proxy_mode_enabled,
    proxy_to_orchestration,
    require_client_or_proxy,
)
from base.plugins.harness.services.policy_rule_service import HarnessPolicyRuleService
from base.plugins.harness.services.policy_service import HarnessPolicyService, approval_config

policy_router = APIRouter(prefix="/policies", tags=["Harness-策略"])


def _policy_dict(row: HarnessActionPolicy) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "action_pattern": row.action_pattern,
        "effect": row.effect,
        "risk_level": row.risk_level,
        "require_approval": row.require_approval,
        "approval_flow_code": row.approval_flow_code,
        "conditions": row.conditions,
        "priority": row.priority,
        "status": row.status,
        "description": row.description,
    }


@policy_router.post("", summary="创建动作策略")
async def create_policy(payload: PolicyCreate, admin_id: int = require_superuser()):
    existing = await HarnessActionPolicy.get_or_none(code=payload.code)
    if existing is not None:
        return fail_response(msg="策略编码已存在", code=409, status_code=409)
    policy = await HarnessActionPolicy.create(**payload.model_dump())
    return success_response(data=_policy_dict(policy), msg="策略已创建")


@policy_router.get("", summary="动作策略列表")
async def list_policies(
    status_filter: str = Query("active", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    query = HarnessActionPolicy.all()
    if status_filter and status_filter != "all":
        query = query.filter(status=status_filter)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-priority", "code")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_policy_dict(r) for r in rows],
    })


@policy_router.get("/rules", summary="三档策略规则列表")
async def list_policy_rules(
    tier: int = Query(None, ge=1, le=3, description="档位：1/2/3"),
    effect: str = Query(None, description="allow/deny/ask"),
    admin_id: int = require_superuser(),
):
    items = await HarnessPolicyRuleService.list_rules(tier=tier, effect=effect)
    return success_response(data={
        "total": len(items),
        "items": items,
        "ruleset_version": approval_config()["ruleset_version"],
    })


@policy_router.post("/rules", summary="新增/更新三档策略规则（更新自动升版本）")
async def upsert_policy_rule(payload: PolicyRuleUpsert, admin_id: int = require_superuser()):
    data = await HarnessPolicyRuleService.upsert_rule(payload)
    return success_response(data=data, msg="规则已保存")


@policy_router.post("/evaluate", summary="动作安全评估（三档判定，未命中转人工）")
async def evaluate_action(
    payload: ActionEvaluate,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    verdict = await HarnessPolicyService.evaluate(payload.action, payload.context, payload.arguments)
    await HarnessAuditService.record(
        "action.evaluated",
        client_id=client.client_id,
        session_no=payload.session_no,
        run_no=payload.run_no,
        actor_type="client",
        actor_id=client.client_id,
        target_type="action",
        target_id=payload.action,
        risk_level=verdict.get("risk_level") or "high",
        decision=verdict.get("decision"),
        policy_code=verdict.get("policy_code"),
        call_id=payload.call_id,
        detail={
            "reason": verdict.get("reason"),
            "tier": verdict.get("tier"),
            "category": verdict.get("category"),
            "command_text": verdict.get("command"),
            "rule_version": verdict.get("rule_version"),
            "ruleset_version": verdict.get("ruleset_version"),
            "signals": verdict.get("signals"),
            "context": payload.context,
        },
    )
    return success_response(data=verdict, msg="评估完成")
