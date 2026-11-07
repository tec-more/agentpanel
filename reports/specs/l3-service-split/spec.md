# Spec：L3 编排与网关物理拆分（独立工程 + Docker 交付）

> 状态：待评审。本文档只定义方案与任务拆解，**不修改代码、不创建容器**。
> 前序：`reports/specs/harness-orchestration-split/spec.md`（L3 逻辑拆分，已完成）。
> 本文解决其遗留问题：L3 仍以 `base/plugins/harness`、`base/common/gateway` 的形式寄生在业务仓库，无法独立构建/发布。

## 0. 目标与非目标

### 0.1 目标

1. 把 L3 编排（9100）与 L3 网关（9999）的运行代码从业务后端（L2，9998）中物理移出，进入独立工程目录；
2. 两个 L3 服务可独立构建镜像、独立发布、独立重启，不随 L2 发布节奏；
3. 业务仓库删除 L3 运行代码，只保留：租约签发、策略 CRUD、模型凭据管理、出网策略下发、管理台读接口，以及 L3 需要的内部额度/心跳 API；
4. 容器内不使用 `config.conf`，配置与密钥全部经环境变量/挂载 secret 注入；
5. 保持现有语义：DB 为权威账本、Redis 计数、`counter_mode` 分支、`fail_closed`、租约缓存 8s TTL、L2→L3 代理与 L3→L2 额度 API 方向不变。

### 0.2 非目标

- 不拆数据库，不改表结构，不迁移历史数据；
- 不改额度算法、对账算法、策略三档语义、网关鉴权协议；
- 不做 Kubernetes/服务网格，先落 Docker Compose；
- 不在本阶段引入消息队列/outbox（离线结算仍为 P2 技术债）。

### 0.3 现状基线（只读核实结论）

| 项 | 现状 |
|---|---|
| L2 | `python run.py`，`0.0.0.0:9998`；插件机制加载 `base/plugins/harness/api/v1`（管理/配置/租约/看板） |
| L3 编排 | `python -m base.plugins.harness.server`，`127.0.0.1:9100`；走 `base/plugins/harness/api/l3` + `api/internal` |
| L3 网关 | `python -m base.common.gateway.server`，`127.0.0.1:9999` |
| 配置来源 | `base/common/setting.py`（`config.conf`）+ 插件 `manifest.json` 的 `config.gateway` / `config.orchestration` |
| 配置耦合 | `base/common/gateway/config.py`、`orchestration_config.py` 都调用 `plugin_manager.get_manifest()` |
| DB | PostgreSQL `127.0.0.1:15432`；迁移由 L2 的 `base/common/database.py`（aerich + `migrations/*.sql` + `generate_schemas`）执行 |
| Redis | `agentredis`，仅宿主回环 `127.0.0.1:6379`；尚无 Docker 网络别名 |
| L2→L3 | `orchestration_proxy`，`orchestration.mode=proxy_l3` 时转发 |
| L3→L2 | `l2_quota_client` + `l3_touch`，HMAC 服务凭据 `ORCHESTRATION_SERVICE_SECRET` |
| 角色开关 | `orchestration_runtime.set_runtime_role("l2"/"l3")`，`quota_backend` 按角色分支 |

---

## 1. 目录与仓库形态

### 1.1 方案对比

| 方案 | 能否独立构建 | 能否独立发布 | 共享代码复用 | 结论 |
|---|---|---|---|---|
| A. 两个独立仓库 + 独立公共包仓库 | 是 | 是 | 需私有包仓库/版本协调 | 过重，暂不推荐 |
| B. **同仓独立子目录（monorepo）** | 是（独立 Dockerfile/构建上下文） | 是（独立镜像 tag） | 路径依赖/本地 wheel，天然单一来源 | **推荐** |
| C. 仅新增 `deploy/`，代码仍留 `base/` | 否 | 否 | 是 | 不满足“物理拆分” |

**推荐 B**：物理目录分离、构建与发布独立，同时保留模型/契约的单一来源。等 L3 发布节奏确实独立、且需要跨团队权限隔离时，再迁 A（迁移成本可控，因为代码已按包边界整理）。

**D1 需用户最终确认**：是否接受 monorepo 子目录（推荐），还是必须独立仓库。

### 1.2 建议路径

```
agentpanel/
├─ base/                              # L2 业务后端（保留运行代码，见 §3 删除边界）
├─ packages/
│  └─ agentpanel_common/              # 共享包：模型/平台/契约/upstream/域服务（单一来源）
│     ├─ pyproject.toml
│     ├─ agentpanel_common/
│     │  ├─ env.py                    # 环境变量配置（不读 config.conf）
│     │  ├─ db.py                     # Tortoise 配置工厂 + 模型注册表
│     │  ├─ platform/                 # log / exceptions / response / cache / health / masking / security
│     │  ├─ upstream/                 # client / config / egress（原 base/common/upstream）
│     │  ├─ models/                   # harness / quota / model_price / service_credential
│     │  └─ domain/                   # run / event / policy / approval / audit / pricing / credential_resolver
│     └─ tests/
├─ services/
│  ├─ l3-orchestration/
│  │  ├─ app/                         # main.py / api/ / services/ / config.py / schema_check.py
│  │  ├─ tests/
│  │  ├─ Dockerfile
│  │  ├─ requirements.lock
│  │  └─ pyproject.toml               # 依赖 agentpanel-common
│  └─ l3-gateway/
│     ├─ app/                         # main.py / api/ / services/ / config.py
│     ├─ tests/
│     ├─ Dockerfile
│     ├─ requirements.lock
│     └─ pyproject.toml
├─ deploy/
│  └─ l3/
│     ├─ docker-compose.yml
│     ├─ .env.example                 # 只放非敏感默认值
│     └─ secrets/                     # 运行期挂载，.gitignore，不入库
└─ reports/specs/l3-service-split/    # 本文档与任务清单
```

