"""
审批任务模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ApprovalTask(BaseModel, TimestampMixin):
    """审批任务（每个审批人在某个节点上的待办任务）"""
    instance_id = fields.IntField(description="关联审批实例ID", index=True)
    # 节点ID（对应流程配置中的节点标识）
    node_id = fields.CharField(max_length=50, description="节点ID", index=True)
    # 审批人ID
    approver_id = fields.IntField(description="审批人ID", index=True)
    # 任务状态：pending(待审批)/approved(已通过)/rejected(已拒绝)/transferred(已转审)/skipped(已跳过)
    status = fields.CharField(max_length=20, default="pending", description="任务状态", index=True)
    # 审批意见
    comment = fields.TextField(null=True, description="审批意见")
    # 审批时间
    approve_time = fields.DatetimeField(null=True, description="审批时间", index=True)
    # 转审目标人ID
    transfer_to = fields.IntField(null=True, description="转审目标人ID")

    class Meta:
        table = "approval_task"
        ordering = ["-created_at"]

    async def to_dict(self, include_approver: bool = False):
        """转换为字典"""
        data = {
            "id": self.id,
            "instance_id": self.instance_id,
            "node_id": self.node_id,
            "approver_id": self.approver_id,
            "status": self.status,
            "comment": self.comment,
            "approve_time": self.approve_time.strftime("%Y-%m-%d %H:%M:%S") if self.approve_time else None,
            "transfer_to": self.transfer_to,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_approver:
            try:
                from base.core.users.models.users import User
                approver = await User.get_or_none(id=self.approver_id)
                if approver:
                    data["approver_name"] = approver.alias or approver.username
                else:
                    data["approver_name"] = None
            except Exception:
                data["approver_name"] = None
        return data
