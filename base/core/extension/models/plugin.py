"""
插件数据模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Plugin(BaseModel, TimestampMixin):
    """插件模型"""

    name = fields.CharField(
        max_length=100,
        unique=True,
        description="插件唯一标识",
        index=True,
    )
    display_name = fields.CharField(
        max_length=200,
        description="插件显示名称",
    )
    version = fields.CharField(
        max_length=50,
        default="1.0.0",
        description="插件版本",
    )
    description = fields.TextField(
        null=True,
        description="插件描述",
    )
    author = fields.CharField(
        max_length=100,
        null=True,
        description="插件作者",
    )
    website = fields.CharField(
        max_length=500,
        null=True,
        description="插件网站",
    )
    is_enabled = fields.BooleanField(
        default=False,
        description="是否启用",
        index=True,
    )
    is_installed = fields.BooleanField(
        default=False,
        description="是否已安装",
        index=True,
    )
    settings = fields.JSONField(
        default=dict,
        description="插件配置",
    )
    dependencies = fields.JSONField(
        default=list,
        description="依赖的插件列表",
    )
    sort_order = fields.IntField(
        default=0,
        description="排序顺序",
    )

    class Meta:
        table = "sys_plugin"
        ordering = ["sort_order", "-created_at"]

    async def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "website": self.website,
            "is_enabled": self.is_enabled,
            "is_installed": self.is_installed,
            "settings": self.settings,
            "dependencies": self.dependencies,
            "sort_order": self.sort_order,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if self.created_at
                else None
            ),
            "updated_at": (
                self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                if self.updated_at
                else None
            ),
        }
