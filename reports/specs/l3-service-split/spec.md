# Spec：L3 编排与网关物理拆分（独立工程 + Docker 交付）

> 状态：待评审。本文档只定义方案与任务拆解，**不修改代码、不创建容器**。
> 前序：`reports/specs/harness-orchestration-split/spec.md`（L3 逻辑拆分，已完成）。
> 本文解决其遗留问题：L3 仍以 `base/plugins/harness`、`base/common/gateway` 的形式寄生在业务仓库，无法独立构建/发布。
>
> **路径同步说明（2026-11-09）**：本文写作时的规划路径为 `packages/agentpanel_common/gateway/*`；同日目录整理先把该包整包迁入 `services/gateway/gateway/`，随后又二次改名为 `services/gateway/common/`（导入名 `services.gateway.common.*`），服务目录也去掉 `l3` 前缀。文中所有路径表述已机械同步为当前布局，但「（新）」「已存在」等时态描述仍属于当时的规划语境；**实际落地位置与依赖方向以 `reports/architecture/as-built-architecture-2026-11-09.md` 和代码为准**。

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

“独立构建”指：`docker build -f services/orchestration/Dockerfile .` 与 `docker build -f services/gateway/Dockerfile .` 不需要先构建整个业务前端；“独立发布”指镜像 `agentpanel-l3-orchestration:<ver>`、`agentpanel-l3-gateway:<ver>` 可单独升版。

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

图例：**迁 L3** = 代码移到 `services/*`；**留 L2** = 保留在业务仓库；**两边** = 抽共享包，两侧只保留薄封装。

### 3.1 `base/plugins/harness/`

| 模块 | 职责 | 归属 | 处理方式 |
|---|---|---|---|
| `server.py` | 编排独立入口（lifespan/自检/uvicorn） | 迁 L3 | 改写为 `services/orchestration/app/main.py`；去掉 plugin_manager |
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
| `server.py` | 迁 L3 | 改写为 `services/gateway/app/main.py` |
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
| `user` | 只读（限列） | 只读（限列） | 编排：审批人解析，仅 `id` / `username` / `is_superuser` / `is_active` 且 `is_active=true`；网关：套餐角色解析，仅 `id`。均不注册 ORM 模型，走只读 SQL |
| `user_role` | — | 只读（限列） | 网关套餐解析（P3 增补）：仅 `user_id` / `role_id`；只读 SQL |
| `role` | — | 只读（限列） | 网关套餐解析（P3 增补）：仅 `id` / `code` / `is_active`，只取 `is_active=true`；只读 SQL |
| `customer_membership` / `customer_membership_level` | — | 只读（限列） | 网关套餐解析（P3 增补）：`customer_membership` 仅 `customer_id` / `membership_level_id` / `expire_time` / `is_active`；`customer_membership_level` 仅 `id` / `level_type`；只取 `is_active=true`，`expire_time` 按 UTC 判过期 |
| `customer_organization` / `customer_organization_member` | 只读 | — | 组织级配额成员校验（组织 owner/member 归属判断） |
| `harness_gateway_lease` | — | 读写 | 状态、用量、最后使用时间 |
| `harness_gateway_budget` / `harness_gateway_concurrency` | — | 读写 | 预算/并发记账 |
| `usage_record` | 只读 | 写 | 网关记账；编排写经 L2 QuotaService |
| `quota_account` / `quota_plan` / `quota_plan_binding` | 只读 | 只读 + 既有 DB 兜底写 | 限额读取；网关在 Redis 不可用时沿用原 `QuotaService` DB 兜底（`ensure_account`、`quota_account.used` 回写），见 §3.2“Redis/DB 计数不动” |
| `quota_reservation` | **不直接写** | 只读 | 预占/结算只经 L2 内部额度 API |
| `model_price` | 只读 | 只读 | 成本计算 |
| `service_credential` | 只读 | 只读 | HMAC 验签 |
| 模型凭据/供应商配置表 | 只读 | 只读 | 共享 `credential_resolver` 解密 |
| `harness_reconcile_batch` / `harness_reconcile_diff` | — | — | 对账留 L2 |

**禁止**：L3 写 `user`/`user_role`/`role`/`permission`/`customer`/`customer_membership`/`customer_membership_level`/`quota_plan*`；禁止 L3 连接管理员账号，编排用只读账号，网关只对上述白名单表使用专用最小权限账号（或同一只读账号 + 受控写连接）。

**§4.2 白名单增补理由（P3 决策 D-P3-2=B）**：

1. `PlanService` 迁入共享包后，网关进程不再能懒加载 L2 插件模型，`cus/usr` 套餐解析改由网关注入“只读 SQL 解析器”，因此新增 `user_role`、`role`、`customer_membership`、`customer_membership_level` 四张表的限列只读；
2. 列清单按 ORM 实际查询逐列收敛：`user_role(user_id,role_id)`、`role(id,code,is_active)`、`customer_membership(customer_id,membership_level_id,expire_time,is_active)`、`customer_membership_level(id,level_type)`；不读这些表的其它列；
3. 过滤条件与 ORM 逐条对齐：仅 `is_active=true` 的角色/会员记录参与解析，`expire_time` 按 UTC 与当前时间比较（naive 视为 UTC）；`user` 自身是否停用不参与角色解析（与原 ORM 行为一致）；
4. **等价性由对拍保证**：同一批 fixture 下 L2 ORM 解析器与网关只读 SQL 解析器逐字段比对，任一分支不等价即停止实施并上报，不接受“近似等价”；对拍范围见 §13.6。

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
      dockerfile: services/orchestration/Dockerfile
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
      dockerfile: services/gateway/Dockerfile
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
3. `GET http://127.0.0.1:9999/health` → `status=ok`、`deployment=standalone`、`fail_closed=true`；**已实现** `GET /health/health` 并校验 database/redis 子项（原“网关 `/health` 不含 redis 检查”为 P1 前状态）；
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
17. 重启网关容器：租约缓存实际存放在 Redis（`gw:lease:state:<id>`，TTL 默认 8s），重启不会清空键，旧状态最迟在一个 TTL 后自然过期；吊销为写穿删除，通常立即生效。吊销租约在 ≤8s 内仍可能被接受（记录为已知语义，不是缺陷）；
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

