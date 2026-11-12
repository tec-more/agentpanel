# AgentPanel 路径契约与装配硬编码：诊断与整改方案

| 项 | 内容 |
|---|---|
| 文档类型 | 诊断 + 整改方案 + **主体已实施 + 动态回归已通过（24/24，2026-11-12）** |
| 日期 / 版本 | 2026-11-12 / v1.1 |
| 判据 | `AgentPanel-平台级需求规格-v3.0-2026-11-12.md`：PLR-01/02/03/04/09/13/14/15/16/20/21/23 及各条 AC；配套 v3.0 评审报告 |
| 前置材料 | ① `reports/prd/AgentPanel-平台级基线-路由与事件订阅符合性检查-2026-11-12.md`（后端路由、事件订阅、前端页面硬编码实证）；② 2026-11-12 路径契约诊断（`/api` 包装器与安装新插件 404，此前仅对话结论，本文首次落文档） |
| 范围 | `base/app_wrapper.py`、`base/start.py`、`base/common/{router,plugin_manager,setting,events}/*`、`base/cli/command.py`、`base/plugins/*/manifest.json` 与插件入口、`base/core/{extension,users}/*`、`web/src/{router,stores,api,utils,layouts}/*`、`web/vite.config.js`、`deploy/nginx/conf.d/agentpanel.conf` |
| 方法 | 静态代码核查 + 只读统计脚本；**另有动态回归 `tests/regression_plugin_assembly.py` 启动真实 app 实测，24/24 通过（2026-11-12）**；整改代码已落盘 |
| 状态前提 | v3.0 严格平台级定义（J1/J2/J3）仍是评审报告 PB-01「待书面签字」。若最终改按方案 A（平台 = 产品整体），需重评的是「判定层级」，本文事实与整改动作不变 |
| 排期约束 | 原「观察期内不实施运行时改造」的约束由产品负责人于 2026-11-12 18:04 明确授权解除（选择「允许完整改造」）；灰度观察期计时、T7.5 准入、旧编排代码与 `mode` 开关仍按原约定保留，不重置、不提前勾选 |

---

## 0. 实施状态（v1.1 追加，2026-11-12 晚）

用户指令：「首先处理路由一致性问题，然后处理在 base/core 中开发一个事件订阅、发布模块，约定订阅和发布规则，并在后台可以管理事件订阅和发布」，并确认「允许完整改造」+「管理后台页面 + 后端 API」。以下为实际落地内容，**静态核查 + 语法检查通过，并已启动真实 app 做运行时回归（`tests/regression_plugin_assembly.py`，24/24 通过，2026-11-12）**。

### 0.1 路由一致性（W0 / W1 / 部分 W2）

| 动作 | 落地文件 |
|---|---|
| 单一路径契约与 manifest 校验（必填字段、`/v1/` 前缀、禁止 `/api`、目录存在、事件名格式） | 新增 `base/common/plugin_contract.py` |
| 全平台唯一启停门控（双真 + mtime 缓存 + 失效） | 新增 `base/common/plugin_gate.py`；`router.py` / `setting.py` / `core/users/api/v1/common.py` / `plugin_manager.py` 全部委托 |
| 装配器按声明校验、零路由拒绝、内部路由声明化、`enable/disable` 对称（菜单+权限+订阅+路由）、钩子 `None` 不再误判失败 | `base/common/plugin_manager.py` |
| CLI 模板与官方示例修正（`route_prefix`、`routes` 目录、`{name}_router.py`、无 `/api` 前缀、带 `events`） | `base/cli/command.py:60-103`、`plugin_manager.py` 模块文档 |
| 存量插件对齐 | `base/plugins/alipay/api/v1/alipay.py`（`alipay_router` + 去掉 `/api`）、`alipay/manifest.json`（`/v1/pay/alipay`）、`harness/manifest.json`（`internal_routes`） |
| 启动入口去硬编码 | `base/start.py`：删除 llm/mail WS 与 harness 内部路由的手动注册；定时作业门控改 `get_active_plugin()`；挂载 `/uploads` 静态目录 |
| 包装器路径契约 | `base/app_wrapper.py`：抽出 `apply_api_prefix()` 供 HTTP/WS 共用、静态白名单统一、SPA 页面白名单、未知路径返回 404 JSON |
| 前端约定 | 新增 `web/src/utils/apiBase.js`（唯一 `/api` 来源）；`request.js` 改引用；`router/index.js` 加插件页面启用态门控与安装检查 URL 配置化；`stores/menu.js` 用稳定 path 生成 `route.name`；清理 `MailBell.vue` / `agent.js` / `dialog-flows/edit.vue` / `joke/*` 的 `/api/v1` 硬编码；`upload.py` 补 `POST /v1/upload/audio`，agent 音频目录与 URL 统一到 `/uploads/audio/` |

### 0.2 base/core 事件订阅与发布模块（新增 W2 / 部分 W3）

