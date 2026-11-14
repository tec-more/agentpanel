# AgentPanel 调度服务与消费服务独立化（taskiq + RabbitMQ + Redis + taskiq-beat + pydantic）可行方案

- 日期：2026-11-14
- 状态：**方案待评审，尚未实施任何代码/配置/部署改动**
- 与既有文档的关系：原拟与 `AgentPanel-调度与消费服务独立化-Celery可行方案-2026-11-14.md`（Celery 候选）并列评估；现 **Celery 方案（含已落地的部署）已由用户删除**，该文档亦已移除，本文为当前**唯一推荐方案**文档。文中现状事实、行号调研与时点保持一致。
- **当前工作区核查（2026-11-14）**：`requirements.txt` 无 celery、`base/` / `packages/` / `services/` 无 celery 代码引用、`deploy/celery/` 为空目录、Celery 方案文档已删除。即本工作区无 Celery 任何残留，taskiq 为唯一候选。早期工作日志中「Celery 方案 B 与同仓双镜像已落地」的记录因用户已删除该落地方案而不再适用，本文不依赖该记录，基线统一为 taskiq-only。
- 范围：把 `job_scheduler`（调度）与 `ConsumerWorker`（消费）从 L2 `app` 进程中拆出为独立进程/容器，引入 taskiq；RabbitMQ 作 broker、Redis 作幂等/锁/（可选）结果后端、`taskiq-beat` 作数据库支撑的 beat、pydantic v2 作消息契约。
- 依据：对 `base/common/jobs/`、`base/common/events/`、`base/core/events/`、`base/start.py`、`run.py`、`deploy/**`、`migrations/`、`tests/regression_*.py` 的只读调研；外部版本与 API 事实于 2026-11-14 通过 PyPI 元数据、taskiq 官方文档与 taskiq-beat README 核实。文中行号为调研时点，实施时需复核。
- 安全约定：本文只列配置**键名**，不记录 `config.conf` / `.env` / `secrets/` 的任何取值或凭据。

---

## 0. 结论摘要与待拍板项

**结论：可行，且为当前唯一推荐方案。** 三条决定性理由（相较原 Celery 候选方案的优势）：

1. **消除异步桥接这一最大工程风险**：taskiq worker 自身就是 asyncio 事件循环，`async def` 任务、Tortoise/asyncpg 连接池、`WORKER_STARTUP/SHUTDOWN` 生命周期在同一 loop 内；不再需要「同步任务 + 常驻 loop 线程 + `run_coroutine_threadsafe`」的桥接层。
2. **插件启停装卸更轻**：`taskiq-beat` 把调度定义与运行历史落在 `scheduler_job` / `scheduler_run` 两张表，自带 `upsert / pause / resume / run_now / delete`。`manifest.jobs` 契约一字不改，插件 enable/disable 变成对调度行的 diff 同步，天然跨进程，比自定义 `celery.beat.Scheduler` 少一层。
3. **版本契合**：taskiq 0.13.0 要求 `pydantic>=2.5,<3`（项目 2.11.7）、`taskiq-aio-pika` 0.6.1 要求 `aio-pika>=9`（项目 `>=10.0.1`）、`taskiq-beat` 1.4.0 要求 Python `>=3.12`（部署镜像 3.12-slim，本地 3.13），内置 Prometheus / OpenTelemetry 中间件与项目已有监控栈对齐。

**新增代价（须书面接受）**：`taskiq-beat` 是第三方包（Artasov，MPL-2.0，非 taskiq 官方；`taskiq-python/taskiq-beat` 仓库为 404），引入 SQLAlchemy 第二套 ORM 与两张表；`taskiq-redis` 与项目 redis-py 版本冲突，需绕开；taskiq CLI 没有 `-Q`、没有 `celery inspect ping` 等价物，运维面要自建。

**需要用户先拍板的 7 个决策：**

| # | 决策 | 推荐 | 影响 |
|---|---|---|---|
| D1 | 调度器实现 | **taskiq-beat（DB 存调度）** | 选官方 `taskiq scheduler` + `ListRedisScheduleSource` 则调度定义存 Redis，但需 `taskiq-redis`（触发 D2 冲突），且两套调度器**禁止并行** |
| D2 | 结果后端 | **`DummyResultBackend`，不装 taskiq-redis** | 作业/事件都不需要返回值；引入 `taskiq-redis` 会把 redis-py 顶到 `>=8,<9`（1.2.4）或 `>=6,<7`（1.1.2），与现有 quota / `RedisCache` 冲突 |
| D3 | 事件消费是否也交给 taskiq | **是（统一方案 B），放第二阶段** | 选「仅物理搬迁 ConsumerWorker」则两套消费框架长期并存 |
| D4 | 一期是否放开 `UVICORN_WORKERS>1` | **不放开，仍为 1** | 拆分后理论上可放开，但 quota 进程内降级态、`_degraded_hooks`、WebSocket 连接表仍是进程内状态 |
| D5 | 调度表落库位置 | **现有 PG 库 + `core_` 前缀幂等 SQL** | 独立 sqlite 需容器共享卷，多副本不可行；PG 连接串走 `_FILE` secret |
| D6 | broker 隔离方式 | **新增 RabbitMQ 专用 vhost** | 旧主队列绑定 `routing_key="#"`，仅换 exchange 隔离不彻底 |
| D7 | pydantic 消息边界 | **schema + `model_dump(mode="json")` / `model_validate`** | 自定义 `TaskiqSerializer` 更统一但需维护序列化层；**禁止**把 `BaseModel` 实例直接塞进 `kiq()` |

**决策记录（M0 已拍板，2026-11-14）**：D1–D7 全部按上表「推荐」项确认，无偏离 ——

