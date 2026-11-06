from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class IntegrationLog(BaseModel, TimestampMixin):
    verbose_name = "集成日志"
    event_name = fields.CharField(max_length=128, description="事件名称")
    source_type = fields.CharField(max_length=64, description="来源类型")
    source_id = fields.IntField(null=True, description="来源ID")
    source_no = fields.CharField(max_length=128, null=True, description="来源单据号")
    result = fields.CharField(max_length=20, description="处理结果: success/failed/skipped")
    payable_id = fields.IntField(null=True, description="关联应付单ID")
    receivable_id = fields.IntField(null=True, description="关联应收单ID")
    payment_id = fields.IntField(null=True, description="关联付款ID")
    receipt_id = fields.IntField(null=True, description="关联收款ID")
    journal_id = fields.IntField(null=True, description="关联凭证ID")
    inventory_cost_ids = fields.JSONField(null=True, description="关联库存成本ID列表")
    error_message = fields.TextField(null=True, description="错误信息")
    processing_time_ms = fields.IntField(default=0, description="处理耗时(毫秒)")

    class Meta:
        table = "finance_integration_logs"

    async def to_dict(self):
        return {
            "id": self.id,
            "event_name": self.event_name,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_no": self.source_no,
            "result": self.result,
            "payable_id": self.payable_id,
            "receivable_id": self.receivable_id,
            "payment_id": self.payment_id,
            "receipt_id": self.receipt_id,
            "journal_id": self.journal_id,
            "inventory_cost_ids": self.inventory_cost_ids,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }