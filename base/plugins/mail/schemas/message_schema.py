"""
消息 Schema
"""
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    """发布消息"""
    model: Optional[str] = Field(None, max_length=100, description="关联业务表名")
    res_id: Optional[int] = Field(None, description="关联业务记录ID")
    subject: Optional[str] = Field(None, max_length=255, description="主题")
    body: str = Field(..., description="正文")
    message_type: str = Field(default="comment", description="消息类型(notification/comment/email)")
    subtype_id: Optional[int] = Field(None, description="子类型ID（与 subtype_code 二选一）")
    subtype_code: Optional[str] = Field(None, max_length=100, description="子类型编码")
    parent_id: Optional[int] = Field(None, description="父消息ID")
    is_internal: bool = Field(default=False, description="是否内部备注")
    attachment_ids: List[Any] = Field(default=[], description="附件元数据列表")
    record_name: Optional[str] = Field(None, max_length=255, description="业务记录显示名")
    notify_followers: bool = Field(default=True, description="是否通知关注者")
    extra_recipient_ids: Optional[List[int]] = Field(None, description="额外收件人ID列表")


class MessageUpdate(BaseModel):
    """更新消息（仅 body/subject/is_internal/attachment_ids 可改）"""
    subject: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = None
    is_internal: Optional[bool] = None
    attachment_ids: Optional[List[Any]] = None


class MessageListQuery(BaseModel):
    """消息列表/线程查询"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    model: Optional[str] = None
    res_id: Optional[int] = None
    message_type: Optional[str] = None
    subtype_id: Optional[int] = None
    author_id: Optional[int] = None
