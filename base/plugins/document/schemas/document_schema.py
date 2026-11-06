"""
文档管理 Schema 定义
"""
from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[T] = Field(..., description="数据列表")


# ==================== 分类 ====================

class DocumentCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="分类名称")
    parent_id: Optional[int] = Field(None, description="父分类ID")
    sort: int = Field(default=0, description="排序值")
    is_active: bool = Field(default=True, description="是否启用")


class DocumentCategoryCreate(DocumentCategoryBase):
    pass


class DocumentCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="分类名称")
    parent_id: Optional[int] = Field(None, description="父分类ID")
    sort: Optional[int] = Field(None, description="排序值")
    is_active: Optional[bool] = Field(None, description="是否启用")


class DocumentCategoryResponse(DocumentCategoryBase):
    id: int
    children: List["DocumentCategoryResponse"] = Field(default_factory=list, description="子分类")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentCategoryFlatResponse(DocumentCategoryBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentCategoryListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=1, le=200, description="每页数量")
    name: Optional[str] = Field(None, description="分类名称")


DocumentCategoryResponse.model_rebuild()


# ==================== 文档 ====================

class DocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="文档标题")
    file_name: str = Field(..., min_length=1, max_length=500, description="原始文件名")
    file_type: Optional[str] = Field(None, max_length=50, description="文件类型扩展名")
    file_size: int = Field(default=0, ge=0, description="文件大小(字节)")
    file_path: str = Field(..., max_length=1000, description="文件存储路径")
    category_id: Optional[int] = Field(None, description="所属分类ID")
    status: str = Field(default="normal", max_length=20, description="状态: normal/archived/deleted")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    description: Optional[str] = Field(None, description="文档描述")
    business_type: Optional[str] = Field(None, max_length=50, description="关联业务类型")
    business_id: Optional[int] = Field(None, description="关联业务单据ID")
    visibility: str = Field(default="private", max_length=20, description="可见性: private/dept/public")


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500, description="文档标题")
    file_name: Optional[str] = Field(None, min_length=1, max_length=500, description="原始文件名")
    file_type: Optional[str] = Field(None, max_length=50, description="文件类型扩展名")
    file_size: Optional[int] = Field(None, ge=0, description="文件大小(字节)")
    file_path: Optional[str] = Field(None, max_length=1000, description="文件存储路径")
    category_id: Optional[int] = Field(None, description="所属分类ID")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    description: Optional[str] = Field(None, description="文档描述")
    business_type: Optional[str] = Field(None, max_length=50, description="关联业务类型")
    business_id: Optional[int] = Field(None, description="关联业务单据ID")
    visibility: Optional[str] = Field(None, max_length=20, description="可见性")


class DocumentResponse(DocumentBase):
    id: int
    version: int
    created_by_id: Optional[int] = None
    category_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    title: Optional[str] = Field(None, description="文档标题(模糊搜索)")
    file_name: Optional[str] = Field(None, description="文件名(模糊搜索)")
    file_type: Optional[str] = Field(None, description="文件类型")
    category_id: Optional[int] = Field(None, description="分类ID")
    status: Optional[str] = Field(None, description="状态")
    business_type: Optional[str] = Field(None, description="关联业务类型")
    business_id: Optional[int] = Field(None, description="关联业务单据ID")
    visibility: Optional[str] = Field(None, description="可见性")
    tag: Optional[str] = Field(None, description="标签")


# ==================== 版本 ====================

class DocumentVersionBase(BaseModel):
    document_id: int = Field(..., description="所属文档ID")
    version: int = Field(..., ge=1, description="版本号")
    file_path: str = Field(..., max_length=1000, description="该版本文件存储路径")
    file_size: int = Field(default=0, ge=0, description="文件大小(字节)")
    change_log: Optional[str] = Field(None, description="变更说明")


class DocumentVersionCreate(BaseModel):
    file_path: str = Field(..., max_length=1000, description="新版本文件存储路径")
    file_size: int = Field(default=0, ge=0, description="文件大小(字节)")
    change_log: Optional[str] = Field(None, description="变更说明")


class DocumentVersionUpdate(BaseModel):
    change_log: Optional[str] = Field(None, description="变更说明")


class DocumentVersionResponse(DocumentVersionBase):
    id: int
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentVersionListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=200, description="每页数量")


# ==================== 操作日志 ====================

class DocumentMoveRequest(BaseModel):
    target_category_id: Optional[int] = Field(None, description="目标分类ID, None表示移到根目录")


class DocumentRestoreRequest(BaseModel):
    document_ids: List[int] = Field(..., description="要恢复的文档ID列表")


class DocumentDeleteRequest(BaseModel):
    document_ids: List[int] = Field(..., description="要删除的文档ID列表(软删除)")


class DocumentVersionRollbackRequest(BaseModel):
    version_id: int = Field(..., description="要回滚到的版本ID")
    change_log: Optional[str] = Field(None, description="回滚说明")
