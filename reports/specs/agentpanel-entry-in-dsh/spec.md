# DeepSeek Harness 集成 AgentPanel 入口（「发现应用」式下拉）

> 状态：P0/P1/P2 已实施；Host 侧采用方案 A（扩展 `agentpanel-account`）。验证见 §6。
> 日期：2026-11-24
> 范围：`dshw/`（vendored DeepSeek Harness 源码）+ `base/plugins/customer` + `customer-portal/`。
> 不改动：网关数据面、编排服务、`dgw.*` / `client_id.secret` / JWT 三类凭据的双向隔离红线（PRD PC-4）。

## 0. 需求理解与边界

截图参考的是桌面客户端顶部的「发现应用」下拉：一个带箭头的胶囊按钮，点开后是搜索框 + 「常用应用」图标卡片区 + 附加应用列表。本方案要在 DeepSeek Harness（下称 dsh）里做一个**位置与交互相近**的入口，让 dsh 用户能直接进入 AgentPanel。

先明确三个边界，避免方案被误读：

1. **主体**：dsh 终端用户是 `typ=cus` 客户域，入口应指向客户门户 `customer-portal`（`/portal`），**不是**运营后台 `web`（`/panel`，`typ=usr`）。若以后需要管理员入口，另立需求并单独授权。
2. **入口 ≠ 免登**：只打开 URL 是"有入口"；不重复登录需要一次性 ticket。两者分阶段交付，但建议一期一起做，否则用户点开落在登录页、体验断裂。
3. **不是改 dsh 原生标题栏**：dsh Desktop 的标题栏由 Web 客户端 slot 绘制（`titleBarStyle: 'hidden'`）。`shell.leading` 已被 `ui-sidebar` 占用（single slot），不能抢占；用 list slot 做增量注册。

## 1. 现状事实（代码勘察结论）

### 1.1 dsh 侧

| 事实 | 位置 |
|---|---|
| Desktop 主窗口加载 Web 客户端；无 React 原生 titlebar 组件 | `dshw/apps/desktop/src/main.ts:264-296` |
| `window.open(http/https)` → 主进程 `shell.openExternal`，`window.open` 本身返回 deny | `dshw/apps/desktop/src/main.ts:297-300,361-369` |
| IPC 有 sender 校验（`dsh-app:` 协议 + hostname 白名单），无通用 openExternal 通道 | `dshw/apps/desktop/src/ipc.ts:12-47,92-128` |
| UI 全是 slot；`shell.leading` 被 ui-sidebar 占用；`shell.overlay` 是 toast/badge 层 | `dshw/packages/client/ui-layout/src/client/index.ts:54-122` |
| 可复用的"More 菜单加一行"范式 | `dshw/packages/client/ui-entry-customization/src/client/index.ts:54-65` |
| 会话头部 actions 是 list slot，可增量注册按钮 | `dshw/packages/client/ui-conversation/src/client/contract/slots.ts:199,219` |
| 插件市场 Discover 页（卡片 48px 图标框 / 36px 图标）可作视觉参照 | `dshw/packages/client/ui-plugin-market/src/client/DiscoverSection.tsx:28,111-144,463-547` + `.module.css:106-196` |
| 已有 AgentPanel 账号服务，持有 CUS JWT、租约续期；`resolveToken(url)` 仅对网关 origin 放行 | `dshw/packages/credentials/agentpanel-account/src/index.ts:31-72,454-466` |
| 桌面侧账号后端持有 CUS JWT，`links.usageUrl/topUpUrl` 已渲染到设置页 | `dshw/apps/desktop/src/agentpanel-account-backend.ts:104-110` + `dshw/packages/client/ui-settings-account/src/client/AccountSection.tsx:129-137,203-254` |
| 外链安全校验：仅 https 或 loopback http，禁 userinfo | `dshw/apps/desktop/src/account-backend.ts:47-54` |
| 现有 links 默认值指向不存在的 API 路径，工作区侧 links 为空串 | `agentpanel-account-backend.ts:104-110`、`agentpanel-account/src/index.ts:240-241,258-265` |

### 1.2 AgentPanel 侧

| 事实 | 位置 |
|---|---|
| 客户门户 `/portal`，token 键 `cp_token`，登录页支持 `?redirect=` | `customer-portal/src/stores/auth.js`、`customer-portal/src/views/Login.vue` |
| 后台 `/panel`，token 键 `token`，动态路由由 `/v1/menus/user-menus` 下发 | `web/src/router/index.js:7-10,154-194`、`web/src/stores/user.js:18-28` |
| CUS JWT 签发点仅 3 处（`typ=cus`），24h 有效期，无 refresh token | `base/plugins/customer/api/v1/auth.py:122,175,277`、`base/common/security.py:104-123` |
| **没有任何** ticket / SSO / 免登 / 外部入口端点 | 全仓 `base/**` 搜索确认 |
| 业务 API 显式拒绝 `dgw.*`；网关拒绝 JWT；编排拒绝 JWT 与 `dgw.*` | `base/common/security.py:52-59`、`services/gateway/common/auth.py`、`base/plugins/harness/services/service_auth.py:169-184` |
| Web 静态资源由 app_wrapper 托管（9998），nginx 映射宿主 9080，无路径前缀 | `base/app_wrapper.py:165,229-232`、`deploy/nginx/conf.d/agentpanel.conf` |

**结论**：可以打开 URL；做不到免登，因为缺 ticket 签发/消费端点；现有 links 是死链或空串，等于没有可用入口。

## 2. 总体设计

