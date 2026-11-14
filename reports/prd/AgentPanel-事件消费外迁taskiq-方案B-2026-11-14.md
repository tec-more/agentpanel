# AgentPanel 调度与消费外迁 taskiq（方案 B 消费 + taskiq-beat 调度）详细设计

- 日期：2026-11-14
- 状态：**方案，未实施任何代码/配置/部署改动**
- 范围：**调度 + 消费 双外迁，统一在 taskiq 生态**。消费采用方案 B（DB 为真相源，§3-4）；调度采用 taskiq-beat（§9），取代原自封装 `JobScheduler` 随 API 进程启停的形态。agentpanel 仅保留"注册订阅 + 发布事件 + 声明作业 manifest"，执行全部外迁到 taskiq worker / beat 进程。
- 决策基线：本方案采用**方案 B**——taskiq worker 不跑 `register_ref`、不依赖进程内 registry，按 `event_name` 直接查 `EventSubscription`（enabled）并 `resolve_callable(handler_ref)` 解析 handler。该方案取代大蓝图 §3.5 的方案 A 消费实现。
- 依据：对 `base/common/events/event_bus_adapter.py`、`base/common/events/event_bus.py`、`base/core/events/registry.py`、`base/common/events/consumer_worker.py`、`base/plugins/audit/services/orm_event_service.py`、`base/start.py`、`requirements.txt` 的只读调研；taskiq / taskiq-aio-pika 版本与 API 于 2026-11-14 经 PyPI 元数据与官方文档核实。行号为调研时点，实施时需复核。
- 安全约定：只列配置**键名**，不记录 `config.conf` / `.env` / `secrets/` 的任何取值或凭据。

---

## 1. 现状事实（消费侧）

1. **handler 解析只读进程内 `_handler_registry`**：`event_bus_adapter.py:143` 的 `get_handlers(event_name)` 返回 `_handler_registry[event_name]`，该表由 `event_center.initialize()` → `register_ref` / `bind_manual` 在**进程内**填充（`registry.py:100/133`、`event_bus_adapter.py:131-136`）。独立消费进程若不重建该表，一个 handler 都跑不了。
2. **发布即双通道执行（陷阱）**：`event_bus_adapter.py:70-113` 一次 `publish` 先发 RabbitMQ（`routing_key=event_name`，写 `EventRecord(status="published")`），**第 113 行无条件 `await self._memory_bus.publish(...)` 同步执行全部内存订阅**；`ConsumerWorker._process_message:86` 又用 `_adapter.get_handlers()` 取同一批 handler。即当前一条事件 handler 在 app 进程内执行 1 次、在 MQ 消费路径再执行 1 次。外迁后若只搬 `ConsumerWorker` 不关内存通道，仍会双执行。
3. **消费端无幂等（W3-1 待办）**：`consumer_worker.py:84-137` 只改 `EventRecord` 状态为 `consuming/consumed/failed/dead_letter`，无"已 consumed 则跳过 handler"判断；发布侧幂等仅在 `EventCenter._idempotency` 进程内 dict（TTL 300s，`registry.py:24/197-205`），跨进程失效。
4. **ORM 探针是 async**：`orm_event_service.py:114/142` 的 `patched_model_save/delete` 本就是 `async def` 且 `await event_bus.publish(...)`，所有生产者（含探针）都从 async 上下文调用 `EventBusAdapter.publish`。切到异步的 `consume_event.kiq(...)` 是 1:1 替换，**不需要 sync→async 桥接**。
5. **taskiq 不在依赖里**：`requirements.txt` 仅有 `aio-pika>=10.0.1`，无 `taskiq` / `taskiq-aio-pika`（2026-11-14 复核）。

---

## 2. 目标架构

