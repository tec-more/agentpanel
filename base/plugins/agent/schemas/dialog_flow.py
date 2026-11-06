from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# 对话流基础模型
class DialogFlowBase(BaseModel):
    name: str = Field(..., description="对话流名称")
    description: Optional[str] = Field(None, description="对话流描述")
    agent_id: Optional[int] = Field(None, description="关联的智能体ID")
    flow_data: Dict[str, Any] = Field(default_factory=dict, description="对话流结构")
    status: str = Field(default="draft", description="状态: draft, active, inactive")


# 创建对话流模型
class DialogFlowCreate(DialogFlowBase):
    pass


# 更新对话流模型
class DialogFlowUpdate(BaseModel):
    name: Optional[str] = Field(None, description="对话流名称")
    description: Optional[str] = Field(None, description="对话流描述")
    flow_data: Optional[Dict[str, Any]] = Field(None, description="对话流结构")
    status: Optional[str] = Field(None, description="状态: draft, active, inactive")


# 对话流响应模型
class DialogFlowResponse(DialogFlowBase):
    id: int = Field(..., description="对话流ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 对话流节点基础模型
class DialogFlowNodeBase(BaseModel):
    dialog_flow_id: int = Field(..., description="所属对话流ID")
    node_type: str = Field(..., description="节点类型: start, question, condition, action, end")
    name: str = Field(..., description="节点名称")
    content: Dict[str, Any] = Field(default_factory=dict, description="节点内容")
    position_x: float = Field(default=0, description="节点X坐标")
    position_y: float = Field(default=0, description="节点Y坐标")


# 创建对话流节点模型
class DialogFlowNodeCreate(DialogFlowNodeBase):
    pass


# 更新对话流节点模型
class DialogFlowNodeUpdate(BaseModel):
    node_type: Optional[str] = Field(None, description="节点类型: start, question, condition, action, end")
    name: Optional[str] = Field(None, description="节点名称")
    content: Optional[Dict[str, Any]] = Field(None, description="节点内容")
    position_x: Optional[float] = Field(None, description="节点X坐标")
    position_y: Optional[float] = Field(None, description="节点Y坐标")


# 对话流节点响应模型
class DialogFlowNodeResponse(DialogFlowNodeBase):
    id: int = Field(..., description="节点ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 对话流边基础模型
class DialogFlowEdgeBase(BaseModel):
    dialog_flow_id: int = Field(..., description="所属对话流ID")
    source_node_id: int = Field(..., description="源节点ID")
    target_node_id: int = Field(..., description="目标节点ID")
    condition: Optional[Dict[str, Any]] = Field(None, description="条件")


# 创建对话流边模型
class DialogFlowEdgeCreate(DialogFlowEdgeBase):
    pass


# 更新对话流边模型
class DialogFlowEdgeUpdate(BaseModel):
    source_node_id: Optional[int] = Field(None, description="源节点ID")
    target_node_id: Optional[int] = Field(None, description="目标节点ID")
    condition: Optional[Dict[str, Any]] = Field(None, description="条件")


# 对话流边响应模型
class DialogFlowEdgeResponse(DialogFlowEdgeBase):
    id: int = Field(..., description="边ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


# 对话流执行基础模型
class DialogFlowExecutionBase(BaseModel):
    dialog_flow_id: int = Field(..., description="对话流ID")
    agent_id: Optional[int] = Field(None, description="智能体ID")
    user_id: Optional[int] = Field(None, description="用户ID")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")


# 创建对话流执行模型
class DialogFlowExecutionCreate(DialogFlowExecutionBase):
    pass


# 对话流执行响应模型
class DialogFlowExecutionResponse(DialogFlowExecutionBase):
    id: int = Field(..., description="执行记录ID")
    status: str = Field(..., description="状态: running, completed, failed")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    execution_path: List[Dict[str, Any]] = Field(default_factory=list, description="执行路径")
    error_message: Optional[str] = Field(None, description="错误信息")
    started_at: datetime = Field(..., description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    class Config:
        from_attributes = True
