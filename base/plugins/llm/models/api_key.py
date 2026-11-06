"""
API密钥模型
"""
from tortoise import fields
from datetime import datetime, timedelta
from base.common.model import BaseModel, TimestampMixin
from base.plugins.llm.models.enums import ModelServiceType, CallMode


class LLMApiKey(BaseModel, TimestampMixin):
    """API密钥表"""

    provider = fields.ForeignKeyField(
        "models.LLMProvider",
        related_name="api_keys",
        on_delete=fields.CASCADE
    )
    
    model = fields.ForeignKeyField(
        "models.LLMModel",
        related_name="api_keys",
        on_delete=fields.CASCADE,
        null=True,
        description="关联的模型"
    )

    # ========== 服务类型 ==========
    model_service_type = fields.CharField(
        max_length=50,
        default=ModelServiceType.LLM.value,
        description="模型服务类型"
    )
    
    # ========== 调用方式 ==========
    call_mode = fields.CharField(
        max_length=50,
        default=CallMode.VENDOR_SDK.value,
        description="调用方式：openapi 使用openai库，vendor_sdk 使用厂商SDK"
    )

    # ========== 认证字段 ==========
    api_id = fields.CharField(max_length=255, null=True, description="API ID")
    api_key = fields.CharField(max_length=512, null=True, description="API Key")
    api_secret = fields.CharField(max_length=512, null=True, description="API Secret")
    access_token = fields.CharField(max_length=512, null=True, description="Access Token")
    endpoint_url = fields.CharField(max_length=512, null=True, description="自定义端点URL")
    
    # ========== 配额管理 ==========
    max_quota = fields.IntField(default=100000, description="每日配额限制(tokens/天)")
    used_quota = fields.IntField(default=0, description="已使用配额")
    quota_reset_date = fields.DateField(default=datetime.now().date, description="配额重置日期")

    # ========== 状态管理 ==========
    status = fields.CharField(max_length=20, default="active", description="状态")
    last_used_at = fields.DatetimeField(null=True, description="最后使用时间")
    expires_at = fields.DatetimeField(null=True, description="过期时间")

    # ========== 备注 ==========
    description = fields.TextField(null=True, description="备注")

    class Meta:
        table = "llm_api_key"

    def __str__(self):
        return f"{self.provider.name} - {self.api_id or self.model_service_type}"

    async def save(self, *args, **kwargs):
        """保存前自动设置 quota_reset_date"""
        if not self.quota_reset_date:
            self.quota_reset_date = datetime.now().date()
        # 确保调用父类的 save 方法时传递所有参数
        await super().save(*args, **kwargs)

    @property
    def is_available(self) -> bool:
        """是否可用"""
        if self.status != "active":
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        if self.max_quota > 0 and self.used_quota >= self.max_quota:
            return False
        return True

    @property
    def remaining_quota(self) -> int:
        """剩余配额"""
        return max(0, self.max_quota - self.used_quota)

    async def reset_quota_if_needed(self):
        """如果需要，重置配额"""
        today = datetime.now().date()
        if self.quota_reset_date < today:
            self.used_quota = 0
            self.quota_reset_date = today
            await self.save()

    @property
    def is_voice_service(self) -> bool:
        """是否为语音服务类型"""
        return self.model_service_type in [t.value for t in ModelServiceType.voice_services()]

    def get_credentials(self) -> dict:
        """获取服务凭据"""
        return {
            "api_id": self.api_id,
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "access_token": self.access_token,
            "endpoint_url": self.endpoint_url,
            "call_mode": self.call_mode
        }
    
    @property
    def is_openapi_mode(self) -> bool:
        """是否为OpenAPI模式"""
        return self.call_mode == CallMode.OPENAPI.value