```
agentpanel (API 进程)
  ├─ 注册订阅: EventSubscription CRUD + register_ref(生产侧 ORM 探针)
  └─ 发布: EventBusAdapter.publish → 写 EventRecord(published) + consume_event.kiq(...)
                                                      │
                                                      ▼
                                                RabbitMQ (已有 broker)
                                                      │
                                                      ▼
taskiq worker (独立进程, 同镜像不同 entrypoint, 可多副本)
  └─ consume_event 任务:
       ① 按 event_uuid 幂等 (已 consumed 直接 ack 返回)
       ② 查 EventSubscription(enabled, event_name) → resolve_callable(handler_ref)
       ③ 逐 handler 执行 (单 handler 30s 超时, 异常隔离)
       ④ EventRecord: consuming → consumed / failed / dead_letter
```

- agentpanel 侧 `EVENT_LOCAL_DISPATCH=false`，**不再本地执行 handler**（消除双通道）。
- worker 与 API 共享同一套 `EventSubscription` 表与 handler 代码（同镜像），但 worker **不执行 `register_ref` 的生产探针段**，避免 worker 内 DB 写入又触发发布→重复入队。

---

## 3. 设计决策

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| D1 | handler 来源 | **DB 为真相源（方案 B）** | worker 不跑 register_ref，按 `event_name` 查 `EventSubscription(enabled)` → `resolve_callable`；天然支持运行期 manual 订阅、避免进程内状态不一致 |
| D2 | 任务粒度 | **单一通用任务** `consume_event(event_uuid, event_name, payload)` | 不为每个事件/订阅预注册 task，保留 manual 订阅运行时灵活性 |
| D3 | 发布路径 | `EventBusAdapter.publish` 改为"写 EventRecord → `consume_event.kiq(...)`"，去掉 aio_pika 直发 + 本地 `_memory_bus.publish` | 统一入队，消除双通道 |
| D4 | 生产探针位置 | **只在 agentpanel 跑**（`register_ref` 的 ORM patch 留在 API 进程） | worker 不执行 register_ref，防重入发布 |
| D5 | 重试/死信 | taskiq `retry_on_error` + `max_retries` + `acks_late`；`EventRecord` 仍记录状态机（含 `dead_letter`） | 不再依赖 RabbitMQ 自定义 DLQ；应用层保留重放能力 |
| D6 | 幂等 | 消费端按 `event_uuid` 去重（已终态跳过）；发布端 300s 内存去重迁 **Redis**（多 API worker 时跨进程生效） | 闭环 W3-1 |
| D7 | broker 选型 | `taskiq-aio-pika`（`AioPikaBroker`），复用现有 RabbitMQ，async 原生 | 与现有 aio-pika 栈契合；worker 即 asyncio loop，无桥接 |
| D8 | 灰度开关 | 新增 `EVENT_LOCAL_DISPATCH`（默认 true 保持现状）；`EVENT_CONSUMER_ENABLED` 控制 app 是否起 ConsumerWorker | 默认行为不变，回滚零代码改动 |

> 多 API worker 时的 vhost/队列隔离：若 app 与 worker 共用现有业务事件 vhost，taskiq 任务消息可能被旧 `ConsumerWorker` 当事件拉走。推荐为 taskiq 新增**专用 vhost / exchange / 队列**（`ap.events`），与现有 `<prefix>.main` 队列完全隔离（沿用大蓝图 R4 结论）。

---

## 4. 改动文件清单与接口契约