- D1 调度器：`taskiq-beat`（调度定义与运行历史落 PG `scheduler_job` / `scheduler_run`）
- D2 结果后端：`DummyResultBackend`，**不装 `taskiq-redis`**（绕开 redis-py 版本冲突）
- D3 事件消费：交 taskiq（统一方案 B），放第二阶段（M3）
- D4 一期 `UVICORN_WORKERS`：不放开，仍为 1
- D5 调度表落库：现有 PG + `core_` 前缀幂等 SQL（`RUN_DB_MIGRATIONS=false` 时单独执行）
- D6 broker 隔离：新增 RabbitMQ **专用 vhost**
- D7 pydantic 边界：schema + `model_dump(mode="json")` / `model_validate`（默认 `JSONSerializer` 不认 `BaseModel` 实例）
- （2026-11-14 追加确认）现有任务重构：采用**逐任务 `@broker.task` + worker 静态聚合 import**（`tasks_registry`），beat 直接投递到真实 task，去除通用 `run_job` 分发层；`interval_ref` 每轮热重载迁移至 `ManifestReconciler`（beat 无原生支持），「handler 返回 int 覆盖下一间隔」语义取消（记为行为变更）

> 下一步进入 **M1**（基础设施与骨架 + 三项必验：R2 `--workers 2` 连接池隔离、R16 调度表 DDL 与 `SchedulerBase.metadata` 对齐、R17 `AckableMessage` 是否 yield 决定 manual ack / `nack(requeue=False)` 与 DLQ 实现；验证前不宣称 DLQ 闭环）。

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
3. 获得持久化队列、执行历史（`scheduler_run`）、重试退避、死信、作业级指标。
4. 为解除 H-1 单 worker 约束创造条件（需二期单独评估进程内状态）。
5. **相对原 Celery 候选方案的额外收益**：不需要同步/异步桥接层；调度定义 DB 化后插件启停同步无需重写调度器 tick；首轮 sleep 语义天然保留（见 §3.4）。

---

## 2. 目标架构

### 2.1 进程/容器清单

| 服务 | 进程 | 队列 | 副本 | 职责 |
|---|---|---|---|---|
| `app`（9998，保留） | `python run.py` | — | 1 | HTTP/API、插件路由、**仅发布**，无调度/无消费/无内存订阅执行 |
| `taskiq-beat`（新） | `taskiq-beat-scheduler base.common.taskiq_app.scheduler:scheduler_app --startup ...:upsert_schedules` | → `ap.jobs` | **严格 1** | 从 PG 读 `scheduler_job`，按 `next_run_at` 投递作业任务 |
| `taskiq-worker`（新，单进程） | `taskiq worker ...:broker base.common.taskiq_app.jobs base.common.taskiq_app.events --workers 2 --ack-type when_executed` | `ap.jobs` + `ap.events` | 可扩（副本） | 由 `tasks_registry` 静态注册全部 `@broker.task`；`ap.jobs` 执行各插件作业单轮 handler，`ap.events` 事件幂等判定 → 按订阅派发 handler → 状态机 |
| `rabbitmq`（已有） | 独立栈 | — | 1 | **新增专用 vhost 给 taskiq**；业务事件 vhost 灰度期保留 |
| `redis`（已有） | 独立栈/外部 `agentredis` | — | 1 | 幂等键、分布式互斥锁、订阅变更广播、`last_run`、心跳键；结果后端按 D2 决定 |
| `postgresql`（已有） | 外部 | — | 1 | 新增 `scheduler_job` / `scheduler_run`；既有 `EventRecord` / `EventSubscription` / 业务库 |

> **taskiq CLI 没有 `-Q`**：jobs/events 分队列靠**单个 broker 上声明两个 `task_queues`**（`ap.jobs` / `ap.events`）或任务 `queue_name` label，不能像 Celery 那样 `-Q jobs,events` 一键切换。见 §3.2。

### 2.2 消息与数据流向

```
HTTP 请求 / 业务代码
  └─ app: EventCenter.publish（契约校验 + Redis 幂等键）
       ├─ write EventRecord(published)
       ├─ await broker.startup() → dispatch.kiq(EventMessage.model_dump()) → ap.events
       └─ [灰度期] 可选双写旧业务 exchange（仅作对账，不消费）

taskiq-beat: SchedulerApp 轮询 scheduler_job（sync_interval_seconds）
  └─ ManifestReconciler 按 manifest.jobs + 平台作业 diff 调度行（upsert/pause/delete）
       └─ 到期 job → 直接 kiq 对应 @broker.task（task_name="{owner}:{name}"）→ ap.jobs

taskiq-worker（单进程，task_queues=[ap.jobs, ap.events]，由 tasks_registry 静态注册全部 @broker.task）：
  ap.jobs 队列：各插件 jobs 模块以 @broker.task(name="{owner}:{name}") 注册
       └─ 执行单轮 handler（循环由 beat IntervalTrigger 负责，不再自带 while）
       └─ 禁用插件 → reconciler pause/delete scheduler_job 行 → beat 不再投递（is_plugin_active 兜底）
  ap.events 队列：dispatch 任务（M3 接真实业务；M1 仅骨架 + smoke）
       └─ 幂等 SETNX(event_uuid) → 查订阅注册表 → 逐 handler（30s 超时、异常隔离）
       └─ EventRecord(consumed/failed/dead_letter) → 失败 SmartRetryMiddleware 退避
       └─ 超上限 reject 进 DLQ；补投/重放走同一 task
```

### 2.3 组件职责澄清（避免概念混用）

| 组件 | 实际职责 | 不负责 |
|---|---|---|
| RabbitMQ / `AioPikaBroker` | 任务消息传输、队列隔离、delay/priority | 不存调度定义、不存结果 |
| **taskiq-beat** | 调度定义 + 运行历史，**存 PG（`scheduler_job` / `scheduler_run`）**，通过 SQLAlchemy `AsyncSession` | 不自带网络 broker、不用 Redis 存调度 |
| Redis | 幂等键、互斥锁、订阅广播、心跳；结果后端按 D2 | 不是 taskiq-beat 的调度存储 |
| pydantic v2 | 消息 schema、边界校验 | 不是序列化器（默认 `JSONSerializer` 不认 `BaseModel` 实例） |

