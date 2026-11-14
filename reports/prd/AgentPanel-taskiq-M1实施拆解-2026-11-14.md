# AgentPanel · taskiq 独立调度与消费 · M1 实施任务拆解

- 日期：2026-11-14
- 上级文档：`AgentPanel-调度与消费服务独立化-taskiq可行方案-2026-11-14.md`（以下简称「主方案」）
- 阶段：M1（基础设施与骨架 + R2/R16/R17 三项必验），**不改动 `run.py` / `base/start.py` 的业务装配**，app 侧 `mode` 在 M1 保持 `off`。
- 状态：**拆解态，未实施任何代码/配置/部署改动**。
- 安全约定：只列配置键名与 `_FILE` secret 约定，不记录 `config.conf` / `.env` / secrets 任何取值。

---

## 0. M1 范围

| 做（M1） | 不做（推迟到 M2/M3/后续） |
|---|---|
| 依赖 pinning（requirements） | 改 `base/start.py` 关闭本地 `job_scheduler` / `ConsumerWorker`（M2/M3） |
| 新增 `[taskiq]` 配置段与 `base/common/taskiq_app/` 模块骨架 | 关 `event_bus_adapter.py:113` 内存双通道（M3，R1） |
| 两张调度表 `core_` 幂等 SQL（基于 taskiq-beat 真实模型） | 事件消费改造 `ap.events.dispatch`（M3，R3/R7/R9） |
| compose 两服务（beat / worker）+ healthcheck | Redis 幂等/锁/订阅广播落地（M2/M3，R10） |
| 启动命令固化（CLI 参数明文） | 监控告警、Jaeger 透传（M4） |
| **R2 / R16 / R17 三项必验并留档** | app 侧 `mode=on` 切换与回归脚本全面改造（M2/M4） |
| 最小 smoke 任务端到端跑通（独立 taskiq 进程，不依赖 app） | 调度表迁移 `RUN_DB_MIGRATIONS=false` 部署流程自动执行（仍单独跑 SQL） |

> M1 交付物是「可独立启动的 taskiq 两进程（beat + worker）+ 已建调度表 + 三项验证结论」，此时 app 仍按现状运行（`mode=off`），`JobScheduler` / `ConsumerWorker` 原样保留，零回滚风险。

---

## 1. 依赖 pinning

在 `requirements.txt` 追加（**不升级** `redis` / `aio-pika`，保持 `redis>=5.0.0` / `aio-pika>=10.0.1`）：

```text
taskiq==0.13.0
taskiq-aio-pika==0.6.1
taskiq-beat==1.4.0
sqlalchemy>=2.0,<3
```

- **不装 `taskiq-redis`**（D2 决策）：结果后端用 `DummyResultBackend`，幂等/锁沿用现有 `redis>=5.0.0`。
- taskiq-beat 1.4.0 真实依赖（解包 wheel 实测）：`sqlalchemy>=2.0.0`、`taskiq>=0.12.0`；仅调度用第二套 ORM，不影响现有 Tortoise。
- 可选 extras：`taskiq[metrics]`（项目已有 `prometheus-client`）、`taskiq[opentelemetry]`（版本约束见主方案 §3.1，M1 先不装，指标埋点留 M4）。
- 验证：在隔离 venv（Python 3.12）`pip install` 上述四行，`python -c "import taskiq, taskiq_aio_pika, taskiq_beat, sqlalchemy"` 全通过；`pip show` 确认 `redis` / `aio-pika` 解析版本未被顶高。

---

## 2. `[taskiq]` 配置段与 `_FILE` secret 约定

沿用 `packages/common/config.py:99` 的 `read_secret_file(env)`（读 `<ENV>_FILE`）与 `read_env_value(..., secret=True)`。新增配置键（**只列键名**）：

| 配置键 | 环境变量 | 类型 | 说明 |
|---|---|---|---|
| `broker_url` | `TASKIQ_BROKER_URL_FILE` | secret | amqp 完整 URL，含 **专用 vhost** 路径 `…/agentpanel` |
| `db_url` | `TASKIQ_DB_URL_FILE` | secret | PG async URL（`postgresql+asyncpg://…`），复用现有 PG 库 |
| `vhost` | `TASKIQ_VHOST` | str | `agentpanel`（部署侧事实，见 §9.4） |
| `exchange` | `TASKIQ_EXCHANGE` | str | 单 broker 共用 exchange（jobs/events 两队列同 broker） |
| `jobs_queue` / `events_queue` / `dlq_queue` | `TASKIQ_JOBS_QUEUE` / `…_EVENTS_QUEUE` / `…_DLQ_QUEUE` | str | 默认 `ap.jobs` / `ap.events` / `ap.dlq` |
| `result_backend` | `TASKIQ_RESULT_BACKEND` | str | M1 固定 `dummy` |
| `ack_type` | `TASKIQ_ACK_TYPE` | str | 固定 `when_executed`（R17） |
| `workers` | `TASKIQ_WORKERS` | int | worker 默认 2（R2 验证用） |
| `max_async_tasks` / `max_prefetch` | `TASKIQ_MAX_ASYNC_TASKS` / `…_MAX_PREFETCH` | int | 单 worker 同池；events 建议 `max_prefetch=0` |
| `shutdown_timeout` / `wait_tasks_timeout` | `TASKIQ_SHUTDOWN_TIMEOUT` / `…_WAIT_TASKS_TIMEOUT` | float | 对齐现有 12s/8s 排空 |
| `beat_sync_interval` / `beat_idle_sleep` | `TASKIQ_BEAT_SYNC_INTERVAL` / `…_IDLE_SLEEP` | float | 直传 `SchedulerConfig` |
| `reconcile_interval` | `TASKIQ_RECONCILE_INTERVAL` | float | reconciler 扫描周期，建议 5 |
| `beat_scheduler_id` | `TASKIQ_BEAT_SCHEDULER_ID` | str | **留空用默认随机（uuid4）**；禁止钉固定值，否则重启可能重复投递（见 §5.1） |
| `lock_ttl` / `idempotency_ttl` | `TASKIQ_LOCK_TTL` / `…_IDEMPOTENCY_TTL` | int | Redis 锁/幂等键 TTL（秒） |
| `event_handler_timeout` / `job_timeout` | `TASKIQ_EVENT_HANDLER_TIMEOUT` / `…_JOB_TIMEOUT` | float | 单 handler / 任务超时 |
| `retry_max` / `retry_delay` | `TASKIQ_RETRY_MAX` / `…_RETRY_DELAY` | int | `SmartRetryMiddleware` 参数 |
| `redis_key_prefix` / `redis_db_taskiq` | `TASKIQ_REDIS_KEY_PREFIX` / `…_REDIS_DB` | str/int | 统一 `ap:taskiq:*` 前缀（R10） |
| `subscription_channel` | `TASKIQ_SUBSCRIPTION_CHANNEL` | str | Redis 订阅变更广播频道 |
| `metrics_port` | `TASKIQ_METRICS_PORT` | int | `PrometheusMiddleware` 端口 |
| `run_history_retention_days` | `TASKIQ_RUN_HISTORY_RETENTION_DAYS` | int | `SchedulerConfig`，建议显式设值 |

> 这些键 **不写入 `config.conf`**（该文件已有明文凭据）；broker/db 连接串只走 `_FILE` secret，沿用 `read_secret_file` 契约。

---

## 3. 模块布局：`base/common/taskiq_app/`

