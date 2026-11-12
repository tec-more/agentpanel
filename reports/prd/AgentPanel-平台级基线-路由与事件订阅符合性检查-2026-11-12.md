# AgentPanel 平台级基线（v3.0）路由与事件订阅符合性检查报告

| 项 | 内容 |
|---|---|
| 检查日期 | 2026-11-12 |
| 检查触发 | 复核「代码评审中看到部分路由、订阅与前端显示页面被硬编码到代码中」是否属实，并判断现状能否按 v3.0 基线约束运行 |
| 判据来源 | `reports/prd/AgentPanel-平台级需求规格-v3.0-2026-11-12.md`：§1.3 J1~J3、§3 PLR-01/02/03/13/14/15/23、各条 AC；`AgentPanel-平台级需求评审报告-v3.0-2026-11-12.md` |
| 检查范围 | `base/start.py`、`base/common/router.py`、`base/common/plugin_manager.py`、`base/common/events/`、`base/plugins/*/manifest.json` 与各插件 `__init__.py`、`base/core/users/{api,services}/`、`web/src/router/`、`web/src/stores/`、`web/src/layouts/` |
| 方法 | 静态代码核查 + 只读统计脚本；**未启动服务、未做运行时启停实测、未修改任何文件** |
| 口径说明 | 「路由」= 后端 API/WebSocket 路由注册 + 前端 vue-router 页面路由；「订阅」= 事件总线订阅关系的注册与注销（ORM 事件、业务事件、RabbitMQ 消费）；「前端显示页面」= 静态路由表指向的 `.vue` 组件 |
| 前提 / 失效条件 | 本报告以 v3.0 采用的**严格平台级定义**（J1 跨模块 / J2 无业务规则 / J3 插件变更无需改平台）为判据。该定义仍是评审报告 PB-01「待书面签字」项；若最终改按方案 A（平台 = 产品整体），涉及「前端静态路由是否算平台级违规」的判定需重评，其余实证事实不变 |

---

## 0. 结论摘要

**能运行，但不按约束运行。** 系统当前可以正常启动：装配失败几乎都被 `try/except` 吞掉，路由在 lifespan 里一次性注册，8 个启用插件的菜单与权限确实由 manifest 注入。但 v3.0 的几条硬约束——「manifest 是装配唯一输入」「仅已安装且已启用插件挂载路由」「门控集中一处」「订阅关系声明式」「后台作业不引用插件实现」——**逐条实测均不成立**。

评审反馈属实，且比反馈更具体：**硬编码不在菜单本身，而在三条旁路** —— `base/start.py` 的手动路由/订阅注册、`web/src/router/index.js` 的静态页面路由表、以及散落在 6 个文件里的 24 条 `subscribe()` 调用。

| 判据 | 要求（摘要） | 实测判定 | 关键阻断事实 |
|---|---|---|---|
| PLR-01 声明式契约 | manifest 为装配唯一输入，不得散落代码补充 | ❌ 不通过 | `plugin_manager.py:75` 允许模块导出 `router` 覆盖声明；`start.py:640-690` 手动挂路由；23 份 manifest 中 **0 份**声明事件订阅 |
| PLR-02 依赖与顺序 | 按声明依赖计算顺序，停用底层时上层不可用 | ⚠️ 部分 | 启用时有依赖检查（`:557-563`），装配有顺序（`:848-849`）；但停用后无运行时级联判定，已挂路由不撤销 |
| PLR-03 启停门控 | 仅双真插件挂路由，禁用清理菜单+权限无残留，门控集中一处 | ❌ 不通过 | `disable_plugin():629-657` **不卸路由、不清权限**；至少 7 处独立判定；`router.py:25` 的门控是死代码 |
| PLR-13 跨插件调用 | 核心层/启动入口不得导入插件实现 | ❌ 不通过 | `base/start.py` 19 行引用 `base.plugins.*`，其中 `:26/:28` 模块级 import 并立即执行；`base/common/` 另有约 10 处 |
| PLR-14 事件契约 | 事件名/载荷/幂等键/重试/确认，订阅方不可用不致发布方失败 | ⚠️ 部分 | 唯一满足的是「发布方不失败」（`event_bus.py:29-35`）；幂等键每次 `uuid4()` 且消费端不去重；订阅关系全硬编码 |
| PLR-15 后台作业解耦 | 定时任务不得直接引用插件实现 | ❌ 不通过 | 6 个作业中 4 个直接 import 插件模型/服务（sales/customer/llm/harness/audit） |
| PLR-23 可装配性 | 禁用非底层插件后启动/路由/作业均不报错，新增模块平台层改动 0 文件 | ❌ 不通过 | 「不报错」靠吞异常而非隔离；新增模块需改 `start.py` 与前端 `router/index.js` |

> **不构成缺陷的部分（按 PLR-03 明文）**：「未启用导致菜单不显示」是按需装配的设计特性，本报告不将其列为问题。被判为问题的是**声明集合之外、绕过门控的路由/页面/订阅**。

---

## 1. 后端路由：门控分散，且存在无门控旁路

### 1.1 真实生效的门控不是 `base/common/router.py:25`

此前记录的「路由门控见 `base/common/router.py:25`」**不成立**：

- `base/common/router.py:14-27` 的 `_is_plugin_enabled()` 只被 `:76` 的 `auto_discover_routers(..., check_plugin_status=True)` 分支调用；该参数默认 `False`（`:35`），全项目唯一调用 `auto_discover_routers` 的位置是 `router.py:159`，且只传 `base_package="base.core"`、不传该参数（`:157-162` 注释明确「插件路由由 plugin_manager 在 startup 时注册」）。**该函数在启动链路中从未执行。**
- 真正生效的是 `base/common/plugin_manager.py:198-206` `get_enabled_plugins_from_manifests()` 的 `is_installed && is_enabled` 判定，以及 `:778-851` 的 `load_enabled_plugins()`。

### 1.2 装配不是「唯一输入」

- 声明路径：`plugin_manager.py:106` 读 `manifest.routes`、`:111` 读 `route_prefix`、`:127` 扫描 `api/v1/*.py`、`:144-147` 按 `{stem}_router` 拼属性名、`:357` 合并 router。
- 覆盖路径：`plugin_manager.py:75` `self.router = getattr(module, 'router', None) or router` —— 插件 `__init__.py` 只要导出 `router`，**manifest 的 `routes` 声明被整段跳过**（`:79` 条件不成立）。实例：`base/plugins/agent/__init__.py:7,22-38,44` 用代码装配 18 个子路由并在 `on_enable` 里再次 `app.include_router(router)`。
- 旁路路径：`base/start.py:638` `register_routers(app)` 之后，`:640-690` 手动注册 5 组路由。

| `start.py` 位置 | 内容 | 启用门控 |
|---|---|---|
| `:642-643` | `from base.plugins.llm.api.v1 import voice_websocket` → `include_router(..., prefix="/v1/llm")` | ❌ 无（仅 `except ImportError` 打印） |
| `:650-651` | `from base.plugins.mail.api.v1.ws_router import ws_router` → `include_router(..., prefix="/v1/mail")` | ❌ 无 |
| `:658-659` | `base.common.events.api.events_api_router` | 公共层，不适用 |
| `:684-687` | harness `app_internal` 的 `app_quota_router` / `app_touch_router` | ✅ `:682-683` 判 manifest 双真 |
| `:698-704` | 网关子应用 mount | 配置开关，非插件启用态 |

`llm` / `mail` 两条 WebSocket 路由即使在 manifest 里停用仍会挂载；且它们位于声明目录 `api/v1` 内、又导出 `{stem}_router`，被 `_load_routes_from_manifest` 扫到一次、被 `start.py` 再挂一次，存在重复注册。`harness` 的 `app_internal` 目录不在 `manifest.routes`（仅 `api/v1`）内，属声明集合之外的注册项 → 直接违反 AC-PLR-01-2「实际注册项与声明集合完全一致，无多无少」。

### 1.3 启停语义：一次性注册，禁用不卸载

