# AgentPanel 声明式任务与事件订阅机制规范（现行基线）

| 项 | 内容 |
|---|---|
| 文档编号 | AP-SPEC-DECL-1.0 |
| 版本 / 日期 | v1.0 / 2026-11-15 |
| 状态 | **现行有效**（代码已落地，全套回归通过） |
| 适用层级 | 平台级装配契约，适用于全部插件 |
| 取代 | `manifest.json` 的 `jobs` 段与 `events` 段（2026-11-15 起废弃，残留即拒绝装配） |
| 上游需求 | `AgentPanel-平台级需求规格-v3.0-2026-11-12.md`（PLR-13 / PLR-14 / PLR-15） |
| 落地代码 | `base/common/taskiq_app/discovery.py`、`reconcile.py`、`tasks_registry.py`、`platform_jobs.py`、`base/core/events/registry.py` |
| 安全约定 | 只列配置键名与代码路径，不记录 `config.conf` / `.env` / secrets 的任何取值 |

---

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
| **app** | 不参与作业发现；`event_center.initialize()` 按发现结果同步订阅注册表（仅作生产探针 / 管理面） | 处理 HTTP、插件启停、**只发布事件**（`EventRecord(published)` + `dispatch.kiq`），不调度、不消费 |
| **beat** | `scheduled_specs(discover())` → 写 `scheduler_job` 行（5s 周期 diff，差集 `pause` 不删行） | 唯一调度源，必须单实例；trigger 用 `PeriodicSchedule(interval=IntervalTrigger(...))` |
| **worker** | `discover()` 注册全部 task + `apply_plugin_gate`；`event_center.initialize()` 建进程内注册表，5s `resync()` 按发现结果收敛装卸 | 消费 `ap.jobs` + `ap.events`，可多副本；`taskiq:dispatch` 按 `get_handlers(event_name)` 执行 |

**双门控**：beat 侧按 `is_plugin_active(owner)` 决定是否进入 targets；worker 侧
`job_gate` 在每条消息执行前再查一次，兜住「已投递但尚未 pause」的窗口。

**发布链路**：`event_center.publish`（contract 校验 + Redis 300s 幂等）→
`EventRecord(published)` + `dispatch.kiq` → `ap.events`。单通道、fail-closed
（入队失败上抛，无内存降级），不在 app 内执行订阅。消费端按 `event_uuid` 终态幂等
跳过；失败置 `failed` 上抛 → SmartRetry 退避重投 → 超预算 `dead_letter`；重放复用
**同一 event_uuid** 重新 `kiq`。

## 6. 对 v3.0 需求条款的现行解释（需求编号与评级不变）

| 条款 | 现行解释 |
|---|---|
| PLR-13 / AC-PLR-13-1 | 平台层不静态导入插件实现：平台只依赖发现结果，插件作业/订阅代码留在插件 `task/` 目录 |
| AC-PLR-13-2 | 新增插件的作业与订阅不需要修改任何平台级定义文件；仅在插件自身 `task/` 目录新增声明文件 |
| PLR-14 / AC-PLR-14-1 | 事件契约不变；发布端 Redis 幂等 + 消费端 `EventRecord` 终态幂等共同保证重复投递不产生重复副作用 |
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
   `core_create_table_scheduler_*.sql`、`core_create_table_event_subscriptions_*.sql`）。
6. 插件启停 ≤ `reconcile_interval`（5s）生效；新增/修改 `task/*.py` 文件需重启
   beat、worker、app（发现结果进程内缓存）。

## 8. 验收与回归（2026-11-15 实测）

- 发现结果：**6 个周期作业**（含平台 quota 2 个）、**24 条事件订阅声明**
  （audit 5 / mail 3 / crm 1 / finance 8 / subcontracting 3 / **mes 4**）。
- `tests/regression_taskiq_split.py`：**27 passed / 5 skipped**；
  `tests/regression_pending.py`：**47/47**；
  `tests/regression_plugin_assembly.py`：**25/25**；改动文件 `py_compile` 全通过。
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
- `reports/prd/*` 历史方案正文按历史记录保留，凡与本文冲突之处**一律以本文为准**。
