from typing import Optional, List, Tuple, Dict
from datetime import datetime
from decimal import Decimal
from loguru import logger
from tortoise.expressions import Q

from base.plugins.crm.models.opportunity import Opportunity, OpportunityStatus
from base.plugins.crm.models.opportunity_stage import OpportunityStage
from base.plugins.crm.models.stage_change_log import StageChangeLog
from base.plugins.crm.schemas.opportunity_schema import (
    OpportunityCreate, OpportunityUpdate, OpportunityListQuery,
    OpportunityAdvanceRequest, OpportunityWinRequest, OpportunityLoseRequest,
)
from base.plugins.crm.services.crm_data_filter import get_crm_data_filter
from base.common.events.event_bus import event_bus
class OpportunityService:
    model = "opportunity"

    @staticmethod
    async def create_opportunity(opp_data: OpportunityCreate, created_by: int) -> Opportunity:
        stage = await OpportunityStage.get_or_none(code=opp_data.stage, is_active=True)
        if not stage:
            raise ValueError("CRM_STAGE_NOT_FOUND: 商机阶段不存在或未启用")
        from base.plugins.customer.models.customer import Customer
        customer = await Customer.get_or_none(id=opp_data.customer_id)
        if not customer:
            raise ValueError("CRM_CUSTOMER_NOT_FOUND: 客户不存在")
        probability = opp_data.probability if opp_data.probability is not None else stage.probability
        opp = await Opportunity.create(
            name=opp_data.name,
            customer_id=opp_data.customer_id,
            contact_id=opp_data.contact_id,
            stage=opp_data.stage,
            expected_amount=opp_data.expected_amount,
            probability=probability,
            expected_close_date=opp_data.expected_close_date,
            assigned_to=opp_data.assigned_to,
            product_id=opp_data.product_id,
        )
        try:
            await event_bus.publish(
                "crm.opportunity.created",
                opportunity_id=opp.id, customer_id=opp.customer_id, stage=opp.stage,
            )
        except Exception as e:
            logger.error(f"发布商机创建事件失败: {e}")
        return opp

    @staticmethod
    async def get_opportunity_list(query_params: OpportunityListQuery, user_id: int) -> Tuple[List[Opportunity], int]:
        data_filter = await get_crm_data_filter(user_id)
        query = Opportunity.all()
        if data_filter:
            query = query.filter(**data_filter)
        if query_params.status:
            query = query.filter(status=query_params.status)
        if query_params.stage:
            query = query.filter(stage=query_params.stage)
        if query_params.assigned_to is not None:
            query = query.filter(assigned_to=query_params.assigned_to)
        if query_params.customer_id is not None:
            query = query.filter(customer_id=query_params.customer_id)
        total = await query.count()
        offset = (query_params.page - 1) * query_params.page_size
        opps = await query.offset(offset).limit(query_params.page_size).order_by("-created_at")
        return opps, total

    @staticmethod
    async def get_opportunity_by_id(opp_id: int) -> Optional[Dict]:
        opp = await Opportunity.get_or_none(id=opp_id)
        if not opp:
            return None
        change_logs = await StageChangeLog.filter(opportunity_id=opp_id).order_by("-created_at")
        opp_dict = await opp.to_dict()
        opp_dict["stage_change_logs"] = [await log.to_dict() for log in change_logs]
        return opp_dict

    @staticmethod
    async def update_opportunity(opp_id: int, opp_data: OpportunityUpdate) -> Optional[Opportunity]:
        opp = await Opportunity.get_or_none(id=opp_id)
        if not opp:
            return None
        if opp.status in (OpportunityStatus.WON, OpportunityStatus.LOST):
            update_data = opp_data.model_dump(exclude_unset=True)
            if set(update_data.keys()) - {"expected_amount"}:
                raise ValueError("CRM_OPPORTUNITY_CLOSED: 已结束的商机仅允许更新部分字段")
        update_data = opp_data.model_dump(exclude_unset=True)
        await opp.update_from_dict(update_data).save()
        return opp

    @staticmethod
    async def delete_opportunity(opp_id: int) -> bool:
        opp = await Opportunity.get_or_none(id=opp_id)
        if not opp:
            return False
        if opp.status in (OpportunityStatus.WON, OpportunityStatus.LOST):
            raise ValueError("CRM_OPPORTUNITY_CLOSED: 已赢单/已输单的商机禁止删除")
        await opp.delete()
        return True

    @staticmethod
    async def advance_stage(opp_id: int, advance_data: OpportunityAdvanceRequest, operated_by: int) -> Optional[Opportunity]:
        opp = await Opportunity.get_or_none(id=opp_id)
        if not opp:
            return None
        if opp.status not in (OpportunityStatus.ACTIVE, OpportunityStatus.STALLED):
            raise ValueError("CRM_OPPORTUNITY_STATUS_ERROR: 仅进行中或停滞的商机可推进阶段")
        current_stage = await OpportunityStage.get_or_none(code=opp.stage)
        target_stage = await OpportunityStage.get_or_none(code=advance_data.to_stage, is_active=True)
        if not target_stage:
            raise ValueError("CRM_STAGE_NOT_FOUND: 目标阶段不存在或未启用")
        if current_stage and target_stage.sort_order <= current_stage.sort_order:
            raise ValueError("CRM_STAGE_ROLLBACK: 禁止回退到排序更低的阶段")
        from_stage = opp.stage
        opp.stage = advance_data.to_stage
        if opp.status == OpportunityStatus.STALLED:
            opp.status = OpportunityStatus.ACTIVE
        if target_stage.probability is not None:
            opp.probability = target_stage.probability
        await opp.save()
        await StageChangeLog.create(
            opportunity_id=opp.id,
            from_stage=from_stage,
            to_stage=advance_data.to_stage,
            changed_by=operated_by,
            remark=advance_data.remark,
        )
        try:
            await event_bus.publish(
                "crm.opportunity.stage_changed",
                opportunity_id=opp.id, from_stage=from_stage, to_stage=advance_data.to_stage,
            )
        except Exception as e:
            logger.error(f"发布商机阶段变更事件失败: {e}")
        return opp

    @staticmethod
    async def mark_won(opp_id: int, win_data: OpportunityWinRequest, operated_by: int) -> Optional[Opportunity]:
        opp = await Opportunity.get_or_none(id=opp_id)
        if not opp:
            return None
        if opp.status not in (OpportunityStatus.ACTIVE, OpportunityStatus.STALLED):
            raise ValueError("CRM_OPPORTUNITY_STATUS_ERROR: 仅进行中或停滞的商机可标记赢单")
        from_stage = opp.stage
        opp.status = OpportunityStatus.WON
        opp.actual_amount = win_data.actual_amount
        opp.won_at = datetime.now()
        await opp.save()
        await StageChangeLog.create(
            opportunity_id=opp.id,
            from_stage=from_stage,
            to_stage="won",
            changed_by=operated_by,
            remark="标记赢单",
        )
        order_id = None
        if win_data.create_order:
            try:
                order_id = await OpportunityService._create_order_from_opportunity(opp)
                if order_id:
                    opp.order_id = order_id
                    await opp.save()
            except Exception as e:
                logger.error(f"商机赢单创建订单失败: {e}")
        try:
            await event_bus.publish(
                "crm.opportunity.won",
                opportunity_id=opp.id, actual_amount=float(win_data.actual_amount), order_id=order_id,
            )
        except Exception as e:
            logger.error(f"发布商机赢单事件失败: {e}")
        return opp

    @staticmethod
    async def mark_lost(opp_id: int, lose_data: OpportunityLoseRequest, operated_by: int) -> Optional[Opportunity]:
        opp = await Opportunity.get_or_none(id=opp_id)
        if not opp:
            return None
        if opp.status not in (OpportunityStatus.ACTIVE, OpportunityStatus.STALLED):
            raise ValueError("CRM_OPPORTUNITY_STATUS_ERROR: 仅进行中或停滞的商机可标记输单")
        from_stage = opp.stage
        opp.status = OpportunityStatus.LOST
        opp.lost_reason = lose_data.lost_reason
        opp.lost_at = datetime.now()
        await opp.save()
        await StageChangeLog.create(
            opportunity_id=opp.id,
            from_stage=from_stage,
            to_stage="lost",
            changed_by=operated_by,
            remark=lose_data.lost_reason,
        )
        try:
            await event_bus.publish(
                "crm.opportunity.lost",
                opportunity_id=opp.id, lost_reason=lose_data.lost_reason,
            )
        except Exception as e:
            logger.error(f"发布商机输单事件失败: {e}")
        return opp

    @staticmethod
    async def get_kanban_view(user_id: int) -> List[dict]:
        data_filter = await get_crm_data_filter(user_id)
        stages = await OpportunityStage.filter(is_active=True).order_by("sort_order")
        result = []
        for stage in stages:
            query = Opportunity.filter(stage=stage.code, status=OpportunityStatus.ACTIVE)
            if data_filter:
                query = query.filter(**data_filter)
            opps = await query.order_by("-created_at")
            result.append({
                "stage_code": stage.code,
                "stage_name": stage.name,
                "opportunities": [await opp.to_dict() for opp in opps],
            })
        return result

    @staticmethod
    async def _create_order_from_opportunity(opp: Opportunity) -> Optional[int]:
        try:
            from base.plugins.sales.services.order_service import OrderService
            items = [{
                "product_id": opp.product_id,
                "product_name": opp.name,
                "product_type": "item",
                "quantity": 1,
                "unit_price": float(opp.actual_amount or opp.expected_amount),
                "extra_info": {},
            }]
            order = await OrderService.create_order(
                customer_id=opp.customer_id,
                items=items,
                payment_method="balance",
                client_ip="",
                device_info={},
                remark=f"商机赢单自动创建 - {opp.name}",
            )
            return order.id
        except Exception as e:
            logger.error(f"从商机创建订单失败: {e}")
            return None