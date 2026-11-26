"""「发现应用」面板的后台可配置应用目录（平台级，harness 插件）。

2026-11-26 从 customer 插件迁入：dsh 客户端通过 /v1/harness/discover-apps
只读启用项；运营后台 /panel 通过 /v1/harness/admin/discover-apps 维护。
表名保留 customer_discover_app（零数据迁移）。只存展示信息与跳转目标，
不存任何凭据。
"""
from tortoise import fields

from base.common.model import BaseModel, TimestampMixin


class CustomerDiscoverApp(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=64, description="应用名称")
    description = fields.CharField(max_length=160, default="", description="卡片副标题")
    icon_text = fields.CharField(max_length=4, default="", description="图标内短文本")
    icon_color = fields.CharField(max_length=16, null=True, description="图标背景色 #RRGGBB")
    open_mode = fields.CharField(max_length=16, default="portal", description="打开方式：portal / link")
    target = fields.CharField(max_length=512, description="站内路径或外部 URL")
    sort = fields.IntField(default=0, description="排序（升序）")
    is_active = fields.BooleanField(default=True, description="是否下发到客户端")

    class Meta:
        table = "customer_discover_app"
        table_description = "发现应用面板的应用目录"