| 文件 | 职责 | 关键签名 / 内容 |
|---|---|---|
| `__init__.py` | 包初始化 | — |
| `config.py` | 读取 §2 配置，暴露 `TaskiqSettings` dataclass | `TaskiqSettings.load()` → 调 `read_env_value(..., secret=True)` |
| `schema.py` | pydantic 消息契约（D7） | `JobMessage`、`EventMessage`，`model_dump(mode="json")` / `model_validate` |
| `broker.py` | 单个 `AioPikaBroker` 定义 + 中间件 | `broker`（`task_queues=[ap.jobs, ap.events]`），带 `DummyResultBackend` + `SmartRetryMiddleware` + `PrometheusMiddleware`；显式 `exchange`；各插件 `@broker.task` 作业与 `dispatch` 任务经 `tasks_registry` 静态注册（CLI 无 `-Q`，见主方案 §2.1） |
| `jobs.py` | worker 生命周期（**不再有通用 `run_job` 分发**，见 §3.1） | `@broker.on_event(WORKER_STARTUP)` 内 `Tortoise.init` + `RedisCache.get_instance()` + `initialize_event_center()` + `import tasks_registry`；`@WORKER_SHUTDOWN` 排空 + `Tortoise.close_connections()` |
| `tasks_registry.py` | manifest 驱动发现并 import 全部已安装插件的 job 模块（含平台作业），触发 `@broker.task` 注册（见 §3.1 ②） | `import_all_job_tasks()` 扫描 `manifest.jobs[].handler_ref` 的 module 段 import（跨进程安全、单模块失败隔离）；平台作业 `base/common/jobs/platform.py` 单独 import |
| `events.py` | 事件 dispatch 任务（M3 才接真实业务；M1 仅骨架 + smoke） | `dispatch(payload: dict)` 骨架（label `ap.events`）；M1 只做 pydantic 往返与 ACK 验证，不接 `ConsumerWorker` 逻辑 |
| `scheduler.py` | 构建 `SchedulerApp` | `scheduler_app = SchedulerApp(broker=broker, session_factory=..., config=SchedulerConfig(sync_interval_seconds=1.0, idle_sleep_seconds=0.2, dispatch_retry_seconds=5, dispatch_concurrency=32, dispatch_batch_size=256, record_runs=True, run_history_retention_days=<显式>, default_timezone="UTC"))` |
| `reconcile.py` | `ManifestReconciler`（主方案 §3.4） | `async def upsert_schedules(session)`：扫 `get_enabled_plugins_from_manifests()` + 各 `manifest.jobs` + 平台作业 → 与 `scheduler_job` diff → 对每作业 `scheduler_app.create_scheduler(job_id=f"{owner}:{name}", task=<真实 task 对象>, trigger=PeriodicSchedule(interval=IntervalTrigger(seconds=interval))).upsert(session)`；`task=<真实 task 对象>` 由 `from base.plugins.<owner>.jobs.<mod> import <fn>` 取得（taskiq-beat 要求已注册对象）；`interval_ref` 热重载已迁 reconciler（§3.1）；插件禁用 `pause`/`delete` |
| `health.py` | 两进程 healthcheck 脚本 | 见 §6 |

> `scheduler_job` 行的 `task=` 必须是已注册 `TaskiqTask` 对象（taskiq-beat `create_scheduler` 要求），reconciler 直接 import 对应插件模块的 task 函数。
> `WORKER_STARTUP` 在同一 asyncio loop 内建连接池 → 这是 R2「消除异步桥接」的落点。

### 3.1 现有任务 `@broker.task` 重构方案（替代通用分发 `run_job`）

> **决策依据**：用户 2026-11-14 确认「逐任务 `@broker.task` + 静态聚合 import」「`interval_ref` 热重载迁到 reconciler」。本方案**不采用** M1 初版的单一通用 `run_job` 分发：现有每个作业改成**各自一个真实的 `@broker.task`**，beat 直接投递到该 task，去掉 `run_job` 中转。
>
> **已核实现状（2026-11-14 读源码）**：当前共 **6 个**已装载作业，handler 全部已是单轮 `async def run() -> None` / `async def quota_*(...) -> None`（W2-3 已剥离 while/sleep/取消），改造成本极低——仅需在函数上加 `@broker.task` 装饰器 + 让 worker 静态 import。

**现状盘点：当前 6 个已装载作业（改造前）**

| job_id（`{owner}:{name}`） | 来源 | `handler_ref` | `interval_seconds` | `interval_ref` | `requires_plugins` |
|---|---|---|---|---|---|
| `audit:audit_cleanup` | `base/plugins/audit/manifest.json` | `base.plugins.audit.jobs.cleanup:run` | 86400 | — | — |
| `customer:update_membership_data` | `base/plugins/customer/manifest.json` | `base.plugins.customer.jobs.membership:run` | 600 | — | `["llm"]` |
| `harness:gateway_reconcile` | `base/plugins/harness/manifest.json` | `base.plugins.harness.jobs.reconcile:run` | 600 | `base.plugins.harness.jobs.reconcile:resolve_interval` | — |
| `sales:cancel_expired_orders` | `base/plugins/sales/manifest.json` | `base.plugins.sales.jobs.orders:run` | 300 | — | — |
| `platform:quota_reconcile` | `base/common/jobs/platform.py::install` 代码注册 | `base.common.jobs.platform:quota_reconcile` | 60 | — | —（平台级） |
| `platform:quota_hold_cleanup` | 同上 | `base.common.jobs.platform:quota_hold_cleanup` | 60 | — | —（平台级） |

> 注：平台作业不经过 `manifest.jobs`，由 `platform.py::install(scheduler)` 在 `JobScheduler.start_all()` 时 `register_platform_job` 代码注册；改造后同样包成 `@broker.task`，但「是否启用」不再由插件启停驱动，而是随 worker 永驻（与现状 `register_platform_job` 语义一致）。

**改造步骤**

**① 每个 job 模块加 `@broker.task` 装饰器（真实文件 + 真实函数，仅加 decorator）**

```python
# base/plugins/audit/jobs/cleanup.py（现状：9 行，仅加 1 行装饰器）
from base.common.taskiq_app.broker import broker

@broker.task(task_name="audit:audit_cleanup", queue_name="ap.jobs")   # ← 新增
async def run() -> None:
    """清理过期数据变更日志（原 audit_cleanup_task 的单轮逻辑）。"""
    ...
```

```python
# base/plugins/customer/jobs/membership.py（原 run 不改；仅加装饰器）
from base.common.taskiq_app.broker import broker

@broker.task(task_name="customer:update_membership_data", queue_name="ap.jobs")  # ← 新增
async def run() -> None:
    ...
```

```python
# base/plugins/harness/jobs/reconcile.py（run + resolve_interval 都保留）
from base.common.taskiq_app.broker import broker

@broker.task(task_name="harness:gateway_reconcile", queue_name="ap.jobs")  # ← 新增
async def run() -> None:
    ...

# resolve_interval 不注册为 task，仅作为 reconciler 的「间隔解析函数」复用（见 ④）
def resolve_interval() -> int:
    ...
```

```python
# base/plugins/sales/jobs/orders.py（仅加装饰器）
from base.common.taskiq_app.broker import broker

@broker.task(task_name="sales:cancel_expired_orders", queue_name="ap.jobs")  # ← 新增
async def run() -> None:
    ...
```

```python
# base/common/jobs/platform.py（两个平台作业，随 worker 永驻）
from base.common.taskiq_app.broker import broker

@broker.task(task_name="platform:quota_reconcile", queue_name="ap.jobs")  # ← 新增
async def quota_reconcile() -> None:
    ...

@broker.task(task_name="platform:quota_hold_cleanup", queue_name="ap.jobs")  # ← 新增
async def quota_hold_cleanup() -> None:
    ...
```

> **`broker.task` 装饰器语义（基于 taskiq 0.13.0 / taskiq-aio-pika 0.6.1 源码核实）**：taskiq 的 `@broker.task(task_name=..., **labels)` 在 import 时把函数注册进 broker 的任务表；`task_name` 全局唯一（用 `owner:name` 天然不冲突，复用现有 `spec.key` 命名）。**`queue_name` 不是独立参数，而是 taskiq-aio-pika 的路由 label**——`AioPikaBroker` 构造参数 `label_for_routing` 默认即 `"queue_name"`，发布时读 `message.labels["queue_name"]` 作为 RabbitMQ routing key；当 broker 声明了**多个** `task_queues`（本方案 `task_queues=[ap.jobs, ap.events]`）时，每个 task **必须**带 `queue_name` label 指明落哪个队列，否则在 DIRECT exchange 下抛 `IncorrectRoutingKeyError`。`dispatch` 任务用 `queue_name="ap.events"`，各作业用 `queue_name="ap.jobs"`。因所有 handler 无参且返回 None，beat 投递时 `task_args=[]` / `task_kwargs={}`。

**② 新增 `base/common/taskiq_app/tasks_registry.py`：manifest 驱动发现 + 聚合 import**

