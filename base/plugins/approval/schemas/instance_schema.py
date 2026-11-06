"""
审批实例 Schema 定义
"""
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class InstanceCreate(BaseModel):
    """创建审批实例（发起审批）"""
    flow_id: Optional[int] = Field(None, description="审批流程ID（与business_type二选一）")
    business_type: Optional[str] = Field(None, description="业务类型（与flow_id二选一）")
    business_id: Optional[int] = Field(None, description="业务对象ID")
    title: str = Field(..., min_length=1, max_length=255, description="审批标题")
    form_data: Dict[str, Any] = Field(default={}, description="表单数据")
    business_data: Optional[Dict[str, Any]] = Field(None, description="业务数据快照")
    action: Optional[str] = Field(None, description="业务动作：create/update/delete（供执行器回调）")


class InstanceResponse(BaseModel):
    """审批实例响应"""
    id: int
    flow_id: int
    business_type: Optional[str] = None
    business_id: Optional[int] = None
    title: str
    applicant_id: int
    status: str
    current_node: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    complete_time: Optional[str] = None
    created_at: Optional[str] = None


class InstanceListQuery(BaseModel):
    """审批实例列表查询"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    status: Optional[str] = Field(None, description="审批状态")
    business_type: Optional[str] = Field(None, description="业务类型")
    applicant_id: Optional[int] = Field(None, description="申请人ID")
    title: Optional[str] = Field(None, description="标题(模糊搜索)")
