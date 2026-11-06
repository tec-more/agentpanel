from tortoise import fields
from tortoise.models import Model


class DialogFlow(Model):
    verbose_name = "对话流"
    """对话流模型"""
    id = fields.IntField(pk=True, description="对话流ID")
    name = fields.CharField(max_length=100, description="对话流名称")
    description = fields.TextField(null=True, description="对话流描述")
    
    # 对话流结构，JSON格式
    flow_data = fields.JSONField(default=dict, description="对话流结构")
    
    # 状态
    status = fields.CharField(max_length=20, default="draft", description="状态: draft, active, inactive")
    
    # 元数据
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    
    class Meta:
        table = "agent_dialog_flow"
        description = "对话流表"


class DialogFlowNode(Model):
    """对话流节点模型"""
    id = fields.IntField(pk=True, description="节点ID")
    dialog_flow_id = fields.IntField(description="所属对话流ID")
    node_type = fields.CharField(max_length=50, description="节点类型: start, end, input, output, llm, knowledge_retrieval, api, message, text, image, voice, question, condition")
    name = fields.CharField(max_length=100, description="节点名称")
    content = fields.JSONField(default=dict, description="节点内容")
    
    # 位置信息（用于前端可视化）
    position_x = fields.FloatField(default=0, description="节点X坐标")
    position_y = fields.FloatField(default=0, description="节点Y坐标")
    
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    
    class Meta:
        table = "agent_dialog_flow_node"
        description = "对话流节点表"


class DialogFlowEdge(Model):
    """对话流边模型"""
    id = fields.IntField(pk=True, description="边ID")
    dialog_flow_id = fields.IntField(description="所属对话流ID")
    source_node_id = fields.IntField(description="源节点ID")
    target_node_id = fields.IntField(description="目标节点ID")
    condition = fields.JSONField(null=True, description="条件")
    
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    
    class Meta:
        table = "agent_dialog_flow_edge"
        description = "对话流边表"


class DialogFlowExecution(Model):
    """对话流执行记录模型"""
    id = fields.IntField(pk=True, description="执行记录ID")
    dialog_flow_id = fields.IntField(description="对话流ID")
    user_id = fields.IntField(null=True, description="用户ID")
    
    # 执行状态
    status = fields.CharField(max_length=20, default="running", description="状态: running, completed, failed")
    
    # 输入和输出
    input_data = fields.JSONField(default=dict, description="输入数据")
    output_data = fields.JSONField(null=True, description="输出数据")
    
    # 执行路径
    execution_path = fields.JSONField(default=list, description="执行路径")
    
    # 错误信息
    error_message = fields.TextField(null=True, description="错误信息")
    
    # 时间信息
    started_at = fields.DatetimeField(auto_now_add=True, description="开始时间")
    completed_at = fields.DatetimeField(null=True, description="完成时间")
    
    class Meta:
        table = "agent_dialog_flow_execution"
        description = "对话流执行记录表"
