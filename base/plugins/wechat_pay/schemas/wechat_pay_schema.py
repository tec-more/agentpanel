from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class WeChatPayOrderRequest(BaseModel):
    """微信支付订单请求模型"""
    body: str  # 商品描述
    out_trade_no: str  # 商户订单号
    total_fee: int  # 总金额，单位为分
    spbill_create_ip: str  # 客户端IP
    notify_url: str  # 通知地址
    trade_type: str = "JSAPI"  # 交易类型
    openid: Optional[str] = None  # 用户openid，JSAPI支付必填

class WeChatPayOrderResponse(BaseModel):
    """微信支付订单响应模型"""
    code: int
    msg: str
    data: Optional[Dict] = None

class WeChatPayRefundRequest(BaseModel):
    """微信支付退款请求模型"""
    out_trade_no: str  # 商户订单号
    out_refund_no: str  # 商户退款单号
    total_fee: int  # 订单总金额，单位为分
    refund_fee: int  # 退款金额，单位为分
    refund_desc: Optional[str] = None  # 退款描述

class WeChatPayRefundResponse(BaseModel):
    """微信支付退款响应模型"""
    code: int
    msg: str
    data: Optional[Dict] = None

class WeChatPayNotifyRequest(BaseModel):
    """微信支付回调请求模型"""
    return_code: str
    return_msg: str
    appid: Optional[str] = None
    mch_id: Optional[str] = None
    nonce_str: Optional[str] = None
    sign: Optional[str] = None
    result_code: Optional[str] = None
    err_code: Optional[str] = None
    err_code_des: Optional[str] = None
    trade_type: Optional[str] = None
    prepay_id: Optional[str] = None
    bank_type: Optional[str] = None
    total_fee: Optional[int] = None
    cash_fee: Optional[int] = None
    cash_fee_type: Optional[str] = None
    transaction_id: Optional[str] = None
    out_trade_no: Optional[str] = None
    time_end: Optional[str] = None
