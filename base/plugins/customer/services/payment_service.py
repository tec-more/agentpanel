"""
支付服务 - 微信支付和支付宝
"""

from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import json
from decimal import Decimal

from base.plugins.customer.models import (
    PaymentTransaction,
    TransactionStatus,
    PaymentMethod
)
from base.plugins.sales.models.order import CustomerOrder, PaymentStatus, OrderStatus
from base.plugins.customer.models.membership import MembershipLevel
class PaymentService:
    model = "payment"
    """支付服务基类"""

    def __init__(self):
        self.config = {}
        # TODO: 从配置文件或数据库加载支付配置

    async def create_order(
        self,
        customer_id: int,
        membership_level_id: int,
        payment_method: str,
        client_ip: str = None
    ) -> CustomerOrder:
        """创建支付订单（适配新架构，使用 OrderService）"""
        # 获取会员等级信息
        level = await MembershipLevel.get_or_none(id=membership_level_id)
        if not level:
            raise ValueError("会员等级不存在")

        # 使用新的 OrderService 创建订单
        from base.plugins.sales.services.order_service import OrderService

        order = await OrderService.create_membership_order(
            customer_id=customer_id,
            membership_level_id=membership_level_id,
            payment_method=payment_method,
            client_ip=client_ip
        )

        return order

    async def get_order(self, order_no: str) -> Optional[CustomerOrder]:
        """获取订单"""
        # 新架构：预加载 customer 和 items 关系
        return await CustomerOrder.get_or_none(order_no=order_no).prefetch_related(
            "customer", "items"
        )

    async def cancel_order(self, order_no: str) -> bool:
        """取消订单"""
        order = await self.get_order(order_no)
        if not order or order.payment_status != PaymentStatus.PENDING:
            return False

        order.payment_status = PaymentStatus.EXPIRED
        order.order_status = OrderStatus.CANCELLED
        await order.save()
        return True

    async def check_order_expired(self) -> None:
        """检查并更新过期订单（定时任务调用）"""
        expired_orders = await CustomerOrder.filter(
            payment_status=PaymentStatus.PENDING
        ).filter(expire_time__lt=datetime.now())

        for order in expired_orders:
            order.payment_status = PaymentStatus.EXPIRED
            order.order_status = OrderStatus.CANCELLED
            await order.save()

    async def process_payment_callback(
        self,
        order_no: str,
        transaction_id: str,
        transaction_type: str,
        amount: float,
        notify_data: Dict[str, Any]
    ) -> bool:
        """处理支付回调（适配新订单架构）"""
        # 获取订单（包含明细）
        order = await self.get_order(order_no)
        if not order:
            print(f"[PaymentCallback] 订单不存在: {order_no}")
            return False

        # 检查订单状态
        if order.payment_status == PaymentStatus.PAID:
            print(f"[PaymentCallback] 订单已支付，跳过: {order_no}")
            return True  # 已处理，避免重复

        # 验证金额（使用新字段 final_amount）
        if float(order.final_amount) != amount:
            print(f"[PaymentCallback] 金额不匹配! 期望: {order.final_amount}, 实际: {amount}")
            return False

        # 创建交易记录
        transaction = await PaymentTransaction.create(
            order_id=order.id,
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            amount=Decimal(str(amount)),
            status=TransactionStatus.SUCCESS,
            notify_data=notify_data
        )
        print(f"[PaymentCallback] 创建交易记录成功: {transaction.id}")

        # 更新订单状态
        order.payment_status = PaymentStatus.PAID
        order.trade_no = transaction_id
        order.pay_time = datetime.now()
        await order.save()
        print(f"[PaymentCallback] 订单状态更新成功: {order_no} -> PAID")

        # 处理订单完成后的业务逻辑
        try:
            from base.plugins.sales.models.order import OrderItem

            # 获取订单明细
            items = await OrderItem.filter(order_id=order.id)
            print(f"[PaymentCallback] 订单 {order_no} 有 {len(items)} 个明细")

            for idx, item in enumerate(items):
                print(f"\n[PaymentCallback] === 处理明细[{idx+1}] ===")
                print(f"[PaymentCallback] product_id: {item.product_id}")
                print(f"[PaymentCallback] product_type: {item.product_type}")
                print(f"[PaymentCallback] product_name: {item.product_name}")
                print(f"[PaymentCallback] extra_info: {item.extra_info}")
                print(f"[PaymentCallback] extra_info type: {type(item.extra_info)}")

                # 1. 更新产品库存和销售数量
                if item.product_id:
                    from base.plugins.product.models.product import Product
                    product = await Product.get_or_none(id=item.product_id)
                    if product:
                        # 减少库存
                        new_stock = product.stock - item.quantity
                        if new_stock < 0:
                            print(f"[PaymentCallback] 警告: 产品 {product.name} 库存不足! 当前库存: {product.stock}, 购买数量: {item.quantity}")
                        else:
                            product.stock = new_stock

                        # 增加销售数量
                        product.sales_count = (product.sales_count or 0) + item.quantity
                        await product.save()
                        print(f"[PaymentCallback] 产品库存更新成功: {product.name}, 库存: {product.stock}, 销量: {product.sales_count}")
                    else:
                        print(f"[PaymentCallback] 警告: 产品ID {item.product_id} 不存在")

                # 2. 处理会员类型的商品（更新用户时长）
                # 支持 "membership" 和 "hours" 两种充值类商品
                if item.product_type in ["membership", "hours"]:
                    print(f"[PaymentCallback] 检测到充值类商品: {item.product_type}")

                    extra = item.extra_info
                    membership_level_id = None
                    total_hours = None

                    # 尝试从 extra_info 获取参数
                    if extra:
                        print(f"[PaymentCallback] extra_info内容: {extra}")

                        # 支持字典和JSON字符串
                        if isinstance(extra, str):
                            import json
                            try:
                                extra = json.loads(extra)
                                print(f"[PaymentCallback] 解析JSON字符串: {extra}")
                            except:
                                print(f"[PaymentCallback] ERROR: extra_info不是有效的JSON字符串")
                                extra = {}

                        membership_level_id = extra.get("membership_level_id")
                        total_hours = extra.get("total_hours")

                        print(f"[PaymentCallback] 从extra_info提取参数: membership_level_id={membership_level_id}, total_hours={total_hours}")

                    # 如果 extra_info 缺失，从产品表获取（统一从产品表取值，不区分类型）
                    if (not membership_level_id or not total_hours) and item.product_id:
                        print(f"[PaymentCallback] extra_info不完整，从产品表获取数据...")
                        from base.plugins.product.models.product import Product
                        product = await Product.get_or_none(id=item.product_id)
                        if product:
                            # 统一从产品表获取充值时长（产品表是唯一数据源）
                            if not total_hours:
                                recharge_hours = product.recharge_hours or 0
                                bonus_hours = product.bonus_hours or 0
                                total_hours = recharge_hours + bonus_hours
                                print(f"[PaymentCallback] 从产品表获取时长: {total_hours}h (recharge={recharge_hours}, bonus={bonus_hours})")

                            if not membership_level_id:
                                membership_level_id = product.membership_level_id
                                print(f"[PaymentCallback] 从产品表获取会员等级ID: {membership_level_id}")

                                # 如果产品没有设置会员等级，根据产品名称自动识别（与订单创建逻辑保持一致）
                                if not membership_level_id:
                                    product_name = product.name.lower()
                                    from base.plugins.customer.models.membership import MembershipLevel
                                    if "svip" in product_name:
                                        svip_level = await MembershipLevel.filter(
                                            level_type="svip"
                                        ).first()
                                        membership_level_id = svip_level.id if svip_level else 3
                                        print(f"[PaymentCallback] 自动识别为SVIP会员，等级ID: {membership_level_id}")
                                    elif "vip" in product_name and "svip" not in product_name:
                                        vip_level = await MembershipLevel.filter(
                                            level_type="vip"
                                        ).first()
                                        membership_level_id = vip_level.id if vip_level else 2
                                        print(f"[PaymentCallback] 自动识别为VIP会员，等级ID: {membership_level_id}")
                                    else:
                                        # 默认使用普通会员
                                        regular_level = await MembershipLevel.filter(
                                            level_type="regular"
                                        ).first()
                                        membership_level_id = regular_level.id if regular_level else 1
                                        print(f"[PaymentCallback] 使用默认普通会员等级ID: {membership_level_id}")
                        else:
                            print(f"[PaymentCallback] WARNING: 产品ID {item.product_id} 不存在")

                    print(f"[PaymentCallback] 最终参数: membership_level_id={membership_level_id}, total_hours={total_hours}")
                    print(f"[PaymentCallback] 说明: 充值时长统一从产品表获取，会员等级用于折扣计算")

                    if membership_level_id and total_hours:
                        print(f"\n{'='*70}")
                        print(f"[PaymentCallback] 开始处理会员充值")
                        print(f"[PaymentCallback] 客户ID: {order.customer_id}")
                        print(f"[PaymentCallback] 充值时长: {total_hours} 小时")
                        print(f"[PaymentCallback] 会员等级ID: {membership_level_id}")
                        print(f"{'='*70}\n")

                        from base.plugins.customer.services.membership_service import MembershipService
                        from base.plugins.customer.models.customer_membership import CustomerMembership

                        # 充值前查询当前会员信息
                        old_membership = await MembershipService.get_customer_membership(order.customer_id)
                        if old_membership:
                            old_membership_level = old_membership.membership_level.level_type if old_membership.membership_level else "unknown"
                            print(f"[PaymentCallback] 充值前状态:")
                            print(f"[PaymentCallback]   会员ID: {old_membership.id}")
                            print(f"[PaymentCallback]   充值总时长: {old_membership.total_hours} 小时")
                            print(f"[PaymentCallback]   Fibonacci动态等级: Lv{old_membership.level}")
                            print(f"[PaymentCallback]   已用时长: {float(old_membership.used_hours):.2f} 小时")
                            print(f"[PaymentCallback]   剩余时长: {float(old_membership.remaining_hours):.2f} 小时")
                            print(f"[PaymentCallback]   会员类别: {old_membership_level}")
                            print(f"[PaymentCallback]   激活状态: {'是' if old_membership.is_active else '否'}")
                        else:
                            print(f"[PaymentCallback] 充值前状态: 无会员记录（新用户）")

                        print(f"\n[PaymentCallback] 开始创建/更新会员...\n")

                        # 执行充值操作
                        membership = await MembershipService.create_customer_membership(
                            customer_id=order.customer_id,
                            membership_level_id=membership_level_id,
                            recharge_hours=total_hours
                        )

                        if membership:
                            membership_level = membership.membership_level.level_type if membership.membership_level else "unknown"
                            print(f"\n{'='*70}")
                            print(f"[PaymentCallback] 会员创建/更新成功!")
                            print(f"{'='*70}")
                            print(f"[PaymentCallback] 充值后状态:")
                            print(f"[PaymentCallback]   会员ID: {membership.id}")
                            print(f"[PaymentCallback]   充值总时长: {membership.total_hours} 小时")
                            print(f"[PaymentCallback]   Fibonacci动态等级: Lv{membership.level}")
                            print(f"[PaymentCallback]   已用时长: {float(membership.used_hours):.2f} 小时")
                            print(f"[PaymentCallback]   剩余时长: {float(membership.remaining_hours):.2f} 小时")
                            print(f"[PaymentCallback]   会员类别: {membership_level}")
                            print(f"[PaymentCallback]   激活状态: {'是' if membership.is_active else '否'}")
                            print(f"[PaymentCallback]   VIP状态: {'是' if membership.is_vip else '否'}")

                            # 计算变化
                            if old_membership:
                                old_membership_level = old_membership.membership_level.level_type if old_membership.membership_level else "unknown"
                                total_hours_diff = membership.total_hours - old_membership.total_hours
                                remaining_diff = float(membership.remaining_hours) - float(old_membership.remaining_hours)
                                level_diff = membership.level - old_membership.level

                                print(f"\n[PaymentCallback] 变化统计:")
                                print(f"[PaymentCallback]   充值总时长: +{total_hours_diff} 小时")
                                print(f"[PaymentCallback]   剩余时长: {remaining_diff:+.2f} 小时")
                            if level_diff > 0:
                                print(f"[PaymentCallback]   Fibonacci动态等级提升: Lv{old_membership.level} → Lv{membership.level}")
                            elif level_diff == 0:
                                print(f"[PaymentCallback]   Fibonacci动态等级保持: Lv{membership.level}")
                            else:
                                print(f"[PaymentCallback]   Fibonacci动态等级: Lv{old_membership.level} → Lv{membership.level}")

                            if membership_level != old_membership_level:
                                print(f"[PaymentCallback]   会员类别变化: {old_membership_level} → {membership_level}")
                            else:
                                print(f"[PaymentCallback]   会员类别: {membership_level}")

                            # 验证计算公式
                            expected_remaining = membership.total_hours - float(membership.used_hours)
                            print(f"\n[PaymentCallback] 验证计算公式:")
                            print(f"[PaymentCallback]   公式: remaining_hours = total_hours - used_hours")
                            print(f"[PaymentCallback]   计算: {float(membership.total_hours)} - {float(membership.used_hours):.2f} = {expected_remaining:.2f}")
                            print(f"[PaymentCallback]   实际: {float(membership.remaining_hours):.2f}")

                            if abs(float(membership.remaining_hours) - expected_remaining) < 0.01:
                                print(f"[PaymentCallback]   计算正确!")
                            else:
                                print(f"[PaymentCallback]   计算有误! 差异: {abs(float(membership.remaining_hours) - expected_remaining):.2f}")

                            # 验证Fibonacci动态等级计算
                            from base.plugins.customer.services.membership_service import fibonacci_service
                            expected_level = fibonacci_service.get_level_from_hours(membership.total_hours)
                            print(f"\n[PaymentCallback] 验证Fibonacci动态等级计算:")
                            print(f"[PaymentCallback]   Fibonacci算法: level = get_level_from_hours({membership.total_hours})")
                            print(f"[PaymentCallback]   计算等级: Lv{expected_level}")
                            print(f"[PaymentCallback]   实际等级: Lv{membership.level}")

                            if membership.level == expected_level:
                                print(f"[PaymentCallback]   Fibonacci动态等级正确!")
                            else:
                                print(f"[PaymentCallback]   Fibonacci动态等级有误!")

                            # 从数据库重新查询验证
                            print(f"\n[PaymentCallback] 重新查询验证...")
                            verified_membership = await CustomerMembership.get_or_none(
                                customer_id=order.customer_id,
                                is_active=True
                            ).prefetch_related("membership_level")

                            if verified_membership:
                                verified_membership_level = verified_membership.membership_level.level_type if verified_membership.membership_level else "unknown"
                                print(f"[PaymentCallback]   数据库验证:")
                                print(f"[PaymentCallback]     充值总时长: {verified_membership.total_hours} 小时")
                                print(f"[PaymentCallback]     Fibonacci动态等级: Lv{verified_membership.level}")
                                print(f"[PaymentCallback]     剩余时长: {float(verified_membership.remaining_hours):.2f} 小时")
                                print(f"[PaymentCallback]     会员类别: {verified_membership_level}")

                                if (verified_membership.total_hours == membership.total_hours and
                                    verified_membership.level == membership.level):
                                    print(f"[PaymentCallback]   数据库保存成功!")
                                else:
                                    print(f"[PaymentCallback]   数据库数据不一致!")
                            else:
                                print(f"[PaymentCallback]   数据库查询失败!")

                            print(f"{'='*70}\n")
                        else:
                            print(f"\n[PaymentCallback] 会员创建失败! 返回 None\n")
                    else:
                        print(f"[PaymentCallback] ERROR: 缺少必要参数! membership_level_id={membership_level_id}, total_hours={total_hours}")
                else:
                    print(f"[PaymentCallback] 跳过非充值类商品: {item.product_type}")

            print(f"\n[PaymentCallback] === 所有明细处理完成 ===\n")

        except Exception as e:
            print(f"[PaymentCallback] 处理订单业务逻辑失败: {e}")
            import traceback
            traceback.print_exc()
            # 业务处理失败不影响支付成功状态

        return True


