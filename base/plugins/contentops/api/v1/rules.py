"""规则库路由（合规规则 + 平台适配配置）。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from base.common.authz import OwnerContext, require_owner, require_action
from base.common.response import success_response, fail_response
from base.plugins.contentops.schemas.content_schema import RuleCreate, RuleUpdate
from base.plugins.contentops.services.rule_service import RuleService

rules_router = APIRouter(prefix="/rules", tags=["规则库"])


@rules_router.post("", summary="新建合规规则")
async def create_rule(
    data: RuleCreate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    return success_response(data=await RuleService.create_rule(data, owner))


@rules_router.get("", summary="规则列表")
async def list_rules(
    layer: Optional[str] = None,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:view"),
):
    return success_response(data={"items": await RuleService.list_rules(layer, owner)})


@rules_router.put("/{rule_id}", summary="编辑规则")
async def update_rule(
    rule_id: int, data: RuleUpdate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    try:
        return success_response(data=await RuleService.update_rule(rule_id, data, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@rules_router.delete("/{rule_id}", summary="删除规则")
async def delete_rule(
    rule_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    try:
        await RuleService.delete_rule(rule_id, owner)
        return success_response(msg="删除成功")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@rules_router.get("/platform/{platform}", summary="平台适配配置列表")
async def list_platform_rules(
    platform: str,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:view"),
):
    return success_response(data={"items": await RuleService.list_platform_rules(platform, owner)})


@rules_router.put("/platform/{platform}/{key}", summary="设置平台适配配置")
async def set_platform_rule(
    platform: str, key: str, value: dict,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    return success_response(data=await RuleService.set_platform_rule(platform, key, value, owner))