---

## 12. P1 实施规格（共享包 + manifest 拆分 + 配置契约）

> 状态：已按用户确认方向冻结，作为 P1 编码与验收的唯一依据。
> 原则：只搬运 + 兼容，不改业务语义；不删除、不重写任何路由/额度/租约算法。

### 12.1 共享包路径与导入方式

- 目录：`packages/agentpanel_common/`；新增 `packages/__init__.py` 使其成为仓库根下的可导入命名空间。
- 导入名：`packages.agentpanel_common.*`（仓库根在 `sys.path`，`python run.py` 与 `python -m base...` 均成立）。
- 共享包内**禁止**出现 `from base` / `import base`；L2 通过 `base/*` 同路径 shim 反向兼容。
- 不引入 `pyproject.toml`/editable install（P1 用仓库根路径导入；P5 容器化时再打包 wheel）。

### 12.2 搬运清单（唯一来源迁入共享包）

| 共享包路径 | 来源 | 约束 |
|---|---|---|
| `masking.py` | `base/common/masking.py` | 原样搬运，零外部依赖 |
| `upstream/__init__.py`、`client.py`、`config.py`、`egress.py` | `base/common/upstream/*` | 仅依赖 httpx；内部 import 改指共享包 |
| `gateway/constants.py` | `base/common/gateway/constants.py` | 原样搬运 |
| `gateway/contracts.py` | 新增 | 错误类型映射 + 幂等/缓存键前缀（§12.6） |
| `models/base.py` | `base/common/model.py` | 去掉 `base.common.setting` 依赖；`DATETIME_FORMAT` 固定 `%Y-%m-%d %H:%M:%S` |
| `models/quota.py`、`binding.py`、`reservation.py` | `base/common/quota/models/*` | 类名/表名/字段/索引完全不变 |
| `models/harness.py`、`model_price.py`、`service_credential.py` | `base/plugins/harness/models/*` | 类名/表名/字段/索引完全不变 |
| `config.py` | 新增 | 配置契约 + INI/ENV 解析（§12.4） |
| `log.py` | `base/common/log.py` 的纯日志逻辑 | 参数化 `app_name/debug/log_dir/elk_enabled`，不读 `settings` |
| `db.py` | 新增 | `build_tortoise_orm()`、共享模型清单、`init_db()/close_db()`；**不迁移、不建表** |

**留在 L2、不迁**：`base/common/setting.py`、`base/common/plugin_manager.py`、`base/common/database.py`（迁移执行方）、`base/common/cache.py`、`base/common/health.py`、`base/common/exceptions.py`、`base/common/quota/services/*`、`base/common/gateway/*` 其余运行代码（P2/P3 再迁 `services/`）。

### 12.3 兼容层（同路径 re-export，禁止再定义表/逻辑）

以下文件改为薄 shim（`from packages.agentpanel_common.X import *` 或显式导出）：

1. `base/common/masking.py`
2. `base/common/upstream/__init__.py`、`client.py`、`config.py`、`egress.py`
3. `base/common/gateway/constants.py`
4. `base/common/model.py`
5. `base/common/quota/models/quota.py`、`binding.py`、`reservation.py`
6. `base/plugins/harness/models/harness.py`、`model_price.py`、`service_credential.py`

**import 变更面**：现有 155 个引用文件无需改动；唯一必须改的是模型注册清单：
`base/common/setting.py::get_model_list()` 中把
`base.common.quota.models.quota|binding|reservation`、
`base.plugins.harness.models.harness|model_price|service_credential`
替换为对应 `packages.agentpanel_common.models.*`。`core` 与其它插件模型扫描逻辑保持不变。
`aerich`/迁移目录若有模型路径引用一并核对（`pyproject.toml`、`migrations/`）。

### 12.4 manifest 三拆

| 文件 | 归属 | 内容 |
|---|---|---|
| `base/plugins/harness/manifest.json` | L2 | 插件元数据 + `routes/models/schemas/permissions`；`config` 仅保留 `hold_ttl_seconds`、`fail_closed`、`lock_runtime_version`、`session_format*`、`model_credential`、`runtime`、`egress`、`approval`，新增 `gateway_issuance`（租约签发：`lease_ttl_seconds`、`renew_ttl_seconds`、`max_lease_ttl_seconds`、`tenant_lease_ttl_seconds`、`max_rpm`、`public_base_url`）。**删除 `config.gateway` 与 `config.orchestration`。** |
| `services/gateway/manifest.json` | L3 网关 | 服务元数据 + `config.gateway`：数据面全部键（`deployment=standalone`、`enabled`、`host/port`、`public_base_url`、`lease_cache_ttl_seconds`、`fail_closed`、`provider_domain_allowlist`、`allow_loopback`、`strip_request_fields`、上游超时/重试/连接池/TLS、`lease_budget_tokens` 及限额键、`reconciliation`）。不含租约签发 TTL、策略、凭据、管理台配置。 |
| `services/orchestration/manifest.json` | L3 编排 | 服务元数据 + `config.orchestration`：`enabled/deployment/host/port/public_base_url/mode/write_enabled/l2_internal_base_url/internal_timeout_seconds/internal_allowed_ips/allow_remote_bind/policy_in_l3/reconcile_in_l3/auth_timestamp_window_seconds/l2_service_id/l2_service_secret_env`。 |