### 4.1 `requirements.txt`（新增依赖）
```
taskiq==0.13.0
taskiq-aio-pika==0.6.1
taskiq-beat==1.4.0        # 仅调度外迁(M4)需要; 见 §9
```
- `aio-pika` 保留（灰度期旧链路 / 健康检查）；不升版本。
- 结果后端用 `DummyResultBackend`（作业/事件都不需要返回值，零新增依赖，避免 `taskiq-redis` 与现有 redis-py 版本冲突——见大蓝图 D2/R14）。
- ⚠️ **`taskiq-beat==1.4.0` 依赖 `sqlalchemy>=2.0` 与 `python>=3.12`**（2026-11-14 经 PyPI 元数据核实）。本项目镜像为 `python:3.12-slim`，满足 Python 下限；但 SQLAlchemy 会成为 Tortoise 之外的**第二套 ORM 依赖**。本方案 §9 采用**自定义 `SchedulerSource` 直接读 `manifest.jobs`**（不依赖 taskiq-beat 默认的 PG 调度表 `scheduler_job`/`scheduler_run`），因此**不引入额外数据库表**，但 SQLAlchemy 包仍会随 taskiq-beat 装入运行时。如不能接受第二 ORM，备选：用 `taskiq scheduler`（官方）配合 `ListRedisScheduleSource`（存 Redis，复用现有 redis-py）替代 taskiq-beat，但届时需自管调度进程与 Redis 连接，工作量相近。

### 4.2 `base/common/events/taskiq_broker.py`（新增）
```python
from taskiq import DummyResultBackend, SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker

event_broker = AioPikaBroker(
    url="...",  # 由 [taskiq] 配置经 _FILE secret 注入, 不落 config.conf
    exchange=...,
    task_queues=[Queue(name="ap.events", routing_key="ap.events", durable=True)],
).with_result_backend(DummyResultBackend()).with_middlewares(
    SmartRetryMiddleware(default_retry_count=3, default_delay=5, use_jitter=True, use_delay_exponent=True)
)

async def get_event_broker() -> AioPikaBroker:
    return event_broker
```

### 4.3 `base/common/events/event_tasks.py`（新增）
```python
from base.common.events.taskiq_broker import event_broker
from base.core.events.models import EventRecord
from base.core.events.registry import resolve_subscription_handlers

@event_broker.task("ap.events.consume")
async def consume_event(event_uuid: str, event_name: str, payload: dict) -> None:
    rec = await EventRecord.get_or_none(event_uuid=event_uuid)
    if rec and rec.status in ("consumed", "dead_letter"):   # D6 消费端幂等
        return
    await EventRecord.filter(event_uuid=event_uuid).update(status="consuming")
    handlers = await resolve_subscription_handlers(event_name)   # D1
    last_error = None
    for handler in handlers:
        try:
            result = handler(event_name=event_name, **payload)
            if asyncio.iscoroutine(result):
                await asyncio.wait_for(result, timeout=30)
        except Exception as e:
            last_error = str(e)
            logger.error(f"事件处理器 {handler.__name__} 执行失败: {e}")
    if last_error:
        ...  # retry_count+1; 未超上限由 SmartRetryMiddleware 退避重试; 超上限置 dead_letter
    else:
        await EventRecord.filter(event_uuid=event_uuid).update(
            status="consumed", consumed_at=datetime.now(timezone.utc),
            processing_time_ms=...)
```
- `retry_on_error` 配合 `SmartRetryMiddleware`：失败自动退避重投；超 `max_retries` 后任务失败，`EventRecord` 置 `dead_letter`，不再重投（修正现状"只改 DB 不 reject"）。
- 重放接口 `/v1/events/replay/*` 改为 `consume_event.kiq(...)` 而非重新 `publish` 到业务 exchange。

### 4.4 `base/core/events/registry.py`（改造——新增 DB 解析）
```python
async def resolve_subscription_handlers(event_name: str, *, cache_ttl: float = 5.0) -> list[Callable]:
    """按 event_name 查 enabled EventSubscription, 解析 handler_ref → callable。带 5s 缓存。"""
    cache_key = f"_sub_handlers:{event_name}"
    if cached := _sub_cache.get(cache_key):
        if time.time() - cached[1] < cache_ttl:
            return cached[0]
    subs = await EventSubscription.filter(
        event_name=event_name, is_enabled=True, handler_ref__not=None).all()
    handlers = []
    for sub in subs:
        try:
            handlers.append(resolve_callable(sub.handler_ref))
        except Exception as e:
            logger.error(f"handler_ref 解析失败 {sub.handler_ref}: {e}")
    _sub_cache[cache_key] = (handlers, time.time())
    return handlers
```
- `get_handlers`（进程内 registry）保留用于过渡期兼容，但消费路径不再使用。
- **前提对账（M1）**：确保每一个消费侧 handler 都有对应 `EventSubscription` 记录（declared 由 `sync_plugin` 从 `manifest.events.subscribe` 生成；manual 由 API 创建）。纯生产侧逻辑（ORM 探针）不在此列。M1 做一次"进程内 registry ↔ EventSubscription 表"完备性对账并留档。

