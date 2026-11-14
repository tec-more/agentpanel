# AgentPanel 调度服务与消费服务独立化（Celery + RabbitMQ + Redis）可行方案

- 日期：2026-11-14
- 状态：**方案待评审，尚未实施任何代码/配置改动**
- 范围：把 `job_scheduler`（调度）与 `ConsumerWorker`（消费）从 L2 `app` 进程中拆出为独立进程/容器，引入 Celery，RabbitMQ 作 broker、Redis 作 result backend / 锁 / 幂等 / 调度状态。
- 依据：对 `base/common/jobs/`、`base/common/events/`、`base/core/events/`、`base/start.py`、`run.py`、`deploy/**`、`tests/regression_*.py` 的只读调研。文中行号为调研时点，实施时需复核。
- 安全约定：本文只列配置**键名**，不记录 `config.conf` / `.env` / `secrets/` 的任何取值或凭据。

---

## 0. 结论摘要与待拍板项

**结论：可行，且现有基础设施无需新增中间件。** RabbitMQ（`deploy/rabbitmq/docker-compose.yml`，3.13-management）与 Redis（`deploy/app/docker-compose.yml`，7-alpine）均已部署并接入 `app_default` 网络；`requirements.txt` 已有 `aio-pika>=10.0.1`、`redis>=5.0.0`；缺的只有 Celery/Kombu 依赖与三个新进程。

推荐目标态：**RabbitMQ 独立 vhost 作 Celery broker + Redis 作 backend/锁/幂等 + 1 个 Beat（调度）+ 2 类 Worker（作业 / 事件）**，L2 `app` 退化为纯 HTTP + 生产者。分两阶段灰度，旧实现保留一个观察期，`mode` 开关可一键回滚。

**需要用户先拍板的 4 个决策：**

| # | 决策 | 推荐 | 影响 |
|---|---|---|---|
| D1 | 事件消费是否也交给 Celery | **是（统一方案 B）**，但放在第二阶段 | 选「仅物理搬迁 ConsumerWorker」（方案 A）则改动最小、但两套消费框架长期并存 |
| D2 | 定时作业的动态装卸语义 | **自定义 Beat Scheduler 读 manifest**，保留 `AC-PLR-15-1` | 选静态 `beat_schedule` 则插件启用/禁用作业需重启 beat，属可接受偏差但需书面确认 |
| D3 | 现有业务事件 exchange 是否保留 | **灰度期保留双写**，观察期后下线 | 保留可回滚；不保留则一步到位但无快速回退路径 |
| D4 | 一期是否放开 `UVICORN_WORKERS>1` | **不放开，仍为 1** | 拆分后理论上可放开，但 quota 进程内降级态、`_degraded_hooks`、WebSocket 连接表仍是进程内状态，需单列二期评估 |

---

## 1. 现状事实与拆分动因

### 1.1 当前拓扑（单进程内耦合）

`run.py:108-119` 以 uvicorn 启动 `base.app_wrapper:app`；`base/start.py` 的 `lifespan`（55-202 行）在**同一事件循环**内装配：

| 顺序 | 行号 | 组件 | 形态 |
|---|---|---|---|
| 1 | 75 | Tortoise `init_data()` | 进程内连接池 |
| 2 | 79-80 | `RedisCache.get_instance()` 预热 | 进程内单例 |
| 3 | 84 | `initialize_event_center()` | 进程内注册表 |
| 4 | 87-93 | `event_bus.initialize()` | 进程内单例 + RabbitMQ 连接 |
| 5 | 96-110 | `ConsumerWorker.start()` | `asyncio` Task 消费 |
| 6 | 116-120 | 插件系统 `load_enabled_plugins()` | 进程内路由表/菜单/权限 |
| 7 | **124** | **`job_scheduler.start_all()`** | 6 个 `asyncio.Task` |
| 8 | 127-134 | Prometheus push worker | `asyncio.Task` |

关闭顺序（`finally`，142-200 行）：`job_scheduler.shutdown()` → background tasks → `consumer_worker.stop()`（外层 12s / 内层 drain 8s）→ `event_bus.shutdown()` → `plugin_manager.shutdown()` → `Tortoise.close_connections()` → WebSocket 清理。该顺序被 `tests/regression_pending.py:462-465` 以字符串下标断言锁定。