读取方式：
- `base/common/plugin_manager.get_manifest("harness")` **只服务 L2**；
- 新增 `packages/agentpanel_common/config.py::load_manifest(path)`（简单 JSON 读取 + 进程内缓存），L3 两个入口各自读自己的 manifest；
- L3 配置 = 自己的 manifest 默认值 ← 环境变量覆盖（§12.5），不再经过 `plugin_manager`；
- L2 租约签发改读 `base/common/gateway/config.py::issuance_config()`（来自 L2 manifest `config.gateway_issuance`）；`gateway_lease_service.py` 中 `gateway_config()` 的 6 个签发字段全部改走 `issuance_config()`。

### 12.5 配置契约（共享包 `config.py`）

字段描述 `Field(name, env, type, required, default, secret, manifest_path)`；缺失/类型不符统一抛
`ConfigError`，消息一次性列出全部字段名（不含值）；进程启动阶段即失败（fail-closed）。

**L2（`load_l2_config(config.conf)`）**：沿用现有 `db/redis/log/deploy` section 与 fallback，不新增必填。
仅 L2 需要的字段（`app.*`、CORS、SMTP、JWT/安全、审计、RabbitMQ、Qdrant 等）**不进入 L3 契约**。

**L3 通用（两个入口共用，§5.2）**：

| 字段 | 类型 | 必填 | 默认 | secret |
|---|---|---|---|---|
| `DB_HOST` | str | 是 | — | 否 |
| `DB_PORT` | int | 否 | 15432 | 否 |
| `DB_NAME` | str | 是 | — | 否 |
| `DB_USER` | str | 是 | — | 否 |
| `DB_PASSWORD` | str | 是 | — | 是（支持 `DB_PASSWORD_FILE`） |
| `DB_MINSIZE`/`DB_MAXSIZE`/`DB_TIMEOUT`/`DB_COMMAND_TIMEOUT` | int | 否 | 5/20/30/30 | 否 |
| `REDIS_ENABLED` | bool | 否 | true | 否 |
| `REDIS_HOST` | str | 否 | 127.0.0.1 | 否 |
| `REDIS_PORT` | int | 否 | 6379 | 否 |
| `REDIS_DB` | int | 否 | 0 | 否 |
| `REDIS_PASSWORD` | str | 是（redis enabled 时） | — | 是（支持 `REDIS_PASSWORD_FILE`） |
| `LOG_DIR` / `LOG_LEVEL` | str | 否 | `<repo>/logs` / INFO | 否 |

**网关（`GW_*`，manifest `config.gateway` 为默认值来源）**：按 Spec §5.4 全量映射；`GW_PUBLIC_BASE_URL`、`GW_FAIL_CLOSED=true`、`GW_PROVIDER_DOMAIN_ALLOWLIST` 非空为硬校验；`GW_ALLOW_ENV_FALLBACK/GW_ALLOW_DIRECT_PROVIDER` 固定拒绝为 true；`GW_HOST/GW_PORT` 默认取 manifest（`127.0.0.1/9999`）。

**编排（`ORCH_*`，manifest `config.orchestration` 为默认值来源）**：按 Spec §5.3 全量映射；`ORCHESTRATION_SERVICE_SECRET` 必填（支持 `_FILE`），`ORCH_L2_BASE_URL`、`ORCH_PUBLIC_BASE_URL` 必须 http(s)，`deployment=standalone`，非回环必须 `ORCH_ALLOW_REMOTE_BIND=true`，`write_enabled` 显式。

**解析实现**：
- `load_env(contract)`：`_FILE` 优先 → env → default；bool 接受 `true/false/1/0/yes/no`；list 逗号分隔；dict 接受 JSON。
- `resolve_component(manifest_path, contract, prefix)`：manifest 默认值 ← env 覆盖 → 校验。
- `load_l2_config(path)`：`configparser` 读取，字段名与现有 `setting.py` 完全一致。
- 任何必填缺失/类型不符：`ConfigError` 携带 `missing_fields` / `invalid_fields`，入口在 `build_app()` 前显式捕获并以退出码 2 终止。

### 12.6 网关契约模块（`gateway/contracts.py`）

- 错误类型映射（与 `gateway/app.py` 现有响应一致）：`gateway_auth_error`（401/403）、`gateway_rate_limit_error`（429）、`invalid_request_error`（400）、`gateway_error`（其余）。
- 幂等键前缀：`GATEWAY_IDEM_PREFIX = "gw:"`（`gateway/service.py` 记账）、`HARNESS_IDEM_PREFIX = "harness:"`（Harness 侧确定性键）。
- 缓存键前缀：`LEASE_CACHE_PREFIX = "gw:lease:state:"`（`gateway/lease_auth.py`）。
- 稳定业务错误码：`orchestration_dependency_unavailable`、`orchestration_not_primary`、`quota_exceeded`、`quota_hold_closed`、`quota_reservation_in_progress`（与现有实现逐字一致）。
- 现有模块改为从该处导入，禁止各自写字面量。

### 12.7 三个独立入口