### 4.5 `base/common/events/event_bus_adapter.py`（改造 `publish`）
现状 `publish`（:70）：写 aio_pika Message 到 exchange（`routing_key=event_name`）+ 写 `EventRecord(published)` + 第 113 行 `_memory_bus.publish`。改为：
```python
async def publish(self, event_name, **kwargs):
    event_uuid = str(uuid.uuid4())
    payload = self._serialize_payload(kwargs)
    now = datetime.now(timezone.utc)
    source_module = kwargs.pop("_source_module", None)
    await EventRecord.create(event_uuid=event_uuid, event_name=event_name,
                            payload=payload, status="published", published_at=now,
                            source_module=source_module)
    try:
        await consume_event.kiq(event_uuid, event_name, payload)   # D3
    except Exception as e:
        # MQ 不可用 → fail-closed, 让调用方/网关返回 503; 不保留"degraded_published 静默丢"
        logger.error(f"事件入队失败( fail-closed ): {e}")
        raise
    if settings.EVENT_LOCAL_DISPATCH:                              # D8
        await self._memory_bus.publish(event_name, **kwargs)
```
- 移除对 `self._connection_manager.get_channel()/get_exchange()` 的 aio_pika 直发（`consumer_worker` 移除后该连接管理仅剩健康检查用途，可保留或精简）。
- `EVENT_LOCAL_DISPATCH`：agentpanel 侧置 `false`（关闭本地派发）；默认 `true` 时本地仍派发一份，便于灰度与回滚。

### 4.6 `base/start.py`（改造）
- 移除 `ConsumerWorker` 启动（≈:95-110）与关闭排空块（≈:158-166）在 `EVENT_CONSUMER_ENABLED` 为 false 时跳过；保留 `event_bus.initialize()` / `event_center.initialize()`（app 仍需 `register_ref` 生产探针 + `EventSubscription` 注册）。
- 新增：`await get_event_broker().connect()`（确保 publish 可用）；关闭期 `await get_event_broker().disconnect()`。

### 4.7 `run_taskiq_worker.py`（新增入口）
职责：引导最小上下文 + 启动 taskiq worker（**不消费 API 请求、不跑 `register_ref` 生产探针**）。
```
1. init_data()                                    # Tortoise 连接池
2. RedisCache.get_instance()
3. get_plugin_manager().set_app(FastAPI()) + load_enabled_plugins()
   # 仅加载 manifest / 路由注册所需; **跳过 register_ref 的 producer 修补** (D4)
4. await get_event_broker().connect()
5. event_broker.run()  (监听 SIGTERM 优雅关闭, 对齐现有 8s 在途排空语义)
```
- 关键：worker 必须能 import 全部 handler（**同镜像**），但**不能**执行 `register_orm_audit_handlers`，否则 worker 内 DB 写入再触发发布→重复入队。实现：在 `event_center.initialize` 增加 `role` 参数（`both` 默认 / `publisher` / `consumer`）；worker 传 `role="consumer"`，只预热 `resolve_subscription_handlers` 缓存、不调 `register_ref`。
- 本地等价两进程：`EVENT_LOCAL_DISPATCH=false python run.py` 与 `EVENT_LOCAL_DISPATCH=false python run_taskiq_worker.py`。

