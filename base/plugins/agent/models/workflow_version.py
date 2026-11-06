"""
WorkflowVersion model - 工作流发布版本（不可变快照）

溯源：docs/arch/02-系统上下文与领域模型.md §4.2
- 发布生成不可变版本快照，执行实例绑定版本（C-08 编辑态/运行态分离）
- workflow.current_version_id 不建 DB 级 FK（Q4），本表 workflow_id 建单向 FK
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class WorkflowVersion(BaseModel, TimestampMixin):
    verbose_name = "工作流版本"
    """Workflow version model (immutable published snapshot)"""

    # 单向 FK 指向 workflow（Q4：反向 current_version_id 不建 FK）
    workflow = fields.ForeignKeyField(
        "models.Workflow",
        related_name="versions",
        on_delete=fields.CASCADE,
        description="所属工作流",
    )
    version_no = fields.IntField(description="版本号（同一工作流内递增）")
    # Schema v2 图 JSON（nodes/edges/variables/settings），从不按内容检索（§03-3.1）
    graph_json = fields.JSONField(description="工作流图快照（Schema v2）")
    schema_version = fields.CharField(max_length=10, default="v2", description="图 Schema 版本: v1/v2")
    # 发布时资源快照 ID 清单（04-F1）：{model: [...], kb: [...], tool: [...], agent: [...]}
    resource_refs = fields.JSONField(null=True, description="发布时引用的资源 ID 快照清单")
    # 发布说明（T15 BUG-T15-002 补字段；BUG-T15-004 openGauss 空串即 NULL，改 nullable + 序列化层 or "" 兜底）
    description = fields.TextField(null=True, description="发布说明（可选，用户填写）")

    # 发布主体（多态归属，cus=客户 / usr=后台用户）
    published_by_type = fields.CharField(max_length=3, description="发布主体类型: cus/usr")
    published_by_id = fields.BigIntField(description="发布主体 ID")
    published_at = fields.DatetimeField(null=True, description="发布时间")

    status = fields.CharField(
        max_length=20, default="published", description="状态: published/archived"
    )

    class Meta:
        table = "workflow_version"
        # 索引策略溯源 §03-4：UNIQUE(workflow_id, version_no) 版本定位
        unique_together = (("workflow", "version_no"),)

    def __str__(self):
        return f"WorkflowVersion(workflow_id={self.workflow_id}, v{self.version_no})"
