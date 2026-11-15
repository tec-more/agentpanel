# AgentPanel 声明式任务与事件订阅机制规范（现行基线）

| 项 | 内容 |
|---|---|
| 文档编号 | AP-SPEC-DECL-1.0 |
| 版本 / 日期 | v1.3 / 2026-11-15（Outbox / Inbox 事务一致性修订 + 后台观测能力补齐 + trace 串联 / DB 状态机重试） |
| 状态 | **现行有效**（代码已落地，全套回归通过） |
| 适用层级 | 平台级装配契约，适用于全部插件 |
| 取代 | `manifest.json` 的 `jobs` 段与 `events` 段（2026-11-15 起废弃，残留即拒绝装配） |
| 上游需求 | `AgentPanel-平台级需求规格-v3.0-2026-11-12.md`（PLR-13 / PLR-14 / PLR-15） |
| 落地代码 | `base/common/taskiq_app/discovery.py`、`reconcile.py`、`tasks_registry.py`、`platform_jobs.py`、`outbox.py`、`events.py`、`base/common/events/event_bus_adapter.py`、`base/common/events/payload_contract.py`、`base/common/events/models/*`、`base/core/events/registry.py`、`base/core/events/service.py`、`base/core/events/api/v1/event_center.py` |
| 安全约定 | 只列配置键名与代码路径，不记录 `config.conf` / `.env` / secrets 的任何取值 |

---

## 0. 修订记录 · v1.1 Transactional Outbox / Inbox（2026-11-15）

> **本节改变发布语义。凡本文 §5 及全部历史文档中「发布即 `dispatch.kiq` / fail-closed」
> 的描述与本节冲突，一律以本节为准。**

- **技术前提（不可含糊）**：RabbitMQ 不支持 XA，无法参与 PostgreSQL 事务；publisher
  confirm 也不能进 DB 事务。「事务一致性」只能落在 DB 侧：业务写库 + 消息记录**同一事务**；
  DB→MQ 用 Outbox（不丢、可能重复），MQ→DB 用 Inbox + 状态机（不重复执行）。端到端是
  **最终一致 / 等效 exactly-once**，不是强一致、不是零重复投递。
- **发布**：`EventBusAdapter.publish()` 只写 `EventRecord(status=pending)`；
  `async with in_transaction()` 复用调用方 `@atomic()` 连接（asyncpg 下即 savepoint），
  现有 20+ 业务调用点零改动即获得原子性。发布端不再连 broker、不再 fail-closed 上抛。
  幂等改由 `idempotency_key` 的 DB 唯一约束判定（冲突在 savepoint 内回滚，不污染外层事务）。
- **投递（唯一通道）**：`platform:outbox_relay`（`platform_jobs.py`，`ap_schedule=1`）。
  `locked_until` 租约 + CAS 抢占防多副本重复；先 `dispatch.kiq`、后 CAS 置 `published`，
  崩溃窗口由消费端幂等兜底；失败保持 `pending` 并累加 `dispatch_attempts`，MQ 恢复自动补投。
  `platform:stale_consuming_reap`（30s）把超时 `consuming` 回收为 `pending`。
- **消费**：`taskiq:dispatch` 两段事务 —— ① CAS 推进 `consuming` + 写 `event_inbox`
  processing 凭据（已 `done` 的 handler 跳过）→ 事务外执行 handler → ② 写回 Inbox 结果并
  CAS 置 `consumed` / `failed` / `dead_letter`。**（失败上抛一条已被 §0.2 推翻，
  现行语义为不上抛、由 relay 退避补投）**。**CAS 允许集刻意不含 `consuming`**，
  否则并发重复投递会双执行。
- **重放**：`service.replay` 与 `event_replay_service.replay_event` 统一把同一 `event_uuid`
  置回 `pending`（CAS 只允许 failed/dead_letter → pending），`ReplayAuditLog` 同事务；不再直接 kiq。
- **表与迁移**：`event_records` 补 `idempotency_key` / `dispatch_attempts` / `locked_until` /
  `dispatched_at` / `consuming_started_at` 五列 + 唯一索引 + outbox 扫描索引；新建
  `event_inbox`（`dedup_key` 唯一）。迁移 `core_alter_table_event_records_1794741648.sql`、
  `core_create_table_event_inbox_1794741649.sql`。**审计 ORM 探针排除名单必须含
  EventRecord / EventInbox / ReplayAuditLog**，否则消息落库会派生 `model.created` 事件形成无限风暴。