```
dsh 渲染进程（client 插件 ui-agentpanel-entry）
  │  ① 点击「发现应用」→ AgentPanel 卡片
  ▼
Remote / Host 服务（agentpanel-account 扩展或新 agentpanel-entry 服务）
  │  ② 用已持有的 CUS JWT 请求一次性 ticket（60s）
  ▼
AgentPanel 业务 API（base/plugins/customer，新增 web-ticket + exchange）
  │  ③ ticket 单次消费，换发标准 typ=cus JWT（复用 create_access_token）
  ▼
系统浏览器打开 <panelUrl>/portal/login?ticket=...&redirect=/dashboard
  │  ④ 门户 Login.vue 检测 ticket → exchange → 写 cp_token → replace 清 URL → 跳转
  ▼
AgentPanel 门户（正常 RBAC / 菜单下发 / 审计链路）
```

**凭据红线**：dsh 侧只把 CUS JWT 交给 AgentPanel 的 ticket 端点；`dgw.*` 虚拟 key 与 `client_id.secret` 不参与、不进浏览器、不写 URL。`resolveToken(url)` 的 origin 白名单语义保持不变。

## 3. dsh 侧改动

### 3.1 Client 插件 `ui-agentpanel-entry`（新增）

- 位置建议：`dshw/packages/client/ui-agentpanel-entry/`，参照 `ui-entry-customization` 的 `inject + apply + ctx.slots.register` 模式。
- 注册点（list slot，增量、不抢占）：
  - `conversation.session.header.actions`：主入口按钮（推荐，位置最接近截图顶部工具栏）；
  - `sidebar.panellist.actions`：侧栏 More 菜单里放一行「打开 AgentPanel」作为降级可达点。
- UI：胶囊按钮「发现应用」+ chevron；下拉面板用 `shell.overlay`（list，frame 级浮层，条目 order 排序、点击层需 opt-in pointer events）承载，避免被列表面板裁剪。
- 面板内容（一期只放一张卡，结构为后续应用预留）：
  - 搜索框 + 「常用应用」小标题；
  - 卡片：48px 圆角图标框 / 36px 图标、名称「AgentPanel」、副标题「后台管理 · 业务支撑」，单行截断；
  - 点击 → 调 host service 取 ticket → `window.open(url, '_blank', 'noopener')`；
  - 失败/未登录 → 降级打开不带 ticket 的登录页，并显示轻提示，不阻塞。
- 国际化：参照 `ui-entry-customization/locales.ts`，至少 zh/en。
- 装配：在 `dshw/packages/bundle/web-app/cordis.patch.yml` 追加插件实例；profile `cordis.yml` 可覆盖 `config.panelUrl`。

### 3.2 Host 侧

二选一，推荐 A：

- **A（推荐）**：扩展 `packages/credentials/agentpanel-account`：配置增加 `panelUrl` 与 `ticketEndpoint`；新增 `webTicket()`（用已持有的 CUS JWT 调用新端点），`links` 增加 `panelUrl` 并修正默认值为真实 Web 路由（不再是 `/v1/customer/account/*` 死链）。复用既有 0o600 凭据存储与自动续期。
- **B**：新建 `packages/host/agentpanel-entry` 服务，只依赖 `agentpanelAccount`；好处是高内聚，代价是多一个服务与装配项。

桌面侧 `apps/desktop/src/agentpanel-account-backend.ts` 同步增加 `panelUrl` 配置注入（env `AGENTPANEL_PANEL_URL`），`production.env.example` 补样例；所有外链仍经 `validateBrowserDestination` 校验（https 或 loopback http）。

### 3.3 不做什么

- 不改 `shell.leading` 占用关系；
- 不加通用 openExternal IPC 通道（用现有 `window.open` → 主进程 openExternal 链路即可）；
- 不做 Electron 内嵌 BrowserView（会话/cookie 隔离与升级维护成本高，外链已满足需求）。

## 4. AgentPanel 侧改动（一次性 ticket）

### 4.1 端点

放在 `base/plugins/customer/api/v1/`，新增：

| 端点 | 鉴权 | 请求 | 响应 |
|---|---|---|---|
| `POST /v1/customer/auth/web-ticket` | `Authorization: Bearer <CUS JWT>`（`typ=cus`） | `{}` 或 `{redirect_to?}` | `{ticket, expires_in: 60}` |
| `POST /v1/customer/auth/web-ticket/exchange` | 无（凭 ticket） | `{ticket}` | `{access_token, token_type, expires_in, user}` |

实现要点：

- ticket 用 `secrets.token_urlsafe(32)`（≥256 bit 熵），**只存哈希**（SHA-256），明文只在响应与 URL 中出现一次；
- 存储：Redis `SET NX EX 60`，消费用 `GETDEL` 原子取回；无 Redis 时用 DB 表（唯一键 + 事务内 `SELECT ... FOR UPDATE` / CAS 置 consumed）降级；
- ticket 绑定 `typ / sub / customer_id / 签发时间 / redirect_to`（redirect_to 必须是同站相对路径白名单，禁止外域）；
- 消费后即删；过期、重放、主体不匹配一律 401，不返回 token；
- 签发与消费各写一条审计（`action = customer.web_ticket.issue / exchange`），记录 `request_id / IP / UA / sub`，**不记录 ticket 值**；
- 换发的 `access_token` 复用 `create_access_token`（`base/common/security.py:104`），payload 与现有 CUS 登录完全一致，`typ=cus`；
- 不新增 refresh token；24h 到期后回登录页，行为与现状一致。

### 4.2 前端（customer-portal）

`customer-portal/src/views/Login.vue` 增加进入即执行的分支：