| 入口 | 启动命令 | 自检 | 独立性要求 |
|---|---|---|---|
| L2 | `python run.py` | 现有 H-1/H-2 preflight + `init_app()` | 可 import `plugin_manager`/`base.plugins.harness` |
| 网关 | `python -m base.common.gateway.server` | `validate_gateway_config()`，DB/Redis 预热 | 不 import `run.py`/`base.start`/`base.plugins.harness.server`；配置不 import `plugin_manager` |
| 编排 | `python -m base.plugins.harness.server` | 只读库写拒绝 + `service_credential` 可读 | 不 import `run.py`/`base.start`/网关入口；配置不 import `plugin_manager` |

验证：`grep -R "run\.py|base\.start" base/common/gateway base/plugins/harness/server.py`、
`grep -R "plugin_manager" base/common/gateway/config.py base/plugins/harness/services/orchestration_config.py` 均应为空。

### 12.8 无法在 P1 硬拆的耦合点（只报告，不改）

| # | 位置 | 耦合 | P1 处理 |
|---|---|---|---|
| C1 | `base/common/gateway/service.py::_resolve_provider_credential` → `base.plugins.harness.services.model_credential_service` | 网关数据面经 L2 插件服务解析 provider 凭据；该服务再依赖 `base.plugins.llm.models.*` 与 `plugin_manager` | 保持函数内懒加载不改；网关启动模型清单额外包含 `base.plugins.llm.models.{api_key,model,provider}`；P2/P3 抽 `credential_resolver` 后删除 |
| C2 | `base/common/gateway/audit.py` → 懒加载 `HarnessAuditService` | 网关审计写 L2 域服务 | 保留；audit_service 依赖的模型已是共享包 |
| C3 | `base/common/gateway/budget.py` → `base.common.quota.services.{plan_service,quota_service}` | 网关预算预检复用 L2 配额域服务 | 保留（P1 不迁 domain）；仅确认其模型依赖已在共享清单 |
| C4 | `base/common/plugin_manager.py::plugin_manager` 全局单例 | L2 插件系统 | 仅 L2 保留；L3 两侧配置 loader 不再引用 |

### 12.9 验证步骤（每阶段完成即报告）

1. **共享包与兼容层**：`.venv\Scripts\python.exe -c "import packages.agentpanel_common.models.harness as m; print(m.HarnessRun.__module__)"` → 输出 `packages.agentpanel_common.models.harness`；`python -c "import base.plugins.harness.models.harness"` 仍成功且类对象相同。
2. **模型注册**：Tortoise `describe_model()` 表名与拆分前一致（抽查 `harness_gateway_lease`/`usage_record`/`quota_reservation`）。
3. **L2 启动**：`python run.py`（9998）→ `GET /health/health` 返回 `status=healthy`（database/redis 子项）。
4. **网关启动**：先注入 `DB_*`/`REDIS_*`，`python -m base.common.gateway.server`（9999）→ `GET /health` 返回 `status=ok`、`deployment=standalone`、`fail_closed=true`。
5. **编排启动**：注入 `DB_*`/`REDIS_*`/`ORCHESTRATION_SERVICE_SECRET`，`python -m base.plugins.harness.server`（9100）→ `GET /health/health` 与 `GET /health/orchestration` 均 healthy。
6. **业务链路**：L2→L3 会话读仍通（L3 停时 503）；L2 签发租约→网关鉴权通过并写 `usage_record(source=gateway, idem_key` 以 `gw:` 开头；编排预占/结算仍只经 L2 `/internal/v1/harness/quota/*`，`quota_reservation.counter_mode=redis`。
7. **负向**：去掉 `DB_PASSWORD` 启动网关 → 退出码 2 且日志包含 `DB_PASSWORD`；`GW_FAIL_CLOSED=false` → 启动失败。

### 12.10 交付物

- 代码：§12.2/§12.3/§12.4/§12.5 全部文件；
- 报告：`reports/ops/l3-split-p1-report.md`（搬走了什么/留下什么/import 变更面/三入口 health 证据/耦合点 C1–C4/回滚方式）。

---

## 13. P3 实施规格（L3 网关独立工程 `services/gateway`）

> 状态：**已确认（2026-11-08，用户选择 `1B 2A 3A 4A`）**。本节把 P3 的依赖取舍、文件清单、验证与回滚写到可执行粒度；
> 原则与 P2 同构：搬代码、共享单一来源、L2 全部留 shim、独立入口、配置契约独立；迁移期 L2 / L3 编排 / 网关三者并行可用。

### 13.1 网关对 `base.*` 的现存依赖（只读核实结论）

| # | 网关位置 | 依赖 | 能否干净剥离 | P3 处理 |
|---|---|---|---|---|
| G1 | `service.py` | `base.plugins.harness.services.model_credential_service` → `base.plugins.llm.models.*` + `plugin_manager` | 可（C1） | 抽共享 `credential_resolver`；llm 模型迁共享包，L2 留 shim |
| G2 | `audit.py` | `base.plugins.harness.services.audit_service` | 可 | 直接用共享 `domain/audit_service.py`（已是单一来源） |
| G3 | `budget.py` | `base.plugins.harness.models.harness`（Budget/Concurrency/Lease） | 可 | 改共享 `models/harness.py`（L2 已是 shim） |
| G4 | `budget.py` / `lease_auth.py` / `server.py` | `base.common.cache.RedisCache`（**读 `config.conf`**，经 `base.common.setting`） | 可 | `RedisCache` 迁共享 `cache.py`，显式 `configure(RedisConfig)`；L2 shim 复原 settings |
| G5 | `budget.py` | `base.common.quota.services.{quota_service,plan_service}`（Redis 预占 / DB 兜底 / 套餐解析） | **否（存在结构性冲突）** | 见 D-P3-2 |
| G6 | `budget.py` | `base.common.quota.metrics`（Prometheus 计数） | 可 | 随 D-P3-2：A 保留；B 迁共享 |
| G7 | `budget.py::maybe_auto_revoke` | `base.plugins.harness.services.gateway_lease_service.revoke_internal` | 可 | 吊销核心迁共享 `domain/lease_revoke.py`；L2 委托 |
| G8 | `lease_auth.py` | `base.common.gateway.config.{gateway_config,lease_cache_ttl_seconds}` | 可 | 共享 `domain/lease_auth.py` 改为注入 config provider；L2 shim 注入 `issuance_config` |
| G9 | `service.py` / `router.py` / `budget.py` | `base.common.upstream` | 已是 shim | 直接改共享 `packages.agentpanel_common.upstream` |
| G10 | `auth.py` / `budget.py` | `base.common.gateway.constants` | 已是 shim | 直接改共享 `services.gateway.common.constants` |