- **周期下限**：`MIN_JOB_INTERVAL=30` 不变（插件作业）；新增 `PLATFORM_MIN_JOB_INTERVAL=1`，
  仅 `platform:*` 可用秒级周期，`reconcile.py` 按 owner 取下限。
- **语义变化**：publish 从「同步入队、MQ 挂即报错」变为「落库即返回、≤1s 异步入队」；
  MQ 故障期间消息堆在 `pending` 不丢，但须监控积压。
- **运维监控**：`pending` 行数 / 最老 `published_at`、`dispatch_attempts` 高值、超时
  `consuming`、`dead_letter` 均须告警。
- **迁移执行路径（勿混淆）**：`RUN_DB_MIGRATIONS` 缺省 `true`，`init_data()` 每次启动都跑
  `init_db()` → `_run_sql_migrations()` → **重跑全部 `migrations/*.sql`**（无「已执行记录」表，
  靠 `IF NOT EXISTS` 幂等），随后 `generate_schemas(safe=True)`。因此本地/dev 重启时两份新
  SQL 自动生效，**不需要手工执行**。只有显式设 `RUN_DB_MIGRATIONS=false` 的容器
  （`deploy/taskiq/compose.taskiq.yml` 的 beat/worker，及历史 runbook 中的 app）才跳过整个
  启动期迁移，那种部署路径才须由发布流程单独执行 `migrations/*.sql`。
- **已知边界**：handler 副作用不在 DB 事务内，必须自身幂等；事务外调用点若把 publish 异常
  `except` 吞掉（如 `order_service.py` 支付事件），业务仍会提交而消息丢失 —— 这是「平台级」
  事务范围的残留风险；真库端到端（savepoint 回滚 / 并发 CAS / relay 多副本）待目标环境验证。

### 0.1 后台观测能力补齐（v1.2，2026-11-15）

不改变发布 / 消费语义，只补齐管理面可观测性：

- **载荷契约单一来源**：新建 `base/common/events/payload_contract.py`，承载
  `MAX_PAYLOAD_BYTES=256KB` / `MAX_RESULT_BYTES=32KB` / `FORBIDDEN_PAYLOAD_KEYS` /
  `validate_payload` / `sanitize_payload` / `to_jsonable`。`base/core/events/contract.py`
  改为再导出，保持 `common` 不反向依赖 `core`，`/v1/event-center/rules` 展示的规则与
  实际落库行为同源。
- **发布端脱敏**：所有 `event_bus.publish` 载荷在落库前递归遮蔽凭据字段 + 体积保护 +
  纯 JSON 化。业务直调的 20+ 调用点采取「遮蔽而非拒绝」，避免一个含 `token` 的载荷
  回滚整个业务事务；后台手动发布仍由 `event_center.publish → contract.validate_payload`
  严格拒绝违规载荷。
- **handler 返回值**：`event_inbox.return_value`（JSONB），由 `taskiq:dispatch` 捕获
  同步 / 异步 handler 返回值，经 `to_jsonable` 脱敏 + 32KB 上限后在事务②写回。
  v1.3 起无返回值写 `{"__no_return__": true}`，历史行 / 失败行由详情接口补说明对象，
  **后台不再显示语义不明的 `-`**（见 §0.2）。
- **后台详情**：`GET /v1/event-center/records/{event_uuid}/detail`（管理员权限）返回
  `EventRecord` 全文 + 按 `handler_key` 排序的 Inbox 明细；前端
  `web/src/views/events/Index.vue` 发布记录列表加「详情」抽屉，展示 payload、
  状态 / 时间与每个 handler 的 status / attempts / error / return_value。
- **迁移**：`core_create_table_event_inbox_1794741649.sql` 补 `return_value JSONB`
  （全新库直接建出），`core_alter_table_event_inbox_1794746532.sql` 幂等补列（已有库）；
  默认 `RUN_DB_MIGRATIONS=true` 路径重启自动执行。