1. 读 `route.query.ticket`；
2. 调 exchange；成功 → `authStore` 写 `cp_token` / `cp_customer`；
3. 用 `router.replace()` 去掉 URL 中的 ticket（避免历史/Referer 泄漏），再 push `redirect`（仅站内相对路径）；
4. 失败 → 清除 URL 参数，显示普通登录表单，不暴露具体原因给 UI（日志留痕）。

后台 `web/` 与 `/panel` 不接 ticket（USR 域不在本方案范围）。

## 5. 配置与部署

| 配置项 | 位置 | 示例 |
|---|---|---|
| `panelUrl` | dsh profile `cordis.yml` / desktop env `AGENTPANEL_PANEL_URL` | `http://127.0.0.1:9080`（loopback http 允许）或 `https://panel.example.com` |
| `ticketEndpoint` | 账号服务 config | `${panelUrl}/api/v1/customer/auth/web-ticket` |
| `redirect_to` | 入口卡片点击参数 | `/dashboard` |

生产环境优先 https；loopback http 仅用于本地开发。URL 中不得带 userinfo 或 fragment。

## 6. 分阶段交付与验收

| 阶段 | 内容 | 验收 |
|---|---|---|
| P0 | 修正 links 死链，配置真实 panelUrl；复用现有 AccountSection 链接 | 设置页「查询用量 / 更多账号信息」可打开门户登录页 |
| P1 | 新增 `ui-agentpanel-entry` 插件（按钮 + 下拉卡片 + 外链） | dsh Desktop/Web 顶部可见入口，点击打开门户；无 ticket 时落登录页 |
| P2 | 后端 ticket 签发/消费 + 门户 exchange 分支 + host `webTicket()` | 已登录 dsh 用户点击后免登进入门户；重放/过期 ticket 被拒；审计可查 |
| P3（可选） | 面板扩展为真正的「发现应用」（更多卡片、搜索、分类） | 新应用按同一卡片契约接入，无需改入口组件 |

测试建议：

- client 插件单测（slot 注册、点击调取 ticket、失败降级）参照 `dshw/packages/client/ui-entry-customization/tests`；
- host 服务单测（URL 校验拒 userinfo/非 https 非 loopback、ticket 调用参数）；
- 后端端点单测：一次性、60s 过期、主体绑定、`dgw.*`/USR JWT 拒绝、审计落库；
- E2E：dsh Desktop 点击 → 系统浏览器打开门户 → 自动登录 → `cp_token` 写入 → URL 无 ticket。

## 7. 风险与待确认

1. **截图来源理解**：按"参考 WorkBuddy 桌面端『发现应用』交互"来做。若实际目标是在 dsh 插件市场 Discover 页里加卡片，挂载点改为 `plugins.tab` 的 discover 条目，其余方案不变。
2. **主体选择**：默认 CUS 门户。若要给 USR 管理员入口，需要单独设计服务凭据 → USR 的授权映射，不在本期。
3. **vendored 源码维护**：`dshw/` 是 vendored 仓库，改动需记录 patch 点，升级上游时逐项比对。
4. **免登安全**：ticket 有效期 60s、单次消费、URL 立即清理；任何失败都降级普通登录页，不得把 token 写入 localStorage 之外的持久化或日志。
5. **现有 links 死链**：无论是否做入口，都建议先修 P0——当前 `AGENTPANEL_USAGE_URL` 未设置时指向的 API 路径在后端不存在。

## 8. 实施记录与验证（2026-11-24）

- **P0**：`AccountLinks` 增加可选 `panelUrl`；`agentpanel-account` 与桌面 `agentpanelAccountBackend` 增加 `panelUrl` 配置，移除 `/v1/customer/account/*` 死链默认值；`AGENTPANEL_PANEL_URL` 注入 Host（`main.ts` + `welcome-backend.ts` + `production.env.example`）；base patch 增加 `DSH_AGENTPANEL_PANEL_URL`。
- **P1**：新增 client 插件 `@deepseek-ai/dsh-client-ui-agentpanel-entry`（会话头部 actions + 下拉卡片 + portal URL 编码），装配进 `web-app/cordis.patch.yml`；`tsconfig.client.json` 增加引用。
- **P2 后端**：`base/plugins/customer` 新增 `web_ticket` 模型、`POST /v1/customer/auth/web-ticket` 与 `/exchange`、60s 单次票据（SHA-256、CAS 消费、拒绝外部 redirect）、审计脱敏；迁移 `customer_create_table_web_ticket_1795500000.sql`。
- **P2 前端**：`customer-portal` 增加 `apiExchangeWebTicket`、Login.vue 的 `?ticket=` 交换分支（replace 清 URL），路由守卫放行带 ticket 的登录跳转。
- **Host A**：`AgentPanelAccount.webTicket()` 用 CUS JWT 请求票据（URL 仅 https/回环 http），经 `AccountController.webTicket` Remote 暴露给 client；typert 类型已重新生成。

验证结果：
- Python：`pytest tests/test_customer_web_ticket.py tests/test_customer_lease_router.py` → 10 passed。
- dsh 客户端插件 vitest → 3 passed；账号服务/控制器 vitest → 34 passed、1 skipped（新增 webTicket 用例）。
- 类型检查：`tsc -b tsconfig.client.json` 通过；`build:artifacts` 8/8 gate 通过（含 Web build）。
- 客户门户 `npm run build` 通过。

部署前置：需配置 `AGENTPANEL_PANEL_URL`（或 `DSH_AGENTPANEL_PANEL_URL`），并在重启 app 时执行迁移新建 `customer_web_ticket` 表；dsh 需使用重建后的镜像（含新插件与 typert 产物）。

