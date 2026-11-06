from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Dict, Any, Optional
import xml.etree.ElementTree as ET
import hashlib
from datetime import datetime
from urllib.parse import urlencode

router = APIRouter(prefix="/v1/pay/wechat", tags=["WeChat Pay"])

def get_wechat_config():
    """获取微信支付配置"""
    from base.common.config import config
    return {
        "app_id": config.get("aif2f.payment", "wechat_app_id", fallback=""),
        "mch_id": config.get("aif2f.payment", "wechat_mch_id", fallback=""),
        "api_key": config.get("aif2f.payment", "wechat_api_key", fallback=""),
        "notify_url": config.get("aif2f.payment", "wechat_notify_url", fallback="")
    }

def verify_wechat_sign(data: Dict[str, Any], api_key: str) -> bool:
    """验证微信支付签名"""
    sign = data.pop("sign", None)
    if not sign:
        return False

    # 过滤空值
    filtered = {k: v for k, v in data.items() if v != "" and v is not None}
    # 按key字典序排序
    sorted_params = sorted(filtered.items())
    # 拼接字符串
    sign_str = "&".join([f"{k}={v}" for k, v in sorted_params])
    sign_str += f"&key={api_key}"
    # MD5加密并转大写
    calculated_sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()

    return calculated_sign == sign

def generate_response(return_code: str, return_msg: str) -> str:
    """生成微信支付响应XML"""
    xml_dict = {
        "return_code": return_code,
        "return_msg": return_msg
    }
    root = ET.Element("xml")
    for key, value in xml_dict.items():
        child = ET.SubElement(root, key)
        child.text = str(value)
    return ET.tostring(root, encoding="unicode")

# 微信支付服务
class WeChatPayService:
    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建微信支付订单（待集成微信SDK）"""
        cfg = get_wechat_config()

        pay_type = order_data.get("pay_type", "h5")  # h5, native, jsapi, app

        # TODO: 集成微信支付SDK
        # 目前返回模拟数据用于测试

        if pay_type == "native":
            # PC端扫码支付（Native支付）返回二维码链接
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "order_id": "wx" + datetime.now().strftime("%Y%m%d%H%M%S"),
                    "code_url": "weixin://wxpay/bizpayurl?pr=abcdef123456",  # 二维码链接
                    "prepay_id": "wx" + datetime.now().strftime("%Y%m%d%H%M%S") + "abcdef",
                    "pay_type": "native"
                }
            }
        elif pay_type == "h5":
            # H5支付返回跳转URL
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "order_id": "wx" + datetime.now().strftime("%Y%m%d%H%M%S"),
                    "mweb_url": "https://wx.tenpay.com/cgi-bin/mmpayweb-bin/checkmweb?prepay_id=xxx",
                    "pay_type": "h5"
                }
            }
        else:
            # JSAPI支付或APP支付返回签名数据
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "order_id": "wx" + datetime.now().strftime("%Y%m%d%H%M%S"),
                    "prepay_id": "wx" + datetime.now().strftime("%Y%m%d%H%M%S") + "abcdef",
                    "appid": cfg["app_id"] or "wx1234567890abcdef",
                    "partnerid": cfg["mch_id"] or "1234567890",
                    "package": "Sign=WXPay",
                    "noncestr": "abcdef1234567890",
                    "timestamp": int(datetime.now().timestamp()),
                    "sign": "ABCDEF1234567890",
                    "pay_type": "jsapi"
                }
            }

    async def query_order(self, order_id: str) -> Dict[str, Any]:
        """查询微信支付订单（待集成微信SDK）"""
        # TODO: 调用微信支付查询订单接口
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "order_id": order_id,
                "trade_state": "SUCCESS",
                "total_fee": 100,
                "transaction_id": "4200001234567890",
                "time_end": datetime.now().strftime("%Y%m%d%H%M%S")
            }
        }

    async def refund_order(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """微信支付退款（待集成微信SDK）"""
        # TODO: 调用微信支付退款接口
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "refund_id": "500001234567890",
                "out_refund_no": refund_data.get("out_refund_no"),
                "refund_fee": refund_data.get("refund_fee"),
                "total_fee": refund_data.get("total_fee"),
                "refund_status": "SUCCESS"
            }
        }

@router.post("/native/create")
async def create_native_payment(order_data: Dict[str, Any]):
    """
    创建PC端扫码支付订单

    请求参数:
    - order_no: 商户订单号
    - total_fee: 支付金额（分）
    - body: 商品描述
    - attach: 附加数据（可选）

    返回参数:
    - code_url: 二维码链接，用于生成二维码
    - order_id: 微信订单号
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # 设置支付类型为Native（扫码支付）
        order_data["pay_type"] = "native"

        service = WeChatPayService()
        result = await service.create_order(order_data)

        if result.get("code") == 0:
            logger.info(f"创建扫码支付订单成功: {order_data.get('order_no')}")
        else:
            logger.error(f"创建扫码支付订单失败: {result.get('msg')}")

        return result

    except Exception as e:
        logger.error(f"创建扫码支付订单异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/native/poll/{order_no}")
async def poll_payment_status(order_no: str):
    """
    PC端扫码支付轮询接口

    前端在展示二维码后，定时调用此接口查询支付状态
    建议轮询间隔：2-3秒
    建议轮询时长：5-10分钟

    返回状态:
    - pending: 待支付
    - success: 支付成功
    - closed: 订单已关闭
    - error: 查询异常
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        service = WeChatPayService()
        result = await service.query_order(order_no)

        if result.get("code") == 0:
            data = result.get("data", {})
            trade_state = data.get("trade_state", "NOTPAY")

            # 映射微信支付状态
            status_map = {
                "SUCCESS": "success",
                "REFUND": "refund",
                "NOTPAY": "pending",
                "CLOSED": "closed",
                "REVOKED": "revoked",
                "USERPAYING": "paying",
                "PAYERROR": "error"
            }

            payment_status = status_map.get(trade_state, "unknown")

            logger.info(f"订单 {order_no} 当前状态: {payment_status}")

            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "order_no": order_no,
                    "status": payment_status,
                    "trade_state": trade_state,
                    "transaction_id": data.get("transaction_id"),
                    "total_fee": data.get("total_fee"),
                    "time_end": data.get("time_end")
                }
            }
        else:
            return {
                "code": -1,
                "msg": result.get("msg", "查询失败"),
                "data": {
                    "order_no": order_no,
                    "status": "error"
                }
            }

    except Exception as e:
        logger.error(f"轮询支付状态异常: {str(e)}", exc_info=True)
        return {
            "code": -1,
            "msg": str(e),
            "data": {
                "order_no": order_no,
                "status": "error"
            }
        }


@router.post("/native/close/{order_no}")
async def close_native_payment(order_no: str):
    """
    关闭PC端扫码支付订单

    当用户取消支付或超时时，前端可调用此接口关闭订单
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # TODO: 调用微信支付关闭订单接口
        logger.info(f"关闭订单: {order_no}")

        return {
            "code": 0,
            "msg": "订单已关闭",
            "data": {
                "order_no": order_no,
                "status": "closed"
            }
        }

    except Exception as e:
        logger.error(f"关闭订单异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders", response_model=Dict[str, Any])