| 组成 | 文件 | 说明 |
|---|---|---|
| 规则契约 | `base/core/events/contract.py` | 事件名格式、载荷 JSON/体积/禁凭据字段、幂等键、至少一次投递、订阅方失败隔离、声明来源；`GET /rules` 可查 |
| 订阅持久化 | `base/core/events/models/event_subscription.py` | 表 `event_subscriptions`，`declared` / `manual` 两类，由 `setting.get_model_list()` 自动登记 |
| 注册表 | `base/core/events/registry.py` | `initialize()` / `sync_plugin()` / `bind_manual()` / `set_enabled()` / `publish()`；`handler_ref` 动态解析，core 不静态导入插件实现 |
| 管理服务 | `base/core/events/service.py` | 订阅 CRUD、发布记录查询、重放、统计 |
| REST | `base/core/events/api/v1/event_center.py` | `/v1/event-center/*`：rules / subscriptions / publish / records / replay / stats / sync，全部管理员鉴权，由 `register_routers` 自动发现 |
| 启动接入 | `base/start.py` | `initialize_event_center()` 在 `init_data()` 后按 manifest 声明初始化，替代硬编码的 5 条审计订阅 |
| 插件声明 | `audit / mail / finance / crm / subcontracting` 的 `manifest.json` | `events.register_ref` / `unregister_ref` / `subscribe` 共 20 条声明；配套 `audit_subscriptions.py`、`finance_event_handler` 幂等注册/注销、`crm`/`subcontracting` 的 `__init__.py` 装卸函数 |
| 后台页面 | `web/src/api/eventCenter.js`、`web/src/views/events/Index.vue` | 订阅管理 / 手动发布 / 发布记录与重放 / 规则说明 + 统计 |
| 菜单权限 | `migrations/core_seed_data_event_center_menus_1794478446.sql` | 幂等写入「事件中心」目录与「订阅与发布」菜单、`events:admin:view` / `events:admin:manage` 权限 |

**关键行为变化**：插件订阅不再依赖只在进程启动时执行的 `on_startup`；`enable_plugin` 即调用事件中心注册、`disable_plugin` 即注销，运行时启停即时生效，且停用不再残留 handler。

### 0.3 校验结果与未完成项

静态校验通过：`py_compile` 全部改动 Python 文件、`node --check` 前端 JS、23 份 manifest 契约（8 个启用插件零问题）、8 个启用插件路由装配模拟（均非零路由，harness 内部路由 2 条）、`events.*_ref` 模块路径全部存在、菜单 `component` 对应 Vue 文件存在、`APIRouter` 前缀含 `/api` 残留 0、前端 `/api/v1` 硬编码残留 0。

**未完成 / 待回归**：
- 幂等键目前是事件中心内存 300 秒去重，RabbitMQ 消费端的业务幂等与 `EventRecord` 按业务键去重仍待 W3-1；
- 未启动服务，四状态路由可达性、逐个关闭插件、启停压测等动态用例（AC-PLR-23-1/23-3）未跑；`RUN_DB_MIGRATIONS=false` 部署下需先建 `event_subscriptions` 表；
- 工作区外 `aipanel.conf` 第二层 `/api` rewrite 已于 2026-11-12 核实：**无**（透明 `location /` 反代），本条划除；
- `agent` 插件 `__init__.py` 仍自行导出 `router` 并在 `on_enable` 里 `include_router`（当前禁用，装配器会记录一致性偏差警告），属后续清理项。前端纯动态路由、base/common 插件模型解耦、audit 专用端点、harness 模型特例均已落地（见 §0.4）。

### 0.4 后续清理项落地（2026-11-12 晚，用户追加指令）

用户追加指令：前端纯动态路由、base/common 插件模型耦合改造、audit 专用菜单端点与 harness 模型特例改造。均已实施并通过 `py_compile` / `node --check`：

| 项 | 动作 | 文件 |
|---|---|---|
| 前端纯动态路由 | 删除 `router/index.js` 中 panel 下除 `profile` 外的全部静态子路由（核心页与插件页均改由菜单接口动态下发）；保留框架路由与插件启用态门控；`profile` 因不在菜单库且 `MainLayout.vue:290` 直链而保留 | `web/src/router/index.js` |
| base/common 插件符号解耦 | 新增运行时符号解析器，所有 `base/common` 对插件模型/异常的直接 import 改为经解析器（插件缺失时抛 `PluginSymbolUnavailable` 降级）；仅 `usage_tracker` 的模型类型标注保留在 `TYPE_CHECKING` 块内 | 新增 `base/common/plugin_symbol.py`；改 `usage_tracker.py` / `authz/service.py` / `authz/audit.py` / `logging_config.py` / `quota/api/usage.py` / `quota/services/org_quota_service.py` / `quota/services/org_scope.py` |
| audit 专用端点改造 | `POST /v1/menus/sync-audit-menu` 专用端点改为通用 `POST /v1/menus/sync-plugin/{plugin_name}`；前端未被调用的 `syncAuditMenu()` 一并删除 | `base/core/users/api/v1/menu.py`、`web/src/api/audit.js` |
| harness 模型特例 | harness manifest `models` 置空（其模型由共享包 `packages.common.models.*` 注册，插件目录为再导出），删除 `setting.py` 中 `if plugin_name=="harness": continue` 硬编码 | `base/plugins/harness/manifest.json`、`base/common/setting.py` |

