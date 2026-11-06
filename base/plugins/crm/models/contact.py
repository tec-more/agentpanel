from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Contact(BaseModel, TimestampMixin):
    customer_id = fields.BigIntField(description="客户ID")
    name = fields.CharField(max_length=100, description="联系人姓名")
    phone = fields.CharField(max_length=20, null=True, description="手机号")
    email = fields.CharField(max_length=100, null=True, description="邮箱")
    position = fields.CharField(max_length=100, null=True, description="职位")
    department = fields.CharField(max_length=100, null=True, description="部门")
    is_primary = fields.BooleanField(default=False, description="是否主联系人")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "crm_contact"
        table_description = "CRM联系人表"
        unique_together = (("customer_id", "phone"),)

    def __str__(self):
        return f"Contact({self.name})"