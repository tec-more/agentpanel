"""
统一的大模型使用记录表
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
import uuid


class LLMUsageRecord(BaseModel, TimestampMixin):
    """统一的大模型使用记录表"""

    record_id = fields.CharField(max_length=64, unique=True, description="记录ID")
    customer_id = fields.IntField(description="客户ID")
    model_id = fields.IntField(description="使用的模型ID")
    
    # 记录类型：voice（语音识别/同声传译）、tts（语音合成）、voice_clone（声音复刻）、conversation（文本对话）
    record_type = fields.CharField(max_length=20, description="记录类型")
    
    # 状态
    status = fields.CharField(max_length=20, default="processing", description="状态")
    error_message = fields.TextField(null=True, description="错误信息")
    
    # 时间信息
    start_time = fields.DatetimeField(auto_now_add=False, null=True, description="开始时间")
    end_time = fields.DatetimeField(null=True, description="结束时间")
    
    # Token和费用
    tokens = fields.IntField(default=0, description="token数")
    cost = fields.DecimalField(max_digits=10, decimal_places=4, default=0, description="费用")
    
    # 通用输入输出
    input_text = fields.TextField(null=True, description="输入文本")
    output_text = fields.TextField(null=True, description="输出文本")
    
    # 音频相关
    audio_file = fields.CharField(max_length=255, null=True, description="音频文件路径")
    audio_duration = fields.IntField(null=True, description="音频时长（秒）")
    audio_format = fields.CharField(max_length=20, null=True, description="音频格式")
    
    # 语音合成相关
    voice_type = fields.CharField(max_length=50, null=True, description="音色")
    speed = fields.FloatField(default=1.0, description="语速")
    pitch = fields.FloatField(default=1.0, description="音调")
    volume = fields.FloatField(default=1.0, description="音量")
    
    # 同声传译相关
    source_language = fields.CharField(max_length=20, null=True, description="源语言")
    target_language = fields.CharField(max_length=20, null=True, description="目标语言")
    
    # 声音复刻相关
    clone_id = fields.CharField(max_length=64, null=True, unique=True, description="复刻ID")
    reference_audio = fields.CharField(max_length=255, null=True, description="参考音频文件路径")
    reference_duration = fields.IntField(null=True, description="参考音频时长（秒）")
    voice_id = fields.CharField(max_length=100, null=True, unique=True, description="生成的音色ID")
    voice_name = fields.CharField(max_length=100, null=True, description="音色名称")
    voice_description = fields.TextField(null=True, description="音色描述")
    training_samples = fields.IntField(default=1, description="训练样本数")
    usage_count = fields.IntField(default=0, description="使用次数")
    
    # 对话相关
    conversation_id = fields.CharField(max_length=100, null=True, unique=True, description="对话ID")
    
    # 额外信息（JSON格式，存储其他类型特有的字段）
    extra_info = fields.JSONField(null=True, description="额外信息")
    
    class Meta:
        table = "llm_usage_record"
    
    def __str__(self):
        return f"{self.record_id}"