- **边界（v1.2 时点，v1.3 已部分闭环）**：`payload` 是事件载荷，**不是 HTTP 请求体**；
  返回值只记录「成功执行的 handler 返回」，不含副作用；事件异步，publish 的 HTTP
  响应不是消费结果。v1.3 已用 `trace_id` 把事件与审计请求/响应串联（§0.2），但
  **仍不修改 `payload` 语义**，也仍未按 `event_uuid` 直接关联审计行。
- **验证**：`tests/regression_outbox.py` **15 passed**；其余 27p/5s、47/47、25/25；
  前端 SFC 经 `@vue/compiler-sfc` 编译通过；`discover()` 仍为 8 作业 / 24 订阅。

### 0.2 三项遗留闭环（v1.3，2026-11-15）

> **本节改变失败重试语义。凡 §0 / §5 / 历史文档中「失败上抛 → SmartRetry 退避重投」
> 的描述与本节冲突，一律以本节为准。**

**① trace_id 跨模块串联（原始 HTTP 请求 / 响应可见）**

- `event_records` 补 `trace_id`（含索引）；`EventBusAdapter.publish` 从
  `base.common.context.get_current_trace_id()`（TraceMiddleware 注入）继承，或用
  `_trace_id` 控制字段显式传入；**控制字段不进入 payload**。定时任务 / 作业无请求
  上下文时为 NULL。
- `GET /v1/event-center/records/{uuid}/detail` 增加 `trace` 段：按 `trace_id` 惰性解析
  审计插件模型（`base.common.plugin_symbol.resolve_plugin_symbol`，**core 不静态
  import 插件**），回查 `AuditLog`（method / path / status_code / duration /
  request_params / response_data）、`InputLayerLog.context_data`（请求体 + query）、
  `OutputLayerLog.final_output`（响应正文）、`ExecutionLayerLog`（各步参数与返回值）。
  审计插件未启用 / 表不存在时降级为 `available=false` + 明确 reason，不返回 500。
- 所有审计文本经 `payload_contract.sanitize_text` / `sanitize_json` 脱敏 + 32KB 上限；
  前端抽屉新增「关联 HTTP 请求 / 响应」区块（列表 + 输入/输出/执行层明细）。
- **仍不是**：`payload` 依旧是事件载荷而非 HTTP 请求体；`event_uuid` 与审计行未直接
  互存外键，串联依赖 `trace_id`。

**② handler 执行结果完整可观测**

- `event_inbox` 补 `execution_time_ms`（单 handler 耗时）与 `error_detail`
  （异常类型 + 截断堆栈，经文本脱敏）；`dispatch` 在事务②与返回值一并写回。
- `return_value` 不再出现裸 NULL：无返回值写 `{"__no_return__": true}`；详情接口对
  历史行（早于采集上线）/ 失败行 / 未完成行分别补 `__no_return__` 说明、
  `__failed__`、`__pending__` 说明对象。前端表格加「耗时(ms)」列与堆栈弹层。
- 迁移：`core_create_table_event_inbox_1794741649.sql`（全新库）与
  `core_alter_table_event_inbox_1794746532.sql`（已有库）同步补两列。

**③ 失败重投链路闭环（DB 状态机是唯一驱动）**

- **根因**：`SmartRetryMiddleware.on_error` 用 `with_labels(delay=...)` 重投，而
  `AioPikaBroker` 既未配 `delay_queue` 也未开 delayed-message-exchange，
  `kick():401-405` 必抛 `IncorrectRoutingKeyError`；旧链路「失败 → ack → DB 停在
  `failed` → 无人补投」实际是断的，只能人工重放。
- **修复**：`broker.py` 把 `default_retry_label` 改回 `False`，`taskiq:dispatch` 加
  `retry_on_error=False` 双保险；`dispatch` 失败**不再上抛**，改为在事务②写
  `failed` + 指数退避的 `next_retry_at`（5/10/20/40… 封顶 300s），由
  `platform:outbox_relay`（1s）到点把 `failed` 与 `pending` 一起投递；按行原状态
  分别 CAS 置 `published`，Inbox 已 `done` 的 handler 自动跳过。禁止两套重试并存。
