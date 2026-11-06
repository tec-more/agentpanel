"""
审批流程定义模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ApprovalFlow(BaseModel, TimestampMixin):
    """审批流程定义"""
    name = fields.CharField(max_length=100, description="流程名称", index=True)
    code = fields.CharField(max_length=100, unique=True, description="流程编码", index=True)
    description = fields.TextField(null=True, description="流程描述")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    # 表单配置（JSON格式，定义审批表单字段）
    form_config = fields.JSONField(default=list, description="表单配置")
    # 流程配置（JSON格式，定义节点、连线、条件等）
    flow_config = fields.JSONField(default=dict, description="流程配置")
    # 业务类型标识（如：purchase_order、expense、leave 等）
    business_type = fields.CharField(max_length=50, null=True, description="业务类型", index=True)
    # 业务模型标识（按模型匹配审批的核心字段，如 purchase_order）
    model = fields.CharField(max_length=50, description="业务模型标识（按模型匹配审批）", index=True, null=True)
    # 执行动作（按模型匹配后的具体业务动作：create/update/delete；NULL 表示匹配全部动作）
    action = fields.CharField(max_length=50, description="执行动作(create/update/delete)，不填表示匹配全部动作", index=True, null=True)
    # 需要拦截的 HTTP 方法列表
    methods = fields.JSONField(default=["POST", "PUT", "DELETE"], description="拦截方法列表")
    # 优先级（数字越大优先级越高；同一 model+action 命中多条流程时取最高）
    priority = fields.IntField(default=0, description="优先级(数字越大优先级越高)", index=True)
    # 前端路由模式列表，全局审批组件按当前路由反查命中的流程
    route_patterns = fields.JSONField(default=list, description="前端路由模式列表，如 ['/panel/purchase/order', '/panel/purchase/order/:id']")
    # 是否为系统预设流程（预设流程不可删除）
    is_system = fields.BooleanField(default=False, description="是否系统预设")

    class Meta:
        table = "approval_flow"
        ordering = ["-created_at"]

    async def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "is_active": self.is_active,
            "form_config": self.form_config,
            "flow_config": self.flow_config,
            "business_type": self.business_type,
            "model": self.model,
            "action": self.action,
            "methods": self.methods,
            "priority": self.priority,
            "route_patterns": self.route_patterns,
            "is_system": self.is_system,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
