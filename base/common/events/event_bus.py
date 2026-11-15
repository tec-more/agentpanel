"""全局事件总线单例（M3 后）。

旧的进程内内存总线（EventBus 类，发布即同步执行订阅者）已随消费外迁删除。
2026-11-15 起发布改为 Transactional Outbox：只在 DB 事务内写
``EventRecord(status=pending)``，由 ``platform:outbox_relay`` 异步投递进
``ap.events``，执行全部发生在 taskiq worker 进程。app 进程不再建立消息中间件连接。
本模块只保留 ``event_bus`` 单例（EventBusAdapter），供发布端调用方与
订阅注册（@ap_subscribe 声明的注册函数 / bind_manual → worker 消费）使用。
"""
from base.common.events.event_bus_adapter import EventBusAdapter

event_bus = EventBusAdapter()