注：`base/common` 内残留的 `from base.core.users...` 为底座自引用（core 属平台而非插件），不在「插件模型零侵入」范围内，未动。

---

## 1. 结论：不是若干个 404，而是「装配契约没有单一来源」

四类现象看似分散，实为同一个缺陷的四个面：

| 现象 | 表面归因 | 实际归属 |
|---|---|---|
| 安装/启用新插件后 API 404、页面 404 | 前后端路径没约定好 | 路径契约分散在 5 处，且官方模板与运行态规则**相反**；菜单/权限运行时入库、路由装配期加载，二者不同步 |
| 部分插件路由绕过启用开关 | 路由注册遗漏 | `start.py` 手动 `include_router`、插件 `__init__.py` 自行注册，manifest 不是唯一输入 |
| 事件订阅停用后仍被调用、hooks 改了没反应 | 订阅代码写得散 | 24 条 `subscribe()` 全在 Python 里，manifest 无事件声明、`hooks` 是死配置，装卸不对称 |
| 前端能打开已禁用插件的页面 | 前端没做权限 | `router/index.js` 静态路由表是第二份装配清单，守卫不判启用态 |

**总判定（静态核查）**：PLR-01/03/13/15/23 不通过，PLR-02/14 部分通过，PLR-04/09/16/20/21 存在连带违规。系统能启动运行，靠的是 `try/except` 兜底与启动时一次性装配，不是契约成立。

---

## 2. 判据与验收目标

| 判据 | 约束要点 | 对应 AC |
|---|---|---|
| PLR-01 | 单一声明文件是装配唯一输入；不得散落代码补充；声明非法应拒绝且可定位 | AC-PLR-01-1 / 01-2 |
| PLR-03 | 仅「已安装且已启用」挂路由；启用注入菜单+权限，禁用清理且无残留；门控集中一处 | AC-PLR-03-1 / 03-2 |
| PLR-13 | 核心层与启动入口不得导入插件实现；跨插件调用只能经服务注册或事件；禁止「尝试导入+可用性标志」兜底 | AC-PLR-13-1 / 13-2 |
| PLR-14 | 事件含事件名/载荷/幂等键/重试/消费确认；订阅方不可用不致发布方失败；契约与业务单据语义解耦 | AC-PLR-14-1 / 14-2 |
| PLR-15 | 定时任务与后台作业不得直接引用插件实现；按注册表动态装载或订阅事件；禁用插件后作业不抛异常 | AC-PLR-15-1 / 15-2 |
| PLR-23 | 禁用非底层插件后启动/路由/作业均不报错；新增模块平台层改动文件数 = 0 | AC-PLR-23-1 / 23-2 / 23-3 |
| 次级 | PLR-04 钩子时序与失败回滚、PLR-09 不依赖前端隐藏做隔离、PLR-16 配置/开关单一读取点、PLR-20 两层需求、PLR-21 四类平台审计事件 | 连带验收 |

> 按 PLR-03 明文，「未启用导致菜单不显示」是按需装配的设计特性，**本文不将其列为缺陷**；被判为缺陷的是声明集合之外、绕过门控的路由/订阅/页面。

---

## 3. 现状诊断

### 3.1 路径契约：主链路自洽，旁路全靠约定

**自洽的主链路**（唯一正确的写法）：

```
浏览器 request.js:6,12  baseURL='/api' + api/*.js 的 '/v1/...'
  → GET /api/v1/foo/list
  → vite.config.js:34-38 仅代理 /api、无 rewrite（生产 agentpanel.conf:30-31 location / 全量透传、无 rewrite）
  → app_wrapper.py:117-123 剥离 /api，scope["path"]='/v1/foo/list'，root_path='/api'
  → FastAPI 路由表：manifest route_prefix='/v1/foo' + 路由文件内路径
```

23 份内置 manifest 的 `route_prefix` 全部以 `/v1/` 开头（`logs/host-l2.out.log:108-152` 实证），故主链路无分歧。**唯一的 `/api` 处理点是 `app_wrapper.py`，不存在第二层 rewrite。**

**并行的 5 套约定与断点**：

