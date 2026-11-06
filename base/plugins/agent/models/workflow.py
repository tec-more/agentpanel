"""
Workflow models
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Workflow(BaseModel, TimestampMixin):
    verbose_name = "工作流"
    """Workflow model"""

    name = fields.CharField(max_length=100, description="Workflow name")
    description = fields.TextField(null=True, description="Workflow description")
    status = fields.CharField(max_length=20, default="draft", description="Status: draft/active/inactive")
    definition = fields.JSONField(description="Workflow definition")

    # ===== T1 双主体归属扩展（溯源 02-§4.3 / Q-C）=====
    # 多态归属：cus=客户用户 / usr=后台用户；放弃 DB 级 FK，服务层校验（C-15）
    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")
    # 可见性：private 私有 / public 公开只读 / template 模板（PRD §7.1）
    visibility = fields.CharField(max_length=20, default="private", description="可见性: private/public/template")
    # 当前发布版本指针：BigInt + 索引，不建 DB 级 FK（Q4），由服务层保证一致性
    current_version_id = fields.BigIntField(null=True, index=True, description="当前发布版本 ID（workflow_version.id）")
    # 图 Schema 版本：存量图为 v1，新图统一 v2（C-03）
    schema_version = fields.CharField(max_length=10, default="v1", description="图 Schema 版本: v1/v2")
    # 草稿乐观锁版本号（04-F1：PUT /draft 携带，不一致即 409）
    draft_version = fields.IntField(default=1, description="草稿乐观锁版本号")

    class Meta:
        table = "workflow"
        # 索引策略溯源 §03-4：(owner_type, owner_id, visibility) 我的列表 / (current_version_id) 版本反查
        indexes = [
            ("owner_type", "owner_id", "visibility"),
        ]
    
    def __str__(self):
        return self.name


class WorkflowNode(BaseModel, TimestampMixin):
    """Workflow node model"""
    
    workflow = fields.ForeignKeyField("models.Workflow", related_name="nodes", description="Associated workflow")
    name = fields.CharField(max_length=100, description="Node name")
    type = fields.CharField(max_length=50, description="Node type: agent/skill/llm/decision/fork/join/iteration/code/template/variable_aggregator/document_extractor/variable_assigner/parameter_extractor/http/list_operation")
    config = fields.JSONField(description="Node configuration")
    position = fields.JSONField(description="Node position in UI")
    
    class Meta:
        table = "workflow_node"
    
    def __str__(self):
        return f"{self.name} ({self.type})"


class WorkflowEdge(BaseModel, TimestampMixin):
    """Workflow edge model"""
    
    workflow = fields.ForeignKeyField("models.Workflow", related_name="edges", description="Associated workflow")
    source_node = fields.ForeignKeyField("models.WorkflowNode", related_name="outgoing_edges", description="Source node")
    target_node = fields.ForeignKeyField("models.WorkflowNode", related_name="incoming_edges", description="Target node")
    condition = fields.TextField(null=True, description="Edge condition")
    label = fields.CharField(max_length=100, null=True, description="Edge label")
    
    class Meta:
        table = "workflow_edge"
    
    def __str__(self):
        return f"{self.source_node.name} -> {self.target_node.name}"


class WorkflowExecution(BaseModel, TimestampMixin):
    """Workflow execution model（架构文档所称 execution 表）"""

    workflow = fields.ForeignKeyField("models.Workflow", related_name="executions", description="Associated workflow")
    status = fields.CharField(max_length=20, default="running", description="Status: running/success/failed")
    input_data = fields.JSONField(description="Input data")
    output_data = fields.JSONField(null=True, description="Output data")
    error_message = fields.TextField(null=True, description="Error message")
    started_at = fields.DatetimeField(auto_now_add=True, description="Start time")
    completed_at = fields.DatetimeField(null=True, description="Completion time")

    # ===== T1 双主体归属扩展（溯源 02-§4.3 / Q-C）=====
    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")
    # 执行绑定的发布版本快照（C-08：运行中禁止切换版本）；不建 DB 级 FK，服务层校验
    version_id = fields.BigIntField(null=True, description="绑定版本 ID（workflow_version.id）")
    # 执行类别（04-F2）：run=正式运行 / dry_run=试跑（不写长期记忆、可筛选）
    kind = fields.CharField(max_length=20, default="run", description="执行类别: run/dry_run")

    class Meta:
        table = "workflow_execution"
        # 索引策略溯源 §03-4：(owner_type, owner_id, created_at) 历史列表 /
        # (workflow_id, version_id) 版本实例 / (status, created_at) 运行中扫描
        indexes = [
            ("owner_type", "owner_id", "created_at"),
            ("workflow", "version_id"),
            ("status", "created_at"),
        ]
    
    def __str__(self):
        return f"Execution of {self.workflow.name} - {self.status}"