## 9. 关键文件清单（实施时按此核对）

```
dshw/packages/client/ui-agentpanel-entry/                      （新增 client 插件）
dshw/packages/bundle/web-app/cordis.patch.yml                  （装配）
dshw/packages/credentials/agentpanel-account/src/index.ts      （config/links/webTicket）
dshw/apps/desktop/src/agentpanel-account-backend.ts            （panelUrl 注入、links 默认值）
dshw/apps/desktop/config/windows-packaging/production.env.example
base/plugins/customer/api/v1/                                  （web-ticket 签发/消费）
customer-portal/src/views/Login.vue                            （ticket 交换分支）
```

## 10. 应用目录后台配置（2026-11-24 追加）

原 P1 面板卡片写在 `DiscoverEntry.tsx` 里，无法运营。本节把它改为「后台配置 → 接口下发 → 客户端渲染」：

```
USR 超管（/panel 配置页） ── CRUD ──> customer_discover_app (PG)
                                            │
dsh client ──Remote discoverApps()──> Host agentpanel-account
                                            │ CUS JWT (GET /v1/harness/discover-apps)
                                            └──> require_customer（底座）→ 仅 is_active，按 sort,id 排序

注（2026-11-26）：路由/模型/菜单/权限已从 customer 插件迁入 harness 插件，
表名 customer_discover_app 保留不变（零数据迁移）；CUS 守卫下沉到底座
base.common.authz.require_customer，插件不互相 import。详见 §10.3。
```

**数据契约**（平台级全局，非租户私有；一期不做按客户分组）：

| 字段 | 约束 | 说明 |
|---|---|---|
| `name` | 1-64 | 卡片名称，搜索命中 |
| `description` | ≤160 | 卡片副标题 |
| `icon_text` | 1-4 | 图标内短文本（如 `AP`） |
| `icon_color` | `^#[0-9a-fA-F]{6}$`，可空 | 图标背景色；空则用主题默认色 |
| `open_mode` | `portal` / `link` | `portal` 走一次性 ticket 免登；`link` 直接系统浏览器打开 |
| `target` | ≤512 | `portal`=站内路径（`/` 开头、禁 `//` 和反斜杠）；`link`=完整 URL（仅 https 或回环 http，禁 userinfo） |
| `sort` / `is_active` | 整数 / 布尔 | 排序升序；停用项不下发 |

**端点**：

- `GET /v1/harness/discover-apps` — CUS JWT + 底座 `require_customer`，返回 `{items: [...]}`；只含启用项。（2026-11-26 由 `/v1/customer/...` 迁入）
- `GET|POST /v1/harness/admin/discover-apps`、`PUT|DELETE /v1/harness/admin/discover-apps/{id}`、`PATCH .../{id}/status` — USR JWT + 超管，返回全量供后台管理。

**安全边界**：后台只存 URL 字符串，不存任何 token；Host 层对下发项再做一次 URL 白名单校验（配置被误改/直接改库也不外发凭据）；`portal` 项复用已有 `webTicket()`，网关 key 与 CUS JWT 都不进浏览器。客户端在拉取失败/未登录时降级为空列表与提示，不影响原有会话功能。

### 10.1 实施状态（2026-11-24 完成）

- 表与迁移：`customer_discover_app` + `migrations/customer_create_table_discover_app_1795501000.sql`（表名保留，归属插件见下）。
- 后端：`base/plugins/harness/api/v1/discover_app_router.py` 用主 router 聚合 CUS 只读与 USR 管理两组路由（装配器只取文件首个 router）；写时 Pydantic 校验 URL，更新时先与旧记录合并再完整校验。模型 `base/plugins/harness/models/discover_app.py`、Schema `base/plugins/harness/schemas/discover_app.py`。
- 后台：`web/src/api/discoverApp.js` + `web/src/views/harness/discover-apps/index.vue`（列表/新增/编辑/启停/删除）；菜单由 harness manifest 下发到 `/harness/discover-apps`（父级「Harness 管控」），权限码 `harness:discover_app`。
- dsh：`AgentPanelAccount.discoverApps()`（`GET /v1/harness/discover-apps`，CUS JWT，Host 层二次过滤非法行）→ `AccountController.discoverApps` Remote（typert 已重生成）→ 客户端面板每次打开重新拉取、渲染图标/名称/描述、搜索、加载与空态；`portal` 项走 ticket 免登，`link` 项仅 https/回环 http。**显式配置 `appsEndpoint`**（不依赖 `${customerUrl}/discover-apps` 默认）。
- 验证：Python 16 passed（含装配聚合断言）；dsh vitest 34 passed / 1 skipped；`tsc -b tsconfig.client.json` 通过；`build:artifacts` 8/8 gate；后台 Vite build 通过（沙箱禁止清空旧 dist，改用临时 outDir 验证，产物含新页面）。
- 部署提醒：重启 app 执行迁移建表；对应插件需重新 sync/enable 以注入新菜单权限；dsh 需重建镜像带上新 Remote 类型与插件。后台配置修改后客户端下次打开面板即生效（无缓存）。
- **2026-11-26 归属变更**：以上模型/路由/菜单/权限已整体从 customer 插件迁到 harness 插件，见 §10.3。

### 10.1.1 完整迁移到 harness 插件（2026-11-26 10:55）

用户要求把「应用配置」（原「发现应用配置」）从 customer 插件完整迁到 harness 插件（模型/路由/菜单/权限四样全迁）。按下列顺序执行，零停机、零数据丢失：

