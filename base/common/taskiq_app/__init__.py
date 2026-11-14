"""taskiq 独立调度与消费服务模块（M2+M3 终态）。

- 单 broker（`AioPikaBroker`，jobs/events 两队列同 broker，专用 vhost）。
- 单 worker 进程消费 jobs + events（无状态，可多副本横向扩）。
- taskiq-beat 单实例写 `scheduler_job` 调度表，worker 经 `@broker.task` 注册真实任务。
- M2：旧进程内 `JobScheduler` 已删除，beat 是唯一调度源（reconciler 周期重扫，
  插件启停 ≤ reconcile_interval 生效）。
- M3：旧 `ConsumerWorker` 与发布端内存通道已删除。发布 = EventRecord(published)
  + `dispatch.kiq` 入 `ap.events`（fail-closed）；worker 的 `dispatch` 任务按进程内
  订阅注册表执行 handler（幂等/重试/终态见 events.py），运行期插件启停由
  worker 周期 `event_center.resync()` 收敛。

本包不被 app 业务代码 import（broker 客户端除外：EventBusAdapter.publish 经
`broker.ensure_started` 惰性建连）；由 compose 的 taskiq-beat / taskiq-worker
服务经 CLI 加载。
"""