- **投递侧无 publisher confirms**：新增 `reap_stale_published()`（挂在既有
  `platform:stale_consuming_reap` 30s 作业内）——`published` 超过 300s 仍未被消费
  且 `dispatch_attempts < 5` → 回 `pending` 补投；超预算 → `dead_letter`，避免静默
  无限重投。周期作业数保持 8 个不变。
- **ack 保持 `when_executed`**：有 Outbox 持久化真源时，ack 时点只影响重复投递频率，
  不影响是否丢失 / 是否重复生效。`config.ack_type` 不再是死配置：由
  `broker._build_broker()` 用 taskiq 官方 `parse_acknowledge_type` 做启动期 fail-fast
  校验，与 compose CLI 的 `--ack-type` 同源（`TASKIQ_ACK_TYPE`）。
- **监控补充**：`failed` 且 `next_retry_at` 已过期仍未被 relay 取走的行数、
  `retried` 计数、`dead_letter` 中 `unconfirmed dispatch exceeded max redelivery` 的数量。

**已知边界（不隐瞒）**：真库端到端（savepoint 回滚、并发 CAS、relay 多副本抢占、
退避补投实测）仍未在目标 DB/MQ 环境跑过，沙箱只有静态 + 假对象回归；handler 副作用
仍不在 DB 事务内，必须自身幂等；`published` 补投阈值 300s 是经验值，队列长期积压时
可能产生额外重复投递（由 Inbox 去重，不产生重复副作用）。

## 1. 背景与要解决的问题

改造前，一个周期作业要声明两次：`@broker.task` 写 `task_name` / `queue_name`，
`manifest.json` 的 `jobs` 再写 `handler_ref` / `interval_seconds` /
`requires_plugins` / `interval_ref`；事件订阅同样要在 `manifest.json` 的 `events`
里写 `register_ref` / `unregister_ref` / `subscribe[]`。beat 的 reconciler、worker 的
`tasks_registry`、事件中心各解析一遍 manifest，形成三份装配逻辑，声明与实装容易漂移。

同时存在两个实证缺陷：

- `reconcile.py` 把 `IntervalTrigger` 直接当 `SchedulerTrigger` 传给
  `taskiq-beat 1.4.0`，`get_strategy()` 必抛 `AttributeError`，配置好 `TASKIQ_DB_URL`
  后首轮 `_sync()` 即失败、调度行一行都建不起来；正确写法是
  `PeriodicSchedule(interval=IntervalTrigger(seconds=...))`。
- `base/plugins/mes/services/event_handlers.py` 的 4 条订阅全仓库无调用点
  （符合性检查 §2.2 / 整改方案 W2-2 均登记为死代码），既未生效也无法随插件启停装卸。

本规范把「声明」收敛到**代码所在处**，一个真源、一个发现器、三个进程共用。

## 2. 单一真源与目录约定

| 声明对象 | 位置 | 声明方式 |
|---|---|---|
| 插件周期作业 | `base/plugins/<plugin>/task/*.py` | `@broker.task(..., ap_schedule=...)` |
| 插件事件订阅 | `base/plugins/<plugin>/task/subscriptions.py` | `@ap_subscribe(...)` 装饰注册函数 |
| 系统级（平台）作业 | `base/common/taskiq_app/platform_jobs.py` | `@broker.task(..., ap_schedule=...)`，`owner=platform`，不受插件启停门控 |

- 发现器：`base/common/taskiq_app/discovery.py`，扫描带 `manifest.json` 的插件目录，
  取优先级最高的任务目录（`task/` → `tasks/` → `jobs/` 兼容回退），`import` 模块触发
  注册后抽取 `TaskSpec` / `EventSubSpec`；单模块导入失败隔离，不影响其它插件。
- **禁止**在 `manifest.json` 写 `jobs` / `events` 段：`plugin_contract.validate_manifest`
  对残留段直接拒绝装配（写了也不会生效，必须显式迁移）。CLI 脚手架
  `base/cli/command.py` 生成新插件时也不再写 `events`。
- 发现结果进程内缓存：新增/改动 `task/*.py` 后需重启 beat、worker、app；
  插件启停与 `ap_interval_ref` 变更仍由 5s 重扫收敛，无需重启。

## 3. 周期作业声明契约（`@broker.task`）