1. **守卫下沉底座**：`require_customer` 从 `base/plugins/customer/services/cus_guard.py` 下沉到 `base/common/authz/context.py`（从 `__init__` 导出）；`cus_guard.py` 改为薄再导出，兼容既有 import 与测试 patch 路径（identity 已验证 `legacy is base == True`）。这样 harness 路由不再跨插件 import customer。
2. **物理迁移**：`models/discover_app.py`、`schemas/discover_app.py`、`api/v1/discover_app_router.py` 从 customer 树移入 harness 树，路由 import 改到 harness + 底座守卫；**表名 `customer_discover_app` 保留不改**（避免 openGauss 数据迁移）；路由前缀随 harness `route_prefix` 变成 `/v1/harness/*`。
3. **manifest**：customer 移除 `models`/`schemas` 的 `discover_app`、菜单子项、权限 `customer:discover_app`；harness 加入模型/Schema、新菜单子项（挂到既有父级「Harness 管控」）、权限 `harness:discover_app`。两个 manifest 均通过 `validate_manifest`。
4. **数据迁移**：harness seed SQL（`harness_seed_data_menus_and_permissions_1793951400.sql`）全量重跑会 `DELETE FROM menu WHERE path LIKE '/harness%'` 再重建，故把新权限与新菜单写进该 seed；新增 `harness_migrate_discover_app_from_customer_1795502000.sql` 幂等删除旧菜单/旧权限行（plugin_manager 的 upsert 不会清理 manifest 已移除项）。本部署角色表为空，`role_permission` 无绑定，不涉及授权迁移；超管走 `is_superuser` 不受影响。
5. **前端**：`web/src/views/customer/discover-apps/` → `harness/discover-apps/`，`discoverApp.js` 5 处路径改 `/v1/harness/admin/...`。
6. **dsh 配置**：`cordis.patch.yml`、`verify-agentpanel-entry.mjs`、`start-web.cmd` 显式注入 `DSH_AGENTPANEL_APPS_ENDPOINT=.../v1/harness/discover-apps`；**不改 `customerUrl`**（登录/webTicket/leases 仍走 `/v1/customer`）。
7. **部署/验证**：改动文件 `docker cp` 进 `agentpanel-app`，删容器内 customer 树旧文件后重启；30 个迁移全执行无错。终态：新菜单 id=2158（parent=2151）、新权限 id=2373，旧行均为空；CUS JWT 直连 `GET /v1/harness/discover-apps` 返回 200 含 `AgentPanel` 卡片，旧 `/v1/customer/discover-apps` 已被 customer 的 `{customer_id}` 路由捕获返回 422（不再提供目录）。`tests/test_harness_discover_apps.py` 6/6；一键脚本已登录态 10/10、未登录态 13/13 全通过。

**迁移要点/坑**：① harness seed SQL 每次启动全量删重建 `/harness%` 菜单，新菜单必须写进 seed 而非只靠 manifest；② 父菜单复用既有「Harness 管控」（id 会随 seed 重建而变，靠 name+path 匹配）；③ 角色-权限绑定若在其他部署存在需重新授权新 code；④ 表名不改是零数据迁移的关键。

### 10.2 本地运行时验证与修复（2026-11-24 晚）

在 dsh Web UI（`dsh web`，默认 `http://127.0.0.1:3080`，仅回环）做真实浏览器验证，发现并修复两处**仅在运行时暴露**的装配缺陷：