### 4.8 `deploy/app/docker-compose.eventworker.yml`（新增，覆盖文件）
不动主 `docker-compose.yml`（保护灰度基线）。
```yaml
services:
  app:
    environment:
      EVENT_LOCAL_DISPATCH: "false"
      EVENT_CONSUMER_ENABLED: "false"
  event-worker:
    image: agentpanel-app:latest
    command: ["python", "run_taskiq_worker.py"]
    restart: always
    environment:
      DEPLOY_ENV: docker
      EVENT_LOCAL_DISPATCH: "false"
    volumes: ["./config.conf:/app/config.conf", "../../logs:/app/logs", "../../storage:/app/storage"]
    networks: [app_default]
```
启动：`docker compose -f deploy/app/docker-compose.yml -f deploy/app/docker-compose.eventworker.yml up -d`。

### 4.9 `tests/regression_event_taskiq.py`（新增）
- admin 发布一条事件 → taskiq worker 执行 1 次、`EventRecord=consumed`。
- 连发 20 条 → 恰好 20 次（同时对照基线，确认从"可能双执行"收敛为"单次"）。
- 运行期新建 manual 订阅 → 在 5s 缓存周期内 worker 生效。
- 停 worker → MQ 积压不丢，重启追平。
- 停 MQ → publish 失败（fail-closed）而非静默丢弃。
- 现有两套回归 `regression_plugin_assembly` 24/24、`regression_pending` 42/42 在默认 `both`（`EVENT_LOCAL_DISPATCH=true`、`EVENT_CONSUMER_ENABLED=true`）下全绿（回滚零改动）。

---

## 5. 分阶段实施计划

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **M0** | 方案评审；确认 taskiq 专用 vhost / 队列创建方式、凭据 `_FILE` 注入路径、EventSubscription 完备性对账方法 | 本文件签字 |
| **M1** | 解耦审计（确认每个消费侧 handler 有 EventSubscription 记录）+ `resolve_subscription_handlers` 抽离 + 执行次数基线打点（不改部署） | 基线打点完成；`role="consumer"` 引导可在同进程模拟；DB 解析与进程内 registry 输出一致 |
| **M2** | 引入 taskiq：依赖、`taskiq_broker.py`、`event_tasks.py`、改 `publish`、新增 `EVENT_LOCAL_DISPATCH`/`EVENT_CONSUMER_ENABLED` | 本地两进程跑通：admin 发布 → worker 执行 1 次；现有两套回归全绿 |
| **M3** | 拆分进程：`run_taskiq_worker.py` + compose 覆盖文件；移除 app 侧 ConsumerWorker（保留代码一个观察期） | 连发 20 条恰好 20；manual 订阅 5s 内生效；停 worker 积压不丢；停 MQ fail-closed；灰度 24h 无 503 尖刺、无 Traceback |
| **M4** | 引入 taskiq-beat：`taskiq_schedule.py` + `run_plugin_job` 通用任务 + `PluginJobScheduleSource`；移除 `plugin_manager._sync_plugin_jobs` 钩子；beat 单实例入队、worker 执行 | 单进程内 beat 按 manifest 入队、worker 执行；启停插件 ≤30s 生效；现有两套回归 24/24 + 42/42 全绿 |
| **M5** | 拆分 beat/worker 进程 + compose；加固 `run_plugin_job`（DS6 强制 async / `wait_for` 超时 / print→logger）；`customer` 作业 print→logger | 多 worker 下作业只执行 1 次；停 beat 作业停摆不丢；灰度 24h 无 503 / Traceback |

---

## 6. 风险与缓解

