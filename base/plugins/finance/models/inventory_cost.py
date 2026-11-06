from datetime import datetime
from enum import Enum
from tortoise import fields, models
from base.common.model import BaseModel, TimestampMixin


class CostMethod(str, Enum):
    FIFO = "fifo"
    LIFO = "lifo"
    WEIGHTED_AVERAGE = "weighted_average"
    SPECIFIC_IDENTIFICATION = "specific_identification"


class InventoryCost(BaseModel, TimestampMixin):
    product = fields.ForeignKeyField("models.Product", related_name="costs", on_delete=fields.SET_NULL, null=True, description="产品")
    product_code = fields.CharField(max_length=64, description="产品编码")
    product_name = fields.CharField(max_length=128, description="产品名称")
    batch_no = fields.CharField(max_length=64, null=True, description="批次号")
    quantity = fields.DecimalField(max_digits=18, decimal_places=4, description="数量")
    unit_cost = fields.DecimalField(max_digits=18, decimal_places=4, description="单位成本")
    total_cost = fields.DecimalField(max_digits=18, decimal_places=2, description="总成本")
    cost_method = fields.CharEnumField(CostMethod, max_length=32, default=CostMethod.WEIGHTED_AVERAGE, description="成本方法")
    period = fields.CharField(max_length=10, description="会计期间")
    source_type = fields.CharField(max_length=32, description="来源类型")
    source_id = fields.IntField(null=True, description="来源ID")
    
    class Meta:
        table = "finance_inventory_costs"


class CostTransfer(BaseModel, TimestampMixin):
    transfer_no = fields.CharField(max_length=64, unique=True, description="结转单号")
    period = fields.CharField(max_length=10, description="会计期间")
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="结转金额")
    status = fields.CharField(max_length=20, default="draft", description="状态")
    journal_entry = fields.ForeignKeyField("models.JournalEntry", related_name="cost_transfers", on_delete=fields.SET_NULL, null=True, description="关联凭证")
    created_by = fields.CharField(max_length=64, description="操作人")
    confirmed_by = fields.CharField(max_length=64, null=True, description="审核人")
    
    class Meta:
        table = "finance_cost_transfers"


class CostVariance(BaseModel, TimestampMixin):
    product = fields.ForeignKeyField("models.Product", related_name="variances", on_delete=fields.SET_NULL, null=True, description="产品")
    period = fields.CharField(max_length=10, description="会计期间")
    standard_cost = fields.DecimalField(max_digits=18, decimal_places=4, description="标准成本")
    actual_cost = fields.DecimalField(max_digits=18, decimal_places=4, description="实际成本")
    variance_amount = fields.DecimalField(max_digits=18, decimal_places=4, description="差异金额")
    variance_rate = fields.DecimalField(max_digits=10, decimal_places=4, description="差异率")
    variance_type = fields.CharField(max_length=32, description="差异类型")
    
    class Meta:
        table = "finance_cost_variances"