### 1.2 六个作业的来源与语义

`base/common/jobs/scheduler.py` 的 `JobScheduler` 是进程内单例：`JobSpec`（`owner`/`name`/`handler`/`interval_seconds`/`interval_ref`/`requires_plugins`）+ 每作业一个 `asyncio.Task`，`_run_loop`（206-230 行）为「先 sleep → 执行 → 异常记日志不中断」的固定间隔循环。

| owner | name | 基础间隔 | 特殊语义 |
|---|---|---|---|
| `__platform__` | `quota_reconcile` | 60s | 代码注册 |
| `__platform__` | `quota_hold_cleanup` | 60s | 代码注册 |
| `sales` | `cancel_expired_orders` | 300s | — |
| `audit` | `audit_cleanup` | 86400s | handler 内每轮重读 `resolve_retention_days()` |
| `harness` | `gateway_reconcile` | 600s | **`interval_ref` 每轮重读 manifest 配置，热生效**；handler 内自查开关 |
| `customer` | `update_membership_data` | 600s | `requires_plugins=["llm"]` 依赖门控 |

`plugin_contract.validate_jobs()`（52-100 行）只验格式不 import；`plugin_manager._sync_plugin_jobs()`（806-822 行）把 enable/disable 接到 `start_plugin/stop_plugin`，运行期禁用立即 `task.cancel()` + `wait_for(2s)` 收尾。

**能力缺口**：无持久化、无分布式锁/选主、无错过补偿、无重试上限与退避、无并发上限、无作业级指标。多 worker 部署下每个进程各跑全套作业（`run.py:38-45` 因此以 H-1 硬约束禁止生产多 worker）。

### 1.3 消费链路的两个决定性事实

**事实 A —— 发布即双通道执行。** `event_bus_adapter.py:70-113`：一次 `publish` 先发 RabbitMQ（`routing_key=event_name`，写 `EventRecord(status="published")`），**第 113 行无条件 `await self._memory_bus.publish(...)` 同步执行全部内存订阅**；而 `subscribe()`（131-136 行）把同一 handler 同时注册进内存总线与 `_handler_registry`，`ConsumerWorker._process_message:86` 又用 `_adapter.get_handlers()` 取同一批 handler。即：当前一次事件，handler 在 app 进程内执行 1 次、在 MQ 消费路径再执行 1 次。

> 拆分后若只把 `ConsumerWorker` 搬走、不关内存通道，事件仍会执行两次；若 app 与 worker 都订阅，则是三次。**「发布端在独立模式下不再执行内存订阅」是本方案第一正确性前提。**

**事实 B —— 消费端无幂等。** `consumer_worker.py:84-137` 只把 `EventRecord` 状态改为 `consuming / consumed / failed / dead_letter`，**没有「已 consumed 则跳过 handler」判断**。发布侧幂等仅在 `EventCenter._idempotency` 进程内 dict（TTL 300s，`registry.py:24,197-205`），跨进程失效。`event_uuid` 有 DB unique 约束，但重投消息仍会重复执行副作用。这正是工作记忆中 W3-1 待办。

其它事实：
- `dead_letter` 分支（111-117 行）只改 DB 状态，之后正常 ack，**未 reject 进 DLQ**；`next_retry_at` 写入后无任何调度器消费，实际靠 `nack(requeue=True)` 立即重入主队列。
- DLQ/主队列拓扑在 `connection_manager.py:62-92`：主 exchange TOPIC、主队列 `<RABBITMQ_QUEUE_PREFIX>.main` 绑定 `routing_key="#"`、声明 DLX。
- `EventSubscription` 表已有 `handler_ref`、`is_enabled`、`source(declared/manual)`，`EventCenter.sync_plugin()` 随插件启停 upsert；`manual` 订阅有 `guarded` 包装按 DB 开关跳过。
- `/v1/events/monitor/*` 的队列深度/consumer 状态探针直接读 `aio_pika` 连接对象；`/v1/events/replay/*` 通过重新 `publish` 重放。
- Redis 与事件链路**零耦合**（只用于缓存、租约短缓存、quota Lua 并发槽、健康探针）；`[redis] db` 为单库，键需规划前缀。
- 回归脚本 `tests/regression_pending.py` 的 B3（`task_count()==6`）、B4/B5（本地 Task cancel/恢复）、B6（`_sync_plugin_jobs` 调用点 ≥3）、D3a（单进程关闭顺序）**全部锁定单进程装配不变量**，拆分后必须按 `mode` 分支改造。

