"""
审批实例模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ApprovalInstance(BaseModel, TimestampMixin):
    """审批实例（一次审批请求的实例）"""
    flow_id = fields.IntField(description="关联流程ID", index=True)
    # 业务类型（冗余存储，便于查询）
    business_type = fields.CharField(max_length=50, null=True, description="业务类型", index=True)
    # 业务对象ID（关联的采购订单ID、报销单ID等）
    business_id = fields.IntField(null=True, description="业务对象ID", index=True)
    # 业务数据快照（JSON格式）
    business_data = fields.JSONField(null=True, description="业务数据快照")
    # 业务动作（供审批通过后的执行器回调）：create / update / delete
    action = fields.CharField(max_length=20, null=True, description="业务动作（create/update/delete）", index=True)
    # 审批标题
    title = fields.CharField(max_length=255, description="审批标题", index=True)
    # 申请人ID
    applicant_id = fields.IntField(description="申请人ID", index=True)
    # 审批状态：pending(审批中)/approved(已通过)/rejected(已拒绝)/cancelled(已撤销)
    status = fields.CharField(max_length=20, default="pending", description="审批状态", index=True)
    # 当前节点ID
    current_node = fields.CharField(max_length=50, null=True, description="当前节点ID")
    # 表单数据（JSON格式，申请人填写的审批表单）
    form_data = fields.JSONField(null=True, description="表单数据")
    # 最终结果说明
    result = fields.TextField(null=True, description="审批结果说明")
    # 审批完成时间
    complete_time = fields.DatetimeField(null=True, description="完成时间", index=True)

    class Meta:
        table = "approval_instance"
        ordering = ["-created_at"]

    async def to_dict(self, include_flow: bool = False):
        """转换为字典"""
        data = {
            "id": self.id,
            "flow_id": self.flow_id,
            "business_type": self.business_type,
            "business_id": self.business_id,
            "business_data": self.business_data,
            "action": self.action,
            "title": self.title,
            "applicant_id": self.applicant_id,
            "status": self.status,
            "current_node": self.current_node,
            "form_data": self.form_data,
            "result": self.result,
            "complete_time": self.complete_time.strftime("%Y-%m-%d %H:%M:%S") if self.complete_time else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_flow:
            from base.plugins.approval.models.approval_flow import ApprovalFlow
            flow = await ApprovalFlow.get_or_none(id=self.flow_id)
            data["flow"] = await flow.to_dict() if flow else None
        return data