“独立构建”指：`docker build -f services/l3-orchestration/Dockerfile .` 与 `docker build -f services/l3-gateway/Dockerfile .` 不需要先构建整个业务前端；“独立发布”指镜像 `agentpanel-l3-orchestration:<ver>`、`agentpanel-l3-gateway:<ver>` 可单独升版。

---

## 2. 共享代码策略

### 2.1 方案对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 抽公共包 `agentpanel_common` | 单一来源；版本可锁；模型/契约不漂移 | 需一次性抽包 + L2 兼容层 | **推荐** |
| 复制 `base/common` 到 L3 | 见效快 | 双份模型，表结构变更必然漂移；不可接受 | 拒绝 |
| git subtree/submodule | 复用仓库历史 | 同步复杂，Windows 协作易出错 | 暂不采用 |

### 2.2 共享包内容（唯一来源）

| 包内模块 | 来源 | 说明 |
|---|---|---|
| `platform/log.py`, `exceptions.py`, `response.py`, `cache.py`, `health.py`, `masking.py`, `security.py` | `base/common/*` 同名模块 | 去掉对 `plugin_manager`/`config.conf` 的依赖，改为构造参数注入 |
| `env.py` | 新写 | 环境变量配置模型（§5），L3 唯一配置入口 |
| `db.py` | 从 `base/common/database.py` 抽 `TORTOISE_ORM` 构建部分 | 仅建连接，不迁移、不 `generate_schemas` |
| `upstream/*` | `base/common/upstream/*` | L2 LLM 插件与 L3 网关共用，避免两份转发实现 |
| `models/harness.py`, `model_price.py`, `service_credential.py` | `base/plugins/harness/models/*` | L2 插件模型迁入共享包，L2 保留同名兼容 shim |
| `models/quota.py`, `binding.py`, `reservation.py` | `base/common/quota/models/*` | 同上 |
| `domain/run_service.py`, `event_service.py`, `policy_service.py`, `policy_rule_service.py`, `approval_service.py`, `audit_service.py`, `pricing_service.py` | `base/plugins/harness/services/*` | 两边都调用的域服务；配置从构造参数注入 |
| `domain/quota_backend.py` | 同名 | 保留接口，L2 实现直调 `QuotaService`，L3 实现走 `l2_quota_client` |
| `domain/credential_resolver.py` | 从 `model_credential_service.py` 抽解析/解密部分 | L2 保留 CRUD 与掩码读接口；L3 仅运行时解析，同一份实现 |

**不进入共享包**：`plugin_manager`、`database.init_db/_run_sql_migrations`、`base/common/setting.py`（读 `config.conf`）、所有 L2 管理域服务（`client_service`、`identity_service`、`gateway_lease_service`、`egress_policy_service`、`dashboard_service`、`reconcile_service`、`runtime_service`）与 L2 路由。

### 2.3 模型漂移防护（必须全部落地）

1. **单一来源**：模型类只在 `packages/agentpanel_common/agentpanel_common/models/`；L2 的 `base/plugins/harness/models/harness.py` 等改为 re-export shim，禁止再定义表。
2. **版本锁定**：共享包版本 `agentpanel_common==x.y.z`；两个 L3 镜像与 L2 的 `requirements.lock` 锁定精确版本；CI 拒绝“未升版却改模型”的 PR。
3. **schema 契约文件**：生成 `contracts/db_schema.json`（表名 + 关键列 + 类型 + 索引），由共享包测试对比 `Tortoise.describe_model()`；任一侧模型与契约不一致即失败。
4. **启动断言（fail-closed）**：L3 启动查询 `information_schema.columns`，校验所需表/列存在且类型兼容；不一致直接退出（不进入半可用状态）。L3 **不执行**任何 DDL/DML 迁移。
5. **迁移单一执行方**：只有 L2 跑迁移（§4）；L3 镜像内不包含 `migrations/` 与 `aerich`。

---

## 3. 删除边界对照表

图例：**迁 L3** = 代码移到 `services/l3-*`；**留 L2** = 保留在业务仓库；**两边** = 抽共享包，两侧只保留薄封装。

### 3.1 `base/plugins/harness/`