> **严禁双调度器**：`taskiq-beat-scheduler` 与官方 `taskiq scheduler ... ListRedisScheduleSource` 只能选一个。两者同时运行会对同一作业重复投递。

### 2.4 必须做 vhost / exchange 隔离

现有主事件队列绑定 `routing_key="#"`。若 taskiq 与业务事件共用同一 exchange，taskiq 的任务消息会被旧 `ConsumerWorker` 当事件拉走并 JSON 解析失败，反之事件消息也会污染 taskiq 队列。因此：

- 在 RabbitMQ 上**新增专用 vhost**（部署脚本 `rabbitmqctl add_vhost` + 授权，或 management definitions 导入），taskiq `broker_url` 指向该 vhost；
- 业务事件 vhost 保持现状，灰度期仅由 app 双写、旧 consumer 停消费；
- `AioPikaBroker` 侧显式声明 `exchange` 与 `task_queues`（`ap.jobs` / `ap.events` / `ap.dlq`），durable、禁自动建队列拼写错误静默通过；
- 队列参数以 M1 复核的 `taskiq-aio-pika` 版本签名为准，示意仅列 `exchange` / `task_queues` / `delay_queue`。

---

## 3. 组件设计

### 3.1 依赖与版本（2026-11-14 核实）

| 项 | 现状 | 目标 | 结论 |
|---|---|---|---|
| Python | 镜像 `python:3.12-slim`（`deploy/app/Dockerfile:16`），本地 3.13.14 | taskiq 0.13.0 `>3.10,<4`；taskiq-beat 1.4.0 `>=3.12`（含 3.12/3.13/3.14 分类器） | 兼容 |
| pydantic | `2.11.7` | taskiq `>=2.5,<3`；taskiq-beat **不依赖** pydantic | 兼容 |
| aio-pika | `>=10.0.1` | taskiq-aio-pika 0.6.1 `aio-pika>=9.0.0`、`taskiq>=0.12,<1` | 兼容 |
| redis-py | `>=5.0.0`（无上界），quota / `RedisCache` / `health.py` 在用 | taskiq-redis 1.2.4 `redis>=8,<9`；1.1.2 `redis>=6,<7` | **冲突，按 D2 绕开** |
| SQLAlchemy | 无 | taskiq-beat `>=2.0.0` | 新增（第二套 ORM，仅调度用） |
| 其它 taskiq 依赖 | — | `aiohttp>=3`、`anyio>=4`（项目 4.8.0）、`pycron>=3`、`taskiq-dependencies` | 无冲突 |

`requirements.txt` 新增示意（**未执行**）：

```
taskiq==0.13.0
taskiq-aio-pika==0.6.1
taskiq-beat==1.4.0
sqlalchemy>=2.0,<3
```

- 可选 `taskiq[metrics]`（项目已有 `prometheus-client`）、`taskiq[opentelemetry]`（项目已有 `opentelemetry-*`，但 extra 要求 `opentelemetry-api>=1.38`，**M1 需核对项目实际版本**再决定是否装 extra 或直接用现有 instrumentation）。
- `aio-pika` 保留给灰度期旧链路；`redis>=5.0.0` **不升版本**。
- **D2 三选项**：① `DummyResultBackend`（推荐，作业/事件 `task_ignore_result` 语义，零新增依赖）；② 自研轻量 result backend（现有 redis-py + `ap:taskiq:result:*` 键，只在启用任务链时需要）；③ 引入 taskiq-redis 并把 redis-py 顶到 8，需对 quota Lua / `RedisCache` / `health.py` 做完整回归（不推荐）。

### 3.2 broker 与任务模块骨架

新增目录 `base/common/taskiq_app/`（示意，M1 复核参数签名）：

```python
# broker.py —— 单个 broker 定义，声明两个 task_queues（CLI 无 -Q 的替代方案）
from taskiq import DummyResultBackend, SmartRetryMiddleware, PrometheusMiddleware
from taskiq_aio_pika import AioPikaBroker

result = DummyResultBackend()
retry = SmartRetryMiddleware(default_retry_count=3, default_delay=5,
                             use_jitter=True, use_delay_exponent=True)
metrics = PrometheusMiddleware(server_addr="0.0.0.0", server_port=9000)

broker = AioPikaBroker(
    # url 由 [taskiq] 配置的 _FILE secret 注入，不在代码/config.conf 落值
    exchange=...,
    task_queues=[
        Queue(name="ap.jobs", routing_key="ap.jobs", durable=True),
        Queue(name="ap.events", routing_key="ap.events", durable=True),
    ],
).with_result_backend(result).with_middlewares(retry, metrics)
```

```python
# base/plugins/audit/jobs/cleanup.py —— 现有 handler 加 @broker.task 即成真实 task
@broker.task(task_name="audit:audit_cleanup", queue_name="ap.jobs")
async def run() -> None:
    # 单轮逻辑；循环由 beat IntervalTrigger 负责，不再自带 while（W2-3 已剥离）
    ...

# base/common/taskiq_app/tasks_registry.py —— worker 启动静态聚合 import，确保 task 注册
from base.plugins.audit.jobs import cleanup        # cleanup.run 即已注册 TaskiqTask
from base.plugins.customer.jobs import membership
from base.plugins.harness.jobs import reconcile
from base.common.jobs import platform as platform_jobs   # 平台作业同样 @broker.task 注册

# reconciler 直接引用真实 task 对象传给 beat（替代通用 run_job 分发）
from base.plugins.audit.jobs.cleanup import run as audit_cleanup_task
scheduler_app.create_scheduler(
    job_id="audit:audit_cleanup",
    task=audit_cleanup_task,                  # 已注册的 TaskiqTask 对象
    trigger=PeriodicSchedule(interval=IntervalTrigger(seconds=86400)),
).upsert(session)

# events.py —— dispatch 任务（M3 接真实业务；M1 仅骨架 + smoke），label ap.events
@broker.task(task_name="ap.events.dispatch", queue_name="ap.events")
async def dispatch(payload: dict) -> None:
    msg = EventMessage.model_validate(payload)
    ...
```