| # | 断点 | 证据 | 后果 |
|---|---|---|---|
| P1 | 官方示例把 `route_prefix` 写成 `/api/v1/customer` 并给出拼接公式 | `base/common/plugin_manager.py:19,29,34,300` | 与运行态剥离规则相反；插件若照抄，FastAPI 内是 `/api/v1/...`，请求却是 `/v1/...` → 404 JSON |
| P2 | CLI 模板四处装配信息不匹配 | `base/cli/command.py:60-103`：manifest 无 `route_prefix`；`routes=["api/v1/{name}"]` 指向**文件**而非目录（`plugin_manager.py:319-321` 判不存在即 skip）；示例导出 `router` 而加载器要求 `{stem}_router`（`:343-346`）；`:85` `APIRouter(prefix="/api/v1/{name}")` | `loaded_count=0` → `:365-370` 返回 `None` → 插件**零路由** |
| P3 | 启用接口静默成功 | `plugin_manager.py:570-574` 先注入菜单/权限，`:576-579` `if plugin.router:` 才注册，`:582-585` 仍写状态并返回 True；`base/core/extension/api/v1/plugins.py:177-204` install 只写 `is_installed=true/is_enabled=false`，不加载路由 | 菜单已下发、页面入口出现，但 API 404；**启用返回 200** |
| P4 | 包装器 SPA 回退吞掉裸路径 | `app_wrapper.py:134-169`：凡非 `/api`、非 `/v1/` 一律 `FileResponse(web/dist/index.html)`；特例仅 `/docs|openapi|redoc|static|metrics|health`（`:67-74`）、`/internal/`（`:77-79`）、`/v1/gateway`（`:58`）、`/api/v1/install`（`:82`）、`/api/v1/common`（`:93`）；WS 分支 `:29-43` 只剥 `/api`、无兜底 | `/files/*`、`/uploads/*`、裸 `/foo/list` 返回 **200 HTML 冒充接口**；插件 WS 写成裸路径直接 404 |
| P5 | 前端硬编码全路径与隐式组件映射 | 按只读统计约 12 条 `/api/v1/...` URL 字面量绕过 `request`，分布于 `MailBell.vue:127,130`、`router/index.js:351`、`agent.js:247`、`dialog-flows/edit.vue:863,876,898,1228,1249,1312`；其中 `POST /api/v1/upload/audio` 后端只有带日期的 GET（`base/core/users/api/v1/upload.py:46,105,134`）；`config.conf:39,40,53,57` 支付回调同样写死 | 换部署前缀即全挂；音频上传必然 404 |

**菜单/页面侧的隐式约定**：151 条 `menus[].path` 中 145 条为裸路径（`/crm`、`/finance/account`），仅 `subcontracting` 6 条带 `/panel`，靠 `web/src/stores/menu.js:253-262` 归一化兜住；`component` 字符串经 `import.meta.glob('@/views/**/*.vue')`（`:160-191`）映射前端**构建产物**，找不到就降级 `NotFound.vue`。按 `loadComponent` 的四种主要匹配模式静态核对：`customer/list/index`、`agent/index` 未找到对应 `.vue`；另有 14 条菜单完全没有 `component`（含 subcontracting 全部 6 条）。**只装后端、前端未发版 → 页面 404（HTTP 仍 200）**。

历史实证：`reports/ops/l3-split-full-flow-recheck-2026-11-09.md:104-105,167` F1/F2（8080 指向 legacy 容器 → `/api/v1/harness/...` 404，改 upstream 后变 401；`web/dist` 未随镜像更新 → `/panel` 200 但旧页面）；`reports/architecture/as-built-architecture-2026-11-09.md:227` 旧图 `/v1/gateway/chat/completions` 按旧图调用 404。

### 3.2 后端路由硬编码（详见符合性检查报告 §1）

- `base/start.py` 共 **19 行**引用 `base.plugins.*`（`15,26,44-47,170,326,329,356,398,433,434,557,642,650,684,685,698`），其中 `:26/:28` 是模块级 import 并立即执行 `configure_shared_runtime()`。
- 手动注册 5 组（`:640-690`）：`:642-643` llm voice WS、`:650-651` mail WS **无任何启用门控**（仅 `except ImportError` 打印），且二者位于声明目录 `api/v1` 内，会被 `_load_routes_from_manifest` 再扫一次 → 重复注册；`:684-687` harness `app_internal` 路由不在 `manifest.routes`（仅 `api/v1`）内；`:698-704` 网关 mount 由配置而非装配状态决定。
- `plugin_manager.py:75` `getattr(module,'router',None) or router` 允许插件 `__init__.py` 覆盖 manifest 声明；实例 `base/plugins/agent/__init__.py:7,22-38,44` 自装配 18 条子路由并在 `on_enable` 里二次 `app.include_router`。
- **门控不是 `router.py:25`**：`_is_plugin_enabled()` 依赖的 `check_plugin_status` 默认 False，唯一调用 `auto_discover_routers` 在 `router.py:159` 只扫 `base.core`，该函数在启动链路从未执行。真正生效的是 `plugin_manager.py:198-206`。至少 **7 处**独立判定，口径不一致（`common.py:23` 只判 `is_enabled`，`plugin_manager.py:203` 判双真，`setting.py:48` 重复实现无调用点，`harness/policy_service.py:21-22` approval 专用）。
- 路由在 lifespan 一次性注册（`plugin_manager.py:578`）；`disable_plugin():629-657` **不卸路由、不清权限**（只 `_cleanup_plugin_menus`），运行时禁用后仍可达、通常需重启；状态源双份（`:783-791` 合并 manifest 与 DB，`plugin_service.py:138-171` 只改 DB）；`setting.py:80-118` 明写「所有已发现插件（含未安装/未激活）的模型全部加载」。
- 存量特例：`base/plugins/alipay/api/v1/alipay.py:5` 自带 `/api/v1/pay/alipay` 前缀且导出 `router` 而非 `alipay_router` → 该插件路由从未注册；`base/core/users/api/v1/menu.py:112` `get_manifest("audit")` 专用同步端点；`setting.py:107-108` harness 特例。