### 13.2 决策结果（用户已确认 `1B 2A 3A 4A`）

| ID | 确认结果 | 约束 / 验收 |
|---|---|---|
| D-P3-1 | **A**：`RedisCache` 迁共享 `cache.py`（显式 `configure(RedisConfig)`），`base/common/cache.py` 改 shim | 网关不读 `config.conf`；D2 硬超时/熔断语义不变；L2 行为由 shim 复原 |
| D-P3-2 | **B**：`quota_service.py` + `plan_service.py` + `metrics.py`（含 `prometheus.py`）迁共享包，L2 留 shim；`plan_service` 的 `cus/usr` 解析改为**注入解析器**（L2 注入 ORM 版、网关注入只读 SQL 版） | **双实现必须对拍**：同一 fixture 下逐字段一致，覆盖无套餐/多套餐优先级/组织套餐/客户等级/过期/停用/无会员/无角色等分支；不等价即停工上报，禁止“近似等价” |
| D-P3-3 | **A**：`LLMProvider/LLMModel/LLMApiKey/enums` 迁共享 `models/`，L2 留 shim；共享 `credential_resolver` 注入配置 | 保持 `Q(__iexact)`/`prefetch_related`/`is_available` 语义逐字一致；§4.2 已覆盖，无需新增凭据表白名单 |
| D-P3-4 | **A**：`lease_auth` 迁共享 `domain/lease_auth.py`（config provider 注入）；`revoke_internal` 核心迁共享 `domain/lease_revoke.py`，L2 委托 | 网关去 `base.plugins.harness.services`；L2 签发/吊销路径引用不变 |
| D-P3-5 | **A**：L2 `base/common/gateway/*` 12 个模块**全部改 shim**，网关运行代码由共享包承载（P2 同构）；L2 `config.py` 保留 `issuance_config()` 与 `gateway_config()` 供 shim 注入 | L2 现有 import 路径不变；embedded 挂载仍停用，回滚以 git 为准 |

### 13.3 文件清单

**新增 `services/gateway/`（仅入口与配置，运行代码在共享包）**

| 文件 | 内容 |
|---|---|
| `run.py` | 与 `services/orchestration/run.py` 同构：注入 `PROJECT_DIR`/`REPO_ROOT` → `from app.main import main` |
| `app/__init__.py` | — |
| `app/config.py` | 数据面配置：`DEFAULTS` + `_GATEWAY_ENV_OVERRIDES` + `gateway_config()` + `validate_gateway_config()` + `gateway_upstream_config()` + `lease_cache_ttl_seconds()`；默认值读 `services/gateway/manifest.json`；删除 `issuance_config/runtime_config/reconciliation_config/validate_issuance_config` |
| `app/plan_resolver.py` | 网关只读 SQL 套餐解析器（实现共享 `PlanResolver` 协议）：`cus` 查 `customer_membership`/`customer_membership_level`，`usr` 查 `user_role`/`role`；仅用 §4.2 白名单列，异常时与原 ORM 一致返回 `None`/`[]` |
| `app/main.py` | `load_l3_common` 失败 `SystemExit(2)`；`gateway.runtime.configure(app.config.gateway_config, app.config.gateway_upstream_config, app.config.lease_cache_ttl_seconds)`；`plan_service.configure(app.plan_resolver.SqlPlanResolver())`；lifespan：`RedisCache.configure(_L3_CONFIG.redis)` → `Tortoise.init(shared_model_modules() + gateway_dependency_modules())` → 预热；`build_app()` 校验 `deployment=standalone` |
| `app/health.py` | 保留 `/health` 形状；新增 `/health/health`（DB `SELECT 1` + Redis `PING`） |
| `tests/fake_provider.py` | 本地假 provider（OpenAI 兼容 JSON/SSE；回显请求体；仅 127.0.0.1）；验证期临时启动，禁止真实 provider |
| `tests/plan_parity.py` | ORM 解析器 vs 只读 SQL 解析器对拍脚本（见 §13.6） |
| `tests/gateway_cases.py` | V1–V12 用例脚本；用例结束清理临时 fixture |

**共享包：网关运行代码（D-P3-5=A，L2 全部 shim）**

| 文件 | 来源/说明 |
|---|---|
| `services/gateway/common/runtime.py`（新） | `configure(config_provider, upstream_provider, lease_ttl_provider)` + 访问器；不 import `base` |
| `services/gateway/common/lease_auth.py`（新） | `base/common/gateway/lease_auth.py` 原样迁入；配置经 `runtime` 取 |
| `services/gateway/common/{auth,audit,service,budget,router,app,logging,health}.py`（新） | 原 8 个网关模块迁入；import 改共享模型/upstream/constants/domain/配额域；删除 embedded 形态 |
| `services/gateway/common/{constants,contracts}.py` | 已存在，按需补 `GatewayConfigError` |