> **发现机制决策（手写清单 vs 裸 glob vs manifest 驱动）**：
> - **手写清单（初版）**：每加一个作业模块要手动补一行 import，易漏；漏了则 beat 投递但 worker 无 handler → 消息卡死/报错，维护成本高。
> - **裸 `glob("base/plugins/*/jobs/*.py")`**：`jobs/` 目录实测含 `__init__.py` 与未来可能的 helper 模块，裸扫会误 import、污染注册表或触发无关副作用；且文件名与 `task_name` 无强制映射，禁用文件名推断后仍不解决「扫到非任务模块」问题。
> - **✅ manifest 驱动发现（M1 采用）**：直接复用各插件 `manifest.json` 的 `jobs[*].handler_ref`（`module:callable`）抽取 module 段 import。与 reconciler(beat 侧) 共用**同一真源**，零维护、不误扫、天然去重；仅「运行时新装插件」需重启 worker（与现有架构一致，M1 接受）。

```python
# tasks_registry.py —— worker 启动 import 本模块即触发全部 @broker.task 注册（跨进程安全）
"""Worker 启动聚合 import：触发全部 @broker.task 注册。

设计（manifest 驱动发现，取舍见 M1 拆解 §3.1 ②）：
- 单一真源 = 各插件 manifest.json 的 jobs[*].handler_ref（"module:callable"）。
- 扫描【所有已安装插件】（不止当前已启用），提取 module 段 import，
  确保任意插件的 @broker.task 都已注册——即便当前被禁用，未来启用后
  beat 投递 worker 也能执行（reconciler 只给已启用插件建调度行）。
- 不依赖文件名推断 task_name（由装饰器显式声明），也不裸扫 jobs/ 目录
  （避免误 import __init__.py / helper 模块）。
- 平台作业（base.common.jobs.platform）不在任何 manifest，单独显式 import。
- 单模块导入失败隔离：与现有 JobScheduler fail-open 语义一致。

前置：init_plugin_manager() 须先调用（worker 镜像复用 L2，由 jobs.py 的
WORKER_STARTUP 或 broker 加载期完成）；依赖 settings.base_path 已配置（同 app）。
"""
from __future__ import annotations

import importlib

from loguru import logger

from base.common.taskiq_app.broker import broker  # 确保 broker 先就绪
from base.common.plugin_manager import get_plugin_manager, init_plugin_manager


def _discover_job_modules() -> list[str]:
    """返回所有已安装插件声明的作业模块路径（去重、保序）。"""
    init_plugin_manager()  # 幂等：独立 worker 进程需先建插件管理器
    mgr = get_plugin_manager()
    seen: dict[str, None] = {}
    for name in mgr.discover_plugins():
        manifest = mgr.get_manifest(name) or {}
        for job in (manifest.get("jobs") or []):
            ref = job.get("handler_ref")
            if not isinstance(ref, str) or ":" not in ref:
                logger.warning(
                    f"[tasks_registry] 插件 {name} 作业 {job.get('name')} 的 "
                    f"handler_ref 非法（应为 module:callable）: {ref!r}，已跳过"
                )
                continue
            seen.setdefault(ref.split(":", 1)[0], None)
    return list(seen)


def _import_one(module_path: str) -> None:
    try:
        importlib.import_module(module_path)
    except Exception as e:  # 单模块失败隔离
        logger.error(
            f"[tasks_registry] 作业模块 {module_path} 导入失败（已隔离，"
            f"对应任务不会被 worker 注册）: {e}"
        )


def import_all_job_tasks() -> None:
    """导入全部作业模块触发 @broker.task 注册；在 WORKER_STARTUP 调用一次。"""
    _import_one("base.common.jobs.platform")     # 平台作业：随 worker 永驻
    modules = _discover_job_modules()            # 插件作业：manifest 驱动
    if not modules:
        logger.warning(
            "[tasks_registry] 未发现任何插件作业模块——请确认 settings.base_path "
            "已配置且插件 manifest.jobs 已声明（否则 worker 将无任务可消费）"
        )
    for module_path in modules:
        _import_one(module_path)
    count = len(broker.get_all_tasks()) if hasattr(broker, "get_all_tasks") else "?"
    logger.info(f"[tasks_registry] 作业模块导入完成，broker 已注册 {count} 个任务")


# 模块被 import 即触发注册（worker 命令 import base.common.taskiq_app.jobs ->
# jobs 内 import tasks_registry -> 此处执行）
import_all_job_tasks()

__all__ = ["broker", "import_all_job_tasks"]
```

> **为什么用「manifest 驱动聚合 import」而不是「app 插件钩子里 `broker.register_task`」**：插件的 enable/disable 钩子跑在 **app 进程**，taskiq worker 是**独立进程**，app 侧注册不会反映到 worker 的 broker 注册表，需额外 IPC/事件机制，故不采用。manifest 驱动让 worker 自包含、跨进程最干净（与 D3「合并单 worker」一致：worker 镜像复用 L2，仅 `command` 不同）。
>
> **与 reconciler 的真源一致性**：reconciler(beat 侧 §3.1 ③) 同样遍历 `manifest.jobs[].handler_ref`，二者从同一份声明抽取 module/函数，避免「注册了但没调度」或「调度了但没注册」的错位；新增作业只改 manifest，两处自动同步。
>
> **发现范围 = 所有已安装插件（含未启用）**：worker 进程启动期把全部已安装插件的作业模块都 import 注册，beat 侧 reconciler 只对已启用插件建调度行。这样插件运行期被启用后 beat 投递时，worker 早已持有对应 `@broker.task`，无需重启 worker。代价：运行时**新装**插件需重启 worker 才能被注册（M1 接受，与现有架构一致）。

**③ `ManifestReconciler` 改写：一行 `scheduler_job` = 一个真实 task**

```python
# reconcile.py（主方案 §3.4 落地）
async def upsert_schedules(session):
    targets = []  # list of (job_id, task_obj, interval, owner, requires)
    # (a) 插件作业：扫已启用插件的 manifest.jobs
    for owner, manifest in get_enabled_plugins_from_manifests():
        for job in manifest.get("jobs") or []:
            job_id = f"{owner}:{job['name']}"
            # requires_plugins AND 门控（见 ⑤），缺失则跳过本轮
            if not _deps_active(job.get("requires_plugins") or []):
                continue
            mod, fn = job["handler_ref"].split(":")   # module:callable
            task_obj = getattr(import_module(mod), fn)  # 已注册的 TaskiqTask
            targets.append((job_id, task_obj, int(job["interval_seconds"]), owner, None))
    # (b) 平台作业：从 tasks_registry 直接取，随 worker 永驻（requires=None）
    for job_id in ("platform:quota_reconcile", "platform:quota_hold_cleanup"):
        targets.append((job_id, getattr(base.common.jobs.platform, job_id.split(':')[1]), 60, "platform", None))
    # diff + upsert（复用 taskiq-beat SchedulerApp.create_scheduler）
    existing = {row.job_id for row in session.query(SchedulerJob).all()}
    for job_id, task_obj, interval, owner, _ in targets:
        scheduler_app.create_scheduler(
            job_id=job_id, task=task_obj,
            trigger=IntervalTrigger(seconds=interval),
        ).upsert(session)
    # 清理已不存在/已禁用：pause + delete 行（beat 不再投递）
    for stale in existing - {t[0] for t in targets}:
        scheduler_app.delete_scheduler(stale, session)
```

> `task=<真实 task 对象>`：taskiq-beat `create_scheduler` 要求 `task` 为已注册的 `TaskiqTask` 对象（即 `jobs.cleanup.run` 经 `@broker.task` 装饰后的产物），不是字符串引用——这正是 ② 静态 import 的目的。

**④ `interval_ref` 每轮热重载 → 迁到 reconciler（beat 无原生支持；`harness:gateway_reconcile` 特例）**