| 模块 | 职责 | 归属 | 处理方式 |
|---|---|---|---|
| `server.py` | 编排独立入口（lifespan/自检/uvicorn） | 迁 L3 | 改写为 `services/l3-orchestration/app/main.py`；去掉 plugin_manager |
| `__init__.py` | L2 插件注册与 v1 路由聚合 | 留 L2 | 不再导出 L3 入口 |
| `manifest.json` | 插件元数据 + `config.gateway/orchestration/runtime` | 留 L2 | 配置迁到环境变量；manifest 只保留 L2 插件元数据与 runtime 配置 |
| `api/internal/router.py` | L3 服务凭据 whoami/自检 | 迁 L3 | 服务凭据验签中间件下沉共享包 |
| `api/l2_internal/quota_router.py` | 内部额度 API（reserve/settle/release） | 留 L2 | L3 的唯一额度写入口，不改协议 |
| `api/l2_internal/touch_router.py` | 心跳/touch 内部 API | 留 L2 | 同上 |
| `api/l3/business_router.py` | 编排读接口 | 迁 L3 | 依赖 `readonly_db` + 共享 domain |
| `api/l3/write_router.py` | 9 条额度副作用写接口 | 迁 L3 | 依赖共享 domain + `quota_backend`(L3 实现) |
| `api/v1/__init__.py` | v1 路由聚合 | 留 L2 | — |
| `api/v1/admin_router.py` | 管理台运维接口 | 留 L2 | — |
| `api/v1/approval_router.py` | 审批查询/处理 | 留 L2 | 审批**创建**由 L3 经共享 `approval_service` 落库 |
| `api/v1/audit_router.py` | 审计查询 | 留 L2 | — |
| `api/v1/client_router.py` | 客户端凭据 CRUD | 留 L2 | — |
| `api/v1/dashboard_router.py` | 看板聚合读 | 留 L2 | 直接只读表，禁止 import L3 运行时代码 |
| `api/v1/egress_policy_router.py` | 出网策略下发 | 留 L2 | 用户明确要求 |
| `api/v1/gateway_router.py` | 租约签发/续期/吊销 | 留 L2 | 用户明确要求；共享 `lease_format` |
| `api/v1/identity_router.py` | 身份映射 CRUD | 留 L2 | — |
| `api/v1/l2_touch_router.py` | L2 侧 touch 路由 | 留 L2 | — |
| `api/v1/policy_router.py` | 策略 CRUD | 留 L2 | 用户明确要求 |
| `api/v1/price_router.py` | 价格 CRUD | 留 L2 | L3 只读价格 |
| `api/v1/run_router.py` | 运行生命周期（管理台） | 留 L2 | 写操作经 L3 代理或共享 domain |
| `api/v1/session_router.py` | 会话查询（管理台） | 留 L2 | — |
| `models/harness.py` / `model_price.py` / `service_credential.py` | ORM 模型 | 两边 | 迁共享包；L2 保留 re-export shim |
| `schemas/harness.py` | 请求/响应契约 | 两边 | 迁共享包，两侧共用 |
| `services/approval_service.py` | 审批创建/校验 | 两边 | 共享 domain；L2 管 CRUD，L3 创建/查询 |
| `services/audit_service.py` | 审计落库 | 两边 | 共享 domain；来源隔离规则不变 |
| `services/client_service.py` | 客户端管理 | 留 L2 | L3 只读 `readonly_db` |
| `services/dashboard_service.py` | 看板聚合 | 留 L2 | 去掉对网关运行时代码的 import，改只读 SQL |
| `services/egress_policy_service.py` | 出网策略来源/快照 | 留 L2 | — |
| `services/event_service.py` | 事件/步骤写入 | 两边 | 共享 domain |
| `services/gateway_lease_service.py` | 租约签发/续期/吊销 | 留 L2 | 共享 `lease_format` + `security` 哈希/指纹 |
| `services/identity_service.py` | 身份映射 | 留 L2 | L3 只读 |
| `services/l2_quota_client.py` | L3→L2 额度 API 客户端 | 迁 L3 | 保留 HMAC 签名，改用 env 配置 |
| `services/l3_client_auth.py` | L3 验证客户端凭据 | 迁 L3 | — |
| `services/l3_touch.py` | L3→L2 心跳 | 迁 L3 | — |
| `services/model_credential_service.py` | 模型凭据 CRUD/解析 | 两边 | L2 保留 CRUD+掩码读；解析逻辑入共享 `credential_resolver` |
| `services/orchestration_config.py` | 编排配置校验 | 迁 L3 | 改为 env 配置 + fail-closed 校验 |
| `services/orchestration_proxy.py` | L2→L3 代理 | 留 L2 | 迁移期保留；切换完成后随 `mode` 一并移除（D5） |
| `services/orchestration_runtime.py` | 进程角色开关 | 删 | L3 独立后不再需要角色分支；L2 直接走 QuotaService |
| `services/policy_rule_service.py` | 策略规则评估 | 两边 | L2 CRUD，L3 只读评估 |
| `services/policy_service.py` | 三档策略评估 | 两边 | 共享 domain |
| `services/pricing_service.py` | 价格读取/成本计算 | 两边 | L2 CRUD；L3/网关只读 |
| `services/quota_backend.py` | 额度后端抽象 | 两边 | L2 直调 `QuotaService`，L3 走 `l2_quota_client` |
| `services/readonly_db.py` | 只读连接 + 写拒绝自检 | 迁 L3 | 迁入 L3 工程 |
| `services/reconcile_service.py` | 对账 | 留 L2 | `reconcile_in_l3=false` |
| `services/run_service.py` | 运行/会话/步骤状态机 | 两边 | 共享 domain；L3 负责编排写，L2 管理台读 |
| `services/runtime_service.py` | 运行时启动配置 | 留 L2 | — |
| `services/service_auth.py` | 服务凭据 HMAC 验签/签名 | 两边 | 规范化/签名算法下沉共享 `security/signing.py`；两侧只留中间件 |

### 3.2 `base/common/gateway/`