1. **bundle 依赖遗漏**：`cordis.patch.yml` 装配了 `agentpanel-entry`，但漏加 `@deepseek-ai/dsh-client-ui-agentpanel-entry` 到 `packages/bundle/web-app/package.json` 的 dependencies，导致 profile 解析报 `ERR_MODULE_NOT_FOUND`，入口插件未激活。已补齐依赖并重新生成产物。
2. **挂载点覆盖不全**：入口只注册到 `conversation.session.header.actions`（session 级），空会话/未登录状态下会话头部不渲染，用户看不到入口。已增加到 `sidebar.footer.action`（root 级，始终可见），并放宽 `DiscoverEntryProps` 为两个 slot 的联合类型 + 引入 `ui-sidebar/client` 类型声明。
3. **入口位置调整（用户要求）**：从左下角 footer 移到侧栏头部右上角（折叠按钮旁）。在 `ui-sidebar` 新增 `sidebar.header.action` slot（root 级 list slot，契约 + 注册表 + `SidebarRoot` 渲染 + CSS 三处改动），入口插件改挂该 slot。`DiscoverEntryProps` 联合类型相应调整为 `conversation.session.header.actions | sidebar.header.action`。
4. **源码还原事故（2026-11-24 22:01 左右）**：dshw 仓库发生一次 reset/checkout，把所有未提交的 tracked 改动抹掉——包括 `web-app/cordis.patch.yml` 的入口装配条目、`web-app/package.json` 的依赖声明、以及 `panelUrl`/`discoverApps`/`webTicket` 整条 Remote 类型链的源码（lib 产物幸存）。已依据 lib 产物 + 设计文档逐项还原 10 处源码；`build.ts --scope artifacts` 全量构建因开头 `pnpm install` 与 `tsc -b` 大堆内存卡死，改用定向重建：`generate-typert.ts` 单独跑（39 包）+ 各包 tsdown 单独编，确认关键产物均为最新后跑端到端验证通过。**排查同类问题时先看 `dump-config` 里有没有插件 id，再看 lib 产物时间戳/内容，不要直接跑全量构建。**
5. **未登录卡片死链修复 → 两步登录流程（2026-11-26 09:42 / 09:45 / 09:50 / 09:58 定稿）**：原实现把 `enabled`（是否显示门户入口）直接绑在 `getState().status === 'credential-stored'` 上，未登录时 `enabled=false`，卡片带 `disabled`，点击完全无反应。账户侧 `links.panelUrl` 本来就与登录态无关，故拆成两个概念：`getPortalUrl()` 只取 `links.panelUrl`（不再检查 status），新增 `isSignedIn()` 单独表达登录态；`loadApps` 用 `isSignedIn` 决定是否读目录，卡片去掉 `disabled`。
   - **最终两步流程（用户 09:56 明确）**：① 已登录点卡片 → 直接走 ticket 跳转应用；② 未登录点卡片 → 先弹一个**纯提示 Modal**（「需要登录 AgentPanel」+「请先登录 Harness 客户账号，登录后点击应用即可打开」，无内嵌表单），点「去登录」→ 通过 `ctx.slots.entries('settings.models.sign-in')[i].inject().start()` 触发 **Harness 自带的登录注册框**（settings-account 的 `EmailSignInDialog`，与左下角账号菜单同一入口）。登录成功后用户再点应用即直接跳转。09:50 曾在提示框内嵌邮箱/密码表单直调 `customerLogin`，用户指出流程不对，已回退。
   - 验证脚本改为「未登录弹出提示 / 文案正确 / 提示框无内嵌表单 / 去登录进入 Harness 登录注册框 / 未登录不跳转应用」，**12/12 通过**。注意本地 `%APPDATA%\dsh-agentpanel\account.json` 若存有凭证则 `status=credential-stored`，会走已登录分支，验证未登录流程前须临时挪开该文件并在结束后恢复。
   - **ticket 失败红字回退 + 登录态实时查询（2026-11-26 10:06 / 10:20）**：用户实测两个现象：① 未登录点卡片显示红字「打开失败，请重试」；② 已登录（左下角显示账号）点卡片仍弹「需要登录」。根因同源——`DiscoverEntry` 的 `signedIn` 是 mount 时一次性快照，不随登录态变化刷新：打开页面时未登录→快照 false，之后在同一会话里登录（凭证写入磁盘 + 服务内存 `applyCustomerLease`），快照不更新，点卡片仍走未登录分支；反之 lease 残留时快照 true 但 ticket 拿不到→旧代码显示红字。修复两处：`activate` 点卡片时 `await isSignedIn()` **实时**查询登录态（不用过期快照）；`openAppDirect` 在 `url === undefined` 或抛错时统一走 `needSignIn()`，portal 应用回退弹登录提示框而非死红字。`isSignedIn()` 注入每次都调 `ctx.remote.account.getState()` Remote，无缓存；Harness 登录成功走 `customerAuthenticate`，同步设置内存 `this.customer`+lease+`changed()`，故同进程登录后实时查询立即返回 true。验证脚本新增「无『打开失败』红字」断言（未登录 13/13）和 `--signed-in` 模式（已登录 10/10：不弹框/开新页/跳转带 ticket）。

验证结果（Chrome 无头 + 后端直连）：
- 侧栏**头部右侧**「发现应用」按钮渲染成功（一键脚本 13/13 通过）；点击弹出面板含标题/搜索框/「常用应用」分区。
- 侧栏头部布局（08:44 定稿）：从左到右依次为**品牌名 → 发现应用 → 收缩按钮**（两者并排在 `headerTrailing`，见参考图）。折叠态下 `headerTrailing` 内的发现应用 slot 隐藏、仅保留收缩按钮，避免窄 rail 溢出。
- 未登录态（09:58 定稿）：`DiscoverEntry::loadApps` 在未登录时用本地默认卡片（紫底 `AP` 图标 + `AgentPanel` / `后台管理 · 业务支撑`）填充「常用应用」，不调用 `getApps`、不在面板内显示红字。卡片**可点击**：`getPortalUrl()` 不再要求已登录（账户侧 `links.panelUrl` 与凭证无关），`isSignedIn()` 单独表达登录态；`openApp()` 仍需 Harness 客户凭证换一次性 ticket。未登录点击先弹纯提示 Modal「需要登录 AgentPanel」（无表单、不跳转），点「去登录」经 `settings.models.sign-in` slot 的 `start()` 打开 Harness 自带登录注册框；登录后用户再点应用即走 ticket 免登。「取消」关闭提示框。验证脚本 12/12 通过（须在无凭证状态下跑）。
- 未登录状态面板内不再显示红字，无控制台错误。ticket 失败/lease 残留场景统一回退到登录提示框（10:06 修复，验证脚本含「无『打开失败』红字」断言）。
- 已登录态（10:20 验证，`--signed-in` 模式 10/10）：点卡片**不弹登录框**，签发 ticket 并打开新标签页 `?ticket=...&redirect=%2Fdashboard`；门户消费 ticket 后进入 `/portal/dashboard`。登录态在点击时实时查询，修复「同会话登录后仍提示去登录」。
- **门户 ticket 消费 500 修复（2026-11-26 10:30，后端 openGauss 时区坑）**：用户实测登录后点卡片，门户 `/portal/login` 顶部报红字「服务器内部错误: TypeError: can't compare offset-naive and offset-aware datetimes」。根因在 `base/plugins/customer/services/web_ticket_service.py::exchange`：`expires_at` 用 `datetime.utcnow()`（naive）写入，但 openGauss 经 asyncpg 读回时 attach 本地时区（Asia/Shanghai +08:00）成 aware，与 `utcnow()` 比较即抛错。修复：新增 `_naive_utc()` 统一归一化——**直接 `value.replace(tzinfo=None)` 剥时区**（读回墙上时钟值仍是写入时的 UTC，不能 `astimezone(UTC)` 转换，否则误判过期 8 小时），与 `customer_membership.is_expired` 范式一致；comparison 改为 `_naive_utc(record.expires_at) <= utcnow()`。`tests/test_customer_web_ticket.py` 补 2 条时区回归（+08:00 aware 剥时区 / exchange 接受 aware），8/8 通过。修复经 `docker cp` 进 `agentpanel-app` 并重启生效；容器内 HTTP 端到端签发+消费 `code:0`；浏览器完整链路（点卡片→ticket→门户）最终落在 `/portal/dashboard`，显示「你好，916145267」，无 500、无登录表单。截图 `dshw/.verify/portal-e2e-1795660148689.png`。
- 用 CUS JWT 直连后端：`GET /v1/harness/discover-apps` 返回 200 且含演示应用（11-26 由 `/v1/customer/...` 迁入）；`POST /v1/customer/auth/web-ticket` 返回 200 且签发 ticket（web-ticket 仍在 customer 插件，后端链路完整）。

