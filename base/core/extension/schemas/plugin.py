"""
插件相关的 Pydantic 模型
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PluginBase(BaseModel):
    """插件基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="插件唯一标识")
    display_name: str = Field(..., min_length=1, max_length=200, description="显示名称")
    version: str = Field(default="1.0.0", max_length=50, description="版本号")
    description: Optional[str] = Field(None, description="插件描述")
    author: Optional[str] = Field(None, max_length=100, description="作者")
    website: Optional[str] = Field(None, max_length=500, description="插件网站")


class PluginCreate(PluginBase):
    """创建插件模型"""
    dependencies: List[str] = Field(default_factory=list, description="依赖插件列表")
    settings: Dict[str, Any] = Field(default_factory=dict, description="插件配置")


class PluginUpdate(BaseModel):
    """更新插件模型"""
    display_name: Optional[str] = Field(None, max_length=200, description="显示名称")
    description: Optional[str] = Field(None, description="插件描述")
    settings: Optional[Dict[str, Any]] = Field(None, description="插件配置")
    sort_order: Optional[int] = Field(None, description="排序顺序")


class PluginResponse(BaseModel):
    """插件响应模型"""
    id: int
    name: str
    display_name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    website: Optional[str] = None
    is_enabled: bool
    is_installed: bool
    settings: Dict[str, Any] = {}
    dependencies: List[str] = []
    sort_order: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PluginListQuery(BaseModel):
    """插件列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    keyword: Optional[str] = Field(None, description="搜索关键词")


class PluginListResponse(BaseModel):
    """插件列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[PluginResponse] = Field(..., description="插件列表")


class PluginSettingsUpdate(BaseModel):
    """插件设置更新模型"""
    settings: Dict[str, Any] = Field(default_factory=dict, description="插件配置")


class PluginUninstallRequest(BaseModel):
    """插件卸载请求（需验证登录密码）"""
    password: str = Field(..., min_length=1, description="当前管理员登录密码")


class PluginDiscoverItem(BaseModel):
    """发现的插件信息"""
    name: str
    display_name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    is_installed: bool = False
    is_enabled: bool = False
