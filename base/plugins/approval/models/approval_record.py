"""
审批操作记录模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ApprovalRecord(BaseModel, TimestampMixin):
    """审批操作记录（审批流水日志）"""
    instance_id = fields.IntField(description="关联审批实例ID", index=True)
    task_id = fields.IntField(null=True, description="关联任务ID", index=True)
    node_id = fields.CharField(max_length=50, null=True, description="节点ID", index=True)
    # 操作人ID
    operator_id = fields.IntField(description="操作人ID", index=True)
    # 操作类型：submit(提交)/approve(通过)/reject(拒绝)/transfer(转审)/cancel(撤销)
    action = fields.CharField(max_length=20, description="操作类型", index=True)
    # 操作意见
    comment = fields.TextField(null=True, description="操作意见")
    # 操作后实例状态
    after_status = fields.CharField(max_length=20, null=True, description="操作后状态")

    class Meta:
        table = "approval_record"
        ordering = ["-created_at"]

    async def to_dict(self, include_operator: bool = False):
        """转换为字典"""
        data = {
            "id": self.id,
            "instance_id": self.instance_id,
            "task_id": self.task_id,
            "node_id": self.node_id,
            "operator_id": self.operator_id,
            "action": self.action,
            "comment": self.comment,
            "after_status": self.after_status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
        if include_operator:
            try:
                from base.core.users.models.users import User
                operator = await User.get_or_none(id=self.operator_id)
                if operator:
                    data["operator_name"] = operator.alias or operator.username
                else:
                    data["operator_name"] = None
            except Exception:
                data["operator_name"] = None
        return data
