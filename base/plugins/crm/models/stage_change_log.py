from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class StageChangeLog(BaseModel, TimestampMixin):
    opportunity_id = fields.BigIntField(description="商机ID")
    from_stage = fields.CharField(max_length=50, null=True, description="原阶段")
    to_stage = fields.CharField(max_length=50, description="新阶段")
    changed_by = fields.BigIntField(description="操作人ID")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "crm_stage_change_log"
        table_description = "CRM商机阶段变更日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"StageChangeLog(opp={self.opportunity_id}, {self.from_stage}->{self.to_stage})"