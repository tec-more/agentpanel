"""
支付交易记录模型
"""

from enum import Enum
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class TransactionStatus(str, Enum):
    """交易状态"""
    PENDING = "pending"      # 待处理
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    REFUNDED = "refunded"    # 已退款


class PaymentTransaction(BaseModel, TimestampMixin):
    verbose_name = "支付交易"
    """支付交易记录表"""

    order = fields.ForeignKeyField(
        "models.CustomerOrder",
        related_name="transactions",
        on_delete=fields.CASCADE,
        null=True
    )
    transaction_id = fields.CharField(max_length=128, unique=True, description="交易ID")
    transaction_type = fields.CharField(max_length=20, description="交易类型(wechat/alipay)")
    amount = fields.DecimalField(max_digits=10, decimal_places=2, description="交易金额")
    status = fields.CharEnumField(
        TransactionStatus,
        max_length=20,
        default=TransactionStatus.PENDING,
        description="交易状态"
    )
    notify_data = fields.JSONField(description="回调通知数据")
    processed_at = fields.DatetimeField(auto_now_add=True, description="处理时间")

    class Meta:
        table = "customer_payment_transaction"
        ordering = ["-processed_at"]

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.status}"

    async def to_dict(self):
        """转换为字典（处理 Decimal 类型）"""
        # 支付方式映射
        payment_type_map = {
            'wxpay': '微信支付',
            'wechat': '微信支付',
            'alipay': '支付宝',
            'qixiang_wxpay': '七相-微信',
            'qixiang_alipay': '七相-支付宝',
        }

        trans_type = self.transaction_type
        payment_display = payment_type_map.get(trans_type, trans_type)

        # 支付方式标签和颜色
        if trans_type in ['wxpay', 'wechat', 'qixiang_wxpay']:
            payment_tag = 'success'
            payment_icon = 'wechat'
        elif trans_type in ['alipay', 'qixiang_alipay']:
            payment_tag = 'primary'
            payment_icon = 'alipay'
        else:
            payment_tag = 'info'
            payment_icon = 'default'

        data = {
            "id": self.id,
            "order_id": self.order_id,
            "transaction_id": self.transaction_id,
            "qixiang_trade_no": self.transaction_id,  # 订单号（别名）
            "transaction_type": self.transaction_type,
            "payment_method_display": payment_display,  # 中文显示
            "payment_method_tag": payment_tag,  # 前端标签颜色
            "payment_method_icon": payment_icon,  # 前端图标
            "amount": float(self.amount) if self.amount else 0,
            "status": self.status.value if hasattr(self.status, 'value') else self.status,
            "notify_data": self.notify_data,
            "processed_at": self.processed_at.strftime("%Y-%m-%d %H:%M:%S") if self.processed_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
        return data