### 1.4 拆分收益

1. L2 请求进程不再被 6 个作业与消息回调抢占事件循环；作业失败/堆积不拖垮 API。
2. 调度与消费可独立扩缩容、独立限流、独立发布（改作业不必重启 API）。
3. 获得持久化队列、ack-late、重试退避、死信、执行历史与作业级指标。
4. 为解除 H-1 单 worker 约束创造条件（需二期单独评估进程内状态）。

---

## 2. 目标架构

### 2.1 进程/容器清单

| 服务 | 进程 | 队列 | 副本 | 职责 |
|---|---|---|---|---|
| `app`（9998，保留） | `python run.py` | — | 1 | HTTP/API、插件路由、**仅发布**，无调度/无消费/无内存订阅执行 |
| `celery-beat`（新） | `celery -A base.common.celery_app beat -S ...` | → `jobs` | **严格 1** | 按 `manifest.jobs` + 平台作业生成调度，投递作业任务 |
| `celery-worker-jobs`（新） | `celery -A ... worker -Q jobs -c N` | `jobs` | 可扩 | 执行 6 类作业单轮 handler |
| `celery-worker-events`（新） | `celery -A ... worker -Q events -c M` | `events` | 可扩 | 事件幂等判定 → 按订阅派发 handler → 状态机 |
| `rabbitmq`（已有） | 独立栈 | — | 1 | **新增独立 vhost 给 Celery**；业务事件 vhost 灰度期保留 |
| `redis`（已有） | 独立栈/外部 `agentredis` | — | 1 | result backend、分布式锁、幂等键、`last_run`、订阅变更广播 |

`jobs` 与 `events` 分队列的理由：作业低频长耗时、事件高频低延迟，独立 `-Q` 才能独立限流与扩容；两个 worker 共用同一镜像与同一 Celery app，仅启动参数不同，必要时可合并成一个 `-Q jobs,events` 进程。

### 2.2 消息与数据流向

```
HTTP 请求 / 业务代码
  └─ app: EventCenter.publish（契约校验 + Redis 幂等键）
       ├─ write EventRecord(published)
       ├─ send_task("events.dispatch", [event_uuid, event_name, payload], queue="events")
       └─ [灰度期] 可选双写旧业务 exchange（仅作对账，不消费）

celery-beat: ManifestBeatScheduler
  └─ 读 manifest.jobs + 平台作业 → send_task("jobs.run", [owner, name], queue="jobs")

worker-events: 幂等 SETNX(event_uuid) → 查 EventSubscription / 内存注册表
  → 逐 handler 调用（30s 超时、异常隔离）→ EventRecord(consumed/failed/dead_letter)
  → 失败 autoretry（退避）→ 超上限 reject 进 DLQ；补投/重放走同一 task
worker-jobs:  is_plugin_active(owner) 门控 → Redis 互斥锁 → async handler（单轮）→ 释放锁
```

### 2.3 **必须做 vhost / exchange 隔离**

现有主事件队列绑定 `routing_key="#"`。若 Celery 与业务事件共用同一 exchange，Celery 的任务消息会被旧 `ConsumerWorker` 当事件拉走并 JSON 解析失败，反之事件消息也会污染 Celery 队列。因此：

- 在 RabbitMQ 上**新增专用 vhost**（部署脚本 `rabbitmqctl add_vhost` + 授权，或 management definitions 导入），Celery `broker_url` 指向该 vhost；
- 业务事件 vhost 保持现状，灰度期仅由 app 双写、旧 consumer 停消费；
- 若暂不新建 vhost，则至少使用独立 exchange 且确保 `#` 绑定不交叉，但**不推荐**（隔离不彻底）。
- Celery 侧队列命名统一前缀，例如 `ap.jobs` / `ap.events` / `ap.dlq`，全部 durable、quorum 或 classic 待定；`task_create_missing_queues=False` 由部署显式声明，避免拼写错误静默建队列。

---

## 3. 组件设计

### 3.1 依赖与版本（已核实）