**共享包：配额域（D-P3-2=B）**

| 文件 | 来源/说明 |
|---|---|
| `packages/agentpanel_common/prometheus.py`（新） | `base/common/prometheus.py` 迁入 |
| `packages/agentpanel_common/quota/metrics.py`（新） | `base/common/quota/metrics.py` 迁入，import 改共享 prometheus |
| `packages/agentpanel_common/quota/services/quota_service.py`（新） | `base/common/quota/services/quota_service.py` 迁入，import 改共享 cache/errors/metrics/models |
| `packages/agentpanel_common/quota/services/plan_service.py`（新） | 同文件迁入；新增 `PlanResolver` 协议与 `configure(resolver)`；`_customer_level_type`/`_user_role_codes` 委托注入解析器（未注入时返回 `None`/`[]`，与原异常分支一致） |

**共享包：模型与域（D-P3-3=A / D-P3-4=A）**

| 文件 | 来源/说明 |
|---|---|
| `packages/agentpanel_common/models/llm_{enums,provider,model,api_key}.py`（新） | `base/plugins/llm/models/*` 原样迁入；表名/字段/属性不变 |
| `packages/agentpanel_common/domain/credential_resolver.py`（新） | 解析逻辑迁入；`configure(defaults, env_fallback, env_names)`；不 import `base`/`plugin_manager` |
| `packages/agentpanel_common/domain/lease_auth.py` | 见上（亦可归入 gateway 包，择一保持单一来源） |
| `packages/agentpanel_common/domain/lease_revoke.py`（新） | `revoke_internal` 核心：共享 `HarnessGatewayLease` 更新 + `invalidate_lease_cache` + `HarnessAuditService` |
| `packages/agentpanel_common/db.py` | `gateway_dependency_modules()` = 共享 llm 模型（只读凭据解析用）；**不再注册** `base.core.users.models.*`（套餐解析走只读 SQL） |

**L2 shim / 委托（全部行为不变）**

| 文件 | 改动 |
|---|---|
| `base/common/gateway/*.py`（12 个） | 全部改 shim：`configure` 共享 `runtime`（注入 L2 的 `gateway_config`/upstream/ttl）后 re-export 共享实现；`config.py` 保留 `issuance_config()`/`gateway_config()` |
| `base/common/cache.py` | shim：`from base.common.setting import settings` → `configure(...)` → re-export `RedisCache` 等 |
| `base/common/prometheus.py`、`base/common/quota/metrics.py` | shim re-export 共享实现 |
| `base/common/quota/services/quota_service.py` | shim re-export 共享实现（供 L2 API 引用） |
| `base/common/quota/services/plan_service.py` | shim re-export 共享 `PlanService`，并 `configure(L2OrmPlanResolver())` 注入 ORM 解析器 |
| `base/common/quota/services/plan_resolver.py`（新，非 shim） | L2 ORM 解析器：保留原 `_customer_level_type`/`_user_role_codes` 懒加载实现，作为对拍基准 |
| `base/plugins/llm/models/{enums,provider,model,api_key}.py` | shim re-export 共享类；`__init__.py` 仍导出 `LLMUsageRecord`（留 L2） |
| `base/plugins/harness/services/model_credential_service.py` | `resolve`/两类型 re-export 共享 resolver + `configure_l2()`；`list_configured()` 保留（读共享 llm 模型） |
| `base/plugins/harness/services/gateway_lease_service.py` | `revoke_internal` 委托共享 `domain/lease_revoke.py` |

### 13.4 配置契约（网关）

- 默认值来源：`services/gateway/manifest.json` 的 `config.gateway`；覆盖来源：`GW_*`（§5.4 全量）。
- 硬校验与现有 `validate_gateway_config()` 等价：`fail_closed=true`、`public_base_url` http(s)、`provider_domain_allowlist` 非空、TTL 合法、重试/连接池合法、`GW_ALLOW_ENV_FALLBACK`/`GW_ALLOW_DIRECT_PROVIDER` 必须为 false。
- DB/Redis 来源：`load_l3_common()`（`DB_*` / `REDIS_*`，支持 `_FILE`）；网关进程**不读** `config.conf`。
- 凭据解析配置：`defaults=(None,None)`、`env_fallback=False`（与 L2 manifest 现值一致）；不新增环境变量。
- L2 的 `issuance_config()` 保持读 L2 manifest `config.gateway_issuance`，仅供租约签发。

### 13.5 验证矩阵（仅本地假 provider，禁止真实 provider）