| 标签 | 必填 | 语义与校验 |
|---|---|---|
| `task_name` | 是 | 必须为 `owner:name`；同时就是 `scheduler_job.job_id`，与既有调度行一致，**零数据迁移** |
| `queue_name` | 周期作业必填 | 必须为 `ap.jobs`；否则不参与排程 |
| `ap_schedule` | 否 | 整数秒且 ≥ `MIN_JOB_INTERVAL`（30）；**有此标签 = 参与 beat 排程**，无则只注册为可调用 task |
| `ap_interval_ref` | 否 | `"module:callable"`，beat 每轮重扫时调用以热重载间隔；必须与 `ap_schedule` 同时声明 |
| `ap_requires` | 否 | 插件名数组，AND 门控；依赖未激活则不进入本轮 targets |
| `ap_description` | 否 | 说明文本，写入调度行 |

```python
@broker.task(
    task_name="harness:gateway_reconcile", queue_name="ap.jobs",
    ap_schedule=600,
    ap_interval_ref="base.plugins.harness.task.reconcile:resolve_interval",
)
async def run() -> None: ...
```

非法标签记 error 并**跳过该任务**，不写进 `scheduler_job`（替代旧 `validate_jobs()`）。

## 4. 事件订阅声明契约（`@ap_subscribe`）

| 参数 | 必填 | 语义与校验 |
|---|---|---|
| `*events` | 是 | 小写点分事件名（复用 `plugin_contract.is_valid_event_name`），同一声明内不得重复；一事件展开一条 `EventSubSpec` |
| `unregister_ref` | 强烈建议 | 注销入口；可写模块内函数名（自动补 `module:`）或完整 `module:callable` |
| `bootstrap` | 否 | 一次性启动钩子，语义同旧 `manifest.events.bootstrap` |
| `description` | 否 | 写入 `event_subscriptions.description` |

```python
@ap_subscribe(
    "sales.paid", description="CRM：订单支付触发跟进任务",
    unregister_ref="unregister",
)
def register() -> None:          # 注册函数，函数体延迟 import 真实现
    from base.plugins.crm import register_crm_event_handlers
    return register_crm_event_handlers()

def unregister() -> None: ...     # 与注册严格对称
```

**关键语义**：被装饰函数是**注册函数**（把真 handler 绑进 `event_bus` 的
`_handler_registry`），不是可直接执行的事件处理体。因此 worker 不能查
`EventSubscription` 行 `resolve_callable(handler_ref)` 直接执行；`handler_ref` 在
发现结果中就是 `register_ref`，DB 行用于管理面展示与状态同步。

`EventSubSpec.sub_name = "<owner>:<event_name>"`，与既有 `event_subscriptions` 主键
完全一致，零数据迁移；旧行按 name 命中后原地更新 `handler_ref`。

## 5. 发现器与三进程消费矩阵

| 进程 | 发现结果用法 | 职责边界 |
|---|---|---|
| **app** | 不参与作业发现；`event_center.initialize()` 按发现结果同步订阅注册表（仅作生产探针 / 管理面） | 处理 HTTP、插件启停、**只在事务内写 Outbox 消息**（`EventRecord(pending)`，见 §0）；不连 broker、不调度、不消费 |
| **beat** | `scheduled_specs(discover())` → 写 `scheduler_job` 行（5s 周期 diff，差集 `pause` 不删行） | 唯一调度源，必须单实例；trigger 用 `PeriodicSchedule(interval=IntervalTrigger(...))` |
| **worker** | `discover()` 注册全部 task + `apply_plugin_gate`；`event_center.initialize()` 建进程内注册表，5s `resync()` 按发现结果收敛装卸 | 消费 `ap.jobs` + `ap.events`，可多副本；`taskiq:dispatch` 两段事务按 `get_handlers(event_name)` 执行；同时跑 outbox relay / 悬挂回收两个平台作业 |

**双门控**：beat 侧按 `is_plugin_active(owner)` 决定是否进入 targets；worker 侧
`job_gate` 在每条消息执行前再查一次，兜住「已投递但尚未 pause」的窗口。

