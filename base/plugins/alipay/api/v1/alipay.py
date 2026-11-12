from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

alipay_router = APIRouter(tags=["Alipay"])

# 路径前缀由 manifest.route_prefix = /v1/pay/alipay 统一声明；
# 浏览器侧 /api 由 base/app_wrapper.py 剥离，插件内不得重复声明。

# 模拟支付宝支付服务
class AlipayService:
    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        # 这里应该调用支付宝SDK创建订单
        # 为了演示，返回模拟数据
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "order_id": order_data.get("out_trade_no"),
                "form": "<form action='https://openapi.alipaydev.com/gateway.do' method='post'>...</form>",
                "trade_no": "202401061234567890abcdef",
                "qr_code": "https://qr.alipay.com/abcdef1234567890"
            }
        }
    
    async def query_order(self, order_id: str) -> Dict[str, Any]:
        # 这里应该调用支付宝SDK查询订单
        # 为了演示，返回模拟数据
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "order_id": order_id,
                "trade_status": "TRADE_SUCCESS",
                "total_amount": "1.00",
                "trade_no": "202401061234567890abcdef",
                "gmt_payment": "2024-01-06 12:34:56"
            }
        }
    
    async def refund_order(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        # 这里应该调用支付宝SDK退款
        # 为了演示，返回模拟数据
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "refund_no": refund_data.get("out_refund_no"),
                "trade_no": "202401061234567890abcdef",
                "out_trade_no": refund_data.get("out_trade_no"),
                "refund_amount": refund_data.get("refund_amount"),
                "refund_status": "REFUND_SUCCESS"
            }
        }

@alipay_router.post("/orders", response_model=Dict[str, Any])
async def create_alipay_order(order_data: Dict[str, Any]):
    """创建支付宝支付订单"""
    try:
        service = AlipayService()
        result = await service.create_order(order_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@alipay_router.get("/orders/{order_id}", response_model=Dict[str, Any])
async def query_alipay_order(order_id: str):
    """查询支付宝支付订单"""
    try:
        service = AlipayService()
        result = await service.query_order(order_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@alipay_router.post("/refunds", response_model=Dict[str, Any])
async def refund_alipay_order(refund_data: Dict[str, Any]):
    """支付宝支付退款"""
    try:
        service = AlipayService()
        result = await service.refund_order(refund_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@alipay_router.post("/notify", response_model=Dict[str, Any])
async def alipay_notify(notify_data: Dict[str, Any]):
    """支付宝支付回调"""
    try:
        # 这里应该验证支付宝回调的签名
        # 处理回调逻辑
        return {
            "code": "10000",
            "msg": "Success"
        }
    except Exception as e:
        return {
            "code": "40004",
            "msg": str(e)
        }
