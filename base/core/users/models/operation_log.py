"""
操作日志模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class OperationLog(BaseModel, TimestampMixin):
    """操作日志模型"""
    user_id = fields.IntField(null=True, description="操作用户ID", index=True)
    username = fields.CharField(max_length=50, null=True, description="操作用户名", index=True)
    module = fields.CharField(max_length=50, null=True, description="操作模块", index=True)
    operation = fields.CharField(max_length=100, description="操作类型", index=True)
    method = fields.CharField(max_length=10, description="请求方法", index=True)
    path = fields.CharField(max_length=500, description="请求路径")
    ip_address = fields.CharField(max_length=50, null=True, description="IP地址", index=True)
    user_agent = fields.CharField(max_length=500, null=True, description="用户代理")
    request_params = fields.JSONField(null=True, description="请求参数")
    response_data = fields.TextField(null=True, description="响应数据")
    status_code = fields.IntField(null=True, description="响应状态码", index=True)
    error_message = fields.TextField(null=True, description="错误信息")
    duration = fields.IntField(null=True, description="执行时长(毫秒)")

    class Meta:
        table = "operation_log"
        ordering = ["-created_at"]