| 项 | 结论 |
|---|---|
| Python | 镜像固定 `python:3.12-slim`（`deploy/app/Dockerfile:16` 等） |
| Celery | **5.6.2 为当前稳定版**，官方支持 CPython 3.9–3.13，含 3.12；5.6 修复了 3.11+ 内存泄漏与 broker URL 凭据日志泄漏 |
| 依赖增量 | `requirements.txt` 新增 `celery==5.6.2` 即可；Kombu ≥5.6 由 Celery 带入；Celery 5.6 要求 `redis-py>=4.5.2`，项目 `redis>=5.0.0` 已满足；`aio-pika` 保留给灰度期旧链路 |
| Windows 本地 | Celery prefork 池在 Windows 不可用，本地用 `--pool=solo`（或 `threads`）；生产 Linux 用默认 `prefork` |

安装命令（示意，未执行）：`pip install "celery==5.6.2"`；生产由镜像 `pip install -r requirements.txt` 固化版本。

### 3.2 Celery app 与 **async/Tortoise 兼容（最大工程风险）**

现有 6 个作业 handler 与全部事件 handler 都是 `async def` + Tortoise/asyncpg。Celery 任务是同步函数，且 asyncpg 连接池绑定到创建它的事件循环——**每任务 `asyncio.run()` 会跨 loop 复用连接池而报错**，这是最容易踩的坑。

推荐实现（目标态）：

```
base/common/celery_app.py
  - celery = Celery("agentpanel", broker=..., backend=...)
  - conf: task_acks_late=True, task_reject_on_worker_lost=True,
          task_ignore_result=True, task_serializer="json", accept_content=["json"],
          worker_prefetch_multiplier=1（事件类长任务必须限预取）,
          broker_connection_retry_on_startup=True, timezone="UTC"
  - class AsyncTask(Task): 把协程提交到「worker 进程级常驻事件循环线程」
  - @worker_process_init: 启动 daemon thread + asyncio.new_event_loop()，
        在该 loop 内 Tortoise.init(...) / RedisCache 预热 / event_center.initialize()
  - @worker_process_shutdown: 排空在途 → Tortoise.close_connections() → 停 loop
```

- `AsyncTask` 用 `asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)` 提交并阻塞等待，一个 worker 进程只建一次连接池，避免跨 loop 与每任务建池开销。
- 事件 worker 高频，必须采用常驻 loop 线程方案；备选 `--pool=threads` + thread-local loop，但需重新验证 Tortoise 线程安全，列为降级方案。
- **每任务「单轮」语义保持不变**：handler 内部不再有 `while True`，Celery 负责循环触发；现有 `jobs/*.py` 的 `run()` 可直接复用。
- Windows 本地 `--pool=solo` 不触发 `worker_process_init` 的 fork 语义，需在 `worker_ready` 信号兜底初始化，实施时验证。

### 3.3 调度服务（Beat）

**推荐：自定义 `ManifestBeatScheduler(celery.beat.Scheduler)`**，在每次 `tick()` 重建 `schedule`：

- 作业源不变：`get_enabled_plugins_from_manifests()` + 各 `manifest.jobs` + `base/common/jobs/platform.py` 的两个平台作业（保留 `__platform__` 保留键）；
- 复用 `plugin_contract.validate_jobs()` 与 `dynamic_ref.resolve_callable()`，不复制校验逻辑；
- `interval_ref`（harness）每 tick 重读 → 天然保留「后台改配置热生效」；
- `requires_plugins` → 生成 entry 时按 `is_plugin_active()` 过滤，等同现有运行期装卸；
- 插件 enable/disable → 下个 tick 自动增删，**无需 app 向 beat 发通知**，`AC-PLR-15-1` 语义闭环；
- `last_run_at` / 调度状态持久化到 Redis（键 `ap:celery:beat:last_run:*`），避免 beat 重启后从文件 `celerybeat-schedule` 读本地状态导致漂移；
- **Beat 必须严格单实例**：部署层 `replicas=1` + Redis 选主锁双保险，否则重复投递。多实例需引入 leader 选举，本期不做。

**简化备选（若认为自定义 Scheduler 过重）**：启动时一次性从 manifest 生成静态 `beat_schedule`，每个作业任务执行前自查 `is_plugin_active(owner)`，harness 改为固定 60s 心跳 + Redis `last_run` + `resolve_interval()` 到期判定。**代价**：新增/启用插件的作业需重启 beat；`interval_ref` 由门控模拟。需在 D2 明确选择。

