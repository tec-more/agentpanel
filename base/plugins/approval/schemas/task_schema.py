"""
审批任务 Schema 定义
"""
from typing import Optional
from pydantic import BaseModel, Field


class TaskApprove(BaseModel):
    """审批通过"""
    comment: Optional[str] = Field(None, description="审批意见")
    # 是否同意：true=通过，false=拒绝
    approved: bool = Field(True, description="是否通过")


class TaskReject(BaseModel):
    """审批拒绝"""
    comment: str = Field(..., min_length=1, description="拒绝理由")


class TaskTransfer(BaseModel):
    """审批转审"""
    transfer_to: int = Field(..., description="转审目标人ID")
    comment: Optional[str] = Field(None, description="转审说明")


class TaskResponse(BaseModel):
    """审批任务响应"""
    id: int
    instance_id: int
    node_id: str
    approver_id: int
    status: str
    comment: Optional[str] = None
    approve_time: Optional[str] = None
    transfer_to: Optional[int] = None
    created_at: Optional[str] = None