| 模块 | 归属 | 处理方式 |
|---|---|---|
| `__init__.py` | 迁 L3 | — |
| `app.py`（create_gateway_app） | 迁 L3 | 去掉 embedded 形态 |
| `audit.py` | 迁 L3 | 落库走共享 `audit_service` |
| `auth.py`（客户端身份/匿名拒绝） | 迁 L3 | 只读 DB 经共享模型 |
| `budget.py`（预算/并发/额度耗尽） | 迁 L3 | Redis/DB 计数不动；额度写仍只经 L2 API 或既有网关记账路径 |
| `config.py` | 迁 L3 | **重写来源**：env 配置，删除 `plugin_manager`/`runtime_config`；保留 fail-closed 校验 |
| `constants.py` | 两边 | `dgw.` 虚拟 key 判定、JWT 形态判定 → 共享 `security/tokens.py` |
| `lease_auth.py` | 迁 L3 | 网关侧验签/缓存；租约签发侧只复用共享 `lease_format` |
| `logging.py` | 迁 L3 | 日志字段格式与共享 `platform/log` 对齐 |
| `router.py` | 迁 L3 | `/health`、`/chat/completions`（+新增 `/health/health`） |
| `server.py` | 迁 L3 | 改写为 `services/l3-gateway/app/main.py` |
| `service.py` | 迁 L3 | 凭据解析改共享 `credential_resolver` |

### 3.3 `base/common/upstream/`

| 模块 | 归属 | 处理方式 |
|---|---|---|
| `__init__.py` / `client.py` / `config.py` / `egress.py` | 两边 | 整体迁共享包 `agentpanel_common/upstream`；L2 LLM 插件与 L3 网关共用同一实现，禁止复制 |

### 3.4 `mode=proxy_l3` 与 `start.py` 挂载

| 项 | 结论 |
|---|---|
| `orchestration.mode` | **拆分完成后不再需要**。L2 不再有“本进程做编排”的语义，L3 永远独立；`quota_backend` 的角色分支删除。迁移期可保留 `mode=proxy_l3` 作为灰度开关（D5），灰度结束删除字段与校验。 |
| `start.py` 的 harness v1 挂载 | 保留（管理台/租约/策略/凭据/出网/看板均在 L2） |
| `start.py` 的 `l2_quota_router` / `l2_touch_router` 挂载 | 保留（L3→L2 内部 API，是拆分后的必要依赖） |
| `start.py` / `app_wrapper.py` 的 embedded 网关挂载（`/v1/gateway`） | 删除；网关只以独立容器运行 |
| `base/plugins/harness/server.py`、`api/l3`、`api/internal` 的启动/挂载 | 从 L2 工程删除（迁 L3） |
| `orchestration_runtime.set_runtime_role` 调用 | 删除（L2/L3 各自固定角色） |
| `base/plugins/harness/api/v1/l2_touch_router.py` | 保留（若仅 L3 使用则随 L3 迁走，实施时按引用核实一次） |

---

## 4. 数据库与迁移归属

### 4.1 单一迁移执行方：L2

- **只有 L2** 执行 `aerich upgrade`、`migrations/*.sql`、`Tortoise.generate_schemas`（现状 `base/common/database.py`）。
- L3 镜像**不包含** `migrations/`、不安装 `aerich`、启动时不执行任何 DDL。
- L3 启动只做 **schema 断言**：查 `information_schema.tables/columns`，校验必需表与关键列；不匹配则 fail-closed 退出。断言清单与共享包 `contracts/db_schema.json` 同源。
- `service_credential` 仍由 L2 启动流程创建/seeding；L3 只读校验 `status='active'`。
- 部署顺序约束：**先 L2 迁移，再滚动 L3 镜像**；L3 版本声明所需 schema 版本（`SCHEMA_MIN_VERSION`），低于则拒绝启动。

### 4.2 L3 读写表清单

| 表 | L3 编排 | L3 网关 | 说明 |
|---|---|---|---|
| `harness_session` / `harness_run` / `harness_step` | 读写 | 只读 | 编排状态机 |
| `harness_audit_event` | 写 | 写 | 来源隔离：`orchestration` / `gateway` |
| `harness_approval_request` / `harness_approval_grant` | 读写 | — | 审批创建/查询 |
| `harness_action_policy` / `harness_policy_rule` | 只读 | — | 策略评估 |
| `harness_client` / `harness_identity` | 只读 | 只读 | 客户端鉴权/身份映射 |
| `harness_gateway_lease` | — | 读写 | 状态、用量、最后使用时间 |
| `harness_gateway_budget` / `harness_gateway_concurrency` | — | 读写 | 预算/并发记账 |
| `usage_record` | 只读 | 写 | 网关记账；编排写经 L2 QuotaService |
| `quota_account` / `quota_plan` / `quota_plan_binding` | 只读 | 只读 | 限额读取 |
| `quota_reservation` | **不直接写** | 只读 | 预占/结算只经 L2 内部额度 API |
| `model_price` | 只读 | 只读 | 成本计算 |
| `service_credential` | 只读 | 只读 | HMAC 验签 |
| 模型凭据/供应商配置表 | 只读 | 只读 | 共享 `credential_resolver` 解密 |
| `harness_reconcile_batch` / `harness_reconcile_diff` | — | — | 对账留 L2 |

**禁止**：L3 写 `user`/`role`/`permission`/`customer`/`quota_plan*`；禁止 L3 连接管理员账号，编排用只读账号，网关只对上述白名单表使用专用最小权限账号（或同一只读账号 + 受控写连接）。

---

## 5. 配置注入

### 5.1 原则

