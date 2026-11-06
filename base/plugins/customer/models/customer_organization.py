"""
CustomerOrganization / CustomerOrganizationMember models - 客户组织与成员（Q-H）

溯源：docs/arch/02-系统上下文与领域模型.md §4.2；01-需求与约束.md C-23
- 仅客户域；用途限于 HITL 审批人范围解析与协作可见性
- 边界禁区：不引入组织级配额、不复用后台 Department（C-23）
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class CustomerOrganization(BaseModel, TimestampMixin):
    verbose_name = "客户组织"
    """Customer organization model (customer domain only, Q-H)"""

    name = fields.CharField(max_length=100, description="组织名称")
    owner_customer = fields.ForeignKeyField(
        "models.Customer",
        related_name="owned_organizations",
        on_delete=fields.CASCADE,
        description="组织所有者（客户）",
    )
    status = fields.CharField(max_length=20, default="active", description="状态: active/disabled")

    class Meta:
        table = "customer_organization"

    def __str__(self):
        return self.name


class CustomerOrganizationMember(BaseModel, TimestampMixin):
    verbose_name = "客户组织成员"
    """Customer organization member (HITL 审批人范围解析依据)"""

    org = fields.ForeignKeyField(
        "models.CustomerOrganization",
        related_name="members",
        on_delete=fields.CASCADE,
        description="所属组织",
    )
    customer = fields.ForeignKeyField(
        "models.Customer",
        related_name="organization_memberships",
        on_delete=fields.CASCADE,
        description="成员客户",
    )
    role = fields.CharField(max_length=20, default="member", description="角色: owner/admin/member")
    status = fields.CharField(max_length=20, default="active", description="状态: active/removed")

    class Meta:
        table = "customer_organization_member"
        # 索引策略溯源 §03-4：(customer_id, status) 成员解析 / (org_id, status) 组织成员列表
        indexes = [
            ("customer", "status"),
            ("org", "status"),
        ]
        # 同一客户在同一组织内仅一条成员记录
        unique_together = (("org", "customer"),)

    def __str__(self):
        return f"OrgMember(org_id={self.org_id}, customer_id={self.customer_id}, role={self.role})"
