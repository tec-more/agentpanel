"""销售插件作业：过期订单检查（单轮，W2-3）。

由 ``manifest.jobs`` 声明，调度器按 300s 间隔驱动；while 循环、取消与异常处理
统一由平台调度器承担，本模块只保留一行业务调用与原输出文案。
"""


async def run() -> None:
    """检查并取消过期订单（原 cancel_expired_orders_task 的单轮逻辑）。"""
    from base.plugins.sales.services.order_service import OrderService

    cancelled_count = await OrderService.cancel_expired_orders()
    if cancelled_count > 0:
        print(f"[定时任务] 已取消 {cancelled_count} 个过期订单")