- 注册：`start.py:79` → `plugin_manager.py:849` → `:578` `self._app.include_router(plugin.router)`，进程内路由表一次性构建。
- 禁用：`plugin_manager.py:629-657` 只做 `on_disable()`、`:652` `_cleanup_plugin_menus()`、`:654` 写 manifest 状态；**无 `remove_api_route` / 路由重建 / 请求期判定**。运行时禁用后 `/v1/xxx/*` 仍可达；停用通常需重启才真正生效。
- 权限残留：`enable_plugin():571-574` 同时注入菜单与权限，`disable_plugin()` **只清菜单、无 `_cleanup_plugin_permissions`** → AC-PLR-03-2「回到基线、无孤儿记录」不成立。
- 门控口径不一致至少 7 处：`router.py:25`（双真，死代码）、`plugin_manager.py:203`（双真）、`:805`（依赖过滤）、`common/setting.py:48`（双真，无调用点）、`base/core/users/api/v1/common.py:23`（**只判 `is_enabled`**）、`start.py:682-683`（harness 专用）、`harness/services/policy_service.py:21-22`（approval 专用）。
- 状态源双份：`plugin_manager.py:783-791` 合并 manifest 与 DB `PluginModel` 状态；`base/core/extension/services/plugin_service.py:138-171` 只改 DB，`plugins.py:199/241` 另写 manifest，需人工同步。
- 模型装配不受门控：`base/common/setting.py:80-118` 明写「所有已发现插件（含未安装/未激活）的模型全部加载」，`:107-108` 还有 `harness` 特例。

---

## 2. 事件订阅：24 条 `subscribe()` 全在 Python 里，manifest 无一处声明

### 2.1 声明缺失与死配置

只读统计（`base/plugins/*/manifest.json`，共 **23** 份；启用 8 个：`audit / crm / customer / harness / llm / mail / product / sales`）：

- `events` / `subscribes` / `subscribers` / `listeners` / `consumers` 字段：**0 份声明**；`plugin_manager.py` 读取的字段只有 `routes / route_prefix / menus / permissions / dependencies / is_installed / is_enabled`（`:305/:310/:379/:487/:558/:641/:800/:203`）。
- `hooks` 字段：7 份非空（`approval / audit / crm / customer / llm / mail / thirdparty`）+ 1 份空（harness），内容均为方法名映射；全库 `*.py` 检索 `get("hooks")` / `["hooks"]` **零命中** → 死配置。实际钩子靠 `plugin_manager.py:77-109` 的 `hasattr` 约定方法反射触发。声明与实现还不一致：audit 声明了 4 个 hooks 但 `__init__.py` 无任何钩子；harness hooks 为空却有 `on_startup()`。

### 2.2 订阅关系分布（`.subscribe(` 共 25 处，其中 24 处为订阅注册）

| 文件 | 条数 | 装卸语义 |
|---|---|---|
| `base/start.py:59-61,67-68` | 5 | `register_audit_handlers()` 无条件注册，`:74-77` 静默吞异常；ORM monkey-patch（`orm_event_service.py:156-163`）**无撤销路径** |
| `base/plugins/finance/services/finance_event_handler.py:88-95` | 8 | 由 `finance/__init__.py:27-28` 的 `on_startup` 注册；`on_disable():12-14` 只打日志，**不注销** |
| `base/plugins/mail/services/event_handler.py:170-172` | 3 | **唯一合规样例**：`mail/__init__.py:22-26` 停用注销、`:37-40` 关闭注销，`register_mail_event_handlers():160-165` 幂等防重 |
| `base/plugins/subcontracting/services/event_handlers.py:58-62` | 3 | `on_disable()` 只打日志 |
| `base/plugins/mes/services/event_handlers.py:87-94` | 4 | **无任何调用点**（`mes/__init__.py` 为空文件）→ 死代码 |
| `base/plugins/crm/__init__.py:24` | 1 | 仅 `on_shutdown():28-32` 注销，`on_disable():16-17` 不注销 |
| `base/common/events/event_bus_adapter.py` | 1 | 总线内部转发，非订阅关系 |

后果：finance/crm/subcontracting 停用后 handler 仍常驻 `_handler_registry`，发布时仍被调用（靠各 handler 内 `try/except` + `FINANCE_AVAILABLE` 兜底做无用功）；AC-PLR-14-2「停用全部订阅方后发布方请求仍成功」字面满足，但不是通过「干净摘除订阅」实现的。

### 2.3 契约完整性

| PLR-14 要素 | 现状 |
|---|---|
| 事件名 | 有，但全是业务单据语义：`sales.paid` / `purchase.confirmed` / `model.created` 等，未与业务单据解耦 |
| 载荷结构 | 仅 `**kwargs`（`event_bus.py:21`），无 schema；业务方直接塞 `order_no/sc_code/total_amount` |
| 幂等键 | `event_bus_adapter.py:71` 每次 `uuid4()` 由发布方生成，业务侧无法指定；`consumer_worker.py:58` 不检查已消费；`event_replay_service.py:38-47` 重放生成新 uuid → **AC-PLR-14-1 不通过** |
| 重试 / 消费确认 | 仅 RabbitMQ 通道有（`consumer_worker.py:80-111`、`max_retries=3`、DLQ、`status=consumed`）；`start.py:113-114` 允许降级为纯内存总线，该通道三者全无 |
| 订阅方不可用不致发布方失败 | ✅ `event_bus.py:29-35` 逐 handler `try/except`；`event_bus_adapter.py:103-113` MQ 失败降级后仍走内存发布 |

### 2.4 后台作业（PLR-15）

`start.py` 内 6 个 `while True` 作业（无 APScheduler / Celery）：

| 作业 | 启动 | 直接引用的插件实现 | 门控 |
|---|---|---|---|
| `cancel_expired_orders_task` | `:144` | `:398` `sales.services.order_service.OrderService` | `:143` `get_plugin("sales")` |
| `update_membership_data_task` | `:152` | `:433` `customer.CustomerMembership`、`:434` `llm.LLMUsageRecord`、`:557` `customer.membership_service.fibonacci_service` | `:151` `get_plugin("customer") and get_plugin("llm")` |
| `gateway_reconcile_task` | `:176` | `:326/:329` `harness.gateway_config` / `reconcile_service` | `:171-175` 三重判定 |
| `audit_cleanup_task` | `:189` | `:356-360` `audit.services.data_change_service` | `:188` `get_plugin("audit")` |
| `quota_reconcile_task` / `quota_hold_cleanup_task` | `:160/:162` | 仅 `base.common.quota`（公共层） | 无（不依赖插件） |

`get_plugin(name)` 实现是 `plugin_manager.py:140-141` `return self._plugins.get(name)` —— **只判断是否加载过，不检查 `enabled`**；`disable_plugin()` 也不从 `_plugins` 移除。门控仅在「启动时 manifest 已禁用 → 未加载」这个快照期有效。作业体每轮直接 import 插件实现并按 ORM 模型查询，插件目录被卸载后 `import` 失败会按 5/10 分钟周期反复报错（被 `except Exception` 吞掉，不冒泡到 lifespan）。这既违反 PLR-15 第一句，也使 AC-PLR-15-2「新增插件无需改平台级作业定义文件」不成立。

---

## 3. 前端页面：菜单是声明式，页面路由是硬编码

### 3.1 合规的一半

`web/src/layouts/MainLayout.vue:20-61` 递归渲染 `menuStore.menuTree`，无写死菜单数组；数据链为 `MainLayout.vue:304-309` → `stores/menu.js:221-240` → `api/rbac.js:68-70` `GET /v1/menus/user-menus` → 后端 `menu_service.get_user_menus()`；后端 `_process_plugin_menus():372-479` / `_process_plugin_permissions():481-533` 确实读 `manifest.menus` / `manifest.permissions` 写入 DB。前端也没有写死的权限码数组。

### 3.2 违规的一半：第二份装配清单

`web/src/router/index.js:6-324` 是一个静态 `routes` 数组，`:326-329` 无条件 `createRouter({ routes })`。只读统计：**73 条静态 `path`，其中 41 条指向当前 `is_installed=false / is_enabled=false` 或根本无 manifest 的插件页面**（`agent`、`finance`、`inventory`、`thirdparty`、`joke/agent-debug`，行号 171-197、199-314）。典型：

- `:198-223` finance 4 页（`/panel/finance/account`、`journal`、`report`）
- `:224-314` inventory 约 16 页
- `:178-196` agent 约 18 页
- `:170-173` thirdparty 3 页；`:197` 孤儿页 `joke/agent-debug`

同时存在的动态路由 `router/index.js:381-422`（`fetchUserMenus()` → `generateRoutes()` → `addRoute('panel', route)`）只是静态表之外的增量补丁；`generateRoutes` 用中文 `menu.name` 作 `route.name`（`stores/menu.js:269`），静态表用英文名（`FinanceAccount`），`hasRoute(route.name)` 判重失效 → 同 path 重复注册，静态记录优先命中。对照更直观：`audit / crm / mail` 等**已启用**插件的页面在静态表里没有、靠动态注入；`agent / finance / inventory` 等**已禁用**插件的页面反而被写死。

### 3.3 门控与可见性

- 前端仅 4 处 `isPluginEnabled()`：`MainLayout.vue:93`（mail 铃铛）、`GlobalApproval.vue:132,163`、`MailBell.vue:212`；`router/index.js` **全文无启用态判断**，路由守卫（`:331`、`:426-438`）只校验登录态与 `meta.public`。
- `base/core/users/services/menu_service.py:140-194` 下发菜单只按 `is_active / is_visible` + 权限过滤，**不按插件启用态过滤**；隔离完全依赖启用/禁用时增删 DB 记录的副作用。
- 后端 `common.py:23` 只判 `is_enabled` 与 `plugin_manager.py:203` 双真口径不一致，前端 `/system-config` 拿到的启用列表因此可能偏大。
- `MainLayout.vue:113,123` 无条件挂载 `GlobalApproval` / `ApprovalPrompt` 两个订阅组件；`ApprovalPrompt.vue:61-67` 硬编码业务路径映射、`MailBell.vue:127` 硬编码 `/api/v1/mail/ws` 端点。
- 实证风险：直接输入 `/panel/finance/account` 仍会命中静态路由并渲染 `web/src/views/finance/account/Index.vue`（后端 API 才 404）→ 与 PLR-09「不得依赖前端隐藏实现隔离」相冲突。
- `dshw/` 是 vendored 的 DeepSeek Harness 独立仓库，与 `base/plugins` / `web` 无引用关系，不含本平台的硬编码清单，已排除。

---

## 4. 硬编码清单（回答评审反馈）

| 类别 | 位置 | 硬编码内容 | 是否绕过门控 |
|---|---|---|---|
| 后端路由 | `base/start.py:642-643,650-651` | llm / mail WebSocket 路由 + 前缀字符串 | ✅ 无门控 |
| 后端路由 | `base/start.py:684-687` | harness 内部路由（不在 manifest.routes 内） | 部分（有专用判定） |
| 后端路由 | `base/plugins/agent/__init__.py:7,22-38,44` | 18 条子路由 + 自行 `include_router` | 覆盖声明 |
| 订阅 | `base/start.py:41-77` | 5 条订阅 + 4 个插件实现 import + ORM 全局 patch | ✅ 无条件 |
| 订阅 | `finance/__init__.py:35-44`、`finance/services/finance_event_handler.py:88-95` | 8 条事件→科目映射 + 8 条 subscribe | 停用不注销 |
| 订阅 | `mail/services/mapping_service.py:13-51` | 5 条业务表→消息映射 | — |
| 订阅 | `mes/services/event_handlers.py:87-94` | 4 条 subscribe（死代码） | — |
| 前端页面 | `web/src/router/index.js:6-324` | 73 条静态路由，41 条属禁用/无 manifest 插件 | ✅ 完全不受门控 |
| 插件名特例 | `start.py:143/151/172/188/682`、`core/users/api/v1/menu.py:112`、`common/setting.py:107-108`、`harness/services/policy_service.py:21` | `get_plugin("sales")` 等字面量、audit 专用同步端点、harness 特例 | 门控分散 |

**未发现**（避免误判）：不存在 `enabled_plugins = [...]`、`PLUGIN_LIST`、`MENU_TABLE`、`PERMISSION_CODES` 这类 Python 常量形式的插件清单/菜单表/权限码表；菜单与权限码确实只在 manifest 中；前端也没有写死的权限码数组。`base/common/constant.py:128-175` 的 `INVALID_PERMISSION_*` 是错误码枚举，不是权限表。

---

## 5. 风险分级与整改方向（仅建议，本次未改代码）