```python
# worker 生命周期（同一个 asyncio loop，R2 由此消除）
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state):
    await Tortoise.init(...)                   # 连接池与任务同 loop
    await RedisCache.get_instance()
    await initialize_event_center()            # 只读注册表，不挂路由
    import base.common.taskiq_app.tasks_registry   # 触发所有 @broker.task 注册

@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state):
    await drain_inflight()                     # 对齐现有 12s / 8s 排空语义
    await Tortoise.close_connections()
```

- taskiq worker 原生执行 `async def`，Tortoise/asyncpg 连接池绑定到创建它的 loop，天然一致；**不再需要** Celery 版的 `AsyncTask` / `run_coroutine_threadsafe` / 常驻 loop 线程。
- CLI 默认 `--workers 2`（子进程），每个子进程各自触发 `WORKER_STARTUP` 建连接池；Windows 本地用 `--workers 1`，并用 `--app-dir` 指定项目根以保证模块可导入。
- 关闭：`--shutdown-timeout`、`--wait-tasks-timeout` 对齐现有 ConsumerWorker 排空语义；`--max-async-tasks` / `--max-prefetch` 控制并发，事件类建议 `max_prefetch=0`（避免长任务堆积预取）。

### 3.3 async/Tortoise 兼容（替换 Celery 版 §3.2）

| Celery 版风险 | taskiq 版处置 | 残留验证 |
|---|---|---|
| 同步任务 + `asyncio.run()` 跨 loop 复用连接池 | 不存在：worker 本身是 asyncio | — |
| `worker_process_init` fork 语义、Windows `--pool=solo` 不触发 | `WORKER_STARTUP/WORKER_SHUTDOWN` 是 broker 事件，与池类型无关 | M1 用最小 async 任务验证连接池不跨 loop |
| prefork 子进程各自初始化 | `--workers N` 每子进程独立 `WORKER_STARTUP`，连接池不共享 | M1 验证 N=2 下无连接串扰 |
| 关闭期在途任务排空 | `--wait-tasks-timeout` + worker 优雅关闭 | M4 演练无 Traceback（沿用历史事件处理回归） |

### 3.4 调度服务（taskiq-beat）

**调度存储与建表**

```python
engine = create_async_engine("postgresql+asyncpg://...")   # 或 postgresql+psycopg://（psycopg>=3.3.4 已装）
session_factory = async_sessionmaker(engine, expire_on_commit=False)
scheduler_app = SchedulerApp(
    broker=broker,
    session_factory=session_factory,
    config=SchedulerConfig(
        sync_interval_seconds=1.0,          # 从 DB 重载 active jobs
        idle_sleep_seconds=0.2,
        dispatch_retry_seconds=5,
        dispatch_concurrency=32,
        dispatch_batch_size=256,
        record_runs=True,
        run_history_retention_days=30,      # 建议显式配置，避免 scheduler_run 无限增长
        default_timezone="UTC",
    ),
)
```

- dev 下可用 `SchedulerBase.metadata.create_all`；**生产必须**按项目约定补 `migrations/core_create_table_scheduler_job_<ts>.sql` 与 `..._scheduler_run_<ts>.sql`（`core_` 前缀 → `MigrationMeta.plugin_name=None` → 恒执行，`CREATE TABLE IF NOT EXISTS`，索引名对齐 SQLAlchemy 生成）。参照 `migrations/core_create_table_event_subscriptions_1794491161.sql` 的写法。
- `RUN_DB_MIGRATIONS=false` 不变：**迁移仍只由 app 单独执行**，beat/worker 不得跑 `migrations/*.sql`。
- 启动命令：`taskiq-beat-scheduler base.common.taskiq_app.scheduler:scheduler_app --startup ...:upsert_schedules`；runner 默认管理 `broker.startup()/shutdown()`，若由其他层管理则加 `--skip-broker-lifespan`。
- **严格单实例**：README 明确「不要对同一数据库跑多个 scheduler 进程」。部署 `replicas=1` + PG advisory lock（或 Redis 选主锁）双保险；worker 可多副本。

**ManifestReconciler（新增组件，替代 Celery 自定义 Beat Scheduler）**

每 `reconcile_interval`（建议 5s）在 beat 进程内执行：扫描 `get_enabled_plugins_from_manifests()` + 各 `manifest.jobs` + `base/common/jobs/platform.py` 两个平台作业 → 与 `scheduler_job` 行做 diff → 以稳定 `job_id`（`{owner}:{name}`）调用 `.upsert(session, trigger=PeriodicSchedule(interval=IntervalTrigger(...)), job_id=...)`；插件禁用则 `pause` 或 `delete`。

- 复用 `plugin_contract.validate_jobs()` 与 `dynamic_ref.resolve_callable()`，不复制校验逻辑；
- `requires_plugins` → 生成时按 `is_plugin_active()` 过滤；
- `interval_ref`（harness）每轮重读，值变化时 upsert 重算 `next_run_at`，保留热生效语义；
- 插件 enable/disable → 下个 reconcile 周期自动增删，**app 无需写 DB、无需发通知**，`AC-PLR-15-1` 语义闭环；任务执行前仍做 `is_plugin_active(owner)` 双保险；
- 备选：app 侧 `_sync_plugin_jobs` 直接写调度行 + Redis 广播。跨进程写 SQLAlchemy 表结构较脆弱，**不推荐**。

**语义偏差登记（相对现状）**

