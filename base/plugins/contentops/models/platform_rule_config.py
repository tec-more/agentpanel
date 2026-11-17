"""平台适配规则配置模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class PlatformRuleConfig(BaseModel, TimestampMixin):
    """平台适配规则配置：字数/尺寸/话题数等，后台可热更新，禁止硬编码。"""
    platform = fields.CharField(max_length=32, description="平台标识", index=True)
    key = fields.CharField(max_length=64, description="配置键（如 title_max/desc_max/cover_ratio）")
    value = fields.JSONField(default=dict, description="配置值")
    enabled = fields.BooleanField(default=True, description="是否启用")

    owner_type = fields.CharField(max_length=3, null=True, description="归属主体类型；NULL=平台级全局配置")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_platform_rule_config"
        indexes = [("platform", "key"), ("owner_type", "owner_id")]
        unique_together = (("platform", "key", "owner_type", "owner_id"),)
