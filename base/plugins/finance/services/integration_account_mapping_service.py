from typing import Optional, List, Dict, Any
try:
    from base.plugins.finance.models.integration_account_mapping import IntegrationAccountMapping
except ImportError:
    IntegrationAccountMapping = None


class IntegrationAccountMappingService:
    model = "integration_account_mapping"
    @staticmethod
    async def get_all_mappings(page: int = 1, page_size: int = 20, event_type: Optional[str] = None, is_active: Optional[bool] = None) -> List[IntegrationAccountMapping]:
        offset = (page - 1) * page_size
        query = IntegrationAccountMapping.all().order_by("event_type")
        if event_type:
            query = query.filter(event_type=event_type)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def get_mapping_count(event_type: Optional[str] = None, is_active: Optional[bool] = None) -> int:
        query = IntegrationAccountMapping.all()
        if event_type:
            query = query.filter(event_type=event_type)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        return await query.count()

    @staticmethod
    async def get_mapping_by_id(mapping_id: int) -> Optional[IntegrationAccountMapping]:
        return await IntegrationAccountMapping.get_or_none(id=mapping_id)

    @staticmethod
    async def get_mapping_by_event_type(event_type: str) -> Optional[IntegrationAccountMapping]:
        return await IntegrationAccountMapping.get_or_none(event_type=event_type, is_active=True)

    @staticmethod
    async def create_mapping(data: Dict[str, Any]) -> IntegrationAccountMapping:
        return await IntegrationAccountMapping.create(
            event_type=data["event_type"],
            debit_account_code=data["debit_account_code"],
            credit_account_code=data["credit_account_code"],
            is_active=data.get("is_active", True),
            description=data.get("description"),
        )

    @staticmethod
    async def update_mapping(mapping_id: int, data: Dict[str, Any]) -> Optional[IntegrationAccountMapping]:
        mapping = await IntegrationAccountMapping.get_or_none(id=mapping_id)
        if not mapping:
            return None
        update_fields = {}
        for field in ["event_type", "debit_account_code", "credit_account_code", "is_active", "description"]:
            if field in data:
                update_fields[field] = data[field]
        if update_fields:
            await IntegrationAccountMapping.filter(id=mapping_id).update(**update_fields)
        return await IntegrationAccountMapping.get(id=mapping_id)

    @staticmethod
    async def delete_mapping(mapping_id: int) -> bool:
        mapping = await IntegrationAccountMapping.get_or_none(id=mapping_id)
        if not mapping:
            return False
        await mapping.delete()
        return True

    @staticmethod
    async def toggle_mapping(mapping_id: int) -> Optional[IntegrationAccountMapping]:
        mapping = await IntegrationAccountMapping.get_or_none(id=mapping_id)
        if not mapping:
            return None
        await IntegrationAccountMapping.filter(id=mapping_id).update(is_active=not mapping.is_active)
        return await IntegrationAccountMapping.get(id=mapping_id)