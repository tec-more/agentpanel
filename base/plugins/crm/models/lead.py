from enum import Enum
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    INVALID = "invalid"


class Lead(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, description="线索姓名")
    phone = fields.CharField(max_length=20, null=True, description="手机号")
    email = fields.CharField(max_length=100, null=True, description="邮箱")
    company = fields.CharField(max_length=200, null=True, description="公司名称")
    source = fields.CharField(max_length=50, null=True, description="线索来源")
    status = fields.CharEnumField(LeadStatus, max_length=20, default=LeadStatus.NEW, description="线索状态")
    assigned_to = fields.BigIntField(null=True, description="负责人ID")
    customer_id = fields.BigIntField(null=True, description="转化后的客户ID")
    description = fields.TextField(null=True, description="描述")
    last_follow_up_time = fields.DatetimeField(null=True, description="最后跟进时间")
    converted_at = fields.DatetimeField(null=True, description="转化时间")

    class Meta:
        table = "crm_lead"
        table_description = "CRM线索表"

    def __str__(self):
        return f"Lead({self.name})"