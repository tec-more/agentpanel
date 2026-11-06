from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class IntegrationAccountMapping(BaseModel, TimestampMixin):
    verbose_name = "集成科目映射"
    event_type = fields.CharField(max_length=64, unique=True, description="事件类型")
    debit_account_code = fields.CharField(max_length=64, description="借方科目编码")
    credit_account_code = fields.CharField(max_length=64, description="贷方科目编码")
    is_active = fields.BooleanField(default=True, description="是否启用")
    description = fields.TextField(null=True, description="描述")

    class Meta:
        table = "finance_integration_account_mappings"

    async def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "debit_account_code": self.debit_account_code,
            "credit_account_code": self.credit_account_code,
            "is_active": self.is_active,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }