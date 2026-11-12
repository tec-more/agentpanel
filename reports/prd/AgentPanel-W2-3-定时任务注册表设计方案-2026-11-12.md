# AgentPanel W2-3 定时任务注册表设计方案

| 项 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 文档类型 | 设计方案 + **已实施（2026-11-12 晚，全量回归通过，详见 §9）** |
| 上游文档 | `AgentPanel-路径契约与装配硬编码诊断及整改方案-2026-11-12.md`（W2-3 条目） |
| 前置状态 | W2-1 已完全整改（2026-11-12 晚）：`base/start.py` 顶层与 init_app/lifespan **装配层**插件导入=0 |
| 目标 AC | AC-PLR-15-1 / AC-PLR-15-2 / AC-PLR-13-1（完全达标）/ AC-PLR-23-1·23-3（保持） |
| 约束 | 用户已授权解除「观察期内不改运行时装配」；本方案不改变任何作业的业务行为，只改装配与门控方式 |
| 实施验证 | `regression_plugin_assembly.py` **24/24** + `regression_pending.py` **28/28** 全绿；`base/start.py` 具体插件导入=**0（含函数体）**；运行期 6 个作业全部装载并对称取消 |

---

## 1. 问题定义

`base/start.py` 中残留 8 处 `from base.plugins.<插件>` 惰性导入，全部位于定时任务相关代码：

| # | 位置 | 导入内容 | 所属作业 |
|---|---|---|---|
| 1 | start.py:149（lifespan gating） | harness `gateway_enabled, reconciliation_config` | 网关对账 gating |
| 2 | start.py:302 | harness `reconciliation_config` | 网关对账任务体 |
| 3 | start.py:305 | harness `HarnessReconcileService` | 网关对账任务体 |
| 4 | start.py:332 | audit `data_change_service`（3 个符号） | 审计日志清理任务体 |
| 5 | start.py:374 | sales `OrderService` | 订单过期取消任务体 |
| 6 | start.py:409 | customer `CustomerMembership` | 会员数据更新任务体 |
| 7 | start.py:410 | llm `LLMUsageRecord` | 会员数据更新任务体 |
| 8 | start.py:533 | customer `fibonacci_service` | 会员数据更新任务体 |

除导入违例外，还存在一个**行为级缺口**（AC-PLR-15-1 真实未闭环点）：

> **运行期禁用插件后，其定时任务仍在空转。** 现有门控只发生在 lifespan 启动那一刻（`manager.get_active_plugin(...)` 判一次），之后插件被 `disable_plugin` 也不会取消已创建的 `asyncio.Task`——任务每轮继续 import 插件模块并空转报错/白跑。动态回归 B 组只覆盖了「启动期跳过」，未覆盖「运行期取消」。

## 2. 现状盘点：6 个作业

| 作业 | 间隔 | 现门控 | 插件耦合 | 公共层？ |
|---|---|---|---|---|
| `cancel_expired_orders_task` | 300s | sales 启用 | sales OrderService | 否 |
| `update_membership_data_task` | 600s | customer **且** llm 启用 | customer 模型+服务、llm 模型 | 否 |
| `quota_reconcile_task` | 60s | 无（恒启） | `base.common.quota`（非插件） | **是** |
| `quota_hold_cleanup_task` | 60s | 无（恒启） | `base.common.quota`（非插件） | **是** |
| `gateway_reconcile_task` | interval 每轮自读（默认 600s，≥30） | harness 启用 且 gateway_enabled 且 reconciliation.enabled | harness 配置+对账服务 | 否 |
| `audit_cleanup_task` | 86400s | audit 启用 | audit data_change_service | 否 |

通用行为模式（现有任务体已统一）：`while True: sleep(interval) → 执行 → CancelledError 退出 → Exception 记日志不中断`；首轮先 sleep 后执行（audit 注释明确要求避免启动瞬间批量删除）。调度器必须**原样保留**该模式。

## 3. 目标架构

### 3.1 manifest `jobs` 声明（契约新增字段）

风格对齐 `events.subscribe`，声明式、随插件启停装卸：

```json
"jobs": [
  {
    "name": "cancel_expired_orders",
    "description": "每5分钟检查并取消过期订单",
    "handler_ref": "base.plugins.sales.jobs.orders:run",
    "interval_seconds": 300
  }
]
```

字段规则（`plugin_contract.py::validate_manifest` 新增校验）：

| 字段 | 必填 | 规则 |
|---|---|---|
| `name` | 是 | 插件内唯一，`^[a-z][a-z0-9_]*$` |
| `handler_ref` | 是 | `module:callable` 格式（与事件中心一致）；校验期**只验格式不导入**，装载期解析失败仅记日志不阻断其他插件（对齐路由装配「单文件失败不阻断」） |
| `interval_seconds` | 是 | 整数 ≥ 30 |
| `requires_plugins` | 否 | 字符串数组；装载时逐个过 `is_plugin_active`，任一未启用则该作业不启动（实现 customer+llm 的 AND 门控） |
| `description` | 否 | 展示用 |

### 3.2 平台统一调度器 `base/common/jobs/`

```
base/common/jobs/
├── __init__.py        # 导出 job_scheduler 单例访问器
└── scheduler.py       # JobScheduler
```

接口（与插件管理器启停钩子对齐）：

```python
class JobScheduler:
    async def start_all(self) -> None
        # lifespan 启动期调用：先装平台作业，再遍历已启用插件的 manifest.jobs
    async def start_plugin(self, name: str) -> int
        # enable_plugin 钩子；返回启动的作业数（防重复：先 stop_plugin 再装）
    async def stop_plugin(self, name: str) -> int
        # disable_plugin 钩子；cancel 该插件全部任务并 await 收尾，返回取消数
    async def shutdown(self) -> None
        # lifespan 关闭期调用：cancel 全部（含平台作业）
```

关键实现约定：

- **任务登记**：`self._tasks: dict[str, list[asyncio.Task]]`，键为插件名，平台作业用保留键 `"__platform__"`。
- **通用 runner**：调度器持有唯一的 `_run_loop(handler, interval, job_key)` 协程，复刻现有 `while True` 模式（首轮 sleep、CancelledError 退出、异常记日志继续）。**各插件 handler 不再自带 while 循环**，只实现单轮逻辑并返回。
- **门控隐式化**：调度器只遍历**已启用**插件（`get_enabled_plugins_from_manifests()`），取代现有 5 段 `get_active_plugin` gating；`requires_plugins` 处理跨插件 AND。
- **启用时序**：`plugin_manager.enable_plugin` 在订阅同步之后追加 `await job_scheduler.start_plugin(name)`（完整链：路由→菜单→权限→订阅→作业）；`disable_plugin` 在订阅停用后追加 `await job_scheduler.stop_plugin(name)`。调度器未初始化/未 set_app 时两个钩子静默跳过并记 debug。
- **解析失败隔离**：单作业 `handler_ref` 解析失败只 `log.error`，不阻断同插件其他作业、不阻断其他插件、不中断启动（fail-open 于单个作业，fail-closed 于平台）。

### 3.3 handler_ref 解析复用

事件中心已有 `base/core/events/registry.py::resolve_callable(ref)`（`module:callable`，importlib 动态解析）。为避免 `base/common/jobs` 反向依赖 `base/core/events`，将其**下沉**为：

```
base/common/dynamic_ref.py    # resolve_callable 定义（新增，~15 行）
base/core/events/registry.py  # 改为 from base.common.dynamic_ref import resolve_callable（保留同名再导出，调用方不受影响）
```

### 3.4 特殊语义处理

- **会员作业跨插件 AND**：声明在 customer manifest，`"requires_plugins": ["llm"]`（customer 自身启用由调度器隐式保证）。
- **网关对账 gating 下沉**：`gateway_enabled()` / `reconciliation.enabled` 判断移入 harness handler 单轮逻辑内自查（interval 本就每轮重读，语义不变）；lifespan 148-164 gating 块整体删除。gating 不满足时 handler 单轮直接返回（任务保留、轻量空转可接受——这与"作业被平台取消"不同层，属于业务级开关）。
- **audit 保留天数每轮解析**：现有行为原样保留在 handler 内。
- **quota 两作业**：以平台作业身份在 `scheduler.start_all()` 内用代码注册（`register_platform_job(name, handler, interval)`），`base/common/quota` 导入不属于插件违例，**不强制 manifest 化**。

### 3.5 start.py 瘦身后形态

lifespan 中 5 段 gating + create_task + 约 300 行任务函数体全部删除，替换为：

```python
        # 初始化插件系统（原有）
        manager = get_plugin_manager()
        manager.set_app(app)
        await manager.load_enabled_plugins()
        await manager.startup()

        # 定时任务统一装配（W2-3）：平台作业 + 已启用插件的 manifest.jobs 声明
        await job_scheduler.start_all()
        print("定时任务装配完成")

        yield

    finally:
        ...
        await job_scheduler.shutdown()   # 先于插件 shutdown，取消全部任务
```

完成后 `base/start.py` 中 `from base.plugins.<插件>` 导入数 = **0（真零，含函数体）**，AC-PLR-13-1 完全达标。

## 4. 作业迁移映射

| 作业 | 任务体去向 | manifest 声明位置 | 门控方式 |
|---|---|---|---|
| cancel_expired_orders | `base/plugins/sales/jobs/orders.py::run` | sales | 隐式（启用即装） |
| update_membership_data | `base/plugins/customer/jobs/membership.py::run` | customer + `requires_plugins:["llm"]` | 隐式 + AND |
| quota_reconcile | `base/common/jobs/platform.py`（原函数体平移） | 平台注册（代码） | 恒启 |
| quota_hold_cleanup | 同上 | 同上 | 恒启 |
| gateway_reconcile | `base/plugins/harness/jobs/reconcile.py::run`（内含 enabled/reconciliation 自查 + interval 每轮自读经返回值/共享状态？→ **见 §7 决议**） | harness | handler 业务自查 |
| audit_cleanup | `base/plugins/audit/jobs/cleanup.py::run` | audit | 隐式 |

**§7 决议（interval 每轮重读）**：gateway 作业 interval 来自 `reconciliation_config().interval_seconds` 且可后台改配置热生效。为不引入平台-插件反向耦合，采用**调度器支持 handler 返回可选 next-interval** 约定：`run()` 返回 `None`（用 manifest interval）或正整数（本轮覆盖）。契约注明该约定，audit 的 86400 固定间隔不受影响。

## 5. 契约校验（plugin_contract.py）

- `jobs` 非列表 → 报错；每项缺 `name`/`handler_ref`/`interval_seconds`、格式或下限非法 → 报错（`route_prefix` 同级硬校验）。
- **不**在校验期 import handler 模块（避免契约校验产生插件代码执行副作用）；解析失败留到装载期隔离。

## 6. 回归与验收

| 项 | 改动 |
|---|---|
| `tests/regression_pending.py` B 组 | B1（顶层导入）保持；B2/B3 改测**调度器**：禁用 audit 后 `job_scheduler` 中 audit 任务被 cancel（运行期取消，补上 15-1 真实缺口）；B4 改为 `start_all()` 后任务计数断言（平台 2 + 插件声明数） |
| `tests/regression_plugin_assembly.py` | 不改断言；approval/alipay 启停回归顺带覆盖 start_plugin/stop_plugin 对称 |
| 新增断言 | ① 禁用 sales → 其作业任务取消；② 重新启用 → 任务恢复；③ smoke_sample 无 jobs 声明 → 启停不受影响 |
| 验收口径 | start.py 插件导入=0；6 作业行为等价（间隔/首轮 sleep/异常不中断）；20/20 + 24/24 全绿 |

## 7. 实施步骤（每步带验证闸门）

1. **契约+解析下沉**：`dynamic_ref.py` 新建、events registry 改导入、`plugin_contract.py` jobs 校验 → py_compile + 既有回归（纯新增，预期零影响）。
2. **调度器骨架**：`base/common/jobs/` 新建，start.py 两个 quota 作业迁为平台作业（行为等价）→ 启动冒烟 + 20/20。
3. **插件 jobs 搬移**：sales/customer(+llm requires)/audit/harness 四插件新增 `jobs/` 模块 + manifest 声明（任务体机械平移，含全部 print）→ py_compile。
4. **启停集成**：plugin_manager 两钩子 + start.py lifespan 替换 + 删旧任务函数 → 全量回归 20/20 + 24/24。
5. **回归改写+文档**：B 组改写为新断言，诊断文档 W2-3 行/§6、MEMORY.md、日志更新。

## 8. 风险与边界

| 风险 | 缓解 |
|---|---|
| 运行期 disable 的任务取消时序 | `stop_plugin` 逐个 `cancel()` + `wait_for(timeout=2)` 收尾（复用现有 finally 模式）；挂在订阅停用之后，handler 内 DB 调用已随 Tortoise 全局关闭语义一致 |
| enable→disable→enable 循环 | `start_plugin` 先 `stop_plugin` 防重复装载（回归压测覆盖） |
| 单作业失败拖垮启动 | 解析/首轮异常均隔离记日志（§3.2 约定） |
| 行为回归 | 任务体只平移不改写（含 print 文案）；间隔、首轮 sleep、异常处理逐字段比对 |

**明确不做**（后续按需另立项）：cron 表达式、分布式锁/多实例互斥、作业执行历史持久化、错峰抖动、interval 配置热更新以外的动态调度。

---

## 评审确认点

1. `handler_ref` 用 `module:callable` 冒号格式（与事件中心一致）而非点分路径——是否接受？
2. gateway interval 热生效采用「handler 返回 next-interval」约定（§4 决议）——是否接受？
3. quota 平台作业保持代码注册、不 manifest 化——是否接受？
4. 实施顺序 5 步、每步回归闸门——是否按此执行？

> 用户以「继续当前项目的上一个问题」推进实施，以上 4 点按方案默认决策执行，其中第 2 点做了等价增强（见 §9.3）。

---

## 9. 实施记录（2026-11-12 晚）

### 9.1 落地清单

| 层 | 文件 | 动作 |
|---|---|---|
| 契约 | `base/common/plugin_contract.py` | 新增 `validate_jobs()`（`name`/`handler_ref`/`interval_ref` 格式、`interval_seconds ≥ 30`、`requires_plugins`），挂入 `validate_manifest`；校验期不 import handler |
| 解析 | `base/common/dynamic_ref.py`（新增）、`base/core/events/registry.py` | `resolve_callable` 下沉到公共层，事件中心改导入并保留同名再导出，调用方无感 |
| 调度器 | `base/common/jobs/{__init__,scheduler,platform}.py`（新增） | `JobScheduler`（`start_all`/`start_plugin`/`stop_plugin`/`shutdown`/`register_platform_job`）+ 唯一 `_run_loop`；quota 两作业平移为平台作业 |
| 插件 | `sales/jobs/orders.py`、`customer/jobs/membership.py`、`audit/jobs/cleanup.py`、`harness/jobs/reconcile.py` + 4 份 `jobs/__init__.py`（新增） | 6 个旧任务体中 4 个插件作业改单轮 handler；任务体机械平移（含全部 print 文案） |
| 声明 | 4 份 `manifest.json` | 新增 `jobs` 声明；customer 带 `requires_plugins:["llm"]`，harness 带 `interval_ref` |
| 装配 | `base/common/plugin_manager.py` | 新增 `_sync_plugin_jobs()`；`enable_plugin`（状态双真后）/`disable_plugin`（订阅停用后，含早退分支）双向挂钩；启动期未就绪静默跳过 |
| 启动 | `base/start.py` | 删除 5 段 gating + 6 个旧任务函数体（**320 行**），lifespan 改 `await job_scheduler.start_all()`，finally 先 `shutdown()`；`from base.plugins.<插件>` 导入数 **= 0（含函数体）** |
| 回归 | `tests/regression_pending.py` | B 组重写为调度器断言（全文零导入、6 作业计数、运行期取消/恢复、启停对称、钩子集成链），C 组补「无 jobs 声明插件启停不受影响」 |

### 9.2 验收结果

- `py_compile` 全部改动文件通过；23 份 manifest 契约校验全通过；4 个 `handler_ref` + 1 个 `interval_ref` 运行期均可解析。
- `regression_plugin_assembly.py` **24/24**、`regression_pending.py` **28/28**（由 20 项扩到 28 项）全绿，退出码均为 0。
- 运行期日志确认：装配 6 个作业，归属 `{'__platform__': 2, 'audit': 1, 'customer': 1, 'harness': 1, 'sales': 1}`；关闭时逐个 `cancel` 并等待收尾；**0** 装载失败 / 间隔解析失败 / 作业同步失败。
- AC-PLR-13-1 **完全达标**（真零，含函数体）；AC-PLR-15-1 运行期禁用即取消已闭环；AC-PLR-15-2 / 23-1 / 23-3 回归保持通过。

### 9.3 与方案的偏差（均为等价增强或安全调整，需复核）

1. **评审确认点 2 的等价增强**：「handler 返回 next-interval」只能影响**下一轮** sleep，首轮仍用 manifest 的 600s；若后台把对账间隔改成 300s，首轮会多睡 300s。故新增可选契约字段 `interval_ref`（`module:callable`，调度器在**每轮 sleep 前**调用，含首轮），harness 用它保持原任务「每轮重读配置」语义；handler 返回 next-interval 的通用能力同时保留。
2. **gateway gating 语义增强**：原任务只在启动期判一次 `gateway_enabled && reconciliation.enabled`；现 handler 每轮自查，后台关闭开关可即时停止业务调用（任务保留轻量空转）。属方案 §3.4 明确要求，但严格说是行为变化，故在此记录。
3. **实施顺序微调**：方案 §7 的步骤 2 要求中途就把 quota 作业迁到 start.py；实际改为「先建全部模块（步骤 1-3）→ 一次性接入 start.py + plugin_manager（步骤 4）」，避免中间态出现重复启动或引用尚未落地的 handler。每步闸门以 `py_compile` + 契约/解析自检 + 调度器行为自测等价替代，最终全量回归口径不变。
4. **B 组真实启停样本改用 audit**：`crm` 声明依赖 `sales`，`disable_plugin('sales')` 会被依赖门控拒绝（返回 False），故 sales 的「禁用取消 / 重新启用恢复」改由调度器 `stop_plugin`/`start_plugin` 直接测；真实 `plugin_manager` 启停集成用 audit（无被依赖、入口无钩子）验证，并在 finally 恢复 manifest 原文、门控缓存与作业。另加静态断言确认两条启停路径都挂了 `_sync_plugin_jobs`。

### 9.4 遗留（不属于 W2-3）—— 已由后续「仍 OPEN 的继续修复」全部闭环

四项均于 2026-11-12 晚修复，详见 `AgentPanel-路径契约与装配硬编码诊断及整改方案-2026-11-12.md` §0.5：

- **AC-PLR-03-1**：装配时给插件路由注入 `plugin_gate.plugin_route_guard` 请求期依赖，禁用即 404、重新启用 200；`app.routes` 对象保留（FastAPI 无法安全卸载），但业务 handler 不再执行。
- **event_subscriptions 迁移**：项目实际用 `migrations/*.sql`（非 aerich python 迁移），已补 `core_create_table_event_subscriptions_1794491161.sql`（core 前缀恒执行）；`RUN_DB_MIGRATIONS=false` 部署流程单独执行 SQL 迁移即可建表。
- **mail Traceback（更正上轮误判）**：不是 dev 库 schema 问题，而是关闭期竞态 —— `queue.cancel` 后在途消息仍在跑，随后 channel / DB 先关导致 `CancelledError` 与 `ChannelInvalidStateError` 被 aio_pika `_task_done` 抛到事件循环。已由 `ConsumerWorker.stop()` 排空在途任务 + 回调外壳异常收口修复；最终回归日志 Traceback **12 → 0**。
- **agent 插件**：删除 `__init__.py` 自导出 `router` 与 `on_enable` 自挂载，改由 `manifest.routes = ["api/aggregate"]` 聚合装配（102 条路径与旧集合完全一致）。

本轮最终回归：`regression_plugin_assembly.py` 24/24、`regression_pending.py` **42/42** 全绿。

### 9.5 部署注意

- 新增目录 `base/common/jobs/` 与 4 个插件的 `jobs/` 必须随代码一同发布；容器镜像若用白名单复制 Python 包，需确认新目录未被排除。
- `interval_ref` 指向的模块由调度器运行期动态 import，无需在镜像启动脚本额外注册；`handler_ref` 解析失败只记日志不阻断启动（fail-open 于单作业），上线后应巡检 `[作业调度] ... 装载失败` 日志。
- prod 建议对 `job_scheduler.task_owners()` 增加一条启动巡检/指标，确认期望的作业数（当前 6）全部在线。