### 3.3 事件订阅硬编码（详见符合性检查报告 §2）

- 23 份 manifest **0 份**声明 `events/subscribes/subscribers/listeners/consumers`；7 份 `hooks` 非空（+1 份空）但全库 `*.py` 零消费，实际钩子靠 `plugin_manager.py:77-109` 的 `hasattr` 约定方法反射。
- **25 处 `.subscribe(`**（24 条订阅关系 + 1 处总线内部转发）：`start.py:59-61,67-68`（5 条，审计，无条件注册、ORM monkey-patch 无撤销）、`finance/services/finance_event_handler.py:88-95`（8 条）、`mail/services/event_handler.py:170-172`（3 条）、`subcontracting/services/event_handlers.py:58-62`（3 条）、`mes/services/event_handlers.py:87-94`（4 条**无人调用的死代码**）、`crm/__init__.py:24`（1 条）。
- 装卸不对称：**只有 mail** 做到 `on_disable` 注销、`on_shutdown` 注销、注册幂等（`mail/__init__.py:22-40`、`event_handler.py:160-187`），可作模板；finance/crm/subcontracting 的 `on_disable()` 只打日志，停用后 handler 常驻 `_handler_registry` 继续被空调用。
- 契约缺口：`event_bus.py:21` 载荷仅 `**kwargs` 无 schema；`event_bus_adapter.py:71` 幂等键每次 `uuid4()`、业务侧无法指定，`consumer_worker.py:58` 不检查已消费，`event_replay_service.py:38-47` 重放生成新 uuid → AC-PLR-14-1 不成立；重试/确认仅 RabbitMQ 通道有，`start.py:113-114` 允许降级为纯内存总线（三者全无）。唯一达标的是「订阅方异常不冒泡到发布方」（`event_bus.py:29-35`）。
- 6 个定时作业中 4 个直接 import 插件实现：`sales`（`:398`）、`customer + llm`（`:433-434,557`）、`harness`（`:326,329`）、`audit`（`:356-360`）；门控 `get_plugin()`（`plugin_manager.py:140-141`）**只查是否加载过、不查 enabled**，且 `disable_plugin()` 不移除实例。「不抛异常」靠每轮 `except Exception` 吞掉，插件卸载后按 5/10 分钟周期反复空转报错。

### 3.4 前端页面硬编码（详见符合性检查报告 §3）

- `web/src/router/index.js:6-324` 静态 **73 条 `path`**，`:326-329` 无条件注册；其中 **41 条**指向当前 `is_installed=false/is_enabled=false` 或无 manifest 的插件页面（agent / finance / inventory / thirdparty / joke，行号 171-197、199-314）。
- 动态路由（`:381-422`）只是增量补丁；`stores/menu.js:269` 用中文 `menu.name` 作 `route.name`，静态表用英文名，`router.hasRoute()` 判重失效 → 同 path 重复注册，静态记录优先命中。
- 前端仅 4 处 `isPluginEnabled()`（`MainLayout.vue:93`、`GlobalApproval.vue:132,163`、`MailBell.vue:212`），路由层与守卫完全不判启用态；`MainLayout.vue:113,123` 无条件挂载两个全局订阅组件。
- 后端 `menu_service.py:140-194` 下发菜单只按 `is_active/is_visible` + 权限过滤，不按插件启用态；隔离依赖启停时增删 DB 记录的副作用。
- 实证：直接输入 `/panel/finance/account` 仍渲染 `views/finance/account/Index.vue`，只有后端 API 404 → 与 PLR-09 冲突。
- `dshw/` 是 vendored DeepSeek Harness 独立仓库，与本平台装配无关，已排除。

### 3.5 根因归纳

| 根因 | 表现 |
|---|---|
| **R1 契约多源且互相矛盾** | `/api` 前缀在前端 baseURL、包装器剥离规则、manifest `route_prefix`、官方示例/CLI 模板、部署反代各写一份；官方模板与运行态规则相反 |
| **R2 装配时机错配** | 菜单/权限运行时写 DB 立即生效；路由/订阅在进程启动或装配期由代码加载；前端组件是构建期产物。三者无一致性校验 |
| **R3 门控分散 + 双状态源** | 7 处判定、manifest 与 DB 两套状态、模型加载不受启用态约束、禁用不卸载 |
| **R4 失败静默** | 零路由仍返回启用成功；订阅注册失败、作业异常、组件缺失一律 `except`/降级为 NotFound，问题以 404 形式在前端暴露 |

---

## 4. 整改方案

**总原则**：把「插件能提供什么」全部收进 manifest，把「平台如何装配」收进单一装配器与单一门控；前端只消费后端下发的清单；任何声明与实装不一致都**拒绝装配并给出可定位错误**，而不是静默降级。

### W0 — 契约定义与模板修正（文档/模板级，不改变运行时行为）