| 现状 | 目标态 | 处理 |
|---|---|---|
| 首轮先 sleep 再执行 | upsert 时设定 `next_run_at = now + interval`，到期才投 | ✅ 天然一致，优于 Celery Beat 的「启动即执行」 |
| handler 返回 int 覆盖下一轮间隔 | 无对应机制 | 现有 6 个 handler 均未使用，登记为废弃 |
| 同作业天然串行（单 Task） | 多 worker 可能重叠 | Redis 互斥锁 `ap:taskiq:lock:{owner}:{name}`（TTL 兜底）+ `--ack-type when_executed` |
| 异常仅记日志、下轮隐式重试 | `SmartRetryMiddleware`（退避/jitter/异常类型过滤）+ 上限 | 更可靠，失败行为变化需回归验证 |
| `interval_ref` 每轮重读 | reconciler 重读并 upsert | 变化才重算 `next_run_at`，不改变 round 语义 |
| 启停即 `task.cancel()` | 下个 reconcile 周期 pause/delete；在途任务由锁与门控收口 | 秒级延迟，需书面接受；任务内门控兜底 |

### 3.5 消费服务（事件 dispatch）

`base/common/taskiq_app/events.py` 定义 `ap.events.dispatch` 任务：

1. **幂等**：Redis `SET ap:taskiq:evt:{event_uuid} NX EX <TTL>`；未取到则查 `EventRecord.status`，终态（`consumed`/`dead_letter`）直接 ack 返回，处理中则延迟重试。同时补上现状缺失的「已 consumed 跳过 handler」。
2. **订阅解析**：worker 启动执行 `event_center.initialize()`，复用现有 `register_ref` / `guarded` / `_handler_registry`，`get_handlers(event_name)` 与 `ConsumerWorker:86` 完全一致 —— **不依赖「DB 订阅表是否完备」**（部分插件只通过 `register_ref` 注册，未声明 `events.subscribe[]`）。M1 阶段先做一次「运行时注册表 ↔ `EventSubscription` 表」完备性对账并留档。
3. **启停同步**：app 侧 `_sync_plugin_subscriptions()` 写 DB 后，向 Redis channel `ap:taskiq:subscriptions` 广播，worker 收到后 `event_center.sync_plugin(...)` 重绑；任务执行前再按 `is_plugin_active()` + `EventSubscription.is_enabled` 双保险自查。
4. **状态机与重试**：沿用 `consuming → consumed / failed / dead_letter`、`processing_time_ms`；单 handler `wait_for(30s)`、逐 handler 异常隔离。失败用 `SmartRetryMiddleware` + `retry_on_error` label + `max_retries=RABBITMQ_MAX_RETRIES`；**超上限必须真实 reject 进 DLQ**（修正现状「只改 DB 不 reject」）。**M1 必须验证** `AioPikaBroker` 是否 yield `AckableMessage`（决定用 `--ack-type manual` + `Context.ack()`，还是显式 `nack(requeue=False)`）；验证前不得声称 DLQ 已闭环。重放接口 `/v1/events/replay/*` 改为 `dispatch.kiq(...)` 而非重新 `publish` 到业务 exchange。
5. **降级补投**：现状 `_recover_degraded_events()`（adapter:36-53）只把状态改成 `degraded_consumed`、**不重新投递**，broker 恢复后事件实际丢失。目标态改为：broker 不可用写 `EventRecord(degraded_published)` 并存 Redis 待投列表，连接恢复后逐条 `kiq` 补投，成功后改状态。
6. **顺序性**：现状单队列单消费者大致有序；多 worker 并发后无全局顺序保证。若业务依赖同一实体事件顺序（如 CRM 线索状态流转），需按业务键分区路由或把 `events` worker 并发限制为 1，M3 前需逐插件确认。

> **ACK 默认值坑**：taskiq worker 默认 `--ack-type when_saved`（结果保存后 ack），在 `DummyResultBackend` 下语义需 M1 验证。目标态统一显式 `--ack-type when_executed`，对齐 Celery `task_acks_late`。

### 3.6 pydantic 消息契约（D7）

taskiq 默认 `JSONSerializer`，消息体为 `{task_id, task_name, labels, args, kwargs}`；`BaseModel` 实例**不能**直接作为 `kiq()` 参数（会序列化失败，`ORJSONSerializer` 同样不支持，除非自定义 `default`）。

```python
class JobMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    owner: str
    name: str
    handler_ref: str | None = None
    scheduled_at: datetime | None = None

class EventMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_uuid: UUID
    event_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    published_at: datetime
    source_module: str | None = None
```

- 发布侧 `msg.model_dump(mode="json")`（自动处理 `datetime` / `UUID` / `Decimal`），任务入口 `Model.model_validate(payload)`；
- 与 `EventBusAdapter._serialize_payload()`（55-68 行）现有 datetime/Decimal 处理对齐，避免两套编码规则；
- 不在消息内传递 Tortoise 模型对象、DB session、插件对象，只传可 JSON 化的标识与参数；
- taskiq 会自动按函数签名做类型解析（可用 pydantic 模型作入参），但显式 `model_validate` 更可控；若启用自动解析，注意 `--no-parse` 会关闭该行为；
- 备选：实现 `TaskiqSerializer.dumpb/loadb` 统一注入 pydantic 支持，代价是多一层需维护与测试。

### 3.7 app 侧改造（灰度开关，改动点逐文件）

