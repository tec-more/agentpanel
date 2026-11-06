"""
通知 Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class NotificationListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    message_type: Optional[str] = None
    model: Optional[str] = Field(None, description="按业务模型过滤")


class MarkReadRequest(BaseModel):
    """标记已读/未读"""
    notification_ids: Optional[List[int]] = Field(
        None, description="通知ID列表（不传或空=全部）"
    )


class StarRequest(BaseModel):
    starred: bool = Field(..., description="True=标星 False=取消标星")
