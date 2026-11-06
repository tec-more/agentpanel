"""
ResourceGrant model - M8 资源授权核心（Q1 决策：放 base/common/authz）

溯源：docs/arch/02-系统上下文与领域模型.md §4.2；PRD §7.2
- (owner_type, owner_id) × (resource_type, resource_id) → allow
- 默认策略：模型仅基础可用、工具/子 Agent 默认关闭、公共知识库需显式授权（PRD §7.2）
- resource_id 用字符串以兼容数值型资源 ID 与 node_type 等编码型资源标识
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ResourceGrant(BaseModel, TimestampMixin):
    verbose_name = "资源授权"
    """Resource grant: subject × resource → allow"""

    owner_type = fields.CharField(max_length=3, description="被授权主体类型: cus/usr")
    owner_id = fields.BigIntField(description="被授权主体 ID")

    # 资源类型：model/kb/tool/agent/node_type（PRD §7.2 授权粒度）
    resource_type = fields.CharField(max_length=20, description="资源类型: model/kb/tool/agent/node_type")
    # 资源标识：数值 ID 的字符串形式，或 node_type 等编码
    resource_id = fields.CharField(max_length=64, description="资源标识（ID 或类型编码）")

    effect = fields.CharField(max_length=10, default="allow", description="效果: allow（预留 deny）")
    # 授权来源标注：admin / migration:dept_to_grant 等（Q3 存量迁移标注迁移来源）
    granted_by = fields.CharField(max_length=64, default="admin", description="授权来源/操作人标注")
    expires_at = fields.DatetimeField(null=True, description="过期时间（空=永久）")

    class Meta:
        table = "resource_grant"
        # 索引策略溯源 §03-4：UNIQUE 四元组授权判定 / (resource_type, resource_id) 资源反查
        unique_together = (("owner_type", "owner_id", "resource_type", "resource_id"),)
        indexes = [
            ("resource_type", "resource_id"),
        ]

    def __str__(self):
        return f"ResourceGrant({self.owner_type}:{self.owner_id} -> {self.resource_type}:{self.resource_id})"