| 动作 | 目标文件 | 验收 |
|---|---|---|
| W0-1 定义 manifest schema v2 | 契约说明（本文 §4 总原则与 W0 表即规范草案，不另建运行时文件） | 明确必填 `name/version/route_prefix/routes/menus/permissions`，可选 `websockets/internal_routes/events.publish/events.subscribe/hooks/jobs/component`；规定 `route_prefix` 必须以 `/v1/` 开头，**禁止路由代码内再写 `/api`** |
| W0-2 修正官方示例 | `base/common/plugin_manager.py:14-40,296-300` | 示例与拼接公式改为 `/v1/hello_world`，补充「`/api` 由包装器统一剥离」说明 |
| W0-3 修正 CLI 模板 | `base/cli/command.py:60-103` | 生成 manifest 带 `route_prefix=/v1/{name}`、`routes=["api/v1"]`；示例文件名 `{name}_router.py` 且导出 `{name}_router`；`APIRouter()` 不自带业务前缀 |
| W0-4 统一菜单声明 | 各 `manifest.json`（重点 `subcontracting`） | `menus[].path` 统一裸路径写法；`component` 统一为 `@/views` 下真实存在的相对路径；补齐 14 条无 `component` 的菜单或显式标为目录节点 |
| W0-5 存量插件对齐 | `base/plugins/alipay/api/v1/alipay.py:5` 等 | 前缀与导出变量名按 schema 对齐（仅登记，**运行时改动排观察期后**） |

> W0 虽不改运行时行为，仍建议与 W1 同批评审执行，避免在观察期内产生「已整改」的误判。

### W1 — 单一契约与集中门控（观察期后）

| 动作 | 目标文件 | 对应 AC |
|---|---|---|
| W1-1 声明校验与拒绝装配 | `plugin_manager.py:245-291,305-370` | 缺必填字段/格式非法 → 拒绝并指出字段位置（AC-PLR-01-1）；`loaded_count=0` → `enable_plugin()` 返回 False 并记录插件名与路由目录，不再静默成功 |
| W1-2 注册项一致性校验 | `plugin_manager.py:535-585` | 启用后比对「实装路由/菜单/权限/订阅」与声明集合，多或少均失败（AC-PLR-01-2） |
| W1-3 门控收敛到一处 | 新增统一 `is_active(name)`；删除/合并 `router.py:14-27`（死代码）、`setting.py:48`、`common.py:23`、`start.py:682-683`、`harness/policy_service.py:21-22`、`plugin_manager.py:203/805` | AC-PLR-03-1 |
| W1-4 状态单源 | `plugin_manager.py:783-791`、`plugin_service.py:138-171`、`plugins.py:199/241` | manifest 与 DB 由单一写入点同步；`get_plugin()` 增加 `enabled` 检查；模型加载按启用态过滤（或明确标注为「数据迁移需要」的例外） |
| W1-5 enable/disable 对称 | `plugin_manager.py:629-657` | `disable` 补 `_cleanup_plugin_permissions`、路由卸载或请求期统一门控、订阅注销；启用须「菜单+权限+路由+订阅」全部就绪才返回成功（AC-PLR-03-2、PLR-04） |
| W1-6 组件存在性校验 | `plugin_manager.py:372-479` + 前端构建期清单 | 由 `web/src/views/**/*.vue` 生成组件清单，启用时校验 `component` 命中；缺失则不注入菜单并报错，杜绝「菜单出现即 404」 |
| W1-7 前端路径配置化 | `web/src/utils/request.js:5-14`；12 处硬编码 URL | `baseURL` 由 `/v1/common/system-config` 或构建变量下发；删除硬编码；补 `POST /v1/upload/audio` 或改前端调用已存在的接口 |

### W2 — 去硬编码（观察期后）