- 现状 `JobScheduler._run_loop` 每轮（含首轮）重读 `interval_ref`、`_resolve_interval` 调 `resolve_interval()` 重算间隔；且 handler 返回 int 可覆盖下一间隔——taskiq-beat 用固定 `IntervalTrigger`，**均非原生能力**。
- **改造**：`harness:gateway_reconcile` 的 `interval_ref` 解析移到 reconciler 周期扫描（reconcile 自带 `interval` 字段，默认 600s）：
  ```python
  # reconcile 扫描时，对带 interval_ref 的 job 重算间隔
  if job.get("interval_ref"):
      ref_fn = resolve_callable(job["interval_ref"])   # -> harness.jobs.reconcile:resolve_interval
      effective = max(int(ref_fn()), MIN_JOB_INTERVAL)  # 复用现有 resolve_interval()，下限 30s
      # 写回 scheduler_job：更新 trigger interval + 重算 next_run_at
      scheduler_app.create_scheduler(job_id, task=task_obj,
          trigger=IntervalTrigger(seconds=effective)).upsert(session)
  ```
- **行为变更（记为回归差异）**：「handler 返回 int 覆盖下一间隔」在 beat 下**取消**（M1 回归 B 组移除该断言）；「每轮重读」改为「reconciler 周期扫描重读」（默认 reconcile_interval=5s 级，足够热生效）。`harness.jobs.reconcile:resolve_interval` 函数体保留复用，仅调用方从调度器循环变为 reconciler。

**⑤ `requires_plugins` AND 门控（仅 `customer:update_membership_data` → 依赖 `llm`）**

- 现状 `_start_owner` 在装载前检查 `requires_plugins` 全 active（缺失则跳过该 job）；改造后在 reconciler 的 (a) 分支 `if not _deps_active(...)` 等价实现（复用 `is_plugin_active`）。
- 语义不变：llm 未启用时 `customer:update_membership_data` 这一行不 upsert / 被 pause，beat 不投递；llm 启用后下一轮 reconcile 自动补建。

**⑥ 启用/禁用单一真源 & 验收**

- **单一真源 = `scheduler_job` 行**（reconciler 在 app 进程写 PG，跨进程同步）：插件 enable → 该行 `upsert(enabled=True)`；disable → `pause`/`delete` → beat 不再投递。
- `is_plugin_active(owner)` 保留为 worker 侧**兜底门控**：即使行未清，幽灵作业也立即 return（防 beat 遗漏时的双执行，呼应 R1 双通道关闭后的幂等约束）。
- **M1 验收（R2/R16/R17 之外，本方案专项）**：
  - 6 个 `@broker.task` 在 worker 启动时全部注册（断言 `broker.get_all_tasks()` 含 6 个 `owner:name`）；
  - reconciler 对 6 个 job 各生成 1 行 `scheduler_job`，`task_name` 与装饰器 `task_name` 一致；
  - 禁用 `customer` 插件 → `update_membership_data` 行 `is_enabled=False`，但 `llm` 仍启 → 不误删（仅依赖门控）；禁用 `llm` → 该行被 pause；
  - `harness:gateway_reconcile` 改 `reconciliation.interval_seconds` → reconciler 周期扫描后 `scheduler_job` interval 更新、`next_run_at` 重算（验证 ④）；
  - 回归 B 组移除「handler 返回 int 覆盖下一间隔」断言（行为变更 ④）。

---

## 4. 调度表 DDL（基于 taskiq-beat 1.4.0 真实模型解包核对）

> 字段/索引/类型逐字段对照 `taskiq_beat/models.py`（`SchedulerJob` / `SchedulerRun` / `SchedulerBase`），wheel 解包实测（2026-11-14）。表名即 `scheduler_job` / `scheduler_run`。
>
> **JSON vs JSONB 决策**：SQLAlchemy `JSON` 类型在 PG 渲染为 `JSON`；为与项目 `event_subscriptions` 迁移一致改用 `JSONB`。SQLAlchemy `JSON` 类型对 `JSONB` 列读写兼容（dict/list 载荷），**R16 须显式验证 dev `create_all` 与 prod 迁移两端行为一致**（见 §7 必验项）。
>
> **类型说明**：`created_at`/`updated_at`/`next_run_at` 等模型为 `DateTime(timezone=True), nullable=False` 但**无 server_default**——值由 taskiq-beat 在 Python 侧写入（`build_new_job` 设 `created_at=updated_at=datetime.now(UTC)`），故 SQL 仅 `NOT NULL`、不加 `DEFAULT`。
> `id`、各 JSON 列、`dispatch_count`、`is_enabled`、`kind`、`strategy` 均有 Python 侧 default，SQL 不设 server default。

**新增单文件迁移**（两表同文件保证 `scheduler_run` 外键晚于 `scheduler_job` 创建；`core_` 前缀 → `MigrationMeta.plugin_name=None` → 恒执行；`RUN_DB_MIGRATIONS=false` 时由部署流程单独执行）：

`migrations/core_create_table_scheduler_<ts>.sql`：

```sql
-- taskiq-beat 调度表（幂等建表，core_ 前缀 => 恒执行，不依赖插件启用态）
-- 字段/索引/类型逐字段对照 taskiq-beat 1.4.0 的 taskiq_beat/models.py（2026-11-14 解包核对）。
-- 注意：SQL 迁移在 generate_schemas 之前执行；CREATE TABLE IF NOT EXISTS 保证不冲突。
-- JSON 列用 JSONB 以与项目 event_subscriptions 约定一致（R16 需验证 SQLAlchemy JSON 类型对 JSONB 列读写兼容）。

CREATE TABLE IF NOT EXISTS scheduler_job (
    id                   VARCHAR(36)  PRIMARY KEY,
    name                 VARCHAR(255),
    description          TEXT,
    task_name            VARCHAR(255) NOT NULL,
    kind                 VARCHAR(16)  NOT NULL,
    strategy             VARCHAR(16)  NOT NULL,
    trigger_payload      JSONB        NOT NULL,
    task_args            JSONB        NOT NULL,
    task_kwargs          JSONB        NOT NULL,
    metadata_payload     JSONB        NOT NULL,
    is_enabled           BOOLEAN      NOT NULL,
    next_run_at          TIMESTAMPTZ,
    claimed_by           VARCHAR(128),
    claimed_at           TIMESTAMPTZ,
    claim_expires_at     TIMESTAMPTZ,
    last_run_at          TIMESTAMPTZ,
    last_error           TEXT,
    last_dispatched_task_id VARCHAR(255),
    dispatch_count       INTEGER      NOT NULL,
    created_at           TIMESTAMPTZ  NOT NULL,
    updated_at           TIMESTAMPTZ  NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduler_run (
    id                VARCHAR(36)  PRIMARY KEY,
    job_id            VARCHAR(36)  NOT NULL REFERENCES scheduler_job(id) ON DELETE CASCADE,
    status            VARCHAR(16)  NOT NULL,
    scheduled_for     TIMESTAMPTZ  NOT NULL,
    dispatched_at     TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    broker_task_id    VARCHAR(255),
    error             TEXT,
    created_at        TIMESTAMPTZ  NOT NULL,
    updated_at        TIMESTAMPTZ  NOT NULL
);

-- 复合索引（taskiq-beat 查询依赖，名称须与 SchedulerBase.__table_args__ 完全一致）
CREATE INDEX IF NOT EXISTS ix_scheduler_job_ready_lookup   ON scheduler_job (is_enabled, next_run_at, claim_expires_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_claim_owner    ON scheduler_job (claimed_by, claim_expires_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_job_finished    ON scheduler_run (job_id, finished_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_status_finished ON scheduler_run (status, finished_at);

-- 单列索引（对应模型 index=True；命名与 create_all 自动生成一致，避免 dev/prod 漂移）
CREATE INDEX IF NOT EXISTS ix_scheduler_job_task_name        ON scheduler_job (task_name);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_is_enabled       ON scheduler_job (is_enabled);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_next_run_at      ON scheduler_job (next_run_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_claimed_by       ON scheduler_job (claimed_by);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_claim_expires_at ON scheduler_job (claim_expires_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_job_updated_at      ON scheduler_job (updated_at);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_job_id           ON scheduler_run (job_id);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_status           ON scheduler_run (status);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_scheduled_for    ON scheduler_run (scheduled_for);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_broker_task_id  ON scheduler_run (broker_task_id);
CREATE INDEX IF NOT EXISTS ix_scheduler_run_finished_at      ON scheduler_run (finished_at);
```

`kind` ∈ {`periodic`, `one_off`}，`strategy` ∈ {`immediate`, `one_off`, `<trigger.strategy>`}——由 `scheduler_app.create_scheduler(...).upsert(...)` 在库内赋值，SQL 只需 `VARCHAR(16) NOT NULL`，reconciler 不需硬编码枚举。

