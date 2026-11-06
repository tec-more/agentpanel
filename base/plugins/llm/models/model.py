"""
大模型模型
"""
from tortoise import fields
from decimal import Decimal
from base.common.model import BaseModel, TimestampMixin


class LLMModel(BaseModel, TimestampMixin):
    """大模型表"""

    provider = fields.ForeignKeyField(
        "models.LLMProvider",
        related_name="models",
        on_delete=fields.CASCADE
    )
    model_id = fields.CharField(max_length=100, description="模型标识")
    model_name = fields.CharField(max_length=100, description="模型名称")
    endpoint_url = fields.CharField(max_length=255, null=True, description="模型访问地址")
    context_length = fields.IntField(default=4096, description="上下文长度")
    input_price = fields.DecimalField(max_digits=10, decimal_places=4, default=0, description="输入价格 (元/1K tokens)")
    output_price = fields.DecimalField(max_digits=10, decimal_places=4, default=0, description="输出价格 (元/1K tokens)")
    supports_streaming = fields.BooleanField(default=True, description="是否支持流式")
    supports_vision = fields.BooleanField(default=False, description="是否支持视觉")
    supports_function = fields.BooleanField(default=False, description="是否支持函数调用")
    status = fields.CharField(max_length=20, default="active", description="状态")
    description = fields.TextField(null=True, description="模型描述")

    class Meta:
        table = "llm_model"

    def __str__(self):
        try:
            return f"{self.provider.name} - {self.model_name}"
        except Exception:
            return f"Model: {self.model_name}"

    @property
    def is_free(self) -> bool:
        """是否免费"""
        return self.input_price == 0 and self.output_price == 0