| # | 用例 | 通过判据 |
|---|---|---|
| V1 | 骨架启动（`GW_PORT=9990`，旧 9999 不动） | `/health` → `ok/standalone/true`；`/health/health` → database/redis 均 healthy |
| V2 | 负向启动 | 缺 `DB_PASSWORD` → 退出码 2；`GW_FAIL_CLOSED=false`、空白名单、非法 `GW_PUBLIC_BASE_URL`、`GW_ALLOW_ENV_FALLBACK=true` → 退出码 2 |
| V3 | 租约鉴权 | 缺失/JWT/格式错 → 401；已吊销 → 401；已过期 → 401；会话关闭 → 403；run 终态 → 403；超 RPM → 429 |
| V4 | 出网白名单 | 非白名单域名 → 403，且假 provider 未收到请求；`GW_ALLOW_LOOPBACK=false` 时 127.0.0.1 → 403 |
| V5 | 字段剥离 | 假 provider 回显：`dsh_session_log` 不存在，其余字段逐字不变 |
| V6 | SSE 逐字节透传 | 假 provider 产出固定帧序列；客户端收到的字节串与上游逐字节相等（除截断场景） |
| V7 | usage 记账 | `usage_record` 每请求恰好 1 行，`source=gateway`、`gateway_key=<lease_id>`、`idem_key` 以 `gw:` 开头、`resource_type=llm_token`，token 数与假 provider 上报一致；失败请求 `resource_type=gateway_error` 且 `amount=0` |
| V8 | 预算/并发 | 租约 `budget_tokens` 耗尽 → 402 `quota.lease_budget_exhausted` 且自动吊销；并发上限 1 时第二路 429；流式越界截断 → `billing_status=partial` + 截断帧 |
| V9 | Redis 缓存 | 鉴权后存在 `gw:lease:state:<lease_id>`（TTL≈8s）；吊销后写穿删除 |
| V10 | DB 兜底 | `REDIS_ENABLED=false` 启动 → 预检/结算走 DB，`quota_account.used`/`harness_gateway_budget` 正确变更，`usage_record` 仍唯一 |
| V11 | 审计 | 鉴权拒绝/额度拒绝/吊销事件 `event_source=gateway` |
| V12 | 与旧网关等价 | 同一租约/同一请求体在 9990（新）与 9999（旧）分别调用假 provider，响应体/状态码/记账字段一致 |
| V13 | 套餐解析对拍（硬门槛） | 见 §13.6；任一分支不等价 → 停止实施并上报 |

### 13.6 套餐解析对拍（D-P3-2=B 的硬门槛）

**目的**：`PlanService` 迁共享包后，L2 ORM 解析器与网关只读 SQL 解析器必须对同一批数据给出完全相同的 `resolve_plan` 结果；不接受“近似等价”。

**对拍方式**：

1. 在同一测试库内用事务或临时 fixture 构造数据，结束后回滚/清理；
2. 分别以 `plan_service.configure(L2OrmPlanResolver())` 与 `configure(SqlPlanResolver())` 调用共享 `PlanService.resolve_plan(owner_type, owner_id)`；
3. 比较字段：`plan.id` / `code` / `name` / `scope` / `status` / `quota_items`（`None` 表示未命中，需两侧同为 `None`）；
4. 另单独比较解析键：`_customer_level_type(customer_id)` 与 `_user_role_codes(user_id)` 的返回值（含异常分支）。

**必须覆盖的 fixture 分支**：

| # | 场景 | 预期 |
|---|---|---|
| P1 | 无任何绑定 | 两侧 `None` |
| P2 | 多套餐同主体命中，`priority` 不同 | 取 `priority` 大者 |
| P3 | `priority` 并列 | 取 `plan_id` 大者 |
| P4 | 组织套餐 `org` | 命中 `bind_type=organization` |
| P5 | 客户等级套餐（active 且未过期） | 命中对应 `level_type` |
| P6 | 客户会员记录过期 | 回落 `regular` 绑定 |
| P7 | 客户无会员记录 | 回落 `regular` 绑定 |
| P8 | 会员等级为 `null` 或 `level_type` 缺失 | 回落 `regular` |
| P9 | 角色套餐（用户多激活角色） | 命中最高优先级角色绑定 |
| P10 | 角色 `is_active=false` | 该角色不参与 |
| P11 | 用户不存在 | 两侧 `[]` → `None` |
| P12 | 绑定套餐 `status=disabled` | 两侧 `None` |
| P13 | 客户不存在 / 查询异常 | 两侧 `None`（异常仅记 warning，不抛出） |
| P14 | 表存在但 `expire_time` 为 naive 时间 | 两侧按 UTC 判过期一致 |

**停止条件**：任一行两侧结果不同（含 `None` 语义、字段值、异常分支），立即停止 P3 实施，保留对拍输出并向用户报告，不得用“近似等价”继续。

### 13.7 回滚（可执行动作）

1. 停新进程：结束 `services/gateway/run.py` 进程（保留代码目录，不删）；
2. 旧网关仍在 9999 运行则无需动作；若已切换到新进程，重新启动 `-m base.common.gateway.server`。P3 代码尚未提交时，工作区的 `base.common.gateway` 为 shim（行为等价）；若判定 shim 异常，用 `git worktree add --detach <临时目录> 02bc87f` 从基线提交启旧入口（已在 9996 预演）；P3 提交后则用 `git revert <P3提交>` 还原；
3. 共享 shim 为行为等价层，无需回退 git；如判定 shim 异常：`git switch --  <单个 shim 文件>` 后重启对应进程；
4. 数据面无需迁移：未新增表/键，仅读现有表；`gw:*` 键格式不变。

### 13.8 P3 新增待办（写入 P4/P5）

- T4.11（D-P3-2=B 后的收口）：确认 L2 无 `base.common.quota.services` 外部引用后，删除 `plan_service/quota_service/metrics` 的 L2 shim 与 `plan_resolver.py` 过渡注入；保留 `base.common.quota.services` 路径直到 P4 删除边界。
- T4.12（新增）：L2 `base/common/gateway/*` shim 随 embedded 挂载一并删除（P4 T4.2），删除前确认 `gateway_lease_service` 只引用 `issuance_config` 与共享 `lease_auth`。
- P5 前置复核：`services/gateway` 不得出现 `from base` 导入（含 `base.core.users`）；`gateway_dependency_modules()` 仅共享模型。
- **套餐规则漂移防护（1B 强制）**：套餐规则改动必须同步共享包 `packages/agentpanel_common/quota/services/plan_resolver.py`（唯一实现，L2 与网关共用）；改动后必须运行黄金用例 `services/gateway/tests/plan_golden.py`，要求 P1–P14 全 PASS（20/20）；新增套餐分支必须补黄金 fixture 并在 §13.6 登记。

