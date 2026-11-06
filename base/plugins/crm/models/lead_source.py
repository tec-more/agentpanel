from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class LeadSource(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="来源名称")
    code = fields.CharField(max_length=50, unique=True, description="来源编码")
    is_active = fields.BooleanField(default=True, description="是否启用")
    sort_order = fields.IntField(default=0, description="排序")

    class Meta:
        table = "crm_lead_source"
        table_description = "CRM线索来源配置表"
        ordering = ["sort_order"]

    def __str__(self):
        return f"LeadSource({self.name})"