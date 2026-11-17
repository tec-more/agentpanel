"""发布台账路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from base.common.authz import OwnerContext, require_owner
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.contentops.schemas.content_schema import (
    LedgerCreate, LedgerUpdate, EffectCreate, EffectCSVImport,
)
from base.plugins.contentops.services.ledger_service import LedgerService

ledger_router = APIRouter(prefix="/ledger", tags=["发布台账"])


@ledger_router.post("", summary="新建台账记录")
async def create_ledger(
    data: LedgerCreate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:ledger:edit"),
):
    return success_response(data=await LedgerService.create(data, owner))


@ledger_router.get("", summary="台账列表")
async def list_ledger(
    status: Optional[str] = None,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:ledger:view"),
):
    return success_response(data={"items": await LedgerService.get_list(status, owner)})


@ledger_router.put("/{ledger_id}", summary="更新发布状态")
async def update_ledger(
    ledger_id: int, data: LedgerUpdate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:ledger:edit"),
):
    try:
        return success_response(data=await LedgerService.update(ledger_id, data, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@ledger_router.post("/{ledger_id}/effect", summary="回填效果数据（手工）")
async def add_effect(
    ledger_id: int, data: EffectCreate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:ledger:edit"),
):
    try:
        return success_response(data=await LedgerService.add_effect(ledger_id, data, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@ledger_router.post("/{ledger_id}/effect/import", summary="CSV 导入效果数据")
async def import_effect(
    ledger_id: int, data: EffectCSVImport,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:ledger:edit"),
):
    try:
        return success_response(data=await LedgerService.import_effect_csv(ledger_id, data, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@ledger_router.get("/{ledger_id}/effect", summary="效果数据列表")
async def get_effect(
    ledger_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:ledger:view"),
):
    return success_response(data={"items": await LedgerService.get_effect(ledger_id, owner)})