**语义偏差登记**（相对现状）：
| 现状 | 目标态 | 处理 |
|---|---|---|
| 首轮先 sleep 再执行 | Beat 启动后按 `last_run_at` 决定是否立即触发 | 用 Redis `last_run` 模拟首轮延迟，或书面接受「启动即执行」 |
| handler 返回 int 覆盖下一轮间隔 | 无对应机制 | 现有 6 个 handler 均未使用，建议登记为废弃；如保留则用 Redis 动态间隔实现 |
| 同作业天然串行（单 Task） | 多 worker 可能重叠 | Redis 互斥锁 `ap:celery:lock:{owner}:{name}`（TTL 兜底）+ `task_acks_late` |
| 异常仅记日志、下轮隐式重试 | Celery `autoretry_for` + 退避 + 上限 | 更可靠，但失败行为变化需回归验证 |

### 3.4 消费服务（事件 dispatch）

`base/common/events/celery_dispatch.py`（新）定义 `events.dispatch` 任务：

1. **幂等**：Redis `SET ap:celery:evt:{event_uuid} NX EX <TTL>`；未取到则查 `EventRecord.status`，终态（`consumed`/`dead_letter`）直接 ack 返回，处理中则 `retry(countdown=...)`。同时补上现状缺失的「已 consumed 跳过 handler」。
2. **订阅解析**：worker 启动时执行 `event_center.initialize()`，复用现有 `register_ref` / `guarded` / `_handler_registry`，`get_handlers(event_name)` 与 `ConsumerWorker:86` 完全一致 —— **不依赖「DB 订阅表是否完备」**（部分插件只通过 `register_ref` 注册，未声明 `events.subscribe[]`，直接用 DB 表派发会漏 handler）。M1 阶段先做一次「运行时注册表 ↔ `EventSubscription` 表」完备性对账并留档。
3. **启停同步**：app 侧 `_sync_plugin_subscriptions()` 写 DB 后，向 Redis channel `ap:celery:subscriptions` 广播，worker 收到后 `event_center.sync_plugin(...)` 重绑；任务执行前再按 `is_plugin_active()` + `EventSubscription.is_enabled` 双保险自查，避免广播丢失导致幽灵订阅。
4. **状态机与重试**：沿用 `consuming → consumed / failed / dead_letter`，`processing_time_ms`；单 handler `wait_for(30s)`、逐 handler 异常隔离（保持现状）。失败用 Celery `autoretry_for` + `retry_backoff` + `max_retries=RABBITMQ_MAX_RETRIES`；**超上限必须 `Reject(requeue=False)` 进 DLQ**，修正现状「只改 DB 不 reject」的缺陷。重放接口 `/v1/events/replay/*` 改为 `send_task("events.dispatch", ...)` 而非重新 `publish` 到业务 exchange。
5. **降级补投**：现状 `_recover_degraded_events()`（adapter:36-53）只把状态改成 `degraded_consumed`、**不重新投递**，broker 恢复后事件实际丢失。目标态改为：broker 不可用写 `EventRecord(degraded_published)` 并存 Redis 待投列表，连接恢复后逐条 `send_task` 补投，补投成功再改状态。
6. **顺序性**：现状单队列单消费者大致有序；多 worker 并发后无全局顺序保证。若业务依赖同一实体事件顺序（如 CRM 线索状态流转），需按业务键做分区路由或把 `events` worker 并发限制为 1，M3 前需逐插件确认。

### 3.5 app 侧改造（灰度开关，改动点逐文件）