class WechatPayService(PaymentService):
    """微信支付服务"""

    def __init__(self):
        super().__init__()
        # TODO: 配置微信支付参数
        self.app_id = ""  # 从配置读取
        self.mch_id = ""  # 商户号
        self.api_key = ""  # API密钥
        self.notify_url = ""  # 回调地址

    async def create_payment(
        self,
        order: CustomerOrder,
        client_ip: str
    ) -> Dict[str, Any]:
        """
        创建微信支付
        返回支付二维码URL或支付参数
        """
        # TODO: 调用微信支付统一下单API
        # 这里是示例代码框架

        # 1. 构造请求参数
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "nonce_str": self._generate_nonce(),
            "body": f"{order.membership_level.name} - {order.total_hours}小时",
            "out_trade_no": order.order_no,
            "total_fee": int(float(order.amount) * 100),  # 单位：分
            "spbill_create_ip": client_ip or "127.0.0.1",
            "notify_url": self.notify_url,
            "trade_type": "NATIVE"  # Native支付（扫码）
        }

        # 2. 生成签名
        params["sign"] = self._generate_sign(params)

        # 3. 调用微信API（需要使用requests等HTTP客户端）
        # response = await self._call_wechat_api(params)

        # 4. 返回支付信息
        return {
            "order_no": order.order_no,
            "amount": str(order.amount),
            "qr_code": "weixin://wxpay/bizpayurl?pr=xxxxx",  # 实际从微信API返回
            "expire_time": order.expire_time
        }

    def _generate_nonce(self) -> str:
        """生成随机字符串"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成签名"""
        # 按照微信支付规则生成签名
        sorted_params = sorted(params.items())
        sign_str = "&".join([f"{k}={v}" for k, v in sorted_params if v != ""])
        sign_str += f"&key={self.api_key}"

        return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()

    async def verify_notify(self, notify_data: Dict[str, Any]) -> bool:
        """验证回调签名"""
        # TODO: 实现签名验证
        return True


