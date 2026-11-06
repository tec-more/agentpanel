from typing import Optional, List, Dict, Any
try:
    from base.plugins.finance.models.integration_config import IntegrationConfig
except ImportError:
    IntegrationConfig = None


class IntegrationConfigService:
    model = "integration_config"
    @staticmethod
    async def get_all_configs(page: int = 1, page_size: int = 20) -> List[IntegrationConfig]:
        offset = (page - 1) * page_size
        return await IntegrationConfig.all().order_by("config_key").offset(offset).limit(page_size)

    @staticmethod
    async def get_config_count() -> int:
        return await IntegrationConfig.all().count()

    @staticmethod
    async def get_config_by_id(config_id: int) -> Optional[IntegrationConfig]:
        return await IntegrationConfig.get_or_none(id=config_id)

    @staticmethod
    async def get_config_by_key(config_key: str) -> Optional[str]:
        config = await IntegrationConfig.get_or_none(config_key=config_key)
        return config.config_value if config else None

    @staticmethod
    async def create_config(data: Dict[str, Any]) -> IntegrationConfig:
        return await IntegrationConfig.create(
            config_key=data["config_key"],
            config_value=data["config_value"],
            description=data.get("description"),
        )

    @staticmethod
    async def update_config(config_id: int, data: Dict[str, Any]) -> Optional[IntegrationConfig]:
        config = await IntegrationConfig.get_or_none(id=config_id)
        if not config:
            return None
        update_fields = {}
        for field in ["config_key", "config_value", "description"]:
            if field in data:
                update_fields[field] = data[field]
        if update_fields:
            await IntegrationConfig.filter(id=config_id).update(**update_fields)
        return await IntegrationConfig.get(id=config_id)

    @staticmethod
    async def delete_config(config_id: int) -> bool:
        config = await IntegrationConfig.get_or_none(id=config_id)
        if not config:
            return False
        await config.delete()
        return True

    @staticmethod
    async def set_config_value(config_key: str, config_value: str, description: Optional[str] = None) -> IntegrationConfig:
        config = await IntegrationConfig.get_or_none(config_key=config_key)
        if config:
            await IntegrationConfig.filter(id=config.id).update(config_value=config_value)
            if description is not None:
                await IntegrationConfig.filter(id=config.id).update(description=description)
            return await IntegrationConfig.get(id=config.id)
        else:
            return await IntegrationConfig.create(
                config_key=config_key,
                config_value=config_value,
                description=description,
            )