---

## 5. compose 两服务（复用 L2 镜像，仅 `command` / `environment` / `healthcheck` 不同）

沿用 `deploy/gateway/docker-compose.yml` 的 `app` 服务形态（`agentpanel-net` + `app_default` 网络、`host.docker.internal` extra_hosts、`db_password` / `redis_password` secrets、`RUN_DB_MIGRATIONS: "false"`、json-file 日志、`no-new-privileges`）。

> **前置（D6，已落地见 §9.4）**：RabbitMQ 专用 vhost `agentpanel` + 账号 `agent_user` 由 `deploy/rabbitmq/definitions.json` 声明、`rabbitmq.conf` 显式 `load_definitions` 导入（镜像不会自动加载 definitions.json，且配置 load_definitions 后 `RABBITMQ_DEFAULT_*` 环境变量被入口忽略）；`TASKIQ_BROKER_URL_FILE` 指向该 vhost 的 URL。旧消费者已删除，vhost 隔离主要防旧 `#` 通配消费者误拉（主方案 R4）。

```yaml
  taskiq-beat:
    image: agentpanel-app:${TAG:-local}
    container_name: agentpanel-taskiq-beat
    restart: unless-stopped
    command:
      - taskiq-beat-scheduler
      - base.common.taskiq_app.scheduler:scheduler_app
      - --startup
      - base.common.taskiq_app.reconcile:upsert_schedules
    environment:
      DEPLOY_ENV: docker
      RUN_DB_MIGRATIONS: "false"
      DB_HOST: host.docker.internal
      DB_PORT: "15432"
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD_FILE: /run/secrets/db_password
      REDIS_ENABLED: "true"
      REDIS_HOST: agentredis
      REDIS_PORT: "6379"
      REDIS_PASSWORD_FILE: /run/secrets/redis_password
      TASKIQ_MODE: "off"
      TASKIQ_BROKER_URL_FILE: /run/secrets/taskiq_broker_url
      TASKIQ_DB_URL_FILE: /run/secrets/taskiq_db_url
      TASKIQ_VHOST: agentpanel-taskiq
    secrets: [db_password, redis_password, taskiq_broker_url, taskiq_db_url]
    networks: [agentpanel-net, app_default]
    extra_hosts: ["host.docker.internal:host-gateway"]
    healthcheck:
      test: ["CMD", "python", "base/common/taskiq_app/health.py", "beat"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }
    security_opt: [no-new-privileges:true]

  taskiq-worker:
    image: agentpanel-app:${TAG:-local}
    container_name: agentpanel-taskiq-worker
    restart: unless-stopped
    # 单 worker 消费 ap.jobs + ap.events 两队列（单 broker，task_queues 在 broker.py 声明）
    # 横向扩缩容：docker compose up --scale taskiq-worker=N 或 k8s replicas（见 §5.2）
    command:
      - taskiq
      - worker
      - base.common.taskiq_app.broker:broker
      - base.common.taskiq_app.jobs
      - base.common.taskiq_app.events
      - --workers
      - "2"
      - --ack-type
      - when_executed
      - --max-prefetch
      - "0"
    environment:
      DEPLOY_ENV: docker
      RUN_DB_MIGRATIONS: "false"
      DB_HOST: host.docker.internal
      DB_PORT: "15432"
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD_FILE: /run/secrets/db_password
      REDIS_ENABLED: "true"
      REDIS_HOST: agentredis
      REDIS_PORT: "6379"
      REDIS_PASSWORD_FILE: /run/secrets/redis_password
      TASKIQ_MODE: "off"
      TASKIQ_BROKER_URL_FILE: /run/secrets/taskiq_broker_url
      TASKIQ_VHOST: agentpanel-taskiq
    secrets: [db_password, redis_password, taskiq_broker_url]
    networks: [agentpanel-net, app_default]
    extra_hosts: ["host.docker.internal:host-gateway"]
    healthcheck:
      test: ["CMD", "python", "base/common/taskiq_app/health.py", "worker"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }
    security_opt: [no-new-privileges:true]
```

并在 compose `secrets:` 块追加（文件由 `deploy/gateway/scripts/prepare-secrets.ps1` 生成，同 `db_password` / `redis_password`）：

```yaml
  taskiq_broker_url:
    file: ./secrets/taskiq_broker_url
  taskiq_db_url:
    file: ./secrets/taskiq_db_url
```

> **beat 严格单实例**（无 `replicas` / `scale`），**worker 可多副本**（见 §5.2）。worker 与 beat 解耦，M1 不互相 `depends_on`（beat 写表、worker 消费 broker，无强序依赖；若需，beat `depends_on` 指向 PG/Redis/RabbitMQ 就绪而非 worker）。
> **scheduler_id 禁止钉固定值**：beat 的 `SchedulerConfig.scheduler_id` 默认 `uuid4().hex`（每次启动随机）。崩溃窗口内孤儿 job 靠租约（`claim_ttl_seconds` 默认 60s）保护；若把 `scheduler_id` 设成固定值（如 pod 名），重启的 beat 会立即重新认领自身孤儿 job → **可能重复投递一次**。故部署约束：不设置 `TASKIQ_BEAT_SCHEDULER_ID`（用默认随机），详见 §5.1。

### 5.1 调度投递语义：at-least-once 边界（含 scheduler_id 约束）

经 taskiq-beat 1.4.0 源码（`engine.py` / `repositories.py`）核实：

- **正常运行（beat 存活）：每个周期只投递一次。** 到期 job 先经 DB 级原子 claim 锁认领（`UPDATE scheduler_job ... WHERE ... AND (claim_expires_at IS NULL OR claim_expires_at<=now OR claimed_by=owner)`，`rowcount==1` 才算认领成功），投递成功后释放 claim 并把 `next_run_at` 从**实际投递时间**推进到下一周期，避免补投式重复。
- **崩溃窗口 = at-least-once，非严格 exactly-once**：在「claim 提交成功 ↔ broker 真正 enqueue（`kiq`）」之间若 beat 崩溃，job 留下 `claimed_by` + 未过期 `claim_expires_at`，但 broker 无消息。恢复时：
  - **默认 scheduler_id 随机**（`uuid4().hex`）：新 beat 见 `claimed_by != 自己` 且租约未过期 → 等 `claim_ttl_seconds`（默认 60s）过期后才补投一次。**表现：延迟最多 60s，不重复、不丢失。**
  - **若 scheduler_id 钉成固定值**：重启 beat 的 `claimed_by == 自己` 成立 → 立即重新认领孤儿 job 并再投一次 → **该周期可能重复投递一次。**
- **跨进程**：claim 锁是 DB 级 CAS，多 beat 并存时也只有一个能认领；另一实例等租约。故「beat 单实例」是纪律约束，非技术必需。
- **端到端 exactly-once 由消费端兜底**：broker 投递到 worker 后是否只执行一次取决于 worker ack + 消费端幂等。**本方案的 W3-1 / R3（Redis SETNX 幂等）必须保留**，不能因 beat 的锁而省略。

> **部署约束**：不在 `[taskiq]` 配置里设置 `beat_scheduler_id`（见 §2 `TASKIQ_BEAT_SCHEDULER_ID` 留空用默认随机）。禁止为 beat 钉固定 `scheduler_id`。
> 新增风险登记 **R19（M1）**：beat 投递为 at-least-once 边界（崩溃窗口 ≤ `claim_ttl_seconds` 默认 60s），端到端 exactly-once 由消费端幂等（W3-1）兜底；若误设固定 scheduler_id 则退化为「可能重复一次」。

### 5.2 横向扩缩容（副本模型）

- **beat 不可扩**：`taskiq-beat` 必须单实例（两个 beat 会各自认领 → 虽 claim 锁阻止同时投递，但无收益且增加租约压力），compose 不设 `replicas` / `scale`。
- **worker 可自由扩副本**：`taskiq-worker` 是无状态消费进程，只从 `ap.jobs` / `ap.events` 抢消息执行，无跨进程共享状态（`WORKER_STARTUP` 的 Tortoise/Redis 连接池各进程自建）。
- **扩容方式**：
  - docker-compose：`docker compose up -d --scale taskiq-worker=N`；
  - k8s：给 `taskiq-worker` Deployment 设 `replicas: N` 或用 HPA（按 CPU/内存，或自建控制器监听 RabbitMQ 队列深度 → 调 replicas）。
