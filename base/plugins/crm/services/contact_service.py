from typing import Optional, List, Tuple
from loguru import logger
from tortoise.expressions import Q
from tortoise.transactions import atomic

from base.plugins.crm.models.contact import Contact
from base.plugins.crm.models.opportunity import Opportunity, OpportunityStatus
from base.plugins.crm.schemas.contact_schema import ContactCreate, ContactUpdate, ContactListQuery
class ContactService:
    model = "contact"

    @staticmethod
    async def create_contact(contact_data: ContactCreate) -> Contact:
        from base.plugins.customer.models.customer import Customer
        customer = await Customer.get_or_none(id=contact_data.customer_id)
        if not customer:
            raise ValueError("CRM_CUSTOMER_NOT_FOUND: 客户不存在")
        if contact_data.phone:
            exists = await Contact.filter(customer_id=contact_data.customer_id, phone=contact_data.phone).exists()
            if exists:
                raise ValueError("CRM_CONTACT_DUPLICATE: 同一客户下手机号已存在")
        contact = await Contact.create(
            customer_id=contact_data.customer_id,
            name=contact_data.name,
            phone=contact_data.phone,
            email=contact_data.email,
            position=contact_data.position,
            department=contact_data.department,
            is_primary=contact_data.is_primary,
            remark=contact_data.remark,
        )
        if contact.is_primary:
            await ContactService._clear_other_primary(contact.id, contact.customer_id)
        return contact

    @staticmethod
    async def get_contact_list(query_params: ContactListQuery, user_id: int) -> Tuple[List[Contact], int]:
        query = Contact.all()
        if query_params.customer_id is not None:
            query = query.filter(customer_id=query_params.customer_id)
        if query_params.keyword:
            query = query.filter(
                Q(name__icontains=query_params.keyword) | Q(phone__icontains=query_params.keyword)
            )
        total = await query.count()
        offset = (query_params.page - 1) * query_params.page_size
        contacts = await query.offset(offset).limit(query_params.page_size).order_by("-created_at")
        return contacts, total

    @staticmethod
    async def update_contact(contact_id: int, contact_data: ContactUpdate) -> Optional[Contact]:
        contact = await Contact.get_or_none(id=contact_id)
        if not contact:
            return None
        update_data = contact_data.model_dump(exclude_unset=True)
        await contact.update_from_dict(update_data).save()
        if contact_data.is_primary is True:
            await ContactService._clear_other_primary(contact.id, contact.customer_id)
        return contact

    @staticmethod
    async def delete_contact(contact_id: int) -> bool:
        contact = await Contact.get_or_none(id=contact_id)
        if not contact:
            return False
        has_active_opp = await Opportunity.filter(
            contact_id=contact_id, status=OpportunityStatus.ACTIVE
        ).exists()
        if has_active_opp:
            raise ValueError("CRM_CONTACT_IN_USE: 联系人有关联进行中商机，无法删除")
        await contact.delete()
        return True

    @staticmethod
    async def set_primary(contact_id: int) -> Optional[Contact]:
        contact = await Contact.get_or_none(id=contact_id)
        if not contact:
            return None
        await Contact.filter(customer_id=contact.customer_id, is_primary=True).exclude(id=contact.id).update(is_primary=False)
        contact.is_primary = True
        await contact.save()
        return contact

    @staticmethod
    async def _clear_other_primary(contact_id: int, customer_id: int):
        await Contact.filter(customer_id=customer_id, is_primary=True).exclude(id=contact_id).update(is_primary=False)