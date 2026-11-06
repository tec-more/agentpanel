"""
审批流程 Schema 定义
"""
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


# ==================== 流程定义 ====================

class FlowCreate(BaseModel):
    """创建流程"""
    name: str = Field(..., min_length=1, max_length=100, description="流程名称")
    code: str = Field(..., min_length=1, max_length=100, description="流程编码")
    description: Optional[str] = Field(None, description="流程描述")
    form_config: List[Any] = Field(default=[], description="表单配置")
    flow_config: Dict[str, Any] = Field(default={}, description="流程配置")
    business_type: Optional[str] = Field(None, description="业务类型")
    model: Optional[str] = Field(None, max_length=50, description="业务模型标识（按模型匹配审批，缺省用 business_type）")
    action: Optional[str] = Field(None, max_length=50, description="执行动作(create/update/delete)，不填表示匹配全部动作")
    methods: List[str] = Field(default=["POST", "PUT", "DELETE"], description="拦截方法列表")
    priority: int = Field(default=0, description="优先级(数字越大优先级越高)")
    is_active: bool = Field(default=True, description="是否启用")
    route_patterns: List[str] = Field(default=[], description="前端路由模式列表，全局审批组件按路由匹配")


class FlowUpdate(BaseModel):
    """更新流程"""
    name: Optional[str] = Field(None, max_length=100, description="流程名称")
    description: Optional[str] = Field(None, description="流程描述")
    form_config: Optional[List[Any]] = Field(None, description="表单配置")
    flow_config: Optional[Dict[str, Any]] = Field(None, description="流程配置")
    business_type: Optional[str] = Field(None, description="业务类型")
    model: Optional[str] = Field(None, max_length=50, description="业务模型标识（按模型匹配审批）")
    action: Optional[str] = Field(None, max_length=50, description="执行动作(create/update/delete)")
    methods: Optional[List[str]] = Field(None, description="拦截方法列表")
    priority: Optional[int] = Field(None, description="优先级(数字越大优先级越高)")
    is_active: Optional[bool] = Field(None, description="是否启用")
    route_patterns: Optional[List[str]] = Field(None, description="前端路由模式列表")


class FlowResponse(BaseModel):
    """流程响应"""
    id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool
    form_config: List[Any] = []
    flow_config: Dict[str, Any] = {}
    business_type: Optional[str] = None
    model: Optional[str] = None
    action: Optional[str] = None
    methods: List[str] = ["POST", "PUT", "DELETE"]
    priority: int = 0
    route_patterns: List[str] = []
    is_system: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FlowListQuery(BaseModel):
    """流程列表查询"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    name: Optional[str] = Field(None, description="流程名称(模糊搜索)")
    business_type: Optional[str] = Field(None, description="业务类型")
    model: Optional[str] = Field(None, description="业务模型标识")
    action: Optional[str] = Field(None, description="执行动作")
    is_active: Optional[bool] = Field(None, description="是否启用")