| 级别 | 问题 | 建议方向 |
|---|---|---|
| Blocker | 禁用插件后路由仍可达、权限残留（AC-PLR-03-1/2） | 门控收敛到单一判定函数；`disable_plugin` 补齐权限清理与路由卸载/重建，或改为请求期统一门控依赖 |
| Blocker | `start.py` 模块级 import 插件实现、19 行插件引用（AC-PLR-13-1 = 0） | 把 WS/内部路由、审计订阅、定时任务改为 manifest 声明 + 服务/事件注册接口；保留 `mail` 装卸幂等做法作模板 |
| Major | 前端静态路由表并行于 manifest，禁用插件页面可直接访问 | 删除或收敛静态路由，以 `/v1/menus/user-menus` 为唯一前端路由来源；服务端下发时按启用态过滤 |
| Major | 订阅关系无声明、`hooks` 死配置、停用不注销 | 在 manifest 增加 `events/subscribes` 声明并由 `plugin_manager` 统一注册/注销；清理 `mes` 死代码 |
| Major | 定时任务直接引用插件模型、`get_plugin` 不检查 enabled | 作业改为注册表动态装载或订阅平台事件；门控改查 `plugin.enabled` |
| Minor | 幂等键每次生成、内存总线无确认/重试（AC-PLR-14-1） | 允许业务侧传入幂等键，消费端按 `event_uuid` 去重 |
| Minor | `router.py:25` 死门控、`setting.py:48` 重复实现、状态源双份 | 删除或合并重复判定，统一 manifest/DB 状态写入点 |

**排期约束**：v3.0 §7 明确「现有插件以声明文件 + 插件管理器装配；核心层与启动入口目前仍存在对插件实现的直接引用，需按 PLR-13 改造」——本次检查是把该「架构约束提示」变成逐条实证与量化，并发现基线未记载的新事实（死门控、前端静态路由、hooks 死声明、订阅残留、权限不清理）。整改涉及启停与路由注册，**不得在 14 天灰度观察期（起算 2026-11-09 13:33:40，最早 2026-11-23 收口）内实施**，不重置计时、不提前勾选 T7.5 准入、不删旧编排代码或 `mode` 开关。

---

## 6. 未验证项与复算方式

- 本报告为**静态核查**：未启动服务，未实跑「四种状态组合路由可达性」「启停压测」「逐个关闭插件后作业执行」等动态用例，AC-PLR-03-1、AC-PLR-15-1、AC-PLR-23-1/3 的运行时结论为代码路径推断，需按 AC 另做实测。
- 可复算数字：23 份 manifest / 8 个启用 / 0 份事件声明 / 7 份非空 hooks 且零消费；25 处 `.subscribe(`（24 处订阅注册 + 1 处总线内部转发）；`base/start.py` 19 行引用 `base.plugins.*`（行号 `15,26,44,45,46,47,170,326,329,356,398,433,434,557,642,650,684,685,698`）；前端 73 条静态 `path`、其中 41 条属于禁用/无 manifest 插件页面。
- 计数差异说明：历史记录中的「24 个插件」与本次 23 份 `manifest.json` 不一致，可能有一目录无声明文件；不影响结论。
- 若 PB-01 最终签字采用「平台 = 产品整体」的宽松定义，需重评的是判定层级（哪些算平台级违规），不是上述事实本身。

---

## 附录：主要证据索引

| 主题 | 文件:行号 |
|---|---|
| 死门控 / 自动发现 | `base/common/router.py:14-27,30-35,75-78,157-162` |
| 生效门控 / 装配顺序 | `base/common/plugin_manager.py:198-206,245-291,778-851,848-849` |
| manifest 路由加载与覆盖 | `base/common/plugin_manager.py:75-79,106-147,305-357` |
| 启用 / 禁用 / 路由注册 | `base/common/plugin_manager.py:535-585,591-627,629-661` |
| 菜单与权限注入 | `base/common/plugin_manager.py:372-479,481-533` |
| 启动入口硬引用 | `base/start.py:15,26-31,41-77,105,143-189,271-589,638-704` |
| 事件总线契约 | `base/common/events/event_bus.py:7,21-43`；`event_bus_adapter.py:70-113,131-144`；`consumer_worker.py:37-111` |
| 订阅注册 | `start.py:59-68`；`finance/services/finance_event_handler.py:87-95`；`crm/__init__.py:24`；`mail/services/event_handler.py:160-187`；`subcontracting/services/event_handlers.py:58-62`；`mes/services/event_handlers.py:87-94` |
| 前端静态 / 动态路由 | `web/src/router/index.js:6-324,326-329,381-422`；`web/src/stores/menu.js:160-191,221-310` |
| 前端门控 | `web/src/stores/system.js:13,32,46-48`；`web/src/layouts/MainLayout.vue:93,113,123,304-309` |
| 后端菜单下发 / 特例 | `base/core/users/services/menu_service.py:140-194`；`base/core/users/api/v1/common.py:8-27`；`base/core/users/api/v1/menu.py:102-123` |