本地启动要点（供复现）：
- 用 `node --import tsx/esm apps/cli/src/bin.ts web --no-open` 直接启动；`pnpm run dev:web` 在本机 Node 22 + `import-without-cache` 下有 ESM loader 兼容问题（`ERR_INVALID_RETURN_PROPERTY_VALUE`）。
- 环境变量需指向 nginx 而非未映射的 9998：`DSH_AGENTPANEL_CUSTOMER_URL=http://127.0.0.1:9080/v1/customer`、`DSH_AGENTPANEL_PANEL_URL=http://127.0.0.1:9080`。
- 已知环境分叉（非集成缺陷）：本地根 `config.conf` 有 `[auth] secret_key`，而 `deploy/app/config.conf` 无，容器内 app 使用硬编码默认 secret——本地签发的 JWT 无法直接用于容器接口，需在容器内签发测试 token。

### 10.3 后台可配置的侧栏品牌 Logo / 文字（2026-11-26 12:05）

用户要求把 dsh Web UI 侧栏左上角的 Logo 与「DSH 本地构建」文字改为后台可维护。实现复用既有系统设置，不新增插件或菜单：

1. **后台字段**：`system_name` / `system_logo` 在 `SystemSettingService.init_default_settings()` 中的显示名/描述改为「品牌文字」「品牌Logo（侧栏品牌图片URL，支持后台上传）」。管理后台路径：系统管理 → 系统设置；图片类型字段可直接上传，上传接口返回 `/uploads/images/...` 相对 URL。
2. **公开读取**：`GET /v1/system-settings/public` 无需登录即可取 `system_name` / `system_logo`。为让 3080 的 dsh Web UI 跨域读取，`base/common/setting.py::ALLOW_ORIGINS` 增加 `http://127.0.0.1:3080` 与 `http://localhost:3080`，已重启 app 生效。
3. **客户端消费**：在 `ui-agentpanel-entry` 新增 `brand.ts`（共享 store + `resolveLogo` 校验）与 `Brand.tsx`；插件启动时注册 `sidebar.brand.name` / `sidebar.brand.mark` 两个 slot。品牌文字/图片从 `links.panelUrl` 拼 `/v1/system-settings/public` 读取，Logo 相对 URL 按 panelUrl origin 解析，仅允许 http(s)、拒绝带用户名密码的 URL；读取失败回退账户 `brandName`，再回退 `AgentPanel`。store 在 mount 与标签页重新可见时刷新，两个 slot 共用一次读取。
4. **验证**：定向 `pnpm --dir ... run bundle` 重建 `lib/client.js`（含 `system-settings/public` 与两个 brand slot）。浏览器脚本 `dshw/.verify/check-brand.mjs` 4/4 通过：后台改「智能体管理」→ 侧栏文字同步；上传 Logo → `<img>` 实际加载成功；临时改成「AgentPanel 测试」→ 再次读取立即生效；无运行时异常。验证后已清除测试 Logo（保留默认鲸鱼图标），正式品牌文字为「智能体管理」。入口脚本 13/13 回归通过，dsh Web UI 保留在 `http://127.0.0.1:3080`。

**部署注意**：`setting.py` / `system_setting_service.py` 只 `docker cp` 进当前 `agentpanel-app` 容器并已重启；重建容器前必须重新 `docker build -f deploy/app/Dockerfile -t agentpanel-app:latest .`。客户端插件为本地 dshw 源码 + `lib/client.js` 产物，后台改设置无需重编前端。

### 10.4 侧栏左下角未登录入口改为「登录」按钮（2026-11-26 13:40）

用户要求左下角不再显示省略号与「更多」，直接显示登录按钮。该行由 `ui-settings-account` 的 `settings.launcher` 占用（`AccountMenu`），未登录时原本是可展开的「… 更多」菜单（设置 / 意见反馈 / 登录）：