| 文件 | 改造 |
|---|---|
| `base/common/events/event_bus_adapter.py:113` | **`mode=on` 时跳过 `await self._memory_bus.publish(...)`**，消除双通道重复；`mode=shadow` 时双写旧 exchange 但打标不消费 |
| `base/common/events/event_bus_adapter.py:70-110` | `publish` 改为「写 EventRecord → `send_task(events.dispatch)`」；保留 `RABBITMQ_ENABLED=false` 的纯内存降级路径供 `mode=off` |
| `base/start.py:95-110, 124` | `mode=on` 时跳过 `ConsumerWorker.start()` 与 `job_scheduler.start_all()`；关闭顺序按 mode 分支，`mode=off` 保持原断言 |
| `base/common/plugin_manager.py:709,831,856` | `_sync_plugin_jobs` 在 `mode=on` 时改为 no-op + 发订阅/作业变更广播（或直接依赖 Beat 自查，无操作）；`_sync_plugin_subscriptions` 增加 Redis 广播 |
| `base/core/events/registry.py:197-205` | 发布幂等从进程内 dict 迁到 Redis `SETNX`（跨进程生效），保留同一 TTL 语义 |
| `base/common/events/api/event_monitor_router.py` | 队列深度/consumer 状态改读 Celery/RabbitMQ management API，或新增 `/v1/events/monitor/celery` 端点，旧端点灰度期标注 deprecated |
| `base/common/health.py` | `/health/ready` 增加 broker/backend 连通性探针（app 作为生产者至少需 broker 可达） |
| `base/common/jobs/scheduler.py`、`consumer_worker.py` | **代码保留一个观察期**（`mode=off` 可完整回滚），观察期结束后再评估删除 |
| `run.py:38-45` H-1 | 一期保持 `UVICORN_WORKERS=1`；注释更新为「调度/消费已外置，但进程内状态仍需评估」 |
| `requirements.txt` | 新增 `celery==5.6.2` |

新增配置段 `[celery]`（**只列键名，不落任何凭据取值**）：`mode`、`broker_url_file`、`result_backend_file`、`jobs_queue`、`events_queue`、`dlq_queue`、`task_default_queue`、`beat_scheduler`、`lock_ttl`、`idempotency_ttl`、`job_timeout_soft`、`job_timeout_hard`、`event_handler_timeout`、`worker_prefetch_multiplier`、`worker_concurrency_jobs`、`worker_concurrency_events`、`redis_key_prefix`、`redis_db_celery`、`visibility_timeout`。连接串走环境变量 + `_FILE` secret（沿用 `packages/common/config.py:99-127` 的 `read_secret_file()` 契约），**不写入 `config.conf`**（该文件已有明文凭据，避免扩散）。

---

## 4. 灰度、回滚与回归

### 4.1 `mode` 三态（沿用项目「保留 mode 开关 + 灰度观察期」惯例）

| mode | 调度 | 消费 | 用途 |
|---|---|---|---|
| `off` | 本地 `JobScheduler` | 本地 `ConsumerWorker` + 内存总线 | 现状 / 回滚态，现有回归脚本全绿 |
| `shadow` | Beat+Worker 跑**空转对账**（只记录应触发/应消费，不产生副作用） | 事件双投：旧链路照常执行，Celery 侧只做幂等与计数对账 | 验证不重不漏、时序与性能 |
| `on` | Celery Beat/Worker 独占 | Celery dispatch 独占，app 仅生产 | 正式态 |

`shadow` 对账指标：作业应触发次数 vs 实际、事件 `event_uuid` 集合差集、handler 执行次数倍数（必须 =1）、`EventRecord` 状态分布、队列堆积与端到端延迟。

### 4.2 回滚

`mode` 改回 `off` 并重启 app 即可（旧实现代码保留）。注意两点：① 回滚前先停 `celery-beat` 与 `events` worker，避免双份执行；② 回滚期间 `shadow` 已投递但未消费的任务需排空或按 `event_uuid` 幂等丢弃（幂等键已落 Redis，可安全忽略）。

### 4.3 回归脚本改造（**必须同步，否则 CI 直接红**）

- `tests/regression_pending.py` B1/B3/B4/B5/B6、D3a 按 mode 分支：`off` 保持原断言；新增 `on` 断言集 —— `start.py` 无本地 `ConsumerWorker`/`job_scheduler` 装配、Beat schedule 含 6 项且 `interval_ref` 生效、禁用插件后任务跳过、`publish` 不再触发内存 handler（**重复执行防护专项用例**）、`event_uuid` 重投不重复执行、禁插件无幽灵订阅、worker 排空无 Traceback。
- `tests/regression_plugin_assembly.py` 的订阅装卸断言需覆盖「app 写 DB → worker 广播重绑」跨进程链路（可用同进程模拟 worker 初始化）。
- 新增 `tests/regression_celery_split.py`：端到端冒烟（发事件 → worker 消费 → DB 状态终态 → 重放 → 重投幂等）。