| 文件 | 改造 |
|---|---|
| `base/common/events/event_bus_adapter.py:113` | **`mode=on` 时跳过 `await self._memory_bus.publish(...)`**，消除双通道重复；`mode=shadow` 时双写旧 exchange 但打标不消费 |
| `base/common/events/event_bus_adapter.py:70-110` | `publish` 改为「写 EventRecord → `broker.startup()` → `dispatch.kiq(EventMessage...)`」；保留 `RABBITMQ_ENABLED=false` 的纯内存降级路径供 `mode=off` |
| `base/start.py:95-110, 124` | `mode=on` 时跳过 `ConsumerWorker.start()` 与 `job_scheduler.start_all()`；关闭顺序按 mode 分支，`mode=off` 保持原断言 |
| `base/common/plugin_manager.py:709,831,856` | `_sync_plugin_jobs` 在 `mode=on` 时 no-op（beat 由 reconciler 自查）；`_sync_plugin_subscriptions` 增加 Redis 广播 |
| `base/core/events/registry.py:197-205` | 发布幂等从进程内 dict 迁到 Redis `SETNX`（跨进程生效），保留同一 TTL 语义 |
| `base/common/events/api/event_monitor_router.py` | 队列深度/consumer 状态改读 RabbitMQ management API，或新增 `/v1/events/monitor/taskiq` 端点，旧端点灰度期标注 deprecated |
| `base/common/health.py` | `/health/ready` 增加 broker 连通性探针（app 作为生产者至少需 broker 可达）+ beat 心跳键新鲜度 |
| `base/common/jobs/scheduler.py`、`consumer_worker.py` | **代码保留一个观察期**（`mode=off` 可完整回滚），观察期结束后再评估删除 |
| `run.py:38-45` H-1 | 一期保持 `UVICORN_WORKERS=1`；注释更新为「调度/消费已外置，但进程内状态仍需评估」 |
| `requirements.txt` | 按 §3.1 新增 4 行；`redis` / `aio-pika` 版本不动 |
| `migrations/`（新增） | `core_create_table_scheduler_job_<ts>.sql`、`core_create_table_scheduler_run_<ts>.sql` |
| `base/common/taskiq_app/`（新增） | `broker.py` / `jobs.py` / `events.py` / `scheduler.py` / `reconcile.py` / `schema.py` |

新增配置段 `[taskiq]`（**只列键名，不落任何凭据取值**）：`mode`、`broker_url_file`、`db_url_file`、`vhost`、`exchange_jobs`、`exchange_events`、`jobs_queue`、`events_queue`、`dlq_queue`、`result_backend`、`ack_type`、`workers`、`max_async_tasks`、`max_prefetch`、`shutdown_timeout`、`wait_tasks_timeout`、`beat_sync_interval`、`beat_idle_sleep`、`reconcile_interval`、`lock_ttl`、`idempotency_ttl`、`event_handler_timeout`、`job_timeout`、`retry_max`、`retry_delay`、`redis_key_prefix`、`redis_db_taskiq`、`subscription_channel`、`metrics_port`、`run_history_retention_days`。连接串走环境变量 + `_FILE` secret（沿用 `packages/common/config.py:99-127` 的 `read_secret_file()` 契约），**不写入 `config.conf`**（该文件已有明文凭据，避免扩散）。

---

## 4. 灰度、回滚与回归

### 4.1 `mode` 三态（沿用项目「保留 mode 开关 + 灰度观察期」惯例）

| mode | 调度 | 消费 | 用途 |
|---|---|---|---|
| `off` | 本地 `JobScheduler` | 本地 `ConsumerWorker` + 内存总线 | 现状 / 回滚态，现有回归脚本全绿 |
| `shadow` | beat + worker 跑**空转对账**（只记录应触发/应消费，不产生副作用） | 事件双投：旧链路照常执行，taskiq 侧只做幂等与计数对账 | 验证不重不漏、时序与性能 |
| `on` | taskiq-beat + jobs worker 独占 | events worker 独占，app 仅生产 | 正式态 |

`shadow` 对账指标：作业应触发次数 vs 实际、事件 `event_uuid` 集合差集、handler 执行次数倍数（必须 =1）、`EventRecord` 状态分布、`scheduler_run` 行数、队列堆积与端到端延迟。

### 4.2 回滚

`mode` 改回 `off` 并重启 app 即可（旧实现代码保留）。注意三点：① 回滚前先停 `taskiq-beat` 与 `events` worker，避免双份执行；② 停 beat 前先确认 `scheduler_job` 中无在途投递或已 drain；③ 回滚期间 `shadow` 已投递但未消费的任务需排空或按 `event_uuid` 幂等丢弃（幂等键已落 Redis，可安全忽略）。

### 4.3 回归脚本改造（**必须同步，否则 CI 直接红**）

- `tests/regression_pending.py` B1/B3/B4/B5/B6、D3a 按 mode 分支：`off` 保持原断言；新增 `on` 断言集 —— `start.py` 无本地 `ConsumerWorker`/`job_scheduler` 装配、reconciler 生成的调度行含 6 项且 `interval_ref` 变更能重算 `next_run_at`、禁用插件后任务跳过、`publish` 不再触发内存 handler（**重复执行防护专项用例**）、`event_uuid` 重投不重复执行、禁插件无幽灵订阅、worker 排空无 Traceback。
- `tests/regression_plugin_assembly.py` 的订阅装卸断言需覆盖「app 写 DB → worker 广播重绑」跨进程链路（可用同进程模拟 worker 初始化）。
- 新增 `tests/regression_taskiq_split.py`：端到端冒烟（发事件 → worker 消费 → DB 状态终态 → 重放 → 重投幂等）+ pydantic 消息往返 + ACK 语义 + 单实例锁。
- **相对原 Celery 候选方案回归差异**：删除 `AsyncTask` / 常驻 loop 线程池专项用例；新增「最小 async 任务同 loop 连接池」「`--workers 2` 连接池隔离」「`DummyResultBackend` + `when_executed` 不丢消息」「reconciler diff 幂等（重复 upsert 不新增行）」四项。

---

## 5. 部署、配置与可观测性

### 5.1 compose / 镜像

