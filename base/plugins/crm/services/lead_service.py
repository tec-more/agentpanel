from typing import Optional, List, Tuple
from datetime import datetime
from loguru import logger
from tortoise.expressions import Q

from base.plugins.crm.models.lead import Lead, LeadStatus
from base.plugins.crm.schemas.lead_schema import LeadCreate, LeadUpdate, LeadListQuery
from base.plugins.crm.services.crm_data_filter import get_crm_data_filter
from base.common.events.event_bus import event_bus
class LeadService:
    model = "lead"

    @staticmethod
    async def create_lead(lead_data: LeadCreate, created_by: int) -> Lead:
        if lead_data.phone:
            exists = await Lead.filter(phone=lead_data.phone, source=lead_data.source).exists()
            if exists:
                raise ValueError("CRM_LEAD_DUPLICATE: 同来源下手机号已存在")
        if lead_data.email:
            exists = await Lead.filter(email=lead_data.email, source=lead_data.source).exists()
            if exists:
                raise ValueError("CRM_LEAD_DUPLICATE: 同来源下邮箱已存在")
        lead = await Lead.create(
            name=lead_data.name,
            phone=lead_data.phone,
            email=lead_data.email,
            company=lead_data.company,
            source=lead_data.source,
            description=lead_data.description,
            assigned_to=lead_data.assigned_to,
        )
        try:
            await event_bus.publish("crm.lead.created", lead_id=lead.id, name=lead.name, source=lead.source)
        except Exception as e:
            logger.error(f"发布线索创建事件失败: {e}")
        return lead

    @staticmethod
    async def get_lead_list(query_params: LeadListQuery, user_id: int) -> Tuple[List[Lead], int]:
        data_filter = await get_crm_data_filter(user_id)
        query = Lead.all()
        if data_filter:
            query = query.filter(**data_filter)
        if query_params.status:
            query = query.filter(status=query_params.status)
        if query_params.source:
            query = query.filter(source=query_params.source)
        if query_params.assigned_to is not None:
            query = query.filter(assigned_to=query_params.assigned_to)
        if query_params.keyword:
            query = query.filter(
                Q(name__icontains=query_params.keyword) | Q(company__icontains=query_params.keyword)
            )
        total = await query.count()
        offset = (query_params.page - 1) * query_params.page_size
        leads = await query.offset(offset).limit(query_params.page_size).order_by("-created_at")
        return leads, total

    @staticmethod
    async def get_lead_by_id(lead_id: int) -> Optional[Lead]:
        return await Lead.get_or_none(id=lead_id)

    @staticmethod
    async def update_lead(lead_id: int, lead_data: LeadUpdate) -> Optional[Lead]:
        lead = await Lead.get_or_none(id=lead_id)
        if not lead:
            return None
        if lead.status == LeadStatus.CONVERTED:
            update_data = lead_data.model_dump(exclude_unset=True)
            if set(update_data.keys()) - {"description"}:
                raise ValueError("CRM_LEAD_CONVERTED: 已转化的线索仅允许更新描述")
        update_data = lead_data.model_dump(exclude_unset=True)
        await lead.update_from_dict(update_data).save()
        return lead

    @staticmethod
    async def delete_lead(lead_id: int) -> bool:
        lead = await Lead.get_or_none(id=lead_id)
        if not lead:
            return False
        if lead.status == LeadStatus.CONVERTED:
            raise ValueError("CRM_LEAD_CONVERTED: 已转化的线索禁止删除")
        await lead.delete()
        return True

    @staticmethod
    async def convert_lead(lead_id: int, operated_by: int) -> Lead:
        lead = await Lead.get_or_none(id=lead_id)
        if not lead:
            raise ValueError("CRM_LEAD_NOT_FOUND: 线索不存在")
        if lead.status != LeadStatus.CONTACTED:
            raise ValueError("CRM_LEAD_STATUS_ERROR: 仅已联系状态的线索可转化")
        from base.plugins.customer.models.customer import Customer
        from base.common.security import get_password_hash
        try:
            customer = await Customer.filter(phone=lead.phone).first() if lead.phone else None
            if not customer and lead.email:
                customer = await Customer.filter(email=lead.email).first()
            if not customer:
                import time
                import secrets
                username = f"lead_{lead.phone or int(time.time())}"
                password = secrets.token_urlsafe(16)
                customer = await Customer.create(
                    username=username,
                    email=lead.email or f"{username}@crm.placeholder",
                    phone=lead.phone,
                    password=get_password_hash(password),
                    nickname=lead.name,
                )
            lead.status = LeadStatus.CONVERTED
            lead.customer_id = customer.id
            lead.converted_at = datetime.now()
            await lead.save()
            try:
                await event_bus.publish("crm.lead.converted", lead_id=lead.id, customer_id=customer.id)
            except Exception as e:
                logger.error(f"发布线索转化事件失败: {e}")
            return lead
        except Exception as e:
            logger.error(f"线索转化失败: {e}")
            raise ValueError(f"CRM_LEAD_CONVERT_FAILED: 线索转化失败 - {e}")

    @staticmethod
    async def assign_lead(lead_id: int, assigned_to: int) -> Optional[Lead]:
        lead = await Lead.get_or_none(id=lead_id)
        if not lead:
            return None
        lead.assigned_to = assigned_to
        await lead.save()
        return lead