**发布链路（§0 修订后）**：`event_center.publish`（contract 校验）→
`EventBusAdapter.publish` 事务内写 `EventRecord(pending)` → **投递唯一通道**
`platform:outbox_relay` 批量 `dispatch.kiq` → `ap.events` → `taskiq:dispatch` 两段事务消费。
app 不连 broker、不在本进程执行订阅；幂等由 DB 唯一键 + `event_inbox` 共同保证。
失败置 `failed` + `next_retry_at`（指数退避），由 relay 到点补投 → 超预算
`dead_letter`（§0.2 ③）；重放复用**同一 event_uuid** 置回 `pending`。

## 6. 对 v3.0 需求条款的现行解释（需求编号与评级不变）

| 条款 | 现行解释 |
|---|---|
| PLR-13 / AC-PLR-13-1 | 平台层不静态导入插件实现：平台只依赖发现结果，插件作业/订阅代码留在插件 `task/` 目录 |
| AC-PLR-13-2 | 新增插件的作业与订阅不需要修改任何平台级定义文件；仅在插件自身 `task/` 目录新增声明文件 |
| PLR-14 / AC-PLR-14-1 | 事件契约不变；发布端 `idempotency_key` DB 唯一约束 + 消费端 `event_inbox` / `EventRecord` 终态幂等共同保证重复投递不产生重复副作用（§0） |
| PLR-15 / AC-PLR-15-1 | 作业声明与执行解耦，插件禁用后 beat 不排程、worker 门控跳过，执行不抛异常 |
| AC-PLR-15-2 | 「新增插件无需修改平台级作业定义文件」由发现器满足；平台作业例外，必须写在 `platform_jobs.py` |

新增可验收条款：

- **AC-DECL-01**：任一 `manifest.json` 出现 `jobs` 或 `events` 段 → 拒绝装配并指出文件。
- **AC-DECL-02**：`discover()` 与 `discover_event_subscriptions()` 的 owner 由模块路径推断，
  与 `task_name` 前缀不一致时以模块路径为准。
- **AC-DECL-03**：每个 `@ap_subscribe` 声明的 `register_ref` / `unregister_ref` 均可解析，
  且注册幂等、注销后进程内注册表不残留 handler。
- **AC-DECL-04**：`scheduler_job.job_id` 等于 `task_name`，重复 `upsert` 不新增行。
- **AC-DECL-05**：发现结果为空或平台作业一个都没发现时，reconciler 跳过本轮 diff（fail-safe，防误停全部调度行）。

## 7. 强制约束与运维

1. 新增插件路由、作业、订阅一律经 `manifest.routes` / `task/` 声明装配，**禁止入口自挂**
   （否则绕过请求期 `plugin_gate` 门控）。
2. `task/` 目录必须随镜像发布；若镜像用白名单复制 Python 包，需确认该目录未被排除。
3. beat 严格单实例、worker 可 `--scale`；三者共用同一份 `TASKIQ_BROKER_URL` secret
   （vhost `agentpanel`）。
4. **禁止手工预建 `ap.*` 队列**：裸参数 durable 声明会让 taskiq 后续声明报
   `PRECONDITION_FAILED` 并连带打挂插件菜单/权限同步；连通性验证只建连接或 passive 声明。
5. `RUN_DB_MIGRATIONS=false` 时须单独执行 `migrations/*.sql`（含
   `core_create_table_scheduler_*.sql`、`core_create_table_event_subscriptions_*.sql`、
   `core_alter_table_event_records_1794741648.sql`、
   `core_create_table_event_inbox_1794741649.sql`、
   `core_alter_table_event_inbox_1794746532.sql`）。默认 `true` 路径下启动期自动重跑全部
   SQL 迁移（每次重启、无执行记录表、SQL 自身幂等），**不必手工执行**。
6. 插件启停 ≤ `reconcile_interval`（5s）生效；新增/修改 `task/*.py` 文件需重启
   beat、worker、app（发现结果进程内缓存）。

## 8. 验收与回归（2026-11-15 实测）

- 发现结果：**8 个周期作业**（原 6 个 + `platform:outbox_relay` / `platform:stale_consuming_reap`）、
  **24 条事件订阅声明**（audit 5 / mail 3 / crm 1 / finance 8 / subcontracting 3 / **mes 4**）。