| # | 风险 | 等级 | 对策 |
|---|---|---|---|
| R1 | **双通道导致 handler 重复执行** | 高 | `EVENT_LOCAL_DISPATCH=false` 必须生效；M3 设专项回归（执行倍数=1）；对照基线确认收敛 |
| R2 | **生产探针误入 worker → 重复入队** | 高 | `role="consumer"` 跳过 `register_ref`；worker 不调 `register_orm_audit_handlers` |
| R3 | **消费端无幂等（W3-1）** | 中高 | `consume_event` 按 `event_uuid` 终态跳过；发布端去重迁 Redis（多 API worker 时） |
| R4 | taskiq 消息与 `#` 通配业务事件队列互相污染 | 高 | 独立 vhost / exchange / 队列 `ap.events`，禁自动建队列 |
| R5 | 单队列吞吐瓶颈 | 中 | taskiq + RabbitMQ 竞争消费 + 多 worker 副本横向扩展 |
| R6 | 回归脚本硬编码单进程装配导致 CI 红 | 中 | 按开关分支改造，`off`（`EVENT_LOCAL_DISPATCH=true`）保留原断言 |
| R7 | `EVENT_LOCAL_DISPATCH` 开关误配导致双执行/漏执行 | 中 | 部署清单 double-check；health 端点暴露当前开关态 |
| R8 | 降级路径静默丢事件 | 中 | 改 fail-closed（publish 失败抛错 → 503），不保留 `degraded_published` 静默丢分支 |

---

## 7. 回滚

- 默认 `EVENT_LOCAL_DISPATCH=true` + `EVENT_CONSUMER_ENABLED=true` 时行为完全不变，**两套现有回归在 `off` 态零回归**。
- 回滚顺序：**先停 `event-worker` → 再把 app 的 `EVENT_CONSUMER_ENABLED` 打开**（`EVENT_LOCAL_DISPATCH` 保持 false，由 app 从 MQ 消费积压），稳定后再决定是否开本地派发。两边同时开会短暂双执行。
- 旧 `ConsumerWorker` / `RabbitMQConnectionManager` / `aio_pika` 直发代码保留一个观察期，观察期结束后再评估删除。

---

## 8. 与既有大方案的关系

- 本方案**完整取代** `AgentPanel-调度与消费服务独立化-taskiq可行方案-2026-11-14.md`：
  - **消费**取代其 §3.5 方案 A（worker 复用 `register_ref` + 进程内 registry），改采用本方案方案 B（DB 为真相源，§3-4）。
  - **调度**取代其"taskiq-beat + `scheduler_job`/`scheduler_run` 两表"章节，但落地形态以本方案 §9 为准（不引入额外两表，改用自定义 `SchedulerSource` + 通用任务 + 可选 `JobRun` 日志）。
- 本方案的 vhost/队列隔离（R4）、ACK/DLQ 语义（R3/D5）、灰度开关结论与大蓝图一致，可直接复用。
- 大蓝图中"agent 执行控制面 `_controls` 外置 / 事件订阅跨进程广播 / quota 进程内降级收口"等**非调度非消费**项不在本方案范围，需另立项（参见本会话多 worker 讨论）。

---

## 9. 调度外迁 taskiq-beat（新增，2026-11-14 决策）

> 决策：消费外迁 taskiq 已定方案 B；**调度也迁 taskiq-beat**，使调度与消费统一在 taskiq 生态，并借 beat 单实例天然解决"多 worker 下作业重复执行"问题。

### 9.1 现状事实（调度侧）
1. **纯自封装 asyncio 调度**：`base/common/jobs/scheduler.py` 的 `JobScheduler` 仅用标准库 `asyncio.create_task` + 自写 `_run_loop`，无 APScheduler/Celery（已核实 `requirements.txt` 无相关依赖）。
2. **随 API 进程启停、多 worker 双跑**：`base/start.py:124` 在 lifespan `await job_scheduler.start_all()`；多 worker 时每个进程各跑一套，**无分布式锁** → 6 个作业（订单取消/审计清理/会员重算/网关对账/配额对账/预占清理）重复执行 N 遍。
3. **插件启停靠钩子**：`plugin_manager._sync_plugin_jobs` 在 enable 时注册、disable 时 cancel（对称）；平台作业由 `platform.py:install()` 静态注册 2 个（`quota_reconcile`、`quota_hold_cleanup`）。
4. **manifest.jobs 声明**：`name` / `handler_ref` / `interval_seconds` 必填；`requires_plugins`（customer 依赖 `llm`）、`interval_ref`（harness 每轮重读间隔）可选；`plugin_contract.validate_jobs()` 仅验格式不 import。
5. **无存活巡检/超时（既有隐患）**：`await result` 无 `wait_for`，同步/卡死 handler 会冻结事件循环；task 意外死掉无自愈（设计文档 §9.5 曾建议巡检未做）。

