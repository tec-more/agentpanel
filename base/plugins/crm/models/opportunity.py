from enum import Enum
from decimal import Decimal
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class OpportunityStatus(str, Enum):
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"
    STALLED = "stalled"


class Opportunity(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=200, description="商机名称")
    customer_id = fields.BigIntField(description="客户ID")
    contact_id = fields.BigIntField(null=True, description="联系人ID")
    stage = fields.CharField(max_length=50, description="商机阶段code")
    expected_amount = fields.DecimalField(max_digits=10, decimal_places=2, description="预期金额")
    actual_amount = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="成交金额")
    probability = fields.IntField(null=True, description="成交概率(%)")
    expected_close_date = fields.DateField(null=True, description="预计成交日期")
    status = fields.CharEnumField(OpportunityStatus, max_length=20, default=OpportunityStatus.ACTIVE, description="商机状态")
    lost_reason = fields.TextField(null=True, description="输单原因")
    assigned_to = fields.BigIntField(null=True, description="负责人ID")
    last_follow_up_time = fields.DatetimeField(null=True, description="最后跟进时间")
    won_at = fields.DatetimeField(null=True, description="赢单时间")
    lost_at = fields.DatetimeField(null=True, description="输单时间")
    product_id = fields.BigIntField(null=True, description="关联产品ID")
    order_id = fields.BigIntField(null=True, description="关联订单ID")

    class Meta:
        table = "crm_opportunity"
        table_description = "CRM商机表"

    def __str__(self):
        return f"Opportunity({self.name})"