- **队列数 ≠ 扩缩容瓶颈**：队列（`ap.jobs` / `ap.events` / 未来按类型拆分）只是绑定，RabbitMQ 多队列无压力；单进程绑定队列过多时协程/连接开销上涨，用「多副本」摊掉。
- **合并单 worker 的取舍（相对拆 jobs/events 两 worker）**：
  - 失去「按类型分别封顶」能力——jobs 与 events 共享 `--workers` 并发池，事件暴涨可能挤占作业执行；要各自保容量需拆回两 worker。
  - 管理后台量级下，单 worker + 副本通常足够；本方案按此简化实施。
- taskiq **自身不带自动伸缩器**，动态伸缩靠编排层（HPA / 自定义队列深度控制器）。

---

## 6. healthcheck 脚本（`base/common/taskiq_app/health.py`）

taskiq worker/beat **不提供 HTTP 端口、无 `inspect ping` 等价物**（主方案 R15），不能用 app 的 `/health/health` 探活。用轻量脚本：

- `beat` 模式：读 Redis 心跳键 `ap:taskiq:beat:heartbeat`（由 reconciler/startup 周期写入，带 TTL），校验 `age < 阈值`（如 30s）；并校验 PG 可达（`asyncpg` connect 试连）。
- `worker` 模式：`aio_pika` connect 探活 broker；读 Redis 心跳键 `ap:taskiq:worker:heartbeat`（单 worker 在 `WORKER_STARTUP` 写入，覆盖 jobs+events 两队列）。
- 退出码 0/1 即 compose `test` 结果。

> heartbeat 键的写入在 M1 骨架里加（startup 事件里 `redis.set(key, now, ex=30)`）；beat 端在 `upsert_schedules` 或独立周期任务里写。这是 M1 明确要补的最小可观测性。

---

## 7. 三项必验（M1 出口门槛，未通过不进 M2）

### R2 · `--workers 2` 连接池隔离
- 构造最小 async 任务 `smoke_db`：在 `WORKER_STARTUP` 内 `await Tortoise.init(...)`（与现有 `base/common/jobs/scheduler.py` 同配置），任务内做一次 `await SomeModel.first()` 或 `await connection.execute_query("select 1")`。
- 以 `--workers 2` 启动 `taskiq-worker`，连续 `kiq` N 次，断言全部执行成功、无 `Event loop is closed` / `connection is closed` / 跨 loop 报错。
- 再验证 `--workers 1`（Windows/兜底路径）同样可跑。
- **验收**：两个子进程各自独立连接池、不在同一 loop 串扰；记录结论到本拆解 §9。

### R16 · 调度表 DDL 与 `SchedulerBase.metadata` 对齐
- 在测试 PG 执行 §4 SQL；随后以 `SchedulerBase.metadata.create_all(engine)` 跑一次，断言**不报任何变更 / 不尝试 ALTER**（或对比 `inspect` 出的列与模型逐字段一致：名/类型/NOT NULL/索引名）。
- 专门验证 **JSON vs JSONB**：用 `SchedulerBase.metadata.create_all` 在另一库建表（得 `JSON` 列），与 §4 `JSONB` 列对比读写 round-trip（写入 `trigger_payload={"interval": {...}}`、读出一致）。确认 SQLAlchemy `JSON` 类型对 `JSONB` 列无异常。
- **验收**：两端 DDL 语义一致、索引名匹配、JSONB 读写正常；否则把 §4 改为 `JSON` 以严格对齐 `create_all`。

### R17 · `AckableMessage` 与 ACK/DLQ 语义
- 在 `dispatch` 任务内探测：`from taskiq import Context`；检查 taskiq-aio-pika 是否 yield `AckableMessage`（消息对象带 `.ack()` / `.nack()`）。写两个探针任务：一个成功、一个抛异常。
- 确认 `--ack-type when_executed` 在 `DummyResultBackend` 下的行为：任务执行完才 ack、崩溃/超时不丢消息。
- 确定 DLQ 实现路径：若支持 manual ack → `Context.ack()` 成功 / `nack(requeue=False)` 进 `ap.dlq`；否则依赖 broker 原生 reject。
- **验收**：明确 manual vs automatic ack 选择并留档；**在 R17 验证前，文档与主方案不宣称 DLQ 已闭环**。

---

## 8. 回归脚本（M1 部分）

新增 `tests/regression_taskiq_split.py`（主方案 §4.3），M1 阶段先落地以下用例（不依赖 app 改造、`mode=off`）：

1. **最小 async 同 loop**：R2 的 `smoke_db` 任务在 `--workers 2` 下全绿。
2. **连接池隔离**：断言两子进程连接池不共享（可通过连接标识/日志区分）。
3. **`DummyResultBackend` + `when_executed` 不丢消息**：发任务 → worker 崩溃模拟 → 重启后消息仍被消费。
4. **reconciler diff 幂等**：重复 `upsert_schedules` 不新增 `scheduler_job` 行；`interval_ref` 变更后 `next_run_at` 重算且行数不变。
5. **pydantic 消息往返**：`JobMessage.model_dump(mode="json")` → `model_validate` 还原一致；`BaseModel` 实例直接 `kiq` 报错（验证 D7 约束）。
6. **调度表存在性**：migrate 后 `scheduler_job` / `scheduler_run` 两表 + 全部索引存在。

> M1 不触碰 `regression_pending.py` / `regression_plugin_assembly.py` 的现有断言（那些按 `mode` 分支改造留到 M2/M4）。

---

## 9. 验收清单（M1 Done 判据）

> 实施进度记录见末尾「§9.1 实施进度（2026-11-14）」。✅=已落地/已验证；🟡=已落地但需目标环境（RabbitMQ/PG）补集成验证；⬜=未做。

- [✅] `requirements.txt` 新增 4 行，隔离 venv 导入全通过，`redis`/`aio-pika` 版本未升（沿用既有，不引 taskiq-redis）。
- [✅] `base/common/taskiq_app/` 九文件就位（§3 布局表 9 项 + `__init__.py`），`taskiq-beat-scheduler` 与 `taskiq worker` 能加载模块（不报 import/loop 错）；本机实测 broker/config/schema/scheduler 冒烟通过、无弃用告警。
- [🟡] §4 SQL 在测试 PG 执行成功，`SchedulerBase.metadata.create_all` 为 no-op——**静态对齐已验证**：metadata 的 21+10 列名/NOT NULL/8+5 索引名与迁移 SQL 逐字段一致；真实 PG 跑迁移 + create_all no-op 比对留目标环境。
- [🟡] compose 两服务 `config --quiet` 通过（含新增 secrets）——本机 YAML 校验通过（5 服务 + 2 secret）；专用 vhost `agentpanel-taskiq` 须先在 RabbitMQ 建并授权（D6）。
- [🟡] 两进程独立启动，healthcheck 探活 200/0；beat/worker 心跳键周期刷新（修复一次性写入过期误判）——留目标环境端到端验收。
- [🟡] R2 / R16 / R17 三项验证：R16 静态部分 ✅（列/索引对齐）；R2（--workers 2 连接池隔离）、R17（ACK/DLQ 语义）待含 RabbitMQ 集成环境验证。
- [🟡] `tests/regression_taskiq_split.py` 上述 6 类用例：schema 往返 / 元数据对齐 / broker 拓扑 7 项本机通过；reconciler 幂等 / 调度表存在性 / 6 任务注册 / R2 共 5 项需 DB 或 broker，已用 skip 门控。
- [✅] 主方案 `regression_plugin_assembly` 24/24、`regression_pending` 42/42 在 `mode=off` 下零回归（app 未改，无反向导入）。
- [✅] 文档状态：`mode=off` 骨架已验证，M2（调度独立）可启动；本拆解 §0 范围未被突破（全部为新增，旧 JobScheduler/ConsumerWorker 原样保留）。

### 9.1 实施进度（2026-11-14）