---

## 5. 部署、配置与可观测性

### 5.1 compose / 镜像

- 复用 L2 镜像（`deploy/gateway/Dockerfile.app` / `deploy/app/Dockerfile`），新增 3 个 service，仅 `command` / `environment` / `healthcheck` / `depends_on` 不同；**不新增镜像**，降低构建与发布成本。
- `deploy/gateway/docker-compose.yml` 当前未声明 rabbitmq 服务（`app_default` external，靠外部 `rabbitmq` 容器），新增服务需确认网络连通与 `RABBITMQ_*` 凭据以 `_FILE` secret 形式挂载；`REDIS_HOST` 沿用外部 `agentredis`。
- `RUN_DB_MIGRATIONS=false` 不变：**迁移仍只由 app 单独执行**，新服务不得跑 `migrations/*.sql`；新增表/索引（如需要）沿用 `core_` 前缀幂等 SQL。
- Beat 单实例（无 `replicas`、无 `scale`）；两个 worker 可按需扩容。
- healthcheck：`celery -A ... inspect ping`（超时需覆盖冷启动）或 Redis 心跳键 + 进程存活检查；`restart: unless-stopped`；日志沿用 json-file 轮转。

### 5.2 本地开发（Windows）

`celery -A base.common.celery_app worker -Q jobs,events --pool=solo -c 1 -l info` 与 `celery -A ... beat -S ...` 分两个终端；`--pool=solo` 下需验证 `worker_process_init` 信号触发时机（必要时用 `worker_ready` 兜底）。建议补 `scripts/dev_celery.ps1`（如创建，注意非 ASCII 路径编码约束）。

### 5.3 可观测性

| 缺口 | 补法 |
|---|---|
| 无作业级指标 | 用 `task_prerun/postrun/failure/retry` 信号打点：执行次数、耗时直方图、失败/重试数、在途数、队列深度，暴露 `/metrics`（celery-exporter 或自研） |
| `/monitor/*` 探针读 aio_pika 对象 | 改读 RabbitMQ management API / Celery inspect，灰度期并列展示 |
| `monitoring/prometheus.yml` 6 个 job 无 worker | 新增 `celery` scrape job；`alert_rules.yml` 补 worker down、队列堆积、beat 心跳过期、任务失败率、DLQ 增长告警 |
| `filebeat.yml` 只采 `app.json` | 新增 worker/beat 日志输入或统一走 docker logging |
| Jaeger 仅 instrument HTTP | 把 `event_uuid` / `task_id` 注入 trace context，串起 HTTP → broker → worker |

---

## 6. 分阶段实施计划与验收

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **M0** | 方案评审，拍板 D1–D4；确认新 vhost 创建方式与凭据注入路径 | 本文件签字 + 决策记录 |
| **M1** | 基础设施与骨架：依赖、`[celery]` 配置键、`celery_app.py`（AsyncTask + worker signals）、vhost/队列声明、compose 3 服务、健康检查、指标埋点、`mode` 开关骨架 | `mode=off` 下 `regression_plugin_assembly` 24/24、`regression_pending` 42/42 零回归；worker 能 `inspect ping`；空任务端到端跑通；Windows solo 池验证 |
| **M2** | 调度独立：`ManifestBeatScheduler`、6 个作业任务、Redis 互斥锁与 `last_run`、`is_plugin_active` 门控 | `shadow` 对账 7 天（或约定观察期）作业触发 0 漏 0 重；`interval_ref` 热生效验证；禁插件任务跳过；切 `on` 后 app 内 `job_scheduler.task_count()==0` |
| **M3** | 消费独立：关闭内存通道、`events.dispatch`、Redis 幂等、订阅广播、重试/DLQ、重放与降级补投改造、monitor 端点 | `shadow` 事件 `event_uuid` 差集为空且 handler 执行倍数=1；重投/重放不产生重复副作用；`dead_letter` 真进 DLQ；`on` 后 app 无 `ConsumerWorker` 实例 |
| **M4** | 收尾：回归脚本全面改造、监控告警上线、观察期结束评估删除旧实现、H-1 多 worker 可行性评估（单列二期） | 三份回归全绿；演练一次 `on→off` 回滚；关闭顺序无 Traceback；文档更新（设计 §偏差、as-built 架构） |