- 容器内**不存在** `config.conf`、`.env`、任何明文密钥文件；
- 配置只从环境变量读取；密钥从 `/run/secrets/*` 文件读取，变量只给**文件路径**；
- 启动时 fail-closed：必填缺失/非法即退出，不进入半可用；
- 镜像构建上下文排除 `config.conf`、`.env`、`secrets/`、`reports/`。

### 5.2 通用配置（两个 L3 共用）

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `APP_ENV` | 否 | `prod` | `dev/prod`；影响日志与严格校验 |
| `LOG_LEVEL` | 否 | `INFO` | — |
| `DB_HOST` | 是 | — | 容器内 `host.docker.internal` |
| `DB_PORT` | 否 | `15432` | — |
| `DB_NAME` | 是 | — | `aipaneladmin` |
| `DB_USER` | 是 | — | 最小权限账号 |
| `DB_PASSWORD` | 是 | — | 可由 `DB_PASSWORD_FILE` 替代 |
| `DB_PASSWORD_FILE` | 否 | — | secret 文件路径，优先于 `DB_PASSWORD` |
| `DB_CONNECT_TIMEOUT` / `DB_COMMAND_TIMEOUT` | 否 | 30 | 秒 |
| `REDIS_HOST` | 是 | — | Docker 网络别名 `agentredis` |
| `REDIS_PORT` | 否 | `6379` | — |
| `REDIS_DB` | 否 | `0` | — |
| `REDIS_PASSWORD` / `REDIS_PASSWORD_FILE` | 是 | — | 文件优先 |
| `ORCHESTRATION_SERVICE_SECRET` / `_FILE` | 是（编排 + L2） | — | L3→L2 HMAC；L2 侧同值 |

### 5.3 L3 编排（`ORCH_*`）

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `ORCH_ENABLED` | 否 | `true` | — |
| `ORCH_HOST` | 否 | `0.0.0.0` | 容器内监听；保留 `ORCH_ALLOW_REMOTE_BIND` 校验 |
| `ORCH_PORT` | 否 | `9100` | — |
| `ORCH_PUBLIC_BASE_URL` | 是 | — | 对外可达地址，如 `http://127.0.0.1:9100` |
| `ORCH_L2_BASE_URL` | 是 | `http://host.docker.internal:9998` | L3→L2 内部 API |
| `ORCH_L2_SERVICE_ID` | 否 | `svc_l3_orchestration` | — |
| `ORCH_INTERNAL_TIMEOUT_SECONDS` | 否 | `5` | — |
| `ORCH_HTTP_TIMEOUT_SECONDS` | 否 | `30` | 客户端请求超时 |
| `ORCH_WRITE_ENABLED` | 是 | `true` | 写接口总闸；生产必须显式 |
| `ORCH_AUTH_TIMESTAMP_WINDOW_SECONDS` | 否 | `60` | 30–300 |
| `ORCH_INTERNAL_ALLOWED_IPS` | 否 | `127.0.0.1,::1` | **容器部署需加 Docker 网段**（D5） |
| `ORCH_SCHEMA_MIN_VERSION` | 否 | 空 | 低于则拒绝启动 |

### 5.4 L3 网关（`GW_*`，完整映射原有 `config.gateway`）

| 变量 | 必填 | 默认 |
|---|---|---|
| `GW_ENABLED` | 否 | `true` |
| `GW_HOST` / `GW_PORT` | 否 | `0.0.0.0` / `9999` |
| `GW_PUBLIC_BASE_URL` | 是 | — |
| `GW_FAIL_CLOSED` | 是 | `true`（必须为 true） |
| `GW_PROVIDER_DOMAIN_ALLOWLIST` | 是 | `api.deepseek.com`（逗号分隔） |
| `GW_ALLOW_LOOPBACK` | 否 | `false` |
| `GW_LEASE_TTL_SECONDS` / `GW_RENEW_TTL_SECONDS` / `GW_MAX_LEASE_TTL_SECONDS` | 否 | 900 / 900 / 3600 |
| `GW_TENANT_LEASE_TTL_JSON` | 否 | `{}` |
| `GW_LEASE_CACHE_TTL_SECONDS` | 否 | `8`（限定 5–10） |
| `GW_MAX_RPM` | 否 | `60` |
| `GW_LEASE_BUDGET_TOKENS` | 否 | `0` |
| `GW_MAX_OUTPUT_TOKENS_PER_REQUEST` | 否 | `4096` |
| `GW_MAX_CONCURRENT_REQUESTS_PER_OWNER` | 否 | `8` |
| `GW_ESTIMATE_CHARS_PER_TOKEN` | 否 | `2.0` |
| `GW_MIN_OUTPUT_ALLOWANCE_TOKENS` | 否 | `1` |
| `GW_AUTO_REVOKE_ON_EXHAUSTED` | 否 | `true` |
| `GW_GATEWAY_QUOTA_TTL_SECONDS` | 否 | `86400` |
| `GW_UPSTREAM_TIMEOUT_SECONDS` / `GW_CONNECT_TIMEOUT_SECONDS` / `GW_TOTAL_TIMEOUT_SECONDS` | 否 | 300 / 10 / 0 |
| `GW_RETRY_MAX_ATTEMPTS` / `GW_RETRY_BACKOFF_SECONDS` / `GW_RETRY_MAX_BACKOFF_SECONDS` | 否 | 3 / 0.5 / 4.0 |
| `GW_RETRY_STATUSES` | 否 | `429,500,502,503,504` |
| `GW_VERIFY_TLS` | 否 | `true` |
| `GW_PROXY_URL` | 否 | 空 |
| `GW_TRUST_ENV` | 否 | `false` |
| `GW_MAX_CONNECTIONS` / `GW_MAX_KEEPALIVE_CONNECTIONS` / `GW_KEEPALIVE_EXPIRY_SECONDS` | 否 | 100 / 20 / 30 |
| `GW_STRIP_REQUEST_FIELDS` | 否 | `dsh_session_log` |
| `GW_HEALTH_CHECK_TIMEOUT_SECONDS` | 否 | `3` |
| `GW_RECONCILE_ENABLED` / `_INTERVAL_SECONDS` / `_WINDOW_HOURS` / `_MAX_WINDOW_HOURS` | 否 | true / 600 / 24 / 168 |