- 复用 L2 镜像（`deploy/gateway/Dockerfile.app` / `deploy/app/Dockerfile`），新增 3 个 service，仅 `command` / `environment` / `healthcheck` / `depends_on` 不同；**不新增镜像**。
- `deploy/gateway/docker-compose.yml` 当前未声明 rabbitmq 服务（`app_default` external，靠外部 `rabbitmq` 容器），新增服务需确认网络连通与 `RABBITMQ_*` / `DB_*` 凭据以 `_FILE` secret 形式挂载；`REDIS_HOST` 沿用外部 `agentredis`（现有 `app` service 已是该形态，见 compose 22-47 行）。
- `RUN_DB_MIGRATIONS=false` 不变：迁移仍只由 app 单独执行；两张新表沿用 `core_` 前缀幂等 SQL。
- Beat 单实例（无 `replicas`、无 `scale`）；两个 worker 可按需扩容；`restart: unless-stopped`；日志沿用 json-file 轮转。
- healthcheck：broker 连通性 + Redis 心跳键（`ap:taskiq:beat:heartbeat`，TTL 过期告警）；taskiq 无 `inspect ping` 等价物，勿照搬 Celery 版做法。

### 5.2 本地开发（Windows）

```bash
taskiq worker base.common.taskiq_app.broker:broker base.common.taskiq_app.jobs base.common.taskiq_app.events --workers 2 --ack-type when_executed
taskiq-beat-scheduler base.common.taskiq_app.scheduler:scheduler_app --startup base.common.taskiq_app.reconcile:upsert_schedules
```

- 三个终端；`--workers 1` 规避 Windows spawn 与连接池重复初始化；`--app-dir` 指向项目根；
- 本地可用 `sqlite+aiosqlite` 跑 beat（需 `aiosqlite`，项目已有），但**调度表结构与 PG 迁移 SQL 必须一致**，M1 需做一次双库 DDL 对账；
- 若创建 `scripts/dev_taskiq.ps1`，注意非 ASCII 路径编码约束。

### 5.3 可观测性

| 缺口 | 补法 |
|---|---|
| 无作业级指标 | `PrometheusMiddleware`（`server_port=9000`）+ 自定义中间件打点：执行次数、耗时直方图、失败/重试数、在途数、队列深度；`monitoring/prometheus.yml` 新增 worker/beat scrape job |
| `/monitor/*` 探针读 aio_pika 对象 | 改读 RabbitMQ management API，灰度期新旧并列展示 |
| 无 beat 存活信号 | Redis 心跳键 + `alert_rules.yml` 补 worker down、队列堆积、beat 心跳过期、任务失败率、DLQ 增长告警 |
| `filebeat.yml` 只采 `app.json` | 新增 worker/beat 日志输入或统一走 docker logging |
| Jaeger 仅 instrument HTTP | `OpenTelemetryMiddleware` / `TaskiqInstrumentor` 把 `event_uuid` / `task_id` 注入 trace context，串起 HTTP → broker → worker；extra 版本约束见 §3.1 |
| 调度执行历史 | `scheduler_run` 表 + `run_history_retention_days` 清理策略，可直接 SQL 审计「应触发 vs 实触发」 |

---

## 6. 分阶段实施计划与验收

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **M0** | 方案评审，拍板 D1–D7；确认新 vhost 创建方式、调度表 DDL 与凭据注入路径 | 本文件签字 + 决策记录 |
| **M1** | 基础设施与骨架：依赖、`[taskiq]` 配置键、broker/任务/schema 模块、worker 生命周期、vhost/队列声明、compose 3 服务、健康检查、指标埋点、`mode` 开关骨架、两张 `core_` 迁移 SQL | `mode=off` 下 `regression_plugin_assembly` 24/24、`regression_pending` 42/42 零回归；最小 async 任务验证 Tortoise 同 loop 且 `--workers 2` 无串扰；pydantic 消息往返通过；`DummyResultBackend` + `when_executed` 不丢消息；`AckableMessage` 支持结论留档；空任务端到端跑通 |**（详细任务拆解见 `AgentPanel-taskiq-M1实施拆解-2026-11-14.md`）** |
| **M2** | 调度独立：`SchedulerApp` + `ManifestReconciler`、6 个作业任务、Redis 互斥锁与 `last_run`、`is_plugin_active` 门控 | `shadow` 对账 7 天（或约定观察期）作业触发 0 漏 0 重；`interval_ref` 热生效验证；禁插件任务跳过；重复 upsert 不新增行；切 `on` 后 app 内 `job_scheduler.task_count()==0` |
| **M3** | 消费独立：关闭内存通道、`ap.events.dispatch`、Redis 幂等、订阅广播、重试/DLQ、重放与降级补投改造、monitor 端点 | `shadow` 事件 `event_uuid` 差集为空且 handler 执行倍数=1；重投/重放不产生重复副作用；`dead_letter` 真进 DLQ；`on` 后 app 无 `ConsumerWorker` 实例 |
| **M4** | 收尾：回归脚本全面改造、监控告警上线、观察期结束评估删除旧实现、H-1 多 worker 可行性评估（单列二期） | 三份回归全绿；演练一次 `on→off` 回滚；关闭顺序无 Traceback；文档更新（设计 §偏差、as-built 架构） |

### 6.1 备选方案对比

| | 方案 A：最小改动（仅物理搬迁，消费侧仍用现有 `ConsumerWorker`） | **方案 B：统一 taskiq（推荐 / 本文评估对象）** |
|---|---|---|
| 调度 | taskiq-beat + jobs worker | 同左 |
| 消费 | 新建 `consumer` 容器跑现有 `ConsumerWorker`（`aio_pika` 直连），app 关闭本地消费 | `ap.events.dispatch` taskiq 任务，broker 统一 |
| app 改动 | 关闭 `ConsumerWorker.start()`、关闭内存通道、启停订阅同步 | 同左 + `publish` 改 `kiq` |
| 优点 | ACK/DLQ/重试/排空逻辑零改动，回滚最容易，M3 风险低 | 一套框架、async 原生无桥接、调度行 DB 化、统一重试/指标/追踪、顺带闭环 W3-1 幂等 |
| 缺点 | 两套消费框架长期并存；`ConsumerWorker` 仍单进程并发受限；幂等缺口需单独补 | 需重建 ACK/重试/DLQ/订阅同步语义；第三方 beat + 第二套 ORM；CLI 运维面较薄 |
| 适用 | 急于先解耦、观察期短、作为 B 的前置低风险阶段 | 目标态明确、愿意分两阶段灰度 |

