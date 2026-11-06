"""
七相支付Schema定义
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class CreateOrderIn(BaseModel):
    """创建支付订单请求"""
    order_no: str = Field(..., min_length=1, max_length=64, description="商户订单号")
    pay_type: str = Field(..., description="支付类型: alipay/wxpay")
    amount: float = Field(..., gt=0, description="支付金额（单位：元）")
    subject: str = Field(..., min_length=1, max_length=127, description="商品名称")
    client_ip: Optional[str] = Field("127.0.0.1", description="客户端IP")
    param: Optional[str] = Field("", description="业务扩展参数")

    @field_validator('pay_type')
    @classmethod
    def validate_pay_type(cls, v):
        """验证支付类型"""
        if v not in ['alipay', 'wxpay']:
            raise ValueError('pay_type必须是alipay或wxpay')
        return v

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """验证金额格式（最多2位小数）"""
        # 检查小数位数
        if isinstance(v, float):
            str_amount = str(v)
            if '.' in str_amount:
                decimal_places = len(str_amount.split('.')[1])
                if decimal_places > 2:
                    raise ValueError('金额最多保留2位小数')
        return v

    @field_validator('client_ip')
    @classmethod
    def validate_ip(cls, v):
        """验证IP地址格式"""
        if v:
            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if not re.match(ip_pattern, v):
                raise ValueError('IP地址格式不正确')
        return v


class CreateOrderOut(BaseModel):
    """创建支付订单响应"""
    order_no: str = Field(..., description="商户订单号")
    trade_no: str = Field(..., description="订单号")
    payurl: str = Field(..., description="支付跳转URL")
    qrcode: Optional[str] = Field(None, description="二维码链接（如有）")
    pay_type: str = Field(..., description="支付类型")


class QueryOrderOut(BaseModel):
    """查询订单响应"""
    order_no: str = Field(..., description="商户订单号")
    trade_no: str = Field(..., description="订单号")
    status: str = Field(..., description="支付状态: success/pending/failed")
    pay_type: str = Field(..., description="支付类型")
    amount: float = Field(..., description="订单金额")
    trade_status: Optional[str] = Field(None, description="原始支付状态")


class NotifyData(BaseModel):
    """支付回调数据"""
    pid: str = Field(..., description="商户ID")
    trade_no: str = Field(..., description="订单号")
    out_trade_no: str = Field(..., description="商户订单号")
    type: str = Field(..., description="支付方式")
    name: Optional[str] = Field(None, description="商品名称")
    money: str = Field(..., description="商品金额")
    trade_status: str = Field(..., description="支付状态")
    param: Optional[str] = Field("", description="业务扩展参数")
    sign: str = Field(..., description="签名字符串")
    sign_type: str = Field(..., description="签名类型")