| 动作 | 目标文件 | 对应 AC |
|---|---|---|
| W2-1 启动入口去插件实现 | `base/start.py:15,26-31,41-77,640-690` | **已完成（2026-11-12 晚，AC-PLR-13-1 达标）**：① events/quota 公共层路由集中到 `register_routers::_register_common_layer_routers`（删除 init_app 手动注册）；② 全部 `try/except ImportError` 兜底删除（events/quota/health/prometheus/jaeger/网关块，base/common 模块直接导入）；③ 嵌入式网关挂载改经 `get_plugin_manager().get_manifest("harness")` 读 config（不 import 插件实现，enabled 缺省 True / deployment 缺省 standalone 与 DEFAULTS 语义一致）；④ `configure_shared_runtime()` 迁入 harness `on_startup` 钩子。`base/start.py` 顶层与 `init_app`/lifespan 装配层 `base.plugins.<插件>` 导入数=0；剩余 8 处惰性导入均在 5 个定时任务函数体内（属 W2-3 作业注册表范围）。验证：py_compile 通过、events=10/quota=17/health=3 路由确认注册、`regression_pending.py` 20/20（B1 PASS）、`regression_plugin_assembly.py` 24/24（路由总数 481 与改前一致，零回归）。WS 路由（随 manifest.routes 装配）与 harness 内部路由（internal_routes）此前已声明驱动。 |
| W2-2 订阅注册表 | 新增 `base/common/events/registry.py` + `plugin_manager.py` 钩子驱动 | manifest `events.subscribe` → enable 注册 / disable 注销，复用 mail 的幂等模式；`start.py:41-77` 审计订阅改为 audit 插件自身声明；清理 `mes/services/event_handlers.py:87-94` 死代码 |
| W2-3 定时任务注册表 | `base/start.py:271-589` | 6 个作业改为插件 `jobs` 声明 + 平台统一调度，平台层不 import 插件模型；门控查 `enabled`（AC-PLR-15-1/15-2） |
| W2-4 前端路由单一来源 | `web/src/router/index.js:6-324,381-422`、`stores/menu.js:266-286`、`MainLayout.vue:113,123` | 静态表只保留框架路由（`/`、`/panel/login`、`/install`、404）；其余全部动态注入；`route.name` 改用稳定标识（path/id）而非中文名；全局订阅组件按启用态挂载（AC-PLR-09、AC-PLR-23-2） |
| W2-5 包装器分支收窄 | `base/app_wrapper.py:58-101,117-169,29-43` | 抽出单一路径判定函数供 HTTP/WS 共用；SPA fallback 改为已知页面前缀白名单，其余返回 404 JSON；补 `/uploads/`、`/files/` 静态特例；特例清单配置化 |
| W2-6 插件名特例通用化 | `core/users/api/v1/menu.py:102-123`、`common/setting.py:107-108`、各 `PLUGIN_NAME` 常量 | 专用端点改为「按插件名同步菜单」的通用接口（AC-PLR-13-2） |

### W3 — 事件契约、可观测与端到端验收（观察期后）

| 动作 | 目标文件 | 对应 AC |
|---|---|---|
| W3-1 幂等与确认 | `event_bus_adapter.py:70-113`、`consumer_worker.py:44-111`、`event_record_service.py:15` | 允许业务侧传 `idempotency_key`，消费端按事件 uuid/业务键去重；重放不产生重复副作用（AC-PLR-14-1）；内存通道补齐确认语义或明确降级边界 |
| W3-2 事件契约解耦 | `base/common/events/*`、各业务插件 | 定义平台事件元数据（事件名/载荷 schema/幂等键/重试/确认），业务单据字段下沉到插件级；覆盖装配启停、授权拒绝、配置变更、数据关联变更四类审计事件（PLR-14、PLR-21） |
| W3-3 端到端冒烟 | 新增测试用例 | 「新建示例插件 → 安装 → 启用 → 菜单可见 → API 200 → 页面加载 → 订阅生效 → 禁用后菜单/权限/路由/订阅全部清理」；四状态组合、逐个关闭非底层插件、启停压测（AC-PLR-03-1/03-2、15-1、23-1/23-3） |
| W3-4 契约文档落位 | `reports/prd/` 插件级需求起步 | 按 PLR-20 把插件业务规则放插件级文档；消除 v3.0 评审报告 PB-02 的范围真空 |

---

## 5. 验收矩阵

| AC | 要求 | 现状（静态核查） | 整改后判据 | 波次 |
|---|---|---|---|---|
| AC-PLR-01-1 | 声明必填字段缺失即拒绝且可定位 | 无 schema 校验；零路由也返回启用成功 | 拒绝 + 字段位置/插件名 | W1 |
| AC-PLR-01-2 | 实装注册项与声明完全一致 | WS 重复注册、harness `app_internal` 越界、agent 代码覆盖、前端静态表并行 | 启用后比对通过，多/少均失败 | W1/W2 |
| AC-PLR-03-1 | 安装×启用四状态仅双真可达 | 禁用不卸路由；2 条 WS 无门控 | 请求期统一门控，停用即不可达 | W1/W2 |
| AC-PLR-03-2 | 启停后菜单与权限回基线、无孤儿 | 只清菜单、权限残留 | 菜单+权限+订阅+路由对称清理 | W1 |
| AC-PLR-13-1 | 核心层/启动入口插件实现导入数 = 0 | `start.py` 19 行、`base/common` 约 10 处 | **start.py 已达标（2026-11-12 晚 W2-1 整改）**：顶层与 init_app/lifespan 装配层=0，剩余 8 处惰性导入在定时任务函数体内（W2-3 范围）；`base/common` 经 plugin_symbol 解析器（前轮已完成） | W2 |
| AC-PLR-13-2 / 23-2 | 新增模块平台层改动 0 文件 | 需改 `start.py` + 前端路由表 | 仅新增插件目录与 manifest | W2 |
| AC-PLR-14-1 | 重复投递同一幂等键无重复副作用 | 每次 `uuid4()`、消费端不去重 | 按幂等键去重，重放不重复执行 | W3 |
| AC-PLR-14-2 | 停用全部订阅方后发布仍成功 | 字面满足（逐 handler 吞异常），但订阅残留 | 订阅干净摘除且发布成功 | W1/W2 |
| AC-PLR-15-1 | 逐个关闭非底层插件后作业成功 | 靠 `except` 吞异常、周期性空转报错 | 作业注册表跳过停用插件，无异常 | W2/W3 |
| AC-PLR-15-2 | 新增插件不改平台级作业定义 | 需在 `start.py` 加任务 | 插件 `jobs` 声明即可 | W2 |
| AC-PLR-23-1/23-3 | 关闭插件后启动/作业/压测无服务端错误 | 已实测通过（动态回归 24/24，2026-11-12） | 自动化用例通过 | W3 |