**已落地（新增，全 additive，不改 `run.py`/`base/start.py`）：**
1. `requirements.txt` 追加 `taskiq==0.13.0` / `taskiq-aio-pika==0.6.1` / `taskiq-beat==1.4.0` / `sqlalchemy>=2.0,<3`。
2. `base/common/taskiq_app/` 九文件：`config.py`(TaskiqSettings)、`broker.py`(单 AioPikaBroker + TOPIC exchange + ap.jobs/ap.events/ap.dlq + SmartRetryMiddleware)、`schema.py`、`events.py`(dispatch M1 骨架)、`jobs.py`(WORKER_STARTUP 建池+注册+周期心跳)、`tasks_registry.py`(manifest 驱动发现+注册)、`scheduler.py`(SchedulerApp+引擎+metadata)、`reconcile.py`(ManifestReconciler，`upsert_schedules` 无参 beat `--startup` 钩子)、`health.py`(beat|worker 探活)。
3. 6 个作业加 `@broker.task`（仅装饰器，不动函数体，旧 JobScheduler 仍可本地执行）。
4. `migrations/core_create_table_scheduler_1794580000.sql`（两表 + 4 复合 + 11 单列索引）。
5. `deploy/gateway/docker-compose.yml` 追加 `taskiq-beat`/`taskiq-worker` 两服务 + `taskiq_broker_url`/`taskiq_db_url` secrets；`prepare-secrets.ps1` 生成两 secret（密码 URI 编码）。
6. `tests/regression_taskiq_split.py`（12 用例）。

**实施期修正（真实缺陷）：**
- beat/worker 心跳只启动期写一次 → 30s 过期后 healthcheck 误判健康长驻进程不健康；改为周期刷新（worker 后台 task 每 10s、beat reconcile 周期循环每轮）。
- `broker.py` 显式传 `result_backend=DummyResultBackend()` 触发 taskiq 0.13 弃用告警；改为不传（构造默认即 DummyResultBackend），消除告警。

**本机验证（Python 3.13 装齐 M1 依赖）：**
- `config`/`broker`(无告警)/`schema`(pydantic 往返)/`scheduler`(metadata 暴露两表) 冒烟通过。
- R16 静态对齐：metadata 列名/NOT NULL/索引名与迁移 SQL 逐字段一致（仅 JSON vs JSONB 渲染差异，运行时兼容）。
- `regression_taskiq_split.py` 7 passed / 3 skipped / 2 placeholder skipped；全部 `taskiq_app/*.py` 与 touched 模块 `py_compile` 通过。
- 无反向导入：`taskiq_app` 未被 `run.py`/`base/start.py` 引用 → 既有 pending/plugin_assembly 回归不受影响。

**遗留（目标环境补验）：** beat/worker 真实端到端（需先建专用 vhost D6）、R2 跨进程连接池隔离、R17 ACK/DLQ 语义、真实 PG 跑迁移 + create_all no-op。

> **Celery 路径已清理（2026-11-14）：** 经核查，Celery 拆分方案仅停留在规划/文档阶段，从未落代码——`base/` 下无 `celery_*.py`、`start.py`/`run.py` 无 Celery 改动、`requirements.txt` 无 celery 依赖、`docker-compose.yml`/`prepare-secrets.ps1` 无 Celery 服务或 secret、`config.conf` 无 `[celery]` 段。遗留的两处痕迹（空目录 `deploy/celery/` 与一份 Celery 替换方案 PRD）均已删除。当前调度/消费独立化只有 taskiq 一条路径。

### 9.2 M2 调度切换开关落地（2026-11-14 晚，TASKIQ_MODE 单一真相源）

> **⚠️ 已被 §9.3 取代**：用户随后指令「开始 M2、M3，不要保留旧的调度和消费」，本节的
> TASKIQ_MODE 开关与「off 保留本地 JobScheduler」语义已随旧代码删除一并移除，仅留档。

针对「旧 `JobScheduler` 与新 beat 双跑」缺口的收口实施（M2 切换点）：

**开关语义（`off` 默认 = 现状/回滚态；`on` = beat 接管）：**
1. `base/common/jobs/scheduler.py`：新增 `local_scheduler_enabled()`（读 `TASKIQ_MODE`，大小写不敏感）；`start_all()` 在 `on` 时直接返回 0 且**不置 `_ready`** —— 借助既有 `_ready` 守卫，`register_platform_job` / `start_plugin`（含 `plugin_manager._sync_plugin_jobs` 插件启停钩子）自动 no-op，**app 侧零本地作业装载**。
2. `base/start.py:122-129`：装配点按 `local_scheduler_enabled()` 分支；off 打印「定时任务装配完成（本地 JobScheduler）」，on 打印「定时任务跳过本地装配（TASKIQ_MODE=on，由独立 taskiq beat 接管）」。关闭顺序不变（on 模式下 `shutdown()` 是 no-op，安全）。
3. `base/common/taskiq_app/reconcile.py::upsert_schedules`：`on` 才执行基线 `_sync` + 周期重扫；`off` 时 beat 休眠不排程（不写任何 `scheduler_job` 行），但仍 spawn **心跳-only 循环**（`beat:heartbeat` 键持续刷新），保证休眠 beat 的 healthcheck 不误判 unhealthy。
4. compose：app / taskiq-beat / taskiq-worker 三服务的 `TASKIQ_MODE` 统一改为 `${TASKIQ_MODE:-off}`，由 `.env` 单点翻转；`prepare-secrets.ps1` 生成的 `.env` 增写 `TASKIQ_MODE=off` 行。

**M2 边界（有意为之）：** `on` 模式下 `ConsumerWorker`（事件消费）**保持运行**——事件消费外迁属 M3（`ap.events.dispatch` 未接业务前关掉会断事件流）。主方案 §「base/start.py 改造」行中「mode=on 跳过 ConsumerWorker.start()」延后到 M3 实施。

**回归用例（`regression_taskiq_split.py` 追加 5 个 M2 用例，本机 10 passed / 2 skipped）：**
- `test_m2_switch_default_keeps_local_scheduler`：默认/off/OFF 均启用本地调度（`regression_pending` B 组语义不变）。
- `test_m2_switch_on_disables_local_scheduler`：`on` 下 `start_all()==0`、`_ready=False`、`task_count()==0`、启停钩子 no-op。
- `test_m2_startpy_wires_switch`：源码锚定 `start.py` 必须按开关分支。
- `test_m2_beat_sleeps_when_mode_off` / `test_m2_beat_schedules_when_mode_on`：reconciler 门控两态（需完整项目依赖，裸环境 skip）。

### 9.3 M2+M3 终态：旧调度/消费全量删除（2026-11-14 晚，用户指令「不要保留旧的调度和消费」）

**删除（不留观察期，取代方案 B 文档的灰度开关 D8 与观察期策略）：**
- `base/common/jobs/` 整包（`JobScheduler` / `platform.py` 的 `install()`）；quota 两作业迁至 `taskiq_app/platform_jobs.py`（`@broker.task` 装饰与 task_name 不变）。
- `base/common/events/consumer_worker.py`、`connection_manager.py`；`event_bus.py` 的进程内 `EventBus`（内存总线）与 ImportError 降级单例。
- `plugin_manager._sync_plugin_jobs` 及全部调用点（启停对称改由 beat reconciler 周期重扫保证，≤ `reconcile_interval` 生效）。
- §9.2 的 `TASKIQ_MODE` 开关整体移除（`local_scheduler_enabled` / config `mode` 字段 / compose 与 .env 注入）；`reconcile.upsert_schedules` 无条件排程。
- `start.py`：`job_scheduler.start_all()/shutdown()`、`ConsumerWorker` 启停与排空块全部移除。

