from enum import Enum
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ActivityType(str, Enum):
    CALL = "call"
    MEETING = "meeting"
    EMAIL = "email"
    VISIT = "visit"
    OTHER = "other"


class Activity(BaseModel, TimestampMixin):
    type = fields.CharEnumField(ActivityType, max_length=20, description="活动类型")
    subject = fields.CharField(max_length=200, description="主题")
    content = fields.TextField(null=True, description="内容")
    activity_time = fields.DatetimeField(description="活动时间")
    lead_id = fields.BigIntField(null=True, description="关联线索ID")
    opportunity_id = fields.BigIntField(null=True, description="关联商机ID")
    contact_id = fields.BigIntField(null=True, description="关联联系人ID")
    created_by = fields.BigIntField(description="创建人ID")

    class Meta:
        table = "crm_activity"
        table_description = "CRM活动记录表"
        ordering = ["-activity_time"]

    def __str__(self):
        return f"Activity({self.subject})"