> 校验规则与原 `validate_gateway_config()` 等价：`fail_closed=true`、白名单非空、`public_base_url` 为 http(s)、TTL 合法、重试配置合法。`runtime.allow_env_fallback/allow_direct_provider` 校验改为 `GW_ALLOW_ENV_FALLBACK=false` / `GW_ALLOW_DIRECT_PROVIDER=false` 固定拒绝。

### 5.5 密钥注入

| 方式 | 用法 | 结论 |
|---|---|---|
| `.env`（仅开发） | `deploy/l3/.env`，`.gitignore` | 允许本地；不进镜像 |
| 环境变量直传（生产） | compose `environment` 引用宿主变量 | 会出现在 `docker inspect`，不推荐放密钥 |
| **Compose secrets（推荐）** | `secrets: {redis_password: {file: ...}}` → `/run/secrets/redis_password` | 推荐；应用读 `_FILE` |
| Docker Swarm secret/K8s secret | 后续演进 | 本阶段不引入 |

**镜像内不得含密钥**：构建阶段不 `COPY .env|secrets|config.conf`；CI 增加 `docker history --no-trunc` 与镜像层关键词扫描（`requirepass`、`ORCHESTRATION_SERVICE_SECRET`、`password`）。

---

## 6. Docker 交付

### 6.1 镜像形态：**两个独立镜像（推荐）**

| 方案 | 优点 | 缺点 |
|---|---|---|
| **A. 两个镜像** | 依赖面最小；可独立扩缩容/重启/发布；攻击面小；镜像体积小 | 两份 Dockerfile（共享 base 层） |
| B. 一个镜像 + 两个 entrypoint | 构建简单 | 网关镜像携带编排依赖；发布耦合；无法独立裁剪权限 |

**D3 需用户确认**（推荐 A）。

### 6.2 Dockerfile 要点（两份同构）

- 基础镜像：`python:3.12-slim-bookworm`；
- 多阶段：
  1. `builder`：构建共享包 wheel（`pip wheel . -w /wheels`），安装 `requirements.lock` 到 `/wheels`；
  2. `runtime`：仅拷贝 wheel + 服务代码，`pip install --no-index --find-links=/wheels`；
- 非 root：创建 `app` 用户（UID/GID `10001`），`USER 10001:10001`；
- 只读根文件系统：compose `read_only: true`，`tmpfs: /tmp`；
- 不写日志文件：stdout/stderr（`python -u`），由 Docker 日志驱动收集；
- `HEALTHCHECK`（不依赖 curl）：
  ```dockerfile
  HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9100/health/health',timeout=3).status==200 else 1)"
  ```
  网关镜像换 9999 + `/health`（建议同时新增 `/health/health`，见 §8）；
- 镜像标签：`agentpanel-l3-orchestration:${GIT_SHA}` + `:latest`（发布时打 semver）。

### 6.3 构建上下文与 `.dockerignore`

- 构建上下文 = 仓库根（需要 `packages/` 与 `services/`）；
- `.dockerignore` 排除：`.venv/`、`web/`、`reports/`、`config.conf*`、`.env*`、`secrets/`、`logs/`、`__pycache__/`、`*.pyc`、`.git/`、`migrations/`（L3 不用）。

### 6.4 `deploy/l3/docker-compose.yml`（骨架）