---

## 6. 风险、约束与未验证项

- **观察期**：W1~W3 改动路由注册、启停门控与事件订阅，属运行时装配变更，**排在 2026-11-23 收口之后**；不删旧编排代码、不删 `mode` 开关、不重置计时、不提前勾选 T7.5 准入。
- **前提风险 PB-01**：v3.0 平台级定义待书面签字。若采用方案 A（平台 = 产品整体），AC-PLR-01/13 的适用范围需重评，但「路径契约冲突」「零路由静默成功」「订阅装卸不对称」仍是事实缺陷。
- **范围真空 PB-02**：整改涉及插件级 schema（events/subscribes/jobs/component），需同步启动插件级需求，避免又形成「平台文档不承接业务口径」。
- **凭据**：`config.conf` 含明文真实凭据，本文仅引用行号，不记录取值；任何整改输出不得携带。
- **部署层未完全核实**：`deploy/nginx/conf.d/agentpanel.conf:5-11` 自述为 legacy 单体栈，P7 正式入口由工作区外的 `aipanel.conf` 挂载；外部 nginx 是否有第二层 `/api` rewrite 无法在本工作区只读确认，W2-5 落地前需核实。
- **静态核查局限（已部分消除）**：四状态路由可达性、启停对称、3 轮启停压测、订阅装卸已由 `tests/regression_plugin_assembly.py` 实测（24/24，2026-11-12）；作业关闭门控（W2-3 核心）与端到端冒烟（W3-3）已由 `tests/regression_pending.py` 实测（2026-11-12：A 部署建表 3/3、B 作业门控 3/3、C 端到端 12/12 全 PASS）；**W2-1 已完全整改（2026-11-12 晚）**：events/quota 路由集中到 `register_routers`、全部 `try/except ImportError` 兜底删除、嵌入式网关挂载经 manager 读 manifest（不 import 插件实现）、`configure_shared_runtime` 迁入 harness `on_startup`——`base/start.py` 装配层插件实现导入数=0，两份回归重跑 20/20 + 24/24 零回归。**仍 OPEN**：① W2-3 作业注册表（5 个定时任务函数体内 8 处惰性插件导入 + 网关对账 gating，待 jobs 声明驱动）；② `event_subscriptions` 无 aerich 迁移，`RUN_DB_MIGRATIONS=false` 容器侧若未单独跑 aerich 该表将缺失（部署清单项）。AC-PLR-23-1/23-3 已实测通过。
- **计数口径**：23 份 `manifest.json`（历史记录写 24 个插件，可能有一目录无声明文件）；25 处 `.subscribe(` 含 1 处总线内部转发；73 条前端静态 `path` 中 41 条属禁用/无 manifest 插件页面；151 条菜单 path 中 6 条带 `/panel`、2 条 `component` 指向不存在的 `.vue`、14 条无 `component`。

---

## 附录：证据索引

| 主题 | 文件:行号 |
|---|---|
| 前缀剥离与 SPA 回退 | `base/app_wrapper.py:29-43,58-101,117-169` |
| 前端 baseURL / 代理 / 部署 | `web/src/utils/request.js:5-14`；`web/vite.config.js:31-41`；`deploy/nginx/conf.d/agentpanel.conf:5-11,30-64` |
| 官方示例与 CLI 模板 | `base/common/plugin_manager.py:14-40,296-300`；`base/cli/command.py:60-103` |
| 路由加载与零路由 | `base/common/plugin_manager.py:75,305-370` |
| 安装/启用/禁用 | `base/core/extension/api/v1/plugins.py:129-150,177-204`；`base/common/plugin_manager.py:535-585,629-657` |
| 手动注册与硬引用 | `base/start.py:15,26-31,41-77,640-690`；定时任务 `:143-189,271-589` |
| 死门控与多口径 | `base/common/router.py:14-27,30-35,157-162`；`base/common/setting.py:48,80-118`；`base/core/users/api/v1/common.py:8-27` |
| 事件订阅 | `base/common/events/{event_bus,event_bus_adapter,consumer_worker}.py`；`base/start.py:59-68`；`finance/services/finance_event_handler.py:87-95`；`mail/services/event_handler.py:160-187`；`mes/services/event_handlers.py:87-94` |
| 前端静态/动态路由与组件映射 | `web/src/router/index.js:6-324,326-329,381-422`；`web/src/stores/menu.js:160-191,243-310`；`web/src/layouts/MainLayout.vue:93,113,123` |
| 菜单下发 / 特例 | `base/core/users/services/menu_service.py:140-194`；`base/core/users/api/v1/menu.py:102-123` |
| 历史 404 记录 | `reports/ops/l3-split-full-flow-recheck-2026-11-09.md:104-105,167`；`reports/architecture/as-built-architecture-2026-11-09.md:227` |
