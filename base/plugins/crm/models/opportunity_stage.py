from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class OpportunityStage(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="阶段名称")
    code = fields.CharField(max_length=50, unique=True, description="阶段编码")
    sort_order = fields.IntField(default=0, description="排序")
    probability = fields.IntField(null=True, description="默认成交概率(%)")
    is_won_stage = fields.BooleanField(default=False, description="是否赢单阶段")
    is_lost_stage = fields.BooleanField(default=False, description="是否输单阶段")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "crm_opportunity_stage"
        table_description = "CRM商机阶段配置表"
        ordering = ["sort_order"]

    def __str__(self):
        return f"OpportunityStage({self.name})"