### 9.2 目标架构
```
taskiq-beat (单实例进程)
  └─ PluginJobScheduleSource: 每 ~30s 读 已启用插件 manifest.jobs + 平台作业
        → 产出 ScheduleEntry(任务=run_plugin_job, args=(plugin,job), interval=...)
                                                      │ enqueue
                                                      ▼
                                                RabbitMQ (ap.jobs 队列, 与 ap.events 隔离)
                                                      │
                                                      ▼
taskiq worker (独立进程, 与事件消费同一 broker.run(), 可多副本竞争消费)
  └─ run_plugin_job(plugin, job):
       ① resolve handler_ref → callable
       ② 可选 Redis 租约 (多 worker 副本时防重复; 单副本可不启)
       ③ asyncio.wait_for(handler(), timeout) + 强制 async + print→logger
       ④ 记录 JobRun 状态 (可选)
```
- beat **只入队不执行**；执行由 worker 完成。单 beat + RabbitMQ 竞争消费 → 天然单实例语义，直接解除"多 worker 作业双跑"（这是迁 beat 相对保留自封装调度器的核心收益）。
- 插件禁用 → 下一个 beat tick（≤30s）不再产出该作业 schedule → 自然停摆，**无需 `plugin_manager` 显式 cancel 钩子**，简化 plugin_manager。
- `interval_ref`（harness）每次 source 轮询重读，比现状"每轮重读"更早生效。

### 9.3 设计决策（调度）
| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| DS1 | 调度框架 | **taskiq-beat**（与消费共用 `event_broker`，独立队列 `ap.jobs`） | 与消费统一 taskiq 生态；beat 单实例天然防重复；复用现有 RabbitMQ |
| DS2 | 任务粒度 | **单一通用任务** `run_plugin_job(plugin_name, job_name)` | 不为每个 job 预注册；支持运行期插件启停/新增 |
| DS3 | 调度源 | **自定义 `SchedulerSource`** 读 enabled 插件 manifest.jobs + 平台作业 | 动态 enable/disable 即时生效、支持 `interval_ref` 重读 |
| DS4 | 插件钩子 | **移除 `plugin_manager._sync_plugin_jobs`** 的 cancel/start；改由 source 主导 | 消除与多进程状态耦合；启停对称由 source 轮询保证（≤30s 生效） |
| DS5 | 平台作业 | 在 source 中静态包含 `plugin_name="__platform__"` 的 2 个作业 | 不依赖任何插件，恒启 |
| DS6 | 执行加固 | 强制 async（`inspect.iscoroutinefunction`，否则 `to_thread` 或拒绝）、`wait_for` 超时（manifest 可选 `timeout_seconds`，默认 120）、`print`→`logger` | 闭环此前提出的 4 项调度器加固，消除"同步 handler 冻结事件循环"风险 |
| DS7 | 单实例保障 | 单 beat 进程 + 可选 Redis 租约（多 worker 副本时） | 单副本已足够；多副本时租约兜底（复用 §4 的 `lease.py` 思路） |
| DS8 | 灰度开关 | `JOB_SCHEDULER_ENABLED`（默认 true 保持现状）；`SCHEDULER_ROLE=beat|worker|both` 控制本进程是否起 beat / 消费 | 默认行为不变，回滚零代码改动 |