- `tests/regression_outbox.py` **21 passed** + `tests/regression_taskiq_split.py`
  **28 passed / 5 skipped**（v1.3 后合计 **49 passed / 5 skipped**）；
  `tests/regression_pending.py`：**47/47**；
  `tests/regression_plugin_assembly.py`：**25/25**；改动文件 `py_compile` 全通过，
  前端 `Index.vue` 经 `@vue/compiler-sfc` 模板 + script 编译通过。
- 冒烟插件端到端验证 `register` / `unregister` 均由新链路调用，finance 8 行订阅装卸对称；
  mes 注册幂等与注销对称经进程内注册表实测（不依赖 DB）。

## 9. 与历史文档的关系

| 历史文档 | 定位 | 处理 |
|---|---|---|
| `AgentPanel-平台级需求规格-v3.0-2026-11-12.md` | 现行需求基线 | 附录 D + PLR-15 补充现行解释；需求编号/评级不变 |
| `AgentPanel-路径契约与装配硬编码诊断及整改方案-2026-11-12.md` | 整改记录 | §0.2 / W0-1 / W2-2 / W2-3 表格按现行修订；W2-2 的 mes 待办闭环 |
| `AgentPanel-W2-3-定时任务注册表设计方案-2026-11-12.md` | W2-3 实施记录 | §9.6 记录废弃与后续改造；§3/§5/§9.1 保留为历史 |
| `AgentPanel-taskiq-M1实施拆解-2026-11-14.md` | M1/M2/M3 实施记录 | §3 布局表按发现器重写，§10 记录后续改造 |
| `AgentPanel-事件消费外迁taskiq-方案B-2026-11-14.md` | 已归档方案 | D1/D4 实施期已改判，以 M1 §9.3 与本规范为准 |
| `AgentPanel-调度与消费服务独立化-taskiq可行方案-2026-11-14.md` | 已实施方案 | 「manifest.jobs 契约一字不改」前提已不成立 |
| `AgentPanel-平台级基线-路由与事件订阅符合性检查-2026-11-12.md` | 时点检查报告 | §2 统计保留为 2026-11-12 事实，整改状态已标注 |
| PRD v1.0 / v2.0 及三份评审报告 | 已归档/作废 | 结论不受装配机制变更影响，不得作为现行基线 |

## 10. 已知边界（尚未闭环，不隐瞒）

- `mes` 的 manifest 默认 `is_installed=false` / `is_enabled=false`：4 条声明会被发现，
  但**只有管理员安装并启用 MES 后**才注册生效；其中
  `inventory.picking_done` / `inventory.receipt_done` 两个 handler 仍是**占位实现**
  （原文件即 no-op），本次只完成接线、未补业务逻辑，不能按已实现功能验收。
- 后台新建/改 `handler_ref` 的 **manual 订阅**：worker 的 5s `resync()` 只收敛
  declared 订阅，不重新 `bind_manual`，仍需重启 worker（或补周期 rebind / 广播通知）。
- `EventSubscription` 行 ↔ 进程内注册表完备性对账未做；beat / worker 容器真实端到端、
  R2 / R17 验证待目标环境（沙箱无 Docker）。
- **`reports/prd/*` 历史方案正文按历史记录保留，凡与本文冲突之处一律以本文为准**。
- **Outbox/Inbox（§0）**：跨 DB 与 MQ 只能最终一致；handler 副作用不在事务内，须自身幂等；
  「平台级」事务范围下，事务外调用点若吞掉 publish 异常，业务仍可能提交而消息丢失；
  真实 PG 上的 savepoint 回滚、并发 CAS、relay 多副本抢占尚未在目标环境做端到端验证
  （沙箱无 DB / MQ 实例，本轮仅静态 + 假对象回归）。
- **trace 串联（§0.2 ①）**：只有经 `TraceMiddleware` 覆盖的 HTTP 请求才会写入
  `trace_id`；被 `exclude_paths` 排除的路径、后台作业 / 定时任务产生的事件为 NULL，
  详情页会明确提示「无关联请求」。审计模块未启用或表未建立时按可选能力降级。
- **重试（§0.2 ③）**：`published` 未确认补投阈值 300s 为经验值；队列长期积压时会产生
  额外重复投递（Inbox 去重只保证副作用不重复）。投递侧**仍无 publisher confirms**
  （第三方 `AioPikaBroker.kick` 不 await confirm），强保证只在 DB 状态机一侧。