1. **实现**：`src/client/AccountMenu.tsx` 的未登录分支改为普通按钮（`IconUserOutlineMedium` + `t('signIn')`），`onClick` 直接调用 `beginSignIn()` → `start()`，即挂载 Harness 自带登录/注册对话框；不再渲染 `Menu`、`aria-haspopup` 与 signed-out 菜单项。已登录分支完全不变（头像 + 设置 / 意见反馈 / 退出登录）。移除不再使用的 `IconEllipsisOutlineMedium` 与 `.signedOutMenu` 样式。
2. **样式**：`AccountMenu.module.css` 未登录行改为 36px 高、浅灰背景、500 字重的可点击按钮；折叠态仍是 36×36 图标按钮。
3. **取舍**：未登录时不再从该行进入「设置 / 意见反馈」（用户明确要求去掉更多菜单），登录后仍可从账户菜单进入。
4. **验证**：定向重建 `ui-settings-account/lib/client.js`。单测 `packages/client/ui-settings-account/tests/account.client.spec.tsx` **74/74**（signed-out 断言改为直接登录、signed-in 菜单断言保留，失败快照文案由 More 改为 Sign in）。浏览器脚本 `dshw/.verify/check-signin-button.mjs` **6/6**：左下角按钮文案为「登录」、无账号菜单/省略号/更多、点击弹出邮箱+密码登录注册框、无运行时异常；截图 `signin-button.png` / `signin-dialog.png`。发现应用入口回归 **13/13**，dsh Web UI 保留在 `http://127.0.0.1:3080`。
5. **部署**：仅 dshw 本地源码与 `lib/client.js` 产物变化，无后端/容器改动；重建 dsh 构建产物前需重新 `pnpm --dir <pkg> run bundle`。

### 10.5 Logo 持久化、首页 Hero 品牌配置与左下角用户名（2026-11-26 14:30）

用户在截图指出三处问题并逐一修复：

1. **侧栏 Logo 404**：后台上传接口把文件写到 `/app/uploads/images`，但容器重建后该目录未挂载、文件丢失；公开设置 `system_logo` 仍指向旧 URL，浏览器报「logo 找不到」。修复：`base/core/users/api/v1/upload.py` 改写到已持久化的 `/app/storage/uploads/images`（`storage/` 宿主目录 bind mount），`base/start.py` 的 `/uploads` 静态挂载同步指向该目录，并对旧目录做只读回退。把当前 Logo 复制进新目录后 URL 恢复 200。两个 Python 文件已 `docker cp` 进当前容器并重启生效；重建容器前须重新 `docker build -f deploy/app/Dockerfile -t agentpanel-app:latest .`。
2. **首页 Hero 可配置**：新增三个系统设置 `hero_headline`（首页标题，默认「探索未至之境」）、`hero_beta`（版本徽标，默认「预览版」）、`hero_logo`（首页 Logo，图片类型，留空回退侧栏 Logo/默认鱼图标）；管理后台「系统管理 → 系统设置」可直接改/上传，`GET /v1/system-settings/public` 免登录返回。客户端：`ui-conversation` 新增 `conversation.hero.headline` / `conversation.hero.preview` 两个 slot，`EmptyHero` 通过 slot 渲染（有 fallback 保持默认文案）；`ui-agentpanel-entry` 的 `Hero.tsx` 注册这三个 Hero slot（含已有 `conversation.hero.brand.mark`），共享 `brand.ts` 的一次公开设置读取。定向重建三个客户端包产物。
3. **左下角显示真实用户名**：`AccountView` 新增可选 `displayName`，`agentpanel-account::getState()` 从持久化客户会话的 `customerName` 填充；`AccountMenu` 的 signed-in 标签优先用 `displayName`，再回退 profile 的 name/contact、最后才是本地化 `signedIn`。这样即使 `/auth/me` 读取失败（部署无 Platform），左下角仍显示真实客户账号（如 `916145267`）。重建 `agentpanel-account/lib/index.js`、`ui-settings-account/lib/client.js`、`deepseek-account/lib/types/types.d.ts`。

**验证**：`account.client.spec.tsx` 74/74、`skeleton.client.spec.tsx` 39/39；浏览器 `dshw/.verify/check-hero-brand.mjs` 6/6（侧栏图片 naturalWidth>0、标题/徽标来自后台、首页 Logo 后台图片、左下角用户名、无异常），后台临时改「AgentPanel 测试标题/内部版」再跑仍 6/6，首页 Logo 单独设置 `hero_logo` 也验证生效后清空恢复；未登录入口 13/13，`check-signin-button.mjs` 6/6。截图 `hero-brand.png` / `signin-button.png`。dsh Web UI 保留在 3080。

### 10.6 账户读取控制台报错修复（2026-11-26 14:40）

截图里两条红色 `[deepseek-account] account read failed {field: profile|balance}` 的根因不是后端接口，而是本地定向重建客户端插件时**没有传 `DSH_CLIENT_VERSION`**：`ui-settings-account` 的 `accountClientMetadata()` 要求构建期内联版本号，产物里变成 `{}.DSH_CLIENT_VERSION`，远程调用 `getProfile` / `getBalance` 同步抛错，被 `read()` 记为 failed 并打 console.error。

修复：恢复临时诊断补丁后，用 `DSH_CLIENT_VERSION=0.2.2-rc.1`（仓库根 `package.json` 版本）重新定向构建 `ui-settings-account`、`ui-agentpanel-entry`、`ui-conversation`，产物中确认 `accountClientMetadata(ctx.locale.getSnapshot().active, "0.2.2-rc.1")`。重启 dsh Web UI 后浏览器控制台账号读取错误消失，左下角仍显示真实用户名 `916145267`。

首页文案/徽标后台管理已在 §10.5 落地并再次端到端验证：后台把 `hero_headline` 改成「后台改的标题」、`hero_beta` 改成「内测版」后页面即时同步（6/6），随后恢复「探索未至之境」/「预览版」；后台设置列表可见 `首页标题` / `首页版本徽标` / `首页Logo` 三项。

**构建坑（必须记住）**：任何对 `packages/client/**` 的定向 `pnpm --dir <pkg> run bundle` 都要带 `DSH_CLIENT_VERSION`，否则会复现这两条报错。完整根构建由 `clientBuildEnvironmentDefines()` 注入，定向构建不会自动补。验证：账户控制台无错误、品牌 6/6、已登录入口 10/10。