### 6.1 备选方案对比

| | 方案 A：最小改动（仅物理搬迁） | **方案 B：统一 Celery（推荐）** |
|---|---|---|
| 调度 | Celery Beat/Worker | 同左 |
| 消费 | 新建 `consumer` 容器跑现有 `ConsumerWorker`（`aio_pika` 直连），app 关闭本地消费 | `events.dispatch` Celery 任务，broker 统一 |
| app 改动 | 关闭 `ConsumerWorker.start()`、关闭内存通道、启停订阅同步 | 同左 + `publish` 改 `send_task` |
| 优点 | ACK/DLQ/重试/排空逻辑零改动，回滚最容易，M3 风险低 | 一套框架、可水平扩容、统一重试/指标/追踪、顺带闭环 W3-1 幂等 |
| 缺点 | 两套消费框架长期并存；`ConsumerWorker` 仍单进程并发受限；幂等缺口需单独补 | 需重建 ACK/重试/DLQ/订阅同步语义，改造面与验证量最大 |
| 适用 | 急于先解耦、观察期短 | 目标态明确、愿意分两阶段灰度 |

> 折中路径：M3 先落方案 A 的 `consumer` 容器（`mode=on-a`），验证物理拆分与双通道关闭无误后，再在同一容器内把消费实现替换为 Celery worker（`mode=on`）。两次切换各自可回滚。

---

## 7. 风险登记

| # | 风险 | 等级 | 对策 |
|---|---|---|---|
| R1 | **双通道导致 handler 重复执行** | 高 | `mode=on` 必须跳过 `adapter:113`；M3 设专项回归用例；`shadow` 对账执行倍数=1 |
| R2 | async/Tortoise 与 Celery prefork 事件循环不兼容 | 高 | 进程级常驻 loop 线程 + `AsyncTask`；M1 先用最小 async 任务验证连接池不跨 loop |
| R3 | 订阅/插件启停跨进程不一致（幽灵订阅、漏订阅） | 高 | worker 复用 `event_center.initialize()`；Redis 广播 + 任务内 `is_plugin_active`/DB 双自查；M1 完备性对账 |
| R4 | Celery 消息与 `#` 通配事件队列互相污染 | 高 | 独立 vhost；显式声明队列、禁自动建队列 |
| R5 | Beat 多实例重复投递 / 同作业重叠 | 中高 | `replicas=1` + Redis 选主锁；任务 Redis 互斥锁 + `acks_late` |
| R6 | `interval_ref`/首轮 sleep/handler 返回间隔语义丢失 | 中 | 自定义 Beat Scheduler + Redis `last_run`；偏差逐条登记并让用户确认 |
| R7 | 事件顺序性被多 worker 并发破坏 | 中 | M3 前逐插件确认顺序依赖；必要时按业务键分区或 `events` worker 并发=1 |
| R8 | 回归脚本硬编码单进程装配导致 CI 红 | 中 | 按 mode 分支改造，旧断言在 `off` 下原样保留 |
| R9 | `/monitor/*`、`/replay/*`、降级补投在目标态失真或失效 | 中 | 同步改造端点；补投改 `send_task`；灰度期新旧并列 |
| R10 | Redis 键冲突（现有 quota/lease 键、单 db） | 中 | 统一 `ap:celery:*` 前缀或独立 db 编号；不复用现有 db 的隐式键空间 |
| R11 | 凭据扩散 | 中 | 连接串只走 `_FILE` secret / 环境变量，不写入 `config.conf`；日志脱敏（Celery 5.6 已修 broker URL 明文日志） |
| R12 | Windows 本地开发体验 | 低 | `--pool=solo` + `worker_ready` 兜底初始化；M1 验证 |

---

## 8. 一句话结论

**现有 RabbitMQ + Redis 已够用，缺的是「Celery 依赖 + 三个新进程 + 发布端关闭内存通道 + 幂等落地」；建议先 M1/M2 把调度独立并灰度对账，M3 再切消费，全程用 `mode` 三态保证可回滚。**

> 本文仅为方案，未修改任何代码、配置或部署文件。实施前需先完成 D1–D4 决策与 M1 的技术验证（尤其 R2 的 async 连接池验证）。