async def create_wechat_order(order_data: Dict[str, Any]):
    """创建微信支付订单"""
    try:
        service = WeChatPayService()
        result = await service.create_order(order_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/{order_id}", response_model=Dict[str, Any])
async def query_wechat_order(order_id: str):
    """查询微信支付订单"""
    try:
        service = WeChatPayService()
        result = await service.query_order(order_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refunds", response_model=Dict[str, Any])
async def refund_wechat_order(refund_data: Dict[str, Any]):
    """微信支付退款"""
    try:
        service = WeChatPayService()
        result = await service.refund_order(refund_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notify")
async def wechat_pay_notify(request_data: str):
    """
    微信支付回调通知处理

    微信支付成功后会调用此接口通知支付结果
    需要验证签名并更新订单状态
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        cfg = get_wechat_config()

        # 解析XML
        try:
            root = ET.fromstring(request_data)
            notify_data = {child.tag: child.text for child in root}
        except Exception as e:
            logger.error(f"解析XML失败: {str(e)}")
            return generate_response("FAIL", "XML格式错误")

        logger.info(f"收到微信支付回调: {notify_data}")

        # 验证签名
        if not verify_wechat_sign(notify_data.copy(), cfg["api_key"]):
            logger.error("签名验证失败")
            return generate_response("FAIL", "签名验证失败")

        # 检查返回码
        return_code = notify_data.get("return_code")
        result_code = notify_data.get("result_code")

        if return_code != "SUCCESS" or result_code != "SUCCESS":
            logger.error(f"支付失败: return_code={return_code}, result_code={result_code}")
            return generate_response("FAIL", "支付失败")

        # 获取订单信息
        out_trade_no = notify_data.get("out_trade_no")  # 商户订单号
        transaction_id = notify_data.get("transaction_id")  # 微信支付订单号
        total_fee = notify_data.get("total_fee")  # 订单金额（分）
        time_end = notify_data.get("time_end")  # 支付完成时间

        if not all([out_trade_no, transaction_id, total_fee]):
            logger.error("回调数据不完整")
            return generate_response("FAIL", "数据不完整")

        # 处理支付回调
        from base.plugins.customer.services.payment_service import wechat_pay_service

        # 转换金额单位（分 -> 元）
        amount = float(total_fee) / 100

        # 调用支付服务处理回调
        success = await wechat_pay_service.process_payment_callback(
            order_no=out_trade_no,
            transaction_id=transaction_id,
            transaction_type="wechat_pay",
            amount=amount,
            notify_data=notify_data
        )

        if success:
            logger.info(f"订单 {out_trade_no} 支付成功，已更新状态")
            return generate_response("SUCCESS", "OK")
        else:
            logger.error(f"订单 {out_trade_no} 处理失败")
            return generate_response("FAIL", "订单处理失败")

    except Exception as e:
        logger.error(f"处理微信支付回调异常: {str(e)}", exc_info=True)
        return generate_response("FAIL", str(e))


@router.get("/return")
async def wechat_pay_return(
    out_trade_no: Optional[str] = None,
    trade_no: Optional[str] = None,
    total_fee: Optional[str] = None,
    sign: Optional[str] = None,
    **kwargs
):
    """
    微信支付完成后的页面跳转接口

    用户在微信支付完成后会跳转到此接口
    此接口验证签名并重定向到前端页面
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        cfg = get_wechat_config()

        # 收集所有参数用于验证签名
        return_params = {
            "out_trade_no": out_trade_no,
            "trade_no": trade_no,
            "total_fee": total_fee,
            **kwargs
        }

        logger.info(f"收到微信支付返回: {return_params}")

        # 验证签名（如果提供）
        if sign:
            sign_params = return_params.copy()
            if not verify_wechat_sign(sign_params, cfg["api_key"]):
                logger.warning("返回签名验证失败，但仍继续处理")

        # 查询订单支付状态
        service = WeChatPayService()
        order_result = await service.query_order(out_trade_no) if out_trade_no else None

        # 判断支付状态
        payment_status = "unknown"
        if order_result and order_result.get("code") == 0:
            trade_state = order_result.get("data", {}).get("trade_state")
            if trade_state == "SUCCESS":
                payment_status = "success"
            elif trade_state in ["REFUND", "CLOSED", "REVOKED"]:
                payment_status = "failed"
            elif trade_state == "NOTPAY":
                payment_status = "pending"
            else:
                payment_status = "processing"

        # 构建前端返回URL
        from base.common.config import config
        frontend_url = config.get("aif2f.payment", "wechat_return_url", fallback="/payment/result")

        # 添加支付结果参数
        result_params = {
            "order_no": out_trade_no,
            "status": payment_status,
            "pay_type": "wechat"
        }

        if trade_no:
            result_params["trade_no"] = trade_no

        # 重定向到前端页面
        redirect_url = f"{frontend_url}?{urlencode(result_params)}"
        logger.info(f"重定向到: {redirect_url}")

        return RedirectResponse(url=redirect_url, status_code=302)

    except Exception as e:
        logger.error(f"处理微信支付返回异常: {str(e)}", exc_info=True)

        # 发生异常时也重定向到前端，带上错误信息
        from base.common.config import config
        frontend_url = config.get("aif2f.payment", "wechat_return_url", fallback="/payment/result")
        error_params = {
            "order_no": out_trade_no,
            "status": "error",
            "error": str(e),
            "pay_type": "wechat"
        }
        redirect_url = f"{frontend_url}?{urlencode(error_params)}"

        return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/result/{order_no}")
async def get_payment_result(order_no: str):
    """
    查询支付结果接口

    前端可调用此接口查询订单的支付状态
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        service = WeChatPayService()
        result = await service.query_order(order_no)

        if result.get("code") == 0:
            data = result.get("data", {})
            trade_state = data.get("trade_state", "UNKNOWN")

            # 映射微信支付状态
            status_map = {
                "SUCCESS": "success",
                "REFUND": "refund",
                "NOTPAY": "pending",
                "CLOSED": "closed",
                "REVOKED": "revoked",
                "USERPAYING": "paying",
                "PAYERROR": "error"
            }

            payment_status = status_map.get(trade_state, "unknown")

            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "order_no": order_no,
                    "status": payment_status,
                    "trade_state": trade_state,
                    "transaction_id": data.get("transaction_id"),
                    "total_fee": data.get("total_fee"),
                    "time_end": data.get("time_end")
                }
            }
        else:
            return {
                "code": -1,
                "msg": result.get("msg", "查询失败"),
                "data": {
                    "order_no": order_no,
                    "status": "unknown"
                }
            }

    except Exception as e:
        logger.error(f"查询支付结果异常: {str(e)}", exc_info=True)
        return {
            "code": -1,
            "msg": str(e),
            "data": {
                "order_no": order_no,
                "status": "error"
            }
        }
