"""销售插件作业：过期订单检查（单轮）。

声明与实装同处本文件：``@broker.task`` 上的 ``ap_schedule`` 即调度周期，
由 ``base.common.taskiq_app.discovery`` 扫描发现，beat 据此写调度行。
while 循环、取消与异常处理统一由平台调度器承担，本模块只保留单轮业务调用。
"""


from base.common.taskiq_app.broker import broker


# 声明即注册：调度周期、依赖、说明全部随 @broker.task 一起声明，
# 由 base.common.taskiq_app.discovery 扫描 ap_* 标签发现（不再写 manifest.jobs）。
@broker.task(
    task_name="sales:cancel_expired_orders",
    queue_name="ap.jobs",
    ap_schedule=300,
    ap_description="每5分钟检查并取消过期订单",
)
async def run() -> None:
    """检查并取消过期订单（原 cancel_expired_orders_task 的单轮逻辑）。"""
    from base.plugins.sales.services.order_service import OrderService

    cancelled_count = await OrderService.cancel_expired_orders()
    if cancelled_count > 0:
        print(f"[定时任务] 已取消 {cancelled_count} 个过期订单")