> 折中路径：M3 先落方案 A 的 `consumer` 容器（`mode=on-a`），验证物理拆分与双通道关闭无误后，再在同一容器内把消费实现替换为 taskiq worker（`mode=on`）。两次切换各自可回滚。本文聚焦方案 B 的评估与落地。

> **§6.2 迁移章节（已撤销）**：原 Celery 版方案及其落地实现已由用户删除，不存在需要迁移的 Celery 工作副本，故迁移路径与成本评估移除。当前基线统一为 taskiq-only（见文首核查），无 Celery beat 与 taskiq beat 并行重复投递风险。



## 7. 风险登记

| # | 风险 | 等级 | 对策 |
|---|---|---|---|
| R1 | **双通道导致 handler 重复执行** | 高 | `mode=on` 必须跳过 `adapter:113`；M3 设专项回归用例；`shadow` 对账执行倍数=1 |
| R2 | worker 子进程各自初始化 Tortoise 连接池 | 中（较 Celery 版已降级） | `WORKER_STARTUP/SHUTDOWN` 生命周期；M1 最小 async 任务 + `--workers 2` 验证；`--workers 1` 兜底 |
| R3 | 订阅/插件启停跨进程不一致（幽灵订阅、漏订阅） | 高 | worker 复用 `event_center.initialize()`；Redis 广播 + 任务内 `is_plugin_active`/DB 双自查；M1 完备性对账 |
| R4 | taskiq 消息与 `#` 通配事件队列互相污染 | 高 | 独立 vhost；显式声明队列、禁自动建队列 |
| R5 | **beat 多实例重复投递 / 同作业重叠** | 中高 | `replicas=1` + PG advisory lock / Redis 选主锁；任务 Redis 互斥锁 + `when_executed` |
| R6 | `interval_ref`/handler 返回间隔/启停即时性语义偏差 | 中 | reconciler 重读 upsert；偏差逐条登记（§3.4）并让用户确认；任务内门控兜底 |
| R7 | 事件顺序性被多 worker 并发破坏 | 中 | M3 前逐插件确认顺序依赖；必要时按业务键分区或 `events` worker 并发=1 |
| R8 | 回归脚本硬编码单进程装配导致 CI 红 | 中 | 按 mode 分支改造，旧断言在 `off` 下原样保留 |
| R9 | `/monitor/*`、`/replay/*`、降级补投在目标态失真或失效 | 中 | 同步改造端点；补投改 `kiq`；灰度期新旧并列 |
| R10 | Redis 键冲突（现有 quota/lease 键、单 db） | 中 | 统一 `ap:taskiq:*` 前缀或独立 db 编号；不复用现有 db 的隐式键空间 |
| R11 | 凭据扩散 | 中 | 连接串只走 `_FILE` secret / 环境变量，不写入 `config.conf`；日志脱敏 |
| R12 | Windows 本地开发体验 | 低 | `--workers 1` + `--app-dir`；本地 sqlite 与 PG DDL 对账 |
| R13 | **taskiq-beat 第三方维护 / MPL-2.0** | 中 | 非官方单人项目，pin 1.4.0 并镜像内固化；评估期内保留 `mode=off` 回滚；如需商用合规复核 MPL 覆盖文件的修改义务 |
| R14 | **`taskiq-redis` 与 redis-py 版本冲突** | 中 | 按 D2 不引入，`DummyResultBackend` + 现有 redis-py 做幂等/锁；如必须引入，先做 quota / `RedisCache` / `health.py` 全量回归 |
| R15 | CLI 无 `-Q`、无 `inspect ping` 等价物 | 中 | 两个 broker 定义 + 显式 queue 声明；healthcheck 用 broker 连通性 + Redis 心跳键；M1 固化启动命令到 compose |
| R16 | SQLAlchemy 第二套 ORM + 调度表 DDL 对齐 | 中 | 仅调度用，连接同一 PG；`core_` 幂等 SQL 与 `SchedulerBase.metadata` 逐字段核对（参照 event_subscriptions 迁移做法）；`RUN_DB_MIGRATIONS=false` 部署流程单独执行 |
| R17 | ACK 默认值与 `AckableMessage` 支持未验证 | 中高 | 显式 `--ack-type when_executed`；M1 必须验证 broker 是否 yield `AckableMessage`，再决定 manual ack / `nack(requeue=False)` 实现；验证前不宣称 DLQ 闭环 |
| R18 | **基线曾不一致（已闭环）**：早期日志记载 Celery 方案已落地，但用户已删除该落地方案与文档，当前工作区无 celery 残留（requirements/代码/`deploy/celery/` 空目录/文档已删） | 已闭环 | 基线已统一为 taskiq-only；不再需要迁移动作，亦无 Celery beat 与 taskiq beat 并行重复投递风险 |

---

## 8. 一句话结论

**可以操作：现有 RabbitMQ + Redis + pydantic v2 + Python 3.12 全部对得上 taskiq 栈，缺的只是「4 个依赖 + 两张调度表 + 3 个新进程 + 发布端关闭内存通道 + 幂等落地」；相对原 Celery 候选方案去掉了异步桥接这一最大风险，代价是接受第三方 beat、SQLAlchemy 双 ORM 与更薄的 CLI 运维面。Celery 候选已删除、基线统一为 taskiq-only，建议按 D1–D7 拍板后，先 M1 做最小 async 与 ACK 语义验证，再 M2/M3 分阶段灰度。**

> 本文仅为方案，未修改任何代码、配置或部署文件，且 Celery 候选方案已删除、不再构成并行选项。实施前需先完成 D1–D7 决策与 M1 的技术验证（尤其 R2 的连接池隔离、R16 的 DDL 对齐、R17 的 ACK/DLQ 语义）。
