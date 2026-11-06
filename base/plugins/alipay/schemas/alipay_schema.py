from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class AlipayOrderRequest(BaseModel):
    """支付宝支付订单请求模型"""
    body: str  # 商品描述
    out_trade_no: str  # 商户订单号
    total_amount: float  # 总金额，单位为元
    subject: str  # 订单标题
    product_code: str = "FAST_INSTANT_TRADE_PAY"  # 产品码
    return_url: Optional[str] = None  # 同步回调地址
    notify_url: Optional[str] = None  # 异步回调地址

class AlipayOrderResponse(BaseModel):
    """支付宝支付订单响应模型"""
    code: int
    msg: str
    data: Optional[Dict] = None

class AlipayRefundRequest(BaseModel):
    """支付宝支付退款请求模型"""
    out_trade_no: str  # 商户订单号
    out_refund_no: str  # 商户退款单号
    refund_amount: float  # 退款金额，单位为元
    refund_reason: Optional[str] = None  # 退款原因

class AlipayRefundResponse(BaseModel):
    """支付宝支付退款响应模型"""
    code: int
    msg: str
    data: Optional[Dict] = None

class AlipayNotifyRequest(BaseModel):
    """支付宝支付回调请求模型"""
    notify_time: Optional[datetime] = None
    notify_type: Optional[str] = None
    notify_id: Optional[str] = None
    app_id: Optional[str] = None
    charset: Optional[str] = None
    version: Optional[str] = None
    sign_type: Optional[str] = None
    sign: Optional[str] = None
    trade_no: Optional[str] = None
    out_trade_no: Optional[str] = None
    out_biz_no: Optional[str] = None
    buyer_id: Optional[str] = None
    buyer_logon_id: Optional[str] = None
    seller_id: Optional[str] = None
    seller_email: Optional[str] = None
    trade_status: Optional[str] = None
    total_amount: Optional[float] = None
    receipt_amount: Optional[float] = None
    invoice_amount: Optional[float] = None
    buyer_pay_amount: Optional[float] = None
    point_amount: Optional[float] = None
    refund_fee: Optional[float] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    gmt_create: Optional[datetime] = None
    gmt_payment: Optional[datetime] = None
    gmt_refund: Optional[datetime] = None
    gmt_close: Optional[datetime] = None
    fund_bill_list: Optional[str] = None
    passback_params: Optional[str] = None
    voucher_detail_list: Optional[str] = None
