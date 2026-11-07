"""
模型价格表 - 按 input+output 合计计量，支持价格版本与生效区间

计量口径（DeepSeek Harness）：
- 计费输入 = inputTokens + cacheReadTokens + cacheWriteTokens（三者互不重叠）
- outputTokens 单独计；reasoningTokens 通常已包含在 output 内，不重复计
- 自动压缩 compaction/summary 的 usage 是额外模型调用，必须单独计
"""
from tortoise import fields

from base.common.model import BaseModel, TimestampMixin


class ModelPrice(BaseModel, TimestampMixin):
    """模型价格（币种/版本/生效区间）"""

    provider = fields.CharField(max_length=50, default="deepseek", index=True, description="提供商")
    model = fields.CharField(max_length=100, index=True, description="模型标识")
    currency = fields.CharField(max_length=8, default="CNY", description="币种")
    input_price_per_1k = fields.DecimalField(
        max_digits=14, decimal_places=8, default=0, description="未缓存输入 单价/1K token",
    )
    output_price_per_1k = fields.DecimalField(
        max_digits=14, decimal_places=8, default=0, description="输出 单价/1K token",
    )
    cache_read_price_per_1k = fields.DecimalField(
        max_digits=14, decimal_places=8, default=0, description="缓存读取 单价/1K token",
    )
    cache_write_price_per_1k = fields.DecimalField(
        max_digits=14, decimal_places=8, default=0, description="缓存写入 单价/1K token",
    )
    price_version = fields.CharField(max_length=50, default="v1", description="价格版本")
    source = fields.CharField(max_length=30, default="manual", description="价格来源 manual/provider/gateway")
    effective_from = fields.DatetimeField(null=True, description="生效时间")
    effective_to = fields.DatetimeField(null=True, description="失效时间")
    status = fields.CharField(max_length=20, default="active", description="active/disabled")
    description = fields.TextField(null=True, description="备注")

    class Meta:
        table = "model_price"
        table_description = "模型价格表"
        unique_together = (("provider", "model", "price_version"),)
        ordering = ["provider", "model", "-effective_from"]

    def __str__(self):
        return f"ModelPrice({self.provider}/{self.model}@{self.price_version})"
