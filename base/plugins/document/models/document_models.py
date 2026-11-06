"""
文档管理数据模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class DocumentCategory(BaseModel, TimestampMixin):
    """文档分类目录模型"""
    name = fields.CharField(max_length=200, description="分类名称")
    parent = fields.ForeignKeyField(
        "models.DocumentCategory",
        related_name="children",
        on_delete=fields.CASCADE,
        null=True,
        description="父分类"
    )
    sort = fields.IntField(default=0, description="排序值")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "document_category"

    def __str__(self):
        return self.name


class Document(BaseModel, TimestampMixin):
    """通用文档模型"""
    category = fields.ForeignKeyField(
        "models.DocumentCategory",
        related_name="documents",
        on_delete=fields.SET_NULL,
        null=True,
        description="所属分类"
    )
    title = fields.CharField(max_length=500, description="文档标题")
    file_name = fields.CharField(max_length=500, description="原始文件名")
    file_type = fields.CharField(max_length=50, null=True, description="文件类型扩展名")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")
    file_path = fields.CharField(max_length=1000, description="文件存储路径")
    version = fields.IntField(default=1, description="当前版本号")
    status = fields.CharField(max_length=20, default="normal", description="状态: normal/archived/deleted")
    tags = fields.JSONField(null=True, description="标签列表")
    description = fields.TextField(null=True, description="文档描述")
    business_type = fields.CharField(max_length=50, null=True, description="关联业务类型(如product/order)")
    business_id = fields.IntField(null=True, description="关联业务单据ID")
    visibility = fields.CharField(max_length=20, default="private", description="可见性: private/dept/public")
    created_by = fields.ForeignKeyField(
        "models.User",
        related_name="documents_created",
        on_delete=fields.SET_NULL,
        null=True,
        description="创建者"
    )

    class Meta:
        table = "document"

    def __str__(self):
        return self.title


class DocumentVersion(BaseModel, TimestampMixin):
    """文档版本模型"""
    document = fields.ForeignKeyField(
        "models.Document",
        related_name="versions",
        on_delete=fields.CASCADE,
        description="所属文档"
    )
    version = fields.IntField(description="版本号")
    file_path = fields.CharField(max_length=1000, description="该版本文件存储路径")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")
    change_log = fields.TextField(null=True, description="变更说明")
    created_by = fields.ForeignKeyField(
        "models.User",
        related_name="document_versions_created",
        on_delete=fields.SET_NULL,
        null=True,
        description="创建者"
    )

    class Meta:
        table = "document_version"

    def __str__(self):
        return f"v{self.version} - {self.document.title}"


class DocumentTag(BaseModel, TimestampMixin):
    """文档标签模型"""
    name = fields.CharField(max_length=50, unique=True, description="标签名称")

    class Meta:
        table = "document_tag"

    def __str__(self):
        return self.name