```yaml
name: agentpanel-l3
networks:
  agentpanel-net:
    external: true          # 由 `docker network create agentpanel-net` 预先创建
secrets:
  redis_password:
    file: ./secrets/redis_password
  orchestration_service_secret:
    file: ./secrets/orchestration_service_secret

services:
  l3-orchestration:
    build:
      context: ../..
      dockerfile: services/l3-orchestration/Dockerfile
    image: agentpanel-l3-orchestration:${TAG:-local}
    restart: unless-stopped
    ports:
      - "127.0.0.1:9100:9100"      # 仅宿主回环
    read_only: true
    tmpfs: [/tmp]
    environment:
      APP_ENV: prod
      DB_HOST: host.docker.internal
      DB_PORT: "15432"
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_READONLY_USER}
      DB_PASSWORD_FILE: /run/secrets/db_password
      REDIS_HOST: agentredis        # Docker 网络别名
      REDIS_PORT: "6379"
      REDIS_PASSWORD_FILE: /run/secrets/redis_password
      ORCH_HOST: 0.0.0.0
      ORCH_PORT: "9100"
      ORCH_PUBLIC_BASE_URL: http://127.0.0.1:9100
      ORCH_L2_BASE_URL: http://host.docker.internal:9998
      ORCH_WRITE_ENABLED: "true"
      ORCH_INTERNAL_ALLOWED_IPS: 172.28.0.0/16
      ORCHESTRATION_SERVICE_SECRET_FILE: /run/secrets/orchestration_service_secret
    secrets: [redis_password, orchestration_service_secret, db_password]
    networks: [agentpanel-net]
    extra_hosts: ["host.docker.internal:host-gateway"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9100/health/health',timeout=3).status==200 else 1)"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 20s
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "3"}

  l3-gateway:
    build:
      context: ../..
      dockerfile: services/l3-gateway/Dockerfile
    image: agentpanel-l3-gateway:${TAG:-local}
    restart: unless-stopped
    ports:
      - "127.0.0.1:9999:9999"
    read_only: true
    tmpfs: [/tmp]
    environment:
      APP_ENV: prod
      DB_HOST: host.docker.internal
      DB_PORT: "15432"
      DB_NAME: ${DB_NAME}
      DB_USER: ${GW_DB_USER}
      DB_PASSWORD_FILE: /run/secrets/db_password
      REDIS_HOST: agentredis
      REDIS_PORT: "6379"
      REDIS_PASSWORD_FILE: /run/secrets/redis_password
      GW_HOST: 0.0.0.0
      GW_PORT: "9999"
      GW_PUBLIC_BASE_URL: ${GW_PUBLIC_BASE_URL}
      GW_FAIL_CLOSED: "true"
      GW_PROVIDER_DOMAIN_ALLOWLIST: ${GW_PROVIDER_DOMAIN_ALLOWLIST}
    secrets: [redis_password, db_password]
    networks: [agentpanel-net]
    extra_hosts: ["host.docker.internal:host-gateway"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9999/health',timeout=3).status==200 else 1)"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 20s
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "3"}
```

补充 `db_password` secret（compose 中一并声明）。`agentredis` 接入：

```powershell
docker network create agentpanel-net          # 一次性
docker network connect agentpanel-net agentredis
```

> `agentredis` 当前只发布到 `127.0.0.1:6379`，容器无法通过宿主回环访问；**必须**用网络别名 `agentredis:6379`。`docker network connect` 为热操作，不重启、不丢数据、不影响 `aipanel-redis`。
>
> `host.docker.internal` 在 Docker Desktop Windows 默认可解析；compose 仍显式加 `extra_hosts: host-gateway` 以兼容 Linux。

---

## 7. 网络与端口

| 方向 | 源 → 目标 | 地址 | 鉴权 |
|---|---|---|---|
| 桌面端（L1）→ 网关 | 宿主 → 容器发布端口 | `127.0.0.1:9999` | `dgw.<lease_id>.<secret>` 租约 |
| L2 → L3 编排 | 宿主机进程 → 容器发布端口 | `http://127.0.0.1:9100` | 客户端凭据（`l3_client_auth`） |
| L3 编排 → L2 额度/心跳 | 容器 → 宿主机 | `http://host.docker.internal:9998` | HMAC 服务凭据 |
| L3 网关 → PG | 容器 → 宿主机 | `host.docker.internal:15432` | DB 最小权限账号 |
| L3 → Redis | 容器 → 容器 | `agentredis:6379`（网络别名） | `requirepass` |
| L3 网关 → 上游 provider | 容器 → 公网 | 白名单域名 | provider key（运行时解析） |

- 容器内监听 `0.0.0.0`（Docker 端口映射必需）；**宿主发布只允许 `127.0.0.1`**，禁止 `0.0.0.0:9999/9100`。
- `ORCH_INTERNAL_ALLOWED_IPS` 与原 `internal_allowed_ips` 是**来源 IP 校验**：容器来源为 Docker 网段，必须把 compose 固定网段（建议 `172.28.0.0/16`）加入白名单；否则 L3→L2 全部 401。**D5**。
- `ORCHESTRATION_SERVICE_SECRET` 分发：compose secret 文件挂载到 L3；L2 宿主进程从环境变量读取同值。轮换：先更新 L2 环境并重启 → 再更新 secret 与 L3（存在短暂 401 窗口），或后续支持多 active 凭据；本阶段接受受控窗口并写入 runbook。

---

## 8. 验证方案（容器起来后必须逐项通过）

### 8.1 基础健康

1. `docker compose ps` 两个服务均为 `healthy`；
2. `GET http://127.0.0.1:9100/health/health` → `status=healthy`、`checks.redis.status=healthy`、`checks.database.status=healthy`；
3. `GET http://127.0.0.1:9999/health` → `status=ok`、`deployment=standalone`、`fail_closed=true`；建议新增 `/health/health` 并校验 DB/Redis 子项（网关当前 `/health` 不含 redis 检查，属实现项）；
4. `GET http://127.0.0.1:9100/health/orchestration` → 只读写拒绝 + `service_credential` 可读。

### 8.2 依赖连通

5. L3 编排容器内 `python -c` 打开 PG 只读连接并 `SELECT 1`；确认写语句被拒；
6. L3 容器内 `redis-cli` 或项目探针 `PING` 通过（走 `agentredis` 别名，不写 `127.0.0.1`）；
7. schema 断言：故意把 `ORCH_SCHEMA_MIN_VERSION` 调高 → 启动必须失败（负向验证）；恢复后重启通过。

### 8.3 业务链路

