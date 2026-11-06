from typing import List, Optional, Dict, Any
from base.plugins.audit.models.audit_log import AuditConfig
from base.plugins.audit.schemas.audit_log import AuditConfigCreate, AuditConfigUpdate
class AuditConfigService:
    model = "audit_config"
    """审计配置服务"""

    @staticmethod
    async def create_config(data: AuditConfigCreate) -> AuditConfig:
        """创建审计配置"""
        config = await AuditConfig.create(**data.model_dump(exclude_unset=True))
        return config

    @staticmethod
    async def get_config_by_id(config_id: int) -> Optional[AuditConfig]:
        """根据ID获取审计配置"""
        return await AuditConfig.get_or_none(id=config_id)

    @staticmethod
    async def get_config_by_module(module_name: str) -> Optional[AuditConfig]:
        """根据模块名获取审计配置"""
        return await AuditConfig.get_or_none(module_name=module_name)

    @staticmethod
    async def get_all_configs() -> List[AuditConfig]:
        """获取所有审计配置"""
        return await AuditConfig.all().order_by("module_name")

    @staticmethod
    async def update_config(config_id: int, data: AuditConfigUpdate) -> Optional[AuditConfig]:
        """更新审计配置"""
        config = await AuditConfig.get_or_none(id=config_id)
        if not config:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(config, key, value)
        await config.save()
        return config

    @staticmethod
    async def delete_config(config_id: int) -> bool:
        """删除审计配置"""
        config = await AuditConfig.get_or_none(id=config_id)
        if not config:
            return False
        await config.delete()
        return True

    @staticmethod
    async def is_operation_enabled(module_name: str, operation_type: str) -> bool:
        """检查某模块的某操作是否启用审计"""
        config = await AuditConfig.get_or_none(module_name=module_name)
        if not config or not config.enabled:
            return False

        operation_map = {
            "create": config.log_create,
            "update": config.log_update,
            "delete": config.log_delete,
            "query": config.log_query,
        }
        return operation_map.get(operation_type, True)

    @staticmethod
    async def get_sensitive_fields(module_name: str) -> List[str]:
        """获取某模块的敏感字段列表"""
        config = await AuditConfig.get_or_none(module_name=module_name)
        if not config or not config.sensitive_fields:
            return []
        return config.sensitive_fields