### 9.4 改动文件清单与接口契约（调度）
- `base/common/jobs/taskiq_schedule.py`（新增）：`PluginJobScheduleSource(SchedulerSource)` + `run_plugin_job` 任务（可与 `event_tasks.py` 共用 `event_broker`）。
- `base/common/jobs/scheduler.py`（废弃）：`JobScheduler` 保留观察期，新代码不再调用；`start_all` / `_sync_plugin_jobs` 标记 deprecated。
- `base/plugins/*/jobs/*.py`：保持不变（`run` 仍 async）；`customer/jobs/membership.py` 的同步 `print` 改为 logger（DS6）。
- `base/start.py`：`await job_scheduler.start_all()` 仅在 `JOB_SCHEDULER_ENABLED and SCHEDULER_ROLE=="both"`（即旧行为）时调用；beat/worker 角色由独立入口负责。
- `plugin_manager.py`：移除 `_sync_plugin_jobs` 对 `job_scheduler` 的调用（DS4）；保留 `manifest.jobs` 读取/校验。
- `run_taskiq_beat.py`（新增）：引导最小上下文 + `taskiq-beat` 启动（挂 `PluginJobScheduleSource`）。
- `run_taskiq_worker.py`（改造 §4.7）：`broker.run()` 同时消费 `ap.events` 与 `ap.jobs` 两队列；保持 `role="consumer"` 不跑生产探针。
- `deploy/app/docker-compose.eventworker.yml`（改造 §4.8）：新增 `beat` 服务（`command: ["python","run_taskiq_beat.py"]`）；`event-worker` 增加 `ap.jobs` 队列消费。

### 9.5 分阶段实施（调度）
| 阶段 | 内容 | 验收 |
|---|---|---|
| **M4** | 引入 taskiq-beat：`taskiq_schedule.py` + `run_plugin_job` + `PluginJobScheduleSource`；移除 `plugin_manager._sync_plugin_jobs` 钩子 | 单进程内 beat 按 manifest 入队、worker 执行；启停插件 ≤30s 生效；现有两套回归 24/24 + 42/42 全绿 |
| **M5** | 拆分 beat/worker 进程 + compose；加固 `run_plugin_job`（DS6）；`customer` 作业 print→logger | 多 worker 下作业只执行 1 次；停 beat 作业停摆不丢；灰度 24h 无 503 / Traceback |

### 9.6 风险（调度）
| # | 风险 | 等级 | 对策 |
|---|---|---|---|
| RS1 | 移除 plugin_manager 作业钩子后启停不对称 | 中 | source 轮询 ≤30s 收敛；M4 专项回归"禁用→不执行、启用→恢复" |
| RS2 | beat 单点 | 中 | beat 无状态，挂了重启即恢复；作业下一 tick 补跑（需 handler 幂等，现有 6 个均幂等） |
| RS3 | `interval_ref` 解析失败导致 harness 作业停滞 | 中 | source 捕获异常，保留上一轮 interval；告警 |
| RS4 | 多 worker 副本下 `run_plugin_job` 重复（误起多 beat 时） | 低-中 | beat 进程数=1 约束（compose 单副本）；可选 Redis 租约兜底 |
| RS5 | 旧 `JobScheduler` 残留引用导致双调度 | 中 | M4 全量 grep `job_scheduler` 调用点清零；观察期保留不删 |

### 9.7 回滚（调度）
- `JOB_SCHEDULER_ENABLED=true` + `SCHEDULER_ROLE=both`（默认）时走旧 `JobScheduler`，行为不变；新 beat/worker 入口不参与。
- 回滚顺序：停 `beat` 与 `event-worker` → 恢复 app 的 `JOB_SCHEDULER_ENABLED=true` → 旧调度器随 API 进程重启接管。
- 旧 `scheduler.py` 保留观察期，确认无遗漏调用后下一版本删除。