**M3 消费模型（对方案 B §4 的关键修正）：**
- **实施期发现**：manifest `events.subscribe[].handler_ref` 指向的是**注册函数**（如 `register_audit_subscriptions`，把真 handler 绑进总线），并非可直接执行的事件处理体——方案 B「worker 按 DB 行 `resolve_callable(handler_ref)` 直接执行」对本代码库不成立。改用**进程内注册表**消费：worker 启动期跑 `event_center.initialize()`（register_ref + bind_manual 填充 `EventBusAdapter._handler_registry`），`dispatch` 按 `get_handlers(event_name)` 执行；运行期插件启停由 worker 周期 `event_center.resync()`（新增，双向：停用→unregister_ref 摘除、启用→幂等补注册）收敛。
- **发布端**（`event_bus_adapter.py` 重写）：`publish = EventRecord.create(published) + dispatch.kiq`；**不再执行内存订阅**（双执行防护）、不再 aio_pika 直发、**fail-closed**（入队失败 `mark_disconnected` + 上抛，无静默丢路径）；连接管理 = `broker.ensure_started()/shutdown_client()`（客户端模式惰性建连，taskiq `kick` 无 startup 会抛 `NoStartupError`）。
- **消费端**（`taskiq_app/events.py::dispatch`）：`EventMessage{event_uuid,event_name,payload,published_at}` 契约；终态（consumed/dead_letter）幂等跳过（W3-1 闭环）；单 handler 30s 超时异常隔离；失败置 failed 并上抛 → **SmartRetryMiddleware 指数退避重投**（注意：`default_retry_label` 默认 False 不重试，broker 已显式置 True）；超 `RABBITMQ_MAX_RETRIES` 置 dead_letter（可经重放接口恢复）。
- **发布端幂等迁 Redis**（`EventCenter._idempotency_seen`，`ap:event:idempotency:*`，TTL 300s；Redis 不可用回退进程内 dict）。
- **重放**：`event_replay_service` 改为**同一 event_uuid 重新 `dispatch.kiq`**（旧实现经 `event_bus.publish` 会生成新 uuid、旧记录悬空）。
- **监控**：`event_monitor_service` 探针改 taskiq 客户端连接态 + worker/beat Redis 心跳键；队列深度移交 RabbitMQ 管理接口。
- **dev 兼容**：`broker._resolve_url()` 未配 `TASKIQ_BROKER_URL` 时回退 `config.conf [rabbitmq]` 构造 URL（旧链路同源凭据；旧消费者已删除故共用 vhost 无污染）；生产仍走 `TASKIQ_BROKER_URL_FILE` 专用 vhost（D6）。
- compose：`app` 服务补 `TASKIQ_BROKER_URL_FILE` secret + vhost env（app 进程发布需要 broker 连接）；`TASKIQ_MODE` 相关全部移除。

**回归（全部真实运行通过，dev venv 装齐 taskiq 依赖）：**
- `regression_taskiq_split.py` **13 passed / 5 skipped**（新增：dispatch 路由 label、终态幂等集、SmartRetry 开启校验、发布 fail-closed 静态锚定、adapter 注册表、EventCenter 幂等 Redis+回退）。
- `regression_pending.py` 重写 B/D 组后 **41/41**：B 组改验「装配移除 + 包删除 + plugin_manager 零钩子 + broker 注册 7 任务（作业6+dispatch）+ 发布单通道」；C2a/C9a 改验 broker 任务计数不变；D3/D4 改验 dispatch 幂等、关闭顺序（broker→DB）、worker resync。
- `regression_plugin_assembly.py` **24/24** 零回归。
- 真实 lifespan 端到端含 broker 客户端建连/关闭验证（dev 回退 URL 连通）。

**遗留（目标环境补验）：** beat/worker 容器真实端到端（需先跑 `migrations/core_create_table_scheduler_*.sql` 与专用 vhost 授权）、R2 跨进程连接池隔离、R17 ACK/DLQ 语义、`EventSubscription` 行 ↔ 进程内注册表完备性对账（方案 B M1 项）。
**运维提示：** 用户 RabbitMQ（definitions.json）现有 vhost `agentpanel` / `agent_user`——在 `config.conf [rabbitmq]` 增加 `taskiq_vhost` / `taskiq_username` / `taskiq_password` 三键后重跑 `prepare-secrets.ps1` 即可让部署侧连接串对齐（不配置则回退 `virtual_host` / `username` / `password`）。

### §9.4 部署侧 RabbitMQ 对齐（2026-11-14 晚，已完成）

**实施前核查发现（与预期不符的三个事实）：**
1. `agentpanel` vhost 与 `agent_user` 账号**实际并未在 RabbitMQ 落地**——`deploy/rabbitmq/docker-compose.yml` 虽挂载了 `definitions.json`，但官方镜像**不会自动加载** `/etc/rabbitmq/definitions.json`，必须经 `rabbitmq.conf` 的 `load_definitions` 显式导入。
2. 旧 compose 的 `RABBITMQ_NODE_NAME=rabbit@rabbitmq` **从未生效**（Docker 默认 hostname=容器 ID，每次重建 hostname 变 → mnesia 数据库换名成 `rabbit@<容器ID>` → 表现为"全新节点"，admin 与 `/` vhost 消失）。
3. 配置了 `load_definitions` 后，镜像入口**忽略 `RABBITMQ_DEFAULT_USER/PASS/VHOST`**（不自动创建 admin/`/`），旧账号只存在于旧节点的 mnesia 目录中。

**整改（全部落地并验证）：**
- `deploy/rabbitmq/rabbitmq.conf`（新增）：`load_definitions = /etc/rabbitmq/definitions.json`，compose 只读挂载。
- `deploy/rabbitmq/definitions.json` 补全为**单一事实源**：vhosts `/`+`agentpanel`，users `admin`(administrator)+`agent_user`(无管理标签)，permissions `admin@/` 全权 + `agent_user@agentpanel` 全权（旧项目/管理界面兼容）。
- compose：`hostname: rabbitmq` 固定节点名（跨重建 mnesia 稳定）；删除无效的 `RABBITMQ_NODE_NAME` 与被 load_definitions 忽略的 `RABBITMQ_DEFAULT_*`。
- 配置链三端一致（优先级链 `taskiq_*` → 共用键 → vhost 缺省 `agentpanel`）：`config.conf [rabbitmq]` 新增 `taskiq_vhost/taskiq_username/taskiq_password` 三键；`setting.py` 新增 `RABBITMQ_TASKIQ_VHOST/USERNAME/PASSWORD`；`taskiq_app/broker.py::_resolve_url` 回退链同步；`taskiq_app/config.py`、gateway compose、prepare-secrets.ps1 的默认 vhost 由 `agentpanel-taskiq` 改为 `agentpanel`。
- `prepare-secrets.ps1` 重跑：生成 `secrets/taskiq_broker_url`（amqp://…@host.docker.internal:5672/agentpanel）+ `taskiq_db_url`，`.env` 补 `TASKIQ_VHOST=agentpanel`。
- **验证**：`rabbitmqctl` 三查（vhost/user/permission）全对齐；dev venv aio_pika 实连 `agentpanel` vhost 鉴权通过；`ap.taskiq` exchange + `ap.jobs/ap.events/ap.dlq` 由 taskiq 声明（DLX 参数齐全：`x-dead-letter-routing-key=ap.dlq`）；`regression_taskiq_split` 13p/5s、`regression_pending` 41/41、`regression_plugin_assembly` 24/24。

**踩坑记录（重要）**：手工裸参数（无 `x-dead-letter-exchange`）预声明 `ap.jobs` 等 durable 队列，会让 taskiq 后续声明报 `PRECONDITION_FAILED - inequivalent arg 'x-dead-letter-exchange'` 并连带打挂插件菜单/权限同步。修复=删除三队列让 taskiq 按自身参数重建。**运维注意：不要用手工工具预创建 ap.* 队列**；连通性验证只建连接或 passive 声明即可。

**遗留**：F:/rabbitmq/data 下存有历史容器 ID 命名的两个孤儿 mnesia 目录（`rabbit@08ed86611432`、`rabbit@df5c14cc0252`，含旧 `/` vhost 的 event_bus 队列定义），确认无依赖后可清理；beat/worker 容器端到端仍待目标环境补验（先跑 `migrations/core_create_table_scheduler_*.sql`）。


---

## 10. 回滚

M2+M3 终态后**没有运行时回滚开关**（旧 JobScheduler / ConsumerWorker 已物理删除，用户指令「不要保留」）。回滚 = git revert 本轮提交（旧调度/消费代码在版本历史中），并停掉 `taskiq-beat` / `taskiq-worker` 两容器；`migrations/core_create_table_scheduler_*.sql` 建的两表对旧代码无影响可保留。事件链路在回滚后恢复「RabbitMQ 直发 + 内存双通道 + ConsumerWorker」旧行为（该旧代码含已知的双执行与幂等缺口，见方案 B §1）。
