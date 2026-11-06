"""
操作日志相关Schemas
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class OperationLogResponse(BaseModel):
    """操作日志响应模型"""
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    module: Optional[str] = None
    operation: str
    method: str
    path: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    duration: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