## 14. P4 网关计费口径（`usage_record.cost`）

- **计费输入** = 非缓存输入 + cache_read + cache_write（三者互不重叠，`tokens_in` 已扣除 cache_read）；output 单独计，reasoning 不重复计；单价按 `model_price.*_price_per_1k` 每 1K token。
- **价格解析**：`ModelPriceService.resolve(provider, model)`，只取 `status=active` 且命中生效区间的行；provider 为空时按 model 最新价格版本。
- **舍入**：`Decimal` 按 6 位小数 `ROUND_HALF_UP`（与 `usage_record.cost numeric(12,6)` 对齐）；不设最低计费下限。
- **缺价**：`cost=0`、`currency=CNY`、`price_snapshot.missing_price=true`；请求正常返回，不因缺价失败。
- **舍入归零**：原始金额 > 0 且 6 位舍入后为 0 时，`price_snapshot.rounded_to_zero=true`，并写入 `price_snapshot.unrounded_cost`（未舍入原值）。
- **失败请求**（`status>=400` 或 `error`）：不查询价格，`amount=0`、`cost=0`，保持现状。
- `price_snapshot` 同时保留网关元数据（`gateway_status/stream/attempt/usage_missing/estimated/truncated/over_budget`）。
- **验证方式**：假 provider + 构造 usage（不调用真实 key），断言正常计价、缺价、舍入归零三条分支。

## 15. 套餐解析器事务约束（唯一 SQL 实现）

`packages/agentpanel_common/quota/services/plan_resolver.py` 通过 `tortoise.connections.get("postgres").execute_query_dict` 直接执行只读 SQL，**不参与调用方已打开的 `in_transaction()` 事务上下文**。

- **当前调用点（均不在事务内，符合约束）**：
  - `packages/agentpanel_common/quota/services/quota_service.py:215`
  - `packages/agentpanel_common/quota/services/quota_service.py:258`
  - `packages/agentpanel_common/quota/services/quota_service.py:1113`
  - `services/gateway/common/budget.py:290`
  - `base/plugins/agent/services/execution_service.py:174`
- **新增调用点禁止**在 `in_transaction()` 内调用 `PlanService.resolve_plan()` / `SqlPlanResolver`；事务内读取不会被解析器感知，可能读到事务外的旧快照。
- **如确需在事务内读取未提交数据**：必须先改造解析器为事务感知实现（复用当前事务连接执行同一只读 SQL），补充黄金用例覆盖该场景，并更新本节调用点清单；不得让业务代码直接调用裸 SQL 解析器绕过约束。
- 解析器只允许 `SELECT`，不得引入任何写路径、`save()` 或事务开启/提交。
- 修改解析器或套餐规则时，仍须运行 `services/gateway/tests/plan_golden.py`（P1–P14，20/20）。
- 解析优先级（P6 修正）：`quota_plan_binding` 命中优先；未命中时回落到 `quota_account.plan_id`；两者都不存在时保持“未绑定”语义，不合成套餐。

---

## 16. 实施状态与 P6/P7 结论（2026-11-09）

### 16.1 阶段状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| P0–P3 | 完成 | 基线冻结、共享包、L3 编排/网关独立工程均已落地 |
| P4 | 完成 | L2 删除边界与内部 API 收口（本文件 §3） |
| P5 | 完成 | 两镜像 + compose 交付；三容器接管 `9998/9999/9100` |
| P6 | 完成 | T6.1–T6.8 全部通过，报告：`reports/ops/l3-split-acceptance.md` |
| P7 | 部分完成 | T7.1–T7.4 完成（T7.4 监控指标见 `reports/ops/l3-split-p7-metrics.md`）；T7.5（删除开关与旧代码、更新架构图）未开始，需 14 天观察期。演练记录：`reports/ops/l3-split-p7-report.md` |

### 16.2 P6 实测与设计假设的两处差异

1. **租约缓存由 Redis 承载，不是进程内存**：键 `gw:lease:state:<lease_id>`，TTL 默认 8s（`services/gateway/app/config.py`，允许 5–10s）。因此网关容器重启不会清空缓存，旧状态最迟在一个 TTL 后自然过期；吊销走写穿删除。该实现比进程内存更好：多实例共享一致视图、重启不丢状态，过期窗口由 TTL 硬约束。
2. **套餐解析改为“绑定优先 + 回落账户 `plan_id`”**：`PlanService.resolve_plan` 先查 `quota_plan_binding`；未命中时使用 `quota_account.plan_id`；两者都没有才按未绑定处理。修复了“有账户但未绑定”租户被静默不计量的缺口（`packages/agentpanel_common/quota/services/plan_service.py`，覆盖用例 `packages/agentpanel_common/quota/tests/test_resolve_plan.py`）。

### 16.3 已知限制

端口仅回环、`web_fetch`/`web_search` 可绕网关直连、DSH 原生审批无终端应答者、灰度仅为部署级二元切换——详见 `reports/ops/l3-split-acceptance.md` §8。`prepare-secrets.ps1` 的 `.env` 旧端口遗留已于 2026-11-09 16:44 修复（`9999/9100`）。原「L3 无 `/metrics` 与告警」缺口已由 T7.4 补齐，Alertmanager 亦于同日 16:46 接入（默认 receiver 为本地占位，正式通知渠道待运维配置，详见 `reports/ops/l3-split-p7-metrics.md` §8）；但重复结算/`used` 一致性与预占悬挂仍需人工 G1 抽查。


