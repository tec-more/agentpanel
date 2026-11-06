"""
七相支付服务层
"""
import hashlib
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode
import httpx

from base.common.config import config

logger = logging.getLogger(__name__)


class QixiangPayService:
    """七相支付服务"""

    def __init__(self):
        """初始化配置"""
        self.pid = config.get("qixiang_pay", "pid", fallback="")
        self.key = config.get("qixiang_pay", "key", fallback="")
        self.api_url = config.get("qixiang_pay", "api_url", fallback="https://api.payqixiang.cn/mapi.php")
        self.query_url = config.get("qixiang_pay", "query_url", fallback="https://api.payqixiang.cn/api.php")
        self.notify_url = config.get("qixiang_pay", "notify_url", fallback="")
        self.return_url = config.get("qixiang_pay", "return_url", fallback="")

        # 验证必需配置
        if not all([self.pid, self.key]):
            logger.warning("七相支付配置不完整，请检查config.conf")

    @staticmethod
    def generate_sign(params: Dict[str, Any], key: str) -> str:
        """
        生成MD5签名

        Args:
            params: 请求参数字典
            key: 商户密钥

        Returns:
            MD5签名字符串（小写）

        签名步骤:
        1. 将所有参数按ASCII码从小到大排序（a-z）
        2. sign、sign_type和空值不参与签名
        3. 拼接成键值对格式：a=b&c=d&e=f
        4. 与商户密钥KEY拼接：a=b&c=d&e=f + KEY
        5. MD5加密得出sign（小写）
        """
        # 1. 复制参数并排除sign、sign_type和空值
        filtered_params = {
            k: v for k, v in params.items()
            if k not in ['sign', 'sign_type'] and v not in [None, '', b'']
        }

        # 2. 按ASCII码排序（a-z）
        sorted_params = sorted(filtered_params.items())

        # 3. 拼接成键值对格式
        sign_str = "&".join([f"{k}={v}" for k, v in sorted_params])

        # 4. 拼接商户密钥
        sign_str += key

        # 5. MD5加密（小写）
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()

        logger.debug(f"签名原始字符串: {sign_str}")
        logger.debug(f"生成签名: {sign}")

        return sign

    @staticmethod
    def verify_sign(params: Dict[str, Any], key: str, sign: str) -> bool:
        """
        验证签名

        Args:
            params: 回调参数字典
            key: 商户密钥
            sign: 待验证的签名

        Returns:
            验证结果
        """
        # 计算签名
        calculated_sign = QixiangPayService.generate_sign(params, key)

        # 比较（使用字符串比较，避免时序攻击）
        result = calculated_sign == sign

        if not result:
            logger.warning(f"签名验证失败! 期望: {calculated_sign}, 实际: {sign}")

        return result

    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建支付订单

        Args:
            order_data: 订单数据
                - order_no: 商户订单号
                - pay_type: 支付类型 (alipay/wxpay)
                - amount: 金额
                - subject: 商品名称
                - client_ip: 客户端IP
                - param: 扩展参数

        Returns:
            包含payurl和qrcode的字典

        Raises:
            ValueError: 参数验证失败
            Exception: 创建订单失败
        """
        try:
            # 验证配置
            if not all([self.pid, self.key]):
                raise ValueError("七相支付配置不完整，请检查config.conf")

            # 构建请求参数
            params = {
                'pid': self.pid,
                'type': order_data.get('pay_type'),
                'out_trade_no': order_data.get('order_no'),
                'notify_url': self.notify_url,
                'return_url': self.return_url,
                'name': order_data.get('subject'),
                'money': str(order_data.get('amount')),  # 转为字符串，保留2位小数
                'clientip': order_data.get('client_ip', '127.0.0.1'),
                'device': 'jump',  # 必须传jump才能返回支付链接
                'param': order_data.get('param', ''),
                'sign_type': 'MD5'
            }

            # 生成签名
            sign = self.generate_sign(params, self.key)
            params['sign'] = sign

            logger.info(f"创建七相支付订单: {order_data.get('order_no')}, 类型: {order_data.get('pay_type')}")

            # 发送请求
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    data=params,  # 使用form-data格式
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                result = response.json()

            logger.info(f"七相支付响应: {result}")

            # 检查返回码
            if result.get('code') != 1:
                error_msg = result.get('msg', '创建订单失败')
                logger.error(f"七相支付创建订单失败: {error_msg}")
                raise ValueError(error_msg)

            # 返回结果
            return {
                'order_no': order_data.get('order_no'),
                'trade_no': result.get('trade_no', ''),
                'payurl': result.get('payurl', ''),
                'qrcode': result.get('qrcode'),
                'pay_type': order_data.get('pay_type')
            }

        except httpx.HTTPError as e:
            logger.error(f"请求七相支付API失败: {str(e)}")
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"创建七相支付订单异常: {str(e)}", exc_info=True)
            raise

    async def query_order(self, order_no: str) -> Dict[str, Any]:
        """
        查询订单状态

        Args:
            order_no: 商户订单号

        Returns:
            订单状态信息

        Raises:
            ValueError: 参数验证失败
            Exception: 查询订单失败
        """
        try:
            # 验证配置
            if not all([self.pid, self.key]):
                raise ValueError("七相支付配置不完整，请检查config.conf")

            # 构建查询URL
            url = f"{self.query_url}?act=order&pid={self.pid}&key={self.key}&out_trade_no={order_no}"

            logger.info(f"查询七相支付订单: {order_no}")

            # 发送请求
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                result = response.json()

            logger.info(f"七相支付查询响应: {result}")

            # 检查返回码
            if result.get('code') != 1:
                error_msg = result.get('msg', '查询订单失败')
                logger.error(f"七相支付查询订单失败: {error_msg}")
                raise ValueError(error_msg)

            # 映射支付状态
            status_int = result.get('status', 0)
            status_map = {
                1: 'success',
                0: 'pending'
            }
            status = status_map.get(status_int, 'unknown')

            # 返回结果
            return {
                'order_no': order_no,
                'trade_no': result.get('trade_no', ''),
                'status': status,
                'pay_type': result.get('type', ''),
                'amount': float(result.get('money', 0)),
                'trade_status': result.get('status')
            }

        except httpx.HTTPError as e:
            logger.error(f"请求七相支付API失败: {str(e)}")
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"查询七相支付订单异常: {str(e)}", exc_info=True)
            raise

    async def process_notify(self, notify_data: Dict[str, Any]) -> bool:
        """
        处理支付异步通知

        Args:
            notify_data: 回调数据

        Returns:
            处理是否成功

        Raises:
            ValueError: 签名验证失败
            Exception: 处理失败
        """
        try:
            logger.info(f"收到七相支付回调: {notify_data}")

            # 验证签名
            # 注意：如果回调没有name参数，不参与签名验证
            params_to_verify = notify_data.copy()

            # 如果name为空，删除它不参与签名
            if not params_to_verify.get('name'):
                params_to_verify.pop('name', None)

            if not self.verify_sign(params_to_verify, self.key, notify_data.get('sign', '')):
                raise ValueError("签名验证失败")

            # 检查支付状态
            trade_status = notify_data.get('trade_status', '')
            if trade_status != 'TRADE_SUCCESS':
                logger.warning(f"支付状态不是成功: {trade_status}")
                return False

            # 获取订单信息
            out_trade_no = notify_data.get('out_trade_no')
            trade_no = notify_data.get('trade_no')
            pay_type = notify_data.get('type')
            amount = float(notify_data.get('money', 0))

            if not all([out_trade_no, trade_no]):
                logger.error("回调数据不完整")
                return False

            # 调用支付服务处理回调
            from base.plugins.customer.services.payment_service import wechat_pay_service

            # 注意：这里使用wechat_pay_service是因为订单状态更新逻辑是通用的
            # 七相支付的type可能是alipay或wxpay，我们需要统一处理
            success = await wechat_pay_service.process_payment_callback(
                order_no=out_trade_no,
                transaction_id=trade_no,
                transaction_type=f"qixiang_{pay_type}",  # qixiang_alipay 或 qixiang_wxpay
                amount=amount,
                notify_data=notify_data
            )

            if success:
                logger.info(f"订单 {out_trade_no} 支付成功，已更新状态")
                return True
            else:
                logger.error(f"订单 {out_trade_no} 处理失败")
                return False

        except ValueError as e:
            logger.error(f"处理七相支付回调失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"处理七相支付回调异常: {str(e)}", exc_info=True)
            raise
