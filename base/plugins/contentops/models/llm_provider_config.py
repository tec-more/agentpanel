"""LLM 供应商配置模型。复用 llm 插件的 ChatService，本表只存 contentops 侧的模型选择。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class LLMProviderConfig(BaseModel, TimestampMixin):
    """LLM 供应商配置：仅境内已备案节点，强制 region=domestic。"""
    provider = fields.CharField(max_length=64, description="供应商标识（对应 llm 插件 provider name_en）")
    model = fields.CharField(max_length=128, description="模型标识")
    endpoint = fields.CharField(max_length=512, null=True, description="自定义 endpoint（可选）")
    enabled = fields.BooleanField(default=True, description="是否启用", index=True)
    purpose = fields.CharField(max_length=32, default="rewrite", description="用途: rewrite/summarize/topics/semantic")

    owner_type = fields.CharField(max_length=3, null=True, description="归属主体类型；NULL=全局")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_llm_provider_config"
        indexes = [("purpose", "enabled"), ("owner_type", "owner_id")]