8. **L2→L3 代理读**：`GET /v1/harness/sessions`（L2）→ 返回 L3 数据；停掉 L3 → 返回 503 fail-closed（不回落本进程）；
9. **租约→网关调用**：L2 签发租约 → `POST 127.0.0.1:9999/chat/completions` → 上游 mock/或非法 JSON（鉴权后 400）→ Redis 出现 `gw:lease:state:<id>`（TTL≈8s）；
10. **预占/结算**：经 L3 写接口（或 L2 内部额度 API 直测）→ `quota_reservation.counter_mode=redis`、`quota_hold:*` 存在；结算后 `usage_record` 唯一、`used` 只加一次；
11. **G1 复跑**：沿用 `reports/ops/redis-enable-runbook.md` §6 的 20 并发用例，在容器形态下复跑，A/B/C 三项全过；
12. **金额/权限边界**：错误服务密钥 → 401；`ORCH_WRITE_ENABLED=false` → 409；禁用 Redis → 降级 DB 且结算仍成功。

### 8.4 容器安全与运维

13. `docker run --rm --entrypoint sh <image> -c 'id -u'` → 非 `0`；
14. 镜像内无 `config.conf`/`.env`/`secrets`：`docker run --rm --entrypoint sh <image> -c 'find / -maxdepth 4 \( -name config.conf -o -name ".env*" -o -name "*secret*" \)'` → 空（`/run/secrets` 只在运行时挂载）；
15. `docker history --no-trunc <image> | Select-String 'requirepass|SERVICE_SECRET|password'` → 空；
16. `docker port` → `127.0.0.1:9999` / `127.0.0.1:9100`，无 `0.0.0.0`；
17. 重启网关容器 → 8s 内旧租约缓存消失；吊销租约在 8s 内仍可能被接受（记录为已知语义，不是缺陷）；
18. `docker stop` L2（宿主进程）→ L3 写接口 503、读接口与网关转发仍可用（符合 fail-closed 设计）。

---

## 9. 回滚

### 9.1 回滚目标态

回到“单仓三进程 + 共享宿主 Redis”的现状，**不改数据库、不迁移数据**。

### 9.2 触发条件

- 8.1–8.4 任一硬项失败；
- L3 容器无法在 2 次重启内 healthy；
- 预占/结算出现重复或 `used` 多加（G1 不通过）；
- L2→L3 代理错误率 > 1% 或 P95 延迟翻倍（阈值实施时固化）。

### 9.3 步骤

1. 打标签：拆分前在业务仓库创建 `pre-l3-physical-split` tag（实施阶段 P0 完成）；
2. `docker compose -f deploy/l3/docker-compose.yml down`（保留镜像与 secret）；
3. `git switch pre-l3-physical-split`（或 `git worktree` 到独立目录，避免打断当前分支）；
4. 用 `.venv` 按既有 runbook 启动 L2(9998) → 网关(9999) → 编排(9100)；
5. 验证三进程 `/health/health`、`gw:lease:state:*`、预占 `counter_mode`；
6. Redis 与 PG 无需变更：拆分不写新表、不改键名；容器与宿主共用同一 `agentredis` 与 PG。

### 9.4 回滚后的残留处理

- L3 容器停止即可，不必删除镜像（保留用于复现）；
- `agentpanel-net` 网络与 `agentredis` 的网络附加可保留，不影响宿主进程；
- 不删除 `agentredis_data` 卷。

---

## 10. 风险与开放问题

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | 模型漂移 | 两侧表/列不一致 | 共享包 + schema 契约 + 启动断言（§2.3） |
| R2 | 密钥进入镜像/日志 | 凭据泄露 | compose secrets + CI 层扫描 + 不回显（§5.5） |
| R3 | Docker 来源 IP 不在白名单 | L3→L2 全 401 | 固定 compose 网段并加入 `ORCH_INTERNAL_ALLOWED_IPS`（D5） |
| R4 | Redis 只绑宿主回环 | 容器连不上 | 附加 `agentpanel-net` + 别名（D4） |
| R5 | 网关健康不含 Redis/DB | 假健康 | 新增 `/health/health` 或扩展 `/health`（§8.1） |
| R6 | L2 与 L3 发布顺序 | 新列未迁移 | 先 L2 迁移；L3 `SCHEMA_MIN_VERSION` 拒绝旧库 |
| R7 | 网关凭据解析去 L2 化 | L2 宕机影响转发 | 共享 `credential_resolver` 只读直连；保留内部 API 备选（D2 子项） |
| R8 | Windows 卷/权限差异 | 非 root 无法写 | `read_only` + `tmpfs`，日志走 stdout；不使用宿主卷 |
| R9 | 服务密钥轮换窗口 | 短暂 401 | runbook 固定顺序 + 受控窗口；后续多凭据支持 |
| R10 | 双写者 `usage_record` | 重复记账 | 沿用既有来源隔离（`gw:` / `orch:` 前缀） |

---

## 11. 数据流（目标态）

```
L1 桌面端
  └─(dgw 租约)─▶ [容器] L3 网关 :9999 ──▶ provider（白名单）
                    │  读写 PG/Redis（记账、预算、并发、租约缓存）
                    └─(服务凭据 / internal)─▶ L2 ?（仅内部管理/额度写）
L2 业务后端 :9998（宿主进程）
  ├─(客户端凭据)─▶ [容器] L3 编排 :9100（会话/运行/步骤/策略/审批）
  │                    └─(HMAC 服务凭据)─▶ L2 /internal/v1/harness/quota|touch
  ├─ 租约签发 / 策略 CRUD / 模型凭据管理 / 出网策略 / 看板
  └─ 唯一迁移执行方（aerich + migrations/*.sql）
共享：PostgreSQL（host.docker.internal:15432）、Redis（agentredis:6379，Docker 网络别名）
```