class AlipayService(PaymentService):
    """支付宝支付服务"""

    def __init__(self):
        super().__init__()
        # TODO: 配置支付宝参数
        self.app_id = ""  # 应用ID
        self.private_key = ""  # 应用私钥
        self.public_key = ""  # 支付宝公钥
        self.notify_url = ""  # 异步通知地址

    async def create_payment(
        self,
        order: CustomerOrder,
        client_ip: str
    ) -> Dict[str, Any]:
        """
        创建支付宝支付
        返回支付表单或二维码
        """
        # TODO: 调用支付宝支付API
        # 这里是示例代码框架

        # 1. 构造请求参数
        params = {
            "app_id": self.app_id,
            "method": "alipay.trade.precreate",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": json.dumps({
                "out_trade_no": order.order_no,
                "total_amount": str(order.amount),
                "subject": f"{order.membership_level.name} - {order.total_hours}小时",
                "timeout_express": "15m"  # 15分钟过期
            })
        }

        # 2. 生成签名
        params["sign"] = self._generate_sign(params)

        # 3. 调用支付宝API
        # response = await self._call_alipay_api(params)

        # 4. 返回支付信息
        return {
            "order_no": order.order_no,
            "amount": str(order.amount),
            "qr_code": "https://qr.alipay.com/xxxxx",  # 实际从支付宝API返回
            "expire_time": order.expire_time
        }

    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """生成签名"""
        # 按照支付宝规则生成RSA签名
        # TODO: 使用RSA私钥签名
        return ""

    async def verify_notify(self, notify_data: Dict[str, Any]) -> bool:
        """验证回调签名"""
        # TODO: 实现RSA签名验证
        return True


# 创建服务实例
wechat_pay_service = WechatPayService()
alipay_service = AlipayService()


def get_payment_service(method: str) -> PaymentService:
    """根据支付方式获取对应的服务"""
    if method == PaymentMethod.WECHAT:
        return wechat_pay_service
    elif method == PaymentMethod.ALIPAY:
        return alipay_service
    else:
        raise ValueError(f"不支持的支付方式: {method}")
