# P1 Spec：Harness 编排层从 app 拆到 独立服务 独立服务

> 状态：待评审（本文档只定义方案与任务拆解，尚未编码）。
> 范围：Harness 编排域。网关数据面（9999）语义不变；租约签发、套餐/额度配置、用户组织权限、模型凭据仍归 app。
> 原则：每个阶段可独立上线、可独立回滚；管理台 6 个 Harness 页面全程可用；不调用真实 provider。

## 1. 目标与边界

### 1.1 搬到 独立服务（编排服务）

- 会话上下文组装与 `harness_session` 生命周期；
- run 生命周期：创建、claim/start、心跳、步骤/事件采集、完成、取消；
- 三档策略评估（allow / ask / deny）与审批联动；
- 额度预扣、结算、释放的**编排调用**（何时预扣/结算由 独立服务 决定）；
- `harness_audit_event` 的编排事件入库；
- 网关记账 vs 客户端上报对账的触发与结果落库；
- 编排域读接口（供 app 管理台只读调用）。

### 1.2 留在 app（业务/配置域）

- 用户、组织、权限、角色；
- 套餐、额度配置、额度账户与预占/用量的**执行**（QuotaService 仍在 app）；
- 模型开关、provider/model/api_key、价格配置；
- Harness 客户端凭据、身份映射配置；
- 策略规则配置（`harness_action_policy` / `harness_policy_rule` 的 CRUD）；
- 版本发布、知识库、报表、看板（看板只做聚合展示，数据经 独立服务 读接口）；
- 网关租约签发/续期/吊销（`/v1/harness/gateway/leases`）；
- 出网策略来源与快照（`/v1/harness/egress-policy/*`）。

### 1.3 明确非目标

- 不改 网关数据面（9999）的鉴权、白名单、记账、对账语义；
- 不改对账算法、额度中断、租约 TTL 行为；
- 不做跨库拆分（仍共享同一 PostgreSQL/Redis），但通过“单写者 + 只读接口”约束访问方式；
- 不一次性重写 Harness 服务层，按阶段搬运与代理。

## 2. 关键决策与取舍（已评审确认，2026-11-07）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 编排进程端口 | **独立进程 9100**，不与 9999 合并 |
| 2 | 多写者例外 | **接受**，但按来源隔离（见 2.3），`idem_key` 前缀分开 |
| 3 | 独立服务 直读 app 配置表 | **接受**，必须只读账号/视图 + 代码层禁止写 |
| 4 | 额度执行留 app | **P1 接受**，登记为 P2 技术债（见 §15） |
| 5 | 管理台 | **保持 app facade，前端零改动** |
| 6 | app 不可用 | **创建/结算 503 fail-closed**；只保心跳/事件/取消/查询；离线结算 outbox 登记 P2 |

### 2.1 编排服务端口：独立 9100（推荐 B）

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 并入现有 网关 9999 | 只多一组路由，部署简单 | 重启编排会打断模型流量；编排与数据面无法独立回滚，风险高 |
| B. 新进程 9100（推荐） | 独立上线/回滚/扩缩容；不动网关进程；契合此前“9100 内部预留” | 多一个进程；dsh 需要拆控制面/业务面 base_url；运维复杂度上升 |

结论：**新增 `base/plugins/harness/server.py`，`python -m base.plugins.harness.server` 监听 `127.0.0.1:9100`**；9999 网关进程保持不变。

### 2.2 跨域读取：独立服务 只读 app 配置表 + app 只走 独立服务 只读接口

- app → 独立服务：**只能**通过 `/internal/v1/harness/*` 只读接口（及少量显式写接口），不直连 独立服务 表。
- 独立服务 → app：低风险配置读取（客户端凭据、身份映射、组织归属、策略规则、价格、套餐绑定）使用**只读数据库角色/只读视图**；额度预扣/结算/释放等**写操作**必须调用 app 内部 API。
- 理由：app 进程挂掉但数据库可用时，独立服务 仍能完成鉴权、身份解析、策略评估与 run 心跳；若全部改为 app API，app 一停 独立服务 立即不可用。
- 代价：独立服务 与 app 表结构存在读耦合，需要只读账号与迁移协同；这是本方案最大的架构取舍。

### 2.3 已存在的多写者账本（已确认接受，按来源隔离）

| 表 | 写者 | 强制隔离规则 |
|---|---|---|
| `usage_record` | 网关、编排（经 app QuotaService） | 网关固定 `source=gateway`、`idem_key` 前缀 `gw:`；编排固定 `source=client`/`estimated`、`idem_key` 前缀 `orch:`。同一来源不得出现第二条写入路径 |
| `harness_audit_event` | 网关、编排、app（租约/出网/客户端管理） | 网关 `event_source=gateway`；编排 `event_source=orchestration`；app 既有来源（`api`/`policy`/`lease`）保持不变。禁止跨来源复用 `action` 名称 |

**必须同时改两边的取舍（记录在案，P1.2/P1.3 实施）**：现有编排写 `usage_record` 用 `source=harness` / `source=provider`，且对账靠 `idem_key__startswith="harness:"` 识别客户端上报；改成 `source=client` / `idem_key="orch:..."` 后，**对账查询和看板过滤必须同版本改**，否则客户端上报会被漏算。处理方式：

1. 写入侧：编排新写 `source=client`（实际值）、`source=estimated`（估算值）、`idem_key="orch:<run_no>:<node>:<seq>"`；
2. 读取侧：对账与看板同时识别 `orch:` 与历史 `harness:` 前缀，`client` 与历史 `provider` 视为同一语义（兼容窗口内双读，不双写）；
3. 完成窗口后只保留新前缀/新来源，历史数据不回写。

### 2.4 额度执行留在 app（通过内部 API 调用）

- `quota_account` / `quota_reservation` / `usage_record` 仍由 app 的 `QuotaService` 写，保持事务与幂等语义不变；
- 独立服务 负责“何时预扣/结算/释放”的编排，通过 app 内部 API 执行；
- 因此 **app 不可用时，独立服务 无法创建 run、无法结算**，必须 fail-closed 返回 503，不伪造成功。
- 如需 app 不可用时继续结算，需引入 独立服务 本地 outbox + 补偿（不在 P1 范围，登记为 P2，见 §15）。

### 2.5 迁移期只代理、不双写

- app 旧客户端路由通过配置开关 `orchestration.mode=proxy` 转发到 独立服务，**不在本地落库**；
- 任一时点只有一侧写编排表：开关为 `app` 时 app 写、独立服务 写接口拒绝；开关为 `proxy` 时 独立服务 写、app 只转发；
- 不做双写，避免 quota hold、审计顺序、幂等与对账被双重写入破坏。

## 3. 服务拓扑与端口

| 服务 | 端口 | 启动方式 | 职责 |
|---|---|---|---|
| app 业务 API | 9998 | `python run.py` | 用户/组织/权限、套餐与额度执行、模型/凭据/价格、客户端与身份配置、策略 CRUD、租约、出网策略；管理台读接口（facade） |
| 网关数据面 | 9999 | `python -m base.common.gateway.server` | `/chat/completions`、网关记账、租约校验；语义不变 |
| 编排服务 | 9100（新） | `python -m base.plugins.harness.server` | 会话/run/步骤/事件、策略评估、审批、对账触发、编排审计、内部读接口 |

绑定：9100 与所有 `/internal/*` 默认仅监听 `127.0.0.1`，并叠加服务凭据 + IP 允许清单（默认 `127.0.0.1/::1`），**不允许内网匿名**。

启动顺序：数据库/Redis → app(9998) → 编排(9100) → 网关(9999) → 客户端。每步以健康检查为门禁（见 §8）。

### 3.1 新增配置（manifest `config.orchestration`）

```json
{
  "enabled": true,
  "deployment": "standalone",
  "host": "127.0.0.1",
  "port": 9100,
  "public_base_url": "http://127.0.0.1:9100",
  "mode": "app",
  "write_enabled": false,
  "app_internal_base_url": "http://127.0.0.1:9998",
  "internal_timeout_seconds": 5,
  "internal_allowed_ips": ["127.0.0.1", "::1"],
  "policy_in_orchestration": false,
  "reconcile_in_orchestration": false
}
```

- `mode`: `app`（app 本地处理）/ `proxy`（app 转发 独立服务）；
- `write_enabled`: 编排写接口总开关，默认关闭，切换阶段才打开；
- manifest 按进程缓存，改配置需重启对应进程（运维门禁需写明）。

## 4. 域与表归属

| 表 | 归属/写者 | 跨域读取方式 |
|---|---|---|
| `harness_client` | app | 独立服务 只读（客户端鉴权、吊销即时生效） |
| `harness_identity` | app | 独立服务 只读（会话身份/owner 解析） |
| `harness_session` / `harness_run` / `harness_step` | **编排** | app 经 `/internal/v1/harness/*` 只读 |
| `harness_audit_event` | 编排 + 网关 + app（例外，见 2.3） | app 经 独立服务 只读接口；独立服务 直读 DB |
| `harness_approval_request` / `harness_approval_grant` | 编排 | app 经只读接口（如管理台需要） |
| `harness_action_policy` / `harness_policy_rule` | app（CRUD） | 独立服务 只读（策略评估） |
| `model_price` | app（价格配置） | 独立服务 只读，run 内保存价格快照 |
| `quota_plan` / `quota_plan_binding` | app | 独立服务 只读（解析套餐额度） |
| `quota_account` / `quota_reservation` / `usage_record` | app QuotaService | 独立服务 只读（看板/对账）；写只能走 app 内部 API |
| `harness_gateway_lease` | app（签发/吊销） | 网关、独立服务 对账只读 |
| `harness_gateway_budget` / `harness_gateway_concurrency` | 网关 | app 看板经 网关只读接口（现有直读需收口） |
| `harness_reconcile_batch` / `harness_reconcile_diff` | **编排** | app 经只读接口 |
| 用户/组织/客户/权限相关表 | app | 独立服务 只读（会话归属校验、看板名称补充） |

## 5. 接口迁移清单（迁移前后对照）

迁移后 编排仍使用 `/v1/harness/*` 路径，**dsh 只需换 base_url（9998→9100）**；管理台路径不变（app facade）。

| 当前路径（app:9998） | 鉴权 | 迁移后 | 阶段 | 调用方变化 |
|---|---|---|---|---|
| `POST /v1/harness/sessions` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `GET /v1/harness/sessions/{no}` | 客户端 | `9100` 同路径（**P1.2 已落点**，9998 代理） | P1.2 第一批 | dsh 可先切 9100，也可继续 9998 |
| `POST /v1/harness/sessions/{no}/close` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `POST /v1/harness/sessions/{no}/runs` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `GET /v1/harness/sessions/{no}/runs` | 客户端 | `9100` 同路径（**P1.2 已落点**，9998 代理） | P1.2 第一批 | dsh 可先切 9100，也可继续 9998 |
| `GET /v1/harness/runs/{no}` | 客户端 | `9100` 同路径（**P1.2 已落点**，9998 代理） | P1.2 第一批 | dsh 可先切 9100，也可继续 9998 |
| `POST /v1/harness/runs/{no}/start`（claim） | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `POST /v1/harness/runs/{no}/heartbeat` | 客户端 | `9100` 同路径（**P1.2 已落点**，9998 代理） | P1.2 第一批 | dsh 可先切 9100，也可继续 9998 |
| `POST /v1/harness/runs/{no}/steps` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `GET /v1/harness/runs/{no}/steps` | 客户端 | `9100` 同路径（**P1.2 已落点**，9998 代理） | P1.2 第一批 | dsh 可先切 9100，也可继续 9998 |
| `POST /v1/harness/runs/{no}/events` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `POST /v1/harness/runs/{no}/complete` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `POST /v1/harness/runs/{no}/cancel` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `POST /v1/harness/approvals/request` | 客户端 | `9100` | P1.2 第二批 | dsh（仍走 9998 本进程） |
| `GET /v1/harness/approvals/pending` | 客户端 | `9100` | P1.2 第二批 | dsh（仍走 9998 本进程） |
| `POST /v1/harness/approvals/{no}/decision` | 客户端 | `9100` | P1.2 第二批 | dsh（仍走 9998 本进程） |
| `POST /v1/harness/audit-events` | 客户端 | `9100` | P1.2 第二批 | dsh（仍走 9998 本进程） |
| `POST /v1/harness/policies/evaluate` | 客户端 | `9100` 同路径（**P1.3 已落点**，9998 代理） | P1.3 | dsh 可切 9100，也可继续 9998 |
| `GET /v1/harness/audit-events` | 管理员 JWT | 留存 `9998`（facade→独立服务 只读） | P1.2 | 无（Audit.vue） |
| `GET /v1/harness/admin/sessions*` | 管理员 | 留存 `9998`（facade→独立服务 只读） | P1.2 | 无（Session.vue） |
| `GET /v1/harness/admin/runs*` | 管理员 | 留存 `9998`（facade→独立服务 只读） | P1.2 | 无（Run.vue） |
| `GET /v1/harness/dashboard/usage*` | 管理员 | 留存 `9998`（facade→独立服务 只读，app 补名称） | P1.2 | 无（Usage.vue） |
| `POST /v1/harness/dashboard/reconcile` | 管理员 | 留存 `9998`（转 编排→app 额度 API） | P1.3 | 无（Usage.vue） |
| `GET /v1/harness/dashboard/anomalies` | 管理员 | 留存 `9998`（额度域） | — | 无 |
| `POST /v1/harness/dashboard/reconcile/gateway` | 管理员 | 留存 `9998`（facade→编排写） | P1.3 | 无（Usage.vue） |
| `GET /v1/harness/dashboard/reconcile/diffs*` | 管理员 | 留存 `9998`（facade→独立服务 只读） | P1.3 | 无（Usage.vue） |
| `POST /v1/harness/dashboard/reconcile/diffs/{id}/resolve` | 管理员 | 留存 `9998`（facade→独立服务 内部写） | P1.3 | 无 |
| `GET /v1/harness/dashboard/reconcile/batches` | 管理员 | 留存 `9998`（facade→独立服务 只读） | P1.3 | 无 |
| `GET /v1/harness/dashboard/gateway/quota` | 管理员 | 留存 `9998`（改为 网关只读接口） | P1.2 | 无 |
| `POST /v1/harness/dashboard/gateway/leases/{id}/revoke` | 管理员 | 留存 `9998`（app 租约域） | — | 无 |
| `POST/GET /v1/harness/policies`、`/policies/rules` | 管理员 | 留存 `9998`（配置域） | — | 无（Policy.vue） |
| `/v1/harness/clients*` | 管理员 | 留存 `9998` | — | 无（Client.vue） |
| `/v1/harness/identities*` | 管理员 | 留存 `9998` | — | 无 |
| `/v1/harness/model-prices*` | 管理员 | 留存 `9998` | — | 无 |
| `/v1/harness/admin/model-credentials*` | 管理员 | 留存 `9998`（凭据/子进程） | — | 无 |
| `/v1/harness/gateway/leases*` | 客户端/管理员 | 留存 `9998`（租约签发） | — | dsh 走 9998 |
| `/v1/harness/egress-policy/snapshot` | 客户端 | 留存 `9998`（策略来源） | — | dsh 走 9998 |

> `/dashboard/usage*` 聚合依赖 `usage_record`（L2）与 session/run（L3）：由 独立服务 只读聚合、返回 owner ID，app facade 补充用户/组织显示名，避免 app 直读 独立服务 表。

### 5.1 P1.2 实际落点与 P1.3 前状态（2026-11-07）

**已由 独立服务（9100，app `mode=proxy` 时同路径代理）**：

| 路径 | 落点 | 鉴权 | 写行为 | 兼容入口 |
|---|---|---|---|---|
| `GET /v1/harness/sessions/{no}` | 独立服务 | 客户端凭据（只读校验） | 无表写；`last_used_at` 经 app 内部接口异步上报 | 9998 代理 / 9100 直连 |
| `GET /v1/harness/sessions/{no}/runs` | 独立服务 | 同上 | 无表写 | 9998 代理 / 9100 直连 |
| `GET /v1/harness/runs/{no}` | 独立服务 | 同上 | 无表写 | 9998 代理 / 9100 直连 |
| `GET /v1/harness/runs/{no}/steps` | 独立服务 | 同上 | 无表写 | 9998 代理 / 9100 直连 |
| `POST /v1/harness/runs/{no}/heartbeat` | 独立服务 | 同上 + `write_enabled` | 仅定向更新 `harness_run.last_heartbeat_at` / `updated_at`（不整行覆盖） | 9998 代理 / 9100 直连 |

- app 内部接口：`POST /internal/v1/harness/clients/{client_id}/touch`（服务凭据 `clients:touch`），唯一 `harness_client.last_used_at` 写入点。
- 代理失败（独立服务 不可达/超时）返回 `503` + `data.error_code=orchestration_downstream_unavailable`，**不回落本进程查询**（实测 5/5 路径一致）。
- `last_seen` 上报为异步 best-effort：app 不可达时只记日志，不影响 9100 查询结果（实测 app 停机时 4 个 GET 仍 200）。

**P1.3 前仍走 app 本进程（9998）**：

- 会话/运行写入：`POST /sessions`、`POST /sessions/{no}/close`、`POST /sessions/{no}/runs`、`POST /runs/{no}/start`、`POST /runs/{no}/steps`、`POST /runs/{no}/events`、`POST /runs/{no}/complete`、`POST /runs/{no}/cancel`。
- 审批/审计写入：`/approvals/*`、`POST /audit-events`；策略评估 `POST /policies/evaluate`（P1.3）。
- 额度/对账/网关：`/dashboard/reconcile*`、`/dashboard/usage*`、`/gateway/*`、`/models/*`、`/policies*`、`/clients*`、`/identities*`、`/model-prices*`、`/egress-policy/snapshot`。
- 管理台全部路径保持 app facade，前端零改动。

### 5.2 P1.3 实际落点（2026-11-07）

| 路径 | 落点 | 鉴权 | 额度副作用 | 兼容入口 |
|---|---|---|---|---|
| `POST /v1/harness/sessions` | 独立服务 | 客户端凭据（只读校验） | 无 | 9998 代理 / 9100 直连 |
| `POST /v1/harness/sessions/{no}/close` | 独立服务 | 同上 | 无（仅状态与授权撤销） | 9998 代理 / 9100 直连 |
| `POST /v1/harness/sessions/{no}/runs` | 独立服务 | 同上 | `reserve(hold_id=orch:<run_no>)` 经 app 内部 API | 9998 代理 / 9100 直连 |
| `POST /v1/harness/runs/{no}/start` | 独立服务 | 同上 | 无 | 9998 代理 / 9100 直连 |
| `POST /v1/harness/runs/{no}/steps` | 独立服务 | 同上 | 无（usage 由 events 结算） | 9998 代理 / 9100 直连 |
| `POST /v1/harness/runs/{no}/events` | 独立服务 | 同上 | `settle(idem_key=orch:<run_no>:<node>:<seq>)` | 9998 代理 / 9100 直连 |
| `POST /v1/harness/runs/{no}/complete` | 独立服务 | 同上 | `settle` + `release`（剩余） | 9998 代理 / 9100 直连 |
| `POST /v1/harness/runs/{no}/cancel` | 独立服务 | 同上 | `release` | 9998 代理 / 9100 直连 |
| `POST /v1/harness/policies/evaluate` | 独立服务 | 同上 | 无（写审计） | 9998 代理 / 9100 直连 |

- app `mode=proxy` 时 9 条写路径只转发，**不在 app 本地落库**；独立服务 不可达/超时 → 503 `orchestration_downstream_unavailable`，不回落本地写。
- 独立服务 写开关：`write_enabled=false` → 409 `orchestration_write_disabled`；`mode != proxy` → 409 `orchestration_not_primary`；读接口不受两道闸影响。
- 回滚：见 §16.12（R1 停写 / R2 切回 app 写 / R3 代码回退），均仅需改 manifest + 重启，无 schema/数据回滚。

## 6. 新增 API 与内部认证

### 6.1 编排内部读接口（app→独立服务）

前缀 `/internal/v1/harness`，仅服务凭据可访问，`include_in_schema=false`：

- `GET /sessions`、`/sessions/{session_no}`
- `GET /runs`、`/runs/{run_no}`、`/runs/{run_no}/steps`
- `GET /audit-events`（分页/过滤，字段与现有管理端一致）
- `GET /usage/overview`、`/usage/runs/{run_no}`、`/usage/sessions/{session_no}`
- `GET /reconcile/diffs`、`/reconcile/diffs/{id}`、`/reconcile/batches`、`/reconcile/summary`
- `POST /reconcile/run`、`POST /reconcile/diffs/{id}/resolve`（显式写 scope，记录 operator_id）
- `GET /health`（编排依赖状态）

### 6.2 编排客户端 API（dsh，P1.2/P1.3）

沿用 `/v1/harness/*` 路径，鉴权仍为 Harness 客户端凭据（`require_harness_client`，独立服务 只读 `harness_client`）。不接受 JWT、不接受 `dgw.*` 租约 key、不接受匿名。

### 6.3 app 内部额度接口（独立服务→app）

前缀 `/internal/v1/quota`，服务凭据 + 显式 scope `quota:operate`：

- `POST /reserve`（owner、tokens、run_no、idempotency_key）
- `POST /settle`（run_no、hold_id、usage_items、idempotency_key）
- `POST /release`（run_no/hold_id、reason）
- `POST /reconcile`（释放超期/终态遗留预占）
- `GET /status`（owner 余额/预占）

要求：保持现有 `QuotaService` 语义与幂等键；402 原样透传；超时/5xx 不重试写操作（仅允许一次有界重试且必须同 idempotency_key）。

### 6.4 服务凭据（P1.1 实施口径）

- 表：`service_credential`（`service_id`、`secret_hash`、`scopes`、`description`、`status`、`expires_at`、`created_at`），additive 迁移；模型随 `manifest.models` 注册，由 app 启动流程建表。
- 请求头：`X-Service-Id`、`X-Service-Timestamp`、`X-Service-Signature`。
- 签名串：`HMAC-SHA256(key=secret_hash, msg=timestamp + "\n" + METHOD + "\n" + path + "\n" + sha256(body))`；`secret_hash` = 明文密钥的 SHA-256 十六进制（客户端自行由明文推导，**不传输明文密钥**）。时间窗 ±60s。
- 校验顺序：凭据类型识别 → 时间窗 → 凭据状态/过期 → 签名（`compare_digest`）→ scope → IP 允许清单。
- 稳定错误码（写在响应 `data.error_code`，HTTP 状态同时给出）：
  - `service_auth_missing_credential` 401（匿名）
  - `service_auth_jwt_rejected` 401（用户 JWT）
  - `service_auth_lease_key_rejected` 401（`dgw.*` 租约 key）
  - `service_auth_invalid_credential` 401（未知/禁用/过期/签名错）
  - `service_auth_timestamp_skew` 401
  - `service_auth_ip_not_allowed` 403
  - `service_auth_scope_denied` 403
  - `orchestration_write_disabled` 409（`write_enabled=false` 时的写请求）
- 拒绝事件写 `harness_audit_event`：`action=internal.auth_rejected`、`event_source=orchestration`、`decision=deny`，只记原因与凭据类型，不落凭据原文。
- 明文密钥只从环境变量/部署密钥注入，不入库、不入 manifest。

## 7. 调用方向与降级矩阵

### 7.1 调用方向

| 方向 | 用途 | 方式 |
|---|---|---|
| app→独立服务 | 管理台/看板/审计读取；对账触发与差异标记 | `/internal/v1/harness/*`，服务凭据，只读/显式写 scope |
| 独立服务→app | 额度预扣/结算/释放/预占对账 | `/internal/v1/quota/*`，服务凭据 `quota:operate` |
| 独立服务→app | 客户端鉴权、身份/组织解析、策略规则、价格、套餐绑定 | 只读数据库角色/只读视图，禁止写 |
| app→独立服务 | 网关额度看板 | 网关 `/internal/v1/gateway/quota` 只读接口（收口现有直读） |
| 客户端→独立服务/app | 编排走 9100；租约/出网策略走 9998 | 客户端凭据 |

### 7.2 降级矩阵

| 故障 | 编排仍可做 | 明确失败/降级 |
|---|---|---|
| app 进程挂掉 | 会话/run 查询、start/claim、心跳、步骤/事件采集、审计入库、审批判定（规则可读时）、取消（本地标记，释放预占延后/靠 TTL）、对账（数据可读时） | **创建 run、完成结算** 返回 `503 orchestration_dependency_unavailable`（配额 API 不可达）；租约签发、出网快照不可用；管理台整体不可用（app 进程本身不可用） |
| 编排挂掉 | app 租约、出网策略、配置类页面、额度/客户端/策略配置仍可用 | dsh 编排接口不可用；管理台 session/run/audit/usage/reconcile 页面返回 503；网关 9999 模型流量不受影响 |
| 网关(9999) 挂掉 | 编排可继续创建/心跳/完成 run（记账由网关侧失败上报） | 模型请求失败；对账可继续但会显示缺失 |
| 数据库不可用 | 全部不可用 | 所有服务 fail-closed 503，不伪造成功 |
| Redis 不可用 | 租约鉴权降级回落 DB（既有语义）；编排不做强依赖 | 不改变现有网关/租约降级行为 |

## 8. 兼容期、单写者与验收门禁

### 8.1 兼容期策略

1. 先启动 编排（`write_enabled=false`），只读接口可用；
2. 将 app `orchestration.mode` 置为 `proxy`，重启 app；旧客户端路径转发到 独立服务（透传请求体/客户端凭据/超时/错误码）；
3. app 管理台读接口改为调用 独立服务 只读 API；
4. 观察窗口内只允许一个写者：app 代理分支不写库；独立服务 写接口要求 `write_enabled=true`；
5. P1.4 后 dsh 直连 9100，旧 app 客户端路径进入弃用期（保留代理或返回 410，可配置）。

**明确不做双写。** 避免两个写者同时改 `harness_run`/`quota_reservation`/`harness_audit_event` 导致幂等、审计顺序与对账错乱。

### 8.2 通用验收门禁（每个阶段都必须满足）

- 健康：`GET /health` 返回依赖状态；失败 fail-closed，不返回 200 假绿。
- 鉴权：内部接口无凭据 401、错凭据 401、scope 不足 403、匿名不可达；用户 JWT/`dgw.*` 不可用于内部接口。
- 单写者：切换前后行数/`updated_at` 无重复变更；同一请求只产生一份 run/审计/预占记录。
- 管理台：Session / Run / Usage / Audit / Policy / Client 6 个页面可用；读取失败要显示错误而非空白。
- 幂等：同一 `run_no` 的 reserve/settle/release 重复调用结果一致。
- 假数据：不调用真实 provider；用假 provider 或直接构造 payload。

## 9. 回滚方案

| 阶段 | 回滚动作 | 回滚后行为 |
|---|---|---|
| P1.1 | 停止 9100 进程 | 无数据路径变化；app 照旧 |
| P1.2 | `orchestration.mode=app` + `write_enabled=false`，重启 app/独立服务 | app 本地处理 run 生命周期；独立服务 仅只读；共享库数据可直接续用；dsh 仍指向 9998 |
| P1.3 | `policy_in_orchestration=false`、`reconcile_in_orchestration=false`，重启 app/独立服务 | 策略评估回 app；app 重启对账定时任务；额度调用仍是同一 app 内部 API |
| P1.4 | 恢复 app 代理开关，dsh base_url 指回 9998 | 旧路径重新代理；无需数据回滚 |

迁移只做 additive 变更（新增 `service_credential` 表、内部路由、配置项），无破坏性 schema 变更；回滚不删表、不改历史数据。切换前需排空在途请求（重启 app 前等待 run 心跳/结算请求完成，或接受客户端重试）。

## 10. 分阶段任务拆解

### P1.1 服务骨架与内部认证

- [x] 新增 `base/plugins/harness/server.py`（`python -m base.plugins.harness.server`，默认 `127.0.0.1:9100`，可配，fail-closed 启动校验）。
- [x] 新增 `config.orchestration` 默认值与校验（host/port/mode/内部地址/允许 IP/只读库）。
- [x] 新增 `service_credential` 模型并随 manifest 注册（app 启动建表），独立服务 只读查询。
- [x] 服务凭据校验依赖（HMAC + scope + 时间窗 + IP 允许清单 + 三类拒绝稳定错误码）。
- [x] 只读数据库连接（`default_transaction_read_only=on` 会话级强制），并提供“写会被拒”自检。
- [x] `GET /health/health`（复用 `base.common.health`，含真实 `SELECT 1`）与 `GET /internal/v1/harness/health|whoami`。
- [x] 拒绝事件审计 `internal.auth_rejected`（`event_source=orchestration`）。
- [x] `write_enabled=false` 时写请求统一 409（依赖已就位，P1.2 写接口直接复用）。

**门禁**：现有 Harness 流程零变化；9998/9999 不受影响；内部接口 401/403/200 用例通过；只读连接写被拒自检通过；`write_enabled=false` 时写接口 409。

### P1.2 run 生命周期迁移

**第一批（先做，无额度副作用）**：`GET /sessions/{no}`、`GET /sessions/{no}/runs`、`GET /runs/{no}`、`GET /runs/{no}/steps`、`POST /runs/{no}/heartbeat`。

**第二批**：`POST /sessions`（身份/组织校验走 独立服务 只读 app 表 + 写审计）、`POST /runs/{no}/complete`、`POST /runs/{no}/cancel`（状态机 + 经 app 内部额度 API 释放/结算）。

**暂不迁**：`POST /sessions/{no}/runs`（创建即预扣，与 P1.3 策略/预扣同批），避免 P1.2 同时改两边。

- 独立服务 业务路由的客户凭据校验只读 `harness_client`，不复用用户 JWT；`last_seen` 由 app 内部接口 `POST /internal/v1/harness/clients/{id}/touch`（服务凭据 `clients:touch`）异步 best-effort 更新，独立服务 代码不写该表。
- [x] 第一批 5 条路径已在 独立服务（9100）落地：4 个 GET 无表写，心跳只定向更新 `harness_run` 两列。
- [x] app `mode=proxy`：5 条路径转发 9100，透传凭据/查询串/错误体；下游不可达返回 503 `orchestration_downstream_unavailable`，不回落本进程。
- [x] 一致性实测 36/36 通过（字段/排序/分页/鉴权/校验/心跳终态与幂等/20 并发）；app 停机时 4 个 GET 仍 200 且零表写。
- [ ] 第二批：`POST /sessions`、start/steps/events/complete/cancel、approvals/audit-ingest 在 独立服务 同路径实现。
- [ ] app 新增内部额度 API（reserve/settle/release/reconcile/status），包装现有 `QuotaService`，保持语义与幂等。
- [ ] 独立服务 额度客户端：402 透传；超时/5xx → 503 fail-closed；不伪造结算。
- [ ] app 管理端 `admin/*`、`audit-events` GET、`dashboard/usage*` 改为 独立服务 只读 API。
- [ ] app `/dashboard/gateway/quota` 改为 网关只读接口（收口现有直读）。
- [ ] 独立服务 只读接口字段/分页/过滤与现有管理端一致。

**门禁**：假 provider 全链路（创建会话→创建 run→预扣→start→心跳→step/event→complete→结算→取消）；与旧实现响应码/字段对比；管理台 4 个读取页面通过；app 停止时 独立服务 心跳/事件/取消可用、创建/结算 503；回滚开关演练。

### P1.3 策略评估、额度编排与对账迁移

**本批（2026-11-07 用户确认范围）只做 9 条额度副作用编排接口**：`POST /sessions`、`POST /sessions/{no}/runs`、`POST /runs/{no}/start`、`POST /runs/{no}/steps`、`POST /runs/{no}/events`、`POST /runs/{no}/complete`、`POST /runs/{no}/cancel`、`POST /policies/evaluate`、`POST /sessions/{no}/close`。对账定时任务、看板聚合、`dashboard/reconcile*` 的迁移拆到 P1.3b，不在本批。实施方案见 §16。

- [ ] `policies/evaluate` 迁移 独立服务，只读 `harness_action_policy`/`harness_policy_rule`，规则版本变化热加载/哈希校验。
- [ ] 三档判定与审批联动回归：allow/ask/deny、超时拒绝、会话内授权撤销。
- [ ] 额度预扣/结算/释放编排固定在 独立服务；`dashboard/reconcile` 通过 app 额度 API 执行。
- [ ] 网关对账定时任务从 `base/start.py` 迁到 编排；app 定时任务由 `reconcile_in_orchestration` 关闭，避免双跑。
- [ ] 对账读/写接口经 独立服务；差异标记操作人写入审计。
- [ ] 用量看板聚合迁 独立服务，app facade 补充名称。

**门禁**：策略判定与旧实现逐条一致；重复 reserve/settle 幂等；手动/定时对账只产生一个批次；无重复定时任务；app 停止时策略（规则可读）仍能判定，缓存未命中则 fail-closed deny/ask。

### P1.4 客户端切换与旧路由下线

- [ ] dsh 控制面 base_url 切到 `http://127.0.0.1:9100`；业务面（租约/出网策略）保留 `http://127.0.0.1:9998`。
- [ ] app 旧客户端路由：弃用窗口内继续代理；到期后返回 410（配置可回退代理）。
- [ ] 前端：**不改 URL**（继续走 app facade）；验证 6 个页面。
- [ ] 文档：启动方式、端口、两种 base_url、回滚 runbook、常见降级。

**门禁**：dsh 假 provider 冒烟经 9100 通过；旧路由行为符合文档；管理台全量回归；回滚演练通过；无真实 provider 调用。

## 11. 前端与 dsh 对接变更

### 11.1 管理台（无需改 URL）

| 页面 | 使用接口 | 变化 |
|---|---|---|
| `web/src/views/harness/Session.vue` | `getSessionList/getSessionDetail` | app facade→独立服务 只读，URL 不变 |
| `Run.vue` | `getRunList/getRunDetail/getRunSteps` | 同上 |
| `Usage.vue` | `getUsage*/reconcile*` | 同上；对账触发转 独立服务 |
| `Audit.vue` | `getAuditEvents` | 同上 |
| `Policy.vue` | `getPolicyList/createPolicy/getAuditEvents` | 策略配置留 app，审计读 facade |
| `Client.vue` | `getClientList/createClient/revokeClient` | 留 app |

> 不建议前端直连 9100：9100 只接受服务凭据，不接受用户 JWT；若要直连，需新增“用户态→独立服务”的鉴权方案（不在 P1）。

### 11.2 dsh

- 编排/控制面：`sessions`、`runs`、`approvals`、`policies/evaluate`、`audit-events` POST → `http://127.0.0.1:9100/v1/harness/*`；
- 业务面：`gateway/leases`、`egress-policy/snapshot` → `http://127.0.0.1:9998/v1/harness/*`；
- 两个 base_url 需写入 dsh profile；启动顺序与租约获取不变。

## 12. 主要风险

| 风险 | 等级 | 说明/缓解 |
|---|---|---|
| 额度跨进程调用 | 高 | app API 延迟/超时会导致创建/结算失败；需要幂等键、有界重试、503 fail-closed；不伪造成功 |
| app 不可用时无法创建/结算 | 高 | 已明确降级；若业务不可接受需追加 outbox（P2） |
| 共享账本多写者 | 高 | `usage_record`/`harness_audit_event` 维持多写者例外；需评审确认，否则租约/出网策略审计会依赖 独立服务 |
| 管理台依赖 独立服务 读接口 | 高 | 编排挂掉时 4 个读取页面 503；需前端错误态与运维告警 |
| 独立服务 只读 app 表 | 中 | 表结构耦合、权限风险；用只读账号/只读视图，禁止写 |
| 双定时任务 | 中 | 对账可能双跑；用配置开关 + 启动断言 + 单实例锁（DB advisory lock） |
| 配置缓存/重启 | 中 | manifest 按进程缓存，切换必须重启且按 runbook 执行 |
| 内部密钥管理 | 中 | 轮换、吊销、审计；密钥仅 env 注入；签名时间窗 |
| dsh base_url 拆分 | 中 | 迁移窗口内需同时支持两地址；文档 + 冒烟 |
| 旧路由下线 | 低 | 弃用期保留代理/410 可配置，可回退 |

## 13. 验证方案（不调用真实 provider）

- 假 provider：复用现有本地假 provider 做 SSE 与非流式，不访问外网；
- 数据构造：直接插入假 `harness_client`、`harness_identity`、策略规则、套餐绑定；
- 对照测试：同一批请求分别走 9998（迁移前）与 9100（迁移后），比对状态码/字段/审计/预占/结算；
- 故障演练：停 app、停 编排、停 Redis、配额 API 超时，逐项核对降级矩阵；
- 管理台回归：6 个页面加载与分页/筛选；
- 清理：测试客户端、测试 run/step/审计/预占，验证后删除。

## 14. 评审结论（已确认）

| # | 原问题 | 结论 | 落地约束 |
|---|---|---|---|
| 1 | 9100 还是并入 9999 | **9100 独立进程** | 入口 `python -m base.plugins.harness.server`，默认仅回环 |
| 2 | 多写者例外 | **接受** | 来源隔离：网关 `source=gateway`/`gw:`；编排 `source=client`/`estimated`/`orch:`；审计按 `event_source` 隔离 |
| 3 | 独立服务 直读 app 配置表 | **接受** | 只读账号或 `default_transaction_read_only=on`；代码层不提供写入口；启动自检“写被拒” |
| 4 | 额度执行留 app | **P1 接受** | 登记 P2 技术债（§15），写明触发条件与迁移要点 |
| 5 | 管理台 app facade | **确认** | 前端 URL 全部不变，仅后端 facade 改数据来源 |
| 6 | app 不可用降级 | **确认** | 创建/结算 503 fail-closed；心跳/事件/取消/查询可用；离线结算 outbox 登记 P2 |

### 14.1 P1.1 实施口径补充

- 健康检查沿用 `base.common.health` 的 `/health/health` 口径（真实 `SELECT 1`、2.5s 超时、不重试）。
- 内部认证只接受服务凭据；`Authorization` 中出现 JWT 或 `dgw.*` 一律拒绝，不进入后续校验。
- 只读连接默认复用主库账号并强制会话级只读；生产应配置独立只读账号（`db.readonly_user`）。

## 15. P2 技术债登记：额度执行从 app 迁到共享存储

### 15.1 现状与目标

- 现状：预占/结算/释放由 app `QuotaService` 执行，独立服务 通过 `/internal/v1/quota/*` 调用；app 不可用时 独立服务 无法创建/结算。
- 目标：把 `quota_account` / `quota_reservation` / `usage_record` 的预占与结算下沉到共享存储层（数据库函数/独立额度服务），app 只保留套餐/额度配置与报表；独立服务 直接扣费，不依赖 app 进程。

### 15.2 触发条件（满足任一即启动 P2）

1. app 计划内/计划外停机导致编排不可用的时长超过业务可接受阈值（建议单次 > 5 分钟或月度累计 > 30 分钟）；
2. 创建/结算的跨进程 P95 延迟超过现有直连数据库的 2 倍；
3. 需要多副本 编排或跨机房部署；
4. 额度对账出现因跨进程重试导致的重复/漏记。

### 15.3 迁移要点

- 幂等：保留 `hold_id`/`idem_key` 语义，迁移前先做全量对账基线；
- 事务：预占与扣减改为共享存储事务/存储过程，禁止应用层两阶段写；
- 双跑：迁移期“写共享存储 + 影子对比 app 结果”，只写一处，禁止双写；
- 回滚：保留 app API 作为降级执行路径，开关切换，数据不回滚；
- 验收：并发下不超扣、不重复扣、不悬挂预占；app 停机时创建/结算仍成功。

## 16. P1.3 实施方案：额度副作用编排接口（2026-11-07）

### 16.0 前置结论：现有额度原语不具备完整幂等（必须先修，否则不迁移）

| 原语 | 现状 | 结论 |
|---|---|---|
| reserve（`QuotaService.quota_estimate` + 确定性 `hold_id`） | 同一 `hold_id` 重复调用：Redis `quota_held:` 再次 `INCRBYFLOAT`；Redis 降级 DB 路径在 `_persist_reservation` 复用旧行前已给 `used` 累加 | **重复预扣，不幂等** |
| settle（`QuotaService.quota_settle`） | `usage_record.idem_key` 有 UNIQUE 约束，串行重试安全；但“先改计数、后写流水”，并发重复可双双通过去重、双双加计数、仅一条落库 | **并发双计** |
| release（`QuotaService.quota_release`） | 释放后 hold 被删除，重复调用为 no-op | 串行幂等；与 settle 无互斥 |

处理原则：**不是“先扣后对账”**。幂等事实源是 `QuotaReservation.hold_id` + `UsageRecord.idem_key` 两个唯一约束；仅补：
1. 按 `hold_id` 的进程内分条带锁（64 把，单实例部署；跨进程由 DB 唯一约束兜底）；
2. `quota_estimate` 在锁内先查 active/partial 预占，存在即直接返回 `hold_id`，不再累加；
3. `quota_settle` 在锁内先写 `usage_record`（唯一键抢占），只对写入成功的条目累加计数；崩溃方向为**少计**（由对账/悬挂清理发现），绝不双计；
4. `quota_release` 与 settle 使用同一把锁，避免 complete/cancel 并发互踩；
5. `ensure_account` 并发首建账户捕获 `IntegrityError` 后回读（`quota_account` 唯一约束兜底），周期滚动与 plan 变更改为 `save(update_fields=...)` 定向更新，禁止用陈旧整行快照覆盖并发写回的 `used`；
6. `quota_settle` 与 `quota_release` 在事务内对 `QuotaReservation` 行加 `select_for_update`，跨进程并发由行锁串行化。
若验证阶段任一用例仍出现双计或多扣，**停止迁移并报告**，不以对账掩盖。

### 16.1 实施顺序与回滚点

| 步 | 动作 | 回滚点（不删数据） |
|---|---|---|
| 1 | 修复 `base/common/quota/services/quota_service.py` 幂等与并发（16.0） | 回退文件；无 schema/数据变更 |
| 2 | 新增 app 内部额度 API（16.3），根路径挂载 | 注销路由；独立服务 尚未调用，无影响 |
| 3 | 新增 独立服务 额度客户端与运行时后端（16.2），共享服务改走后端 | `orchestration_runtime` 角色回 `app`；独立服务 不产生额度调用 |
| 4 | 独立服务 写路由 + `write_enabled` 门禁（16.2） | `write_enabled=false` → 全部写 409 |
| 5 | app 写路径代理分支（16.2） | `mode=app` 重启 app/独立服务 |
| 6 | 兼容读取：`orch:`/`harness:` 双前缀、`client`/`harness` 双 source | 双读保留，无破坏 |
| 7 | 验证、清理测试数据、回填 §5 实际落点 | — |

### 16.2 文件与函数级改动

| 文件 | 改动 |
|---|---|
| `base/common/quota/services/quota_service.py` | 新增 `_hold_lock(hold_id)` 分条带锁；`quota_estimate` 锁内预检查预占；`quota_settle` 锁内“先落流水再计数”，捕获 `IntegrityError` 视为重复；`quota_release` 锁内重读 hold；`ensure_account` 并发首建 `IntegrityError` 回读；周期/plan 更新改 `update_fields` |
| `base/plugins/harness/services/service_auth.py` | `ensure_write_enabled()` 增加第二道闸：`mode != proxy` → 409 `orchestration_not_primary`（独立服务 read 不受影响） |
| `base/plugins/harness/services/app_quota_client.py` | 409 分流：`orchestration_not_primary` → `QuotaUnavailable`(503)；其余 → `QuotaReservationConflict`（status 缺省 `unknown`，不再伪造成 `closed`） |
| `base/plugins/harness/api/app_internal/quota_router.py`（新） | `POST /internal/v1/harness/quota/reserve|settle|release`、`GET /status`；服务凭据 scope `quota:operate`；`mode!=proxy` 时 reserve/settle/release 返回 409 `orchestration_not_primary` |
| `base/start.py` | 在 touch router 旁挂载 `app_quota_router`（根路径，避免 `/v1/harness` 前缀） |
| `base/plugins/harness/services/orchestration_runtime.py`（新） | 进程角色（`app`/`orchestration`）；`server.py` 导入时置 `orchestration` |
| `base/plugins/harness/services/app_quota_client.py`（新） | 服务凭据 HMAC 调用 app 内部额度 API；429 原样映射为 `QuotaError`；超时/5xx 抛 `QuotaUnavailable`，**不重试** |
| `base/plugins/harness/services/quota_backend.py`（新） | `reserve/settle/release` 按角色分派（app→`QuotaService`，独立服务→HTTP 客户端） |
| `base/plugins/harness/services/run_service.py` | 预扣/结算/释放改走 `quota_backend`；`hold_id=orch:{run_no}`；`source=client`；`idem_key=orch:{run_no}:{node}:{seq}`；跨进程不可用 → 503 `orchestration_dependency_unavailable` |
| `base/plugins/harness/services/event_service.py` | `_usage` 改走 `quota_backend`；同一 `orch:` 幂等键；不可用 → 503，批次不确认 |
| `base/plugins/harness/api/orchestration/write_router.py`（新；`server.py` 注册） | 8 条业务写路由 + `policies/evaluate`；先客户端凭据校验，再 `ensure_write_enabled()`；复用 `HarnessRunService`/`HarnessEventService`/`HarnessPolicyService`，行为与 app 同源 |
| `base/plugins/harness/api/v1/session_router.py`/`run_router.py`/`policy_router.py` | `proxy` 下这 9 条写路径转发 独立服务（`require_client_or_proxy` + `proxy_to_orchestration`），app 不本地落库 |
| `base/plugins/harness/services/dashboard_service.py` | `run_usage` 同时识别 `harness:{run_id}:` 与 `orch:{run_no}:`；reservation 过滤 `source__in=["harness","client"]` |
| `base/plugins/harness/services/reconcile_service.py` | `_client_run_id` 改为返回 `(run_id?, run_no?)`，兼容 `harness:<id>:` 与 `orch:<run_no>:`；`_load_runs` 同时按 id/run_no 装载 |
| DB `service_credential` | 给 `svc_orchestration` 追加 scope `quota:operate`（不改其它字段） |

**明确不改**：`harness_audit_event.event_source` 仍沿用现有 `api`/`jsonl`/`policy` 值，保证 app 与 独立服务 同请求的审计行逐列可比；§2.3 的审计来源隔离推到 app 停止写编排表之后的 P1.4。这是一处有意识的取舍。

### 16.3 app 内部额度 API 契约（原语级）

前缀 `/internal/v1/harness/quota`，`include_in_schema=false`；服务凭据（`X-Service-Id` / `X-Service-Timestamp` / `X-Service-Signature`，HMAC 同 §6.4）+ scope `quota:operate`；仅 127.0.0.1。

**reserve**

- 入参：`{owner_type, owner_id, items:{token:…}, hold_id, source, ref_type?, ref_id?, member_id?}`
- 幂等键构成：`hold_id`（必须 `orch:` 前缀，否则 400 `quota_hold_id_invalid`）。事实源为 `quota_reservation.hold_id` UNIQUE。
- 返回：首次 `{hold_id, idempotent:false}`；重复 `{hold_id, idempotent:true, status}`——同 `hold_id` 只产生一次预扣，不累加。
- 失败码：400 `quota_hold_id_invalid`；401/403 凭据/scope；409 `orchestration_not_primary`（app 非写主）；409 `quota_reservation_in_progress` / `quota_hold_closed`（同 hold 处于 pending 或其他状态）；429 `{code:42901, item, remaining, estimated}`；503 `quota_backend_unavailable`。

**settle**

- 入参：`{hold_id, owner_type?, owner_id?, usage_items:[{idem_key, resource_type, amount, tokens_in, tokens_out, usage_kind, session_ref, model, source, member_id}]}`
- 幂等键构成：每条 `usage_items.idem_key`，必须 `orch:<run_no>:<node_id>:<seq>`，否则 400 `quota_idempotency_key_required`（拒绝非幂等写入）。事实源为 `usage_record.idem_key` UNIQUE；行锁 `select_for_update` 串行化同一 hold 的结算。
- 返回：`{settled: n, skipped: m, hold_id, status}`；重复/并发同幂等键时 `settled` 只计一次，后续为 0/跳过。
- 失败码：400 `quota_idempotency_key_required`；404 `quota_hold_not_found`；409 `orchestration_not_primary`；503 `quota_backend_unavailable`。

**release**

- 入参：`{hold_id, reason}`
- 幂等：重复释放返回 `released:false`；已结算后再释放为 no-op；释放后再结算返回 `settled:0`（hold 不存在）。`used` 以 `max(used - items, 0)` 回退，不产生负余额。
- 返回：`{released: bool}`。
- 失败码：403/401 凭据；409 `orchestration_not_primary`；503 `quota_backend_unavailable`。

**status**

- `GET /status` → `{mode, write_enabled}`，供 独立服务 启动/健康自检；不触发额度写。

**通用**：请求体上限、超时由 独立服务 侧 `internal_timeout_seconds`（默认 5s）控制；独立服务 不重试、不本地兜底。

### 16.4 幂等键与来源

- `hold_id = orch:<run_no>`；`usage_record.idem_key = orch:<run_no>:<node_id>:<seq>`。
- `quota_reservation.source = client`；`usage_record.source` 实际值写 `client`，估算值写 `estimated`；客户端上报的 `provider` 归一为 `client`，`gateway` 保持。
- 读取侧兼容窗口：对账/看板同时识别 `harness:` 与 `orch:`、`harness` 与 `client`；不回写历史数据。
- `release` 接受任意已存在 `hold_id`（含迁移前 `harness:` 在途 run），仅按 DB 登记释放。

### 16.5 部分成功补偿

| 场景 | 立即处理 | 崩溃/未完成的兜底 |
|---|---|---|
| 预扣成功、run 落库失败 | 调 `release` 释放；释放也失败则记录原始错误 + 异常日志 | app `quota_hold_cleanup_task`（`QuotaService.cleanup_stale_holds`）+ 预占 `expire_at`(3600s)；`HarnessReconcileService.reconcile` 释放终态遗留 |
| run 创建成功、start 失败 | start 无额度副作用，返回 5xx，run 保持 `created` | 客户端重试 start；未重试则预占到期由清理释放 |
| 结算成功、run 状态更新失败 | 返回 5xx，run 保持非终态 | 客户端重试 complete：settle 由 `orch:` 幂等跳过、release no-op、再更新状态；悬挂预占由对账释放 |
| 事件批次中途结算失败 | 返回 503，不确认批次 | 客户端重放：step upsert 幂等、usage 由 `orch:` 幂等跳过；审计可能重复（与 app 现状一致） |
| 取消时 release 失败 | 返回 503，run 不改 `cancelled` | 客户端重试；未重试则 TTL 清理 |

### 16.6 状态机一致性（与 app 逐状态对齐，复用同一 `HarnessRunService`）

| 接口 | app 现有行为（独立服务 必须一致） |
|---|---|
| create run | 会话不存在/非本客户端 → 404；会话非 `open` → 409；配额不足 → 429（42901 体）；其他 → 500 |
| start | 终态 → 409「运行已结束」；否则置 `running`，`started_at` 仅在为空时写 |
| steps | 终态 → 409；否则按 `(run_id,node_id,seq)` upsert |
| events | 终态 → 409；否则采集 |
| complete | 已终态 → 直接返回原 run（200，不结算）；否则结算→释放→写终态/摘要 |
| cancel | 已终态 → 返回原 run（200）；否则释放→`cancelled` |
| close session | 不存在/非本客户端 → 404；已 `closed/expired` → 返回原值 200；仍有未终态 run → 409；否则关闭并撤销会话授权 |
| policies/evaluate | 规则后端不可用 → `deny`（fail-closed）；否则返回三档 verdict 并写审计 |

### 16.7 `write_enabled` 与单写者切换

切到 独立服务：① 独立服务 以 `write_enabled=false` 启动（写 409、读正常）→ ② app `mode=proxy` 重启（app 不再本地写，全部写经 独立服务 得 409）→ ③ 独立服务 `write_enabled=true` 重启 → ④ 观察。全程不存在两边同时可写的窗口。
切回 app：③→② 逆序（先 `write_enabled=false`，再 `mode=app`）。manifest 按进程缓存，两次切换都需重启对应进程；切换前排空在途请求。
app 内部额度 API 在 `mode=app` 时拒绝写操作，作为“独立服务 误连”时的第二道单写者闸门。

### 16.8 验证矩阵（同一批假请求，对比最终 DB 而非只看 HTTP）

| 用例 | 方法 | 通过标准 |
|---|---|---|
| 全链路基线 | 等价 fixture 分别打 9998（`mode=app`）与 9100（`mode=proxy`+`write_enabled=true`）：建会话→建 run→start→step→event→complete→close | `harness_run/session/step` 除 id/编号/时间戳外逐字段一致；`usage_record` 条数/`idem_key`/`source`/`amount` 一致；`quota_reservation` 终态/`items`/`used_items` 一致；`quota_account.used` 一致；审计 action 集合与条数一致（`event_source` 保持同值） |
| 重复提交 | complete/cancel/event 同批重复 3 次 | run 终态只变一次；`usage_record` 不增；`used` 不增；hold 只释放一次 |
| 并发提交 | 同一 run 20 并发 complete；同一新 run 10 并发 create | 每条 `(node,seq)` 仅 1 条 usage；`used` 精确等于真实用量；hold 只释放一次；无 500 |
| 跨进程超时 | 独立服务 指向不可达 app 额度地址或停 app | create_run/complete/events 返回 503 `orchestration_dependency_unavailable`；**无新增 run/usage/reservation**；本地无兜底扣减 |
| 下游 5xx | 用本地 mock 返回 500 替代 app 额度 API | 503 fail-closed；无写入；不重试 |
| write 开关 | `write_enabled=false` | 9 条写路径 409 `orchestration_write_disabled`；5 条读路径 200 |
| 单写者 | `mode=app` 时直接打 独立服务 写路由；`mode=proxy` 时打 app 写路由 | 前者 409 且 app 额度 API 拒绝；后者只代理、app 本地零写入 |
| app 只读边界 | 独立服务 批次的 `harness_client/identity/policy/model_price/quota_*` 行指纹 | 除经 app API 合法变更的 `quota_*`/`usage_record` 与 `last_used_at` 外，其它零变更 |

测试数据用独立前缀（`p13_`）构造，结束后按 run_no/session_no/owner 删除，并核对无残留。不调用真实 provider。

### 16.9 本批验收门禁

- 9 条写路径在 9100 可用，9998 `mode=proxy` 下只代理；错误码/错误体与 app 逐条一致。
- reserve/settle/release 重复与并发均不双扣；跨进程不可用时一律 503，无本地兜底。
- `write_enabled=false` 写 409、读正常；切换 runbook 演练无双边推进。
- 测试数据清理完毕；§5 对照表回填本批实际落点与回滚动作。

### 16.10 行为变化与影响面（逐条）

> 既有 app 本地写路径、网关（`source=gateway`/`gw:`）、对账、额度中断的**成功路径语义未变**；以下为需要知会的变化项。

| # | 变化 | 原行为 | 新行为 | 影响面 |
|---|---|---|---|---|
| 1 | reserve 重复调用 | 同 `hold_id` 再次预扣会累加 | 幂等返回首次结果（`idempotent:true`），不累加 | 无调用方依赖重复累加；首次预扣金额不变 |
| 2 | settle 并发/重复 | “先计数后流水”，并发可双计 | 行锁 + `usage_record.idem_key` 唯一约束；先流水后计数，并发只计一次 | 串行返回结构不变；崩溃方向改为“少计”，由对账发现 |
| 3 | release 幂等 | 释放后删除 hold，重复为 no-op；与 settle 无互斥 | 重复释放 `released:false`；已结算后释放不改 `used`；`used` 以 `max(0, …)` 回退 | 返回值仍为 bool；不再可能出现负余额 |
| 4 | `hold_id` 前缀 | `harness:<execution_id>` | 编排路径改为 `orch:<run_no>` | 对账/看板已双读（`harness:<id>:` / `orch:<run_no>:`）；历史行不回写；依赖 `hold_id == execution_id` 的外部脚本需改用 `ref_id` |
| 5 | `usage_record.source` | 客户端上报 `provider` | 归一为 `client`（`gateway` 保持 `gateway`，估算保持 `estimated`） | 仅新数据；按 source 聚合的看板行由 `provider` 变 `client` |
| 6 | 新增 409 `orchestration_not_primary` | 无 | `mode != proxy` 时 独立服务 写路由、app 内部额度写 API 拒绝 | 仅在错误配置/回滚窗口触发；正常切换顺序不会出现 |
| 7 | 账户并发首建 | 唯一冲突时 500 | `IntegrityError` 回读，成功返回 | 对外不可见；消除并发首扣 500 |
| 8 | 错误体 | 新写路径部分错误为扁平 `{code,message}` | 统一 `{code,msg,data}`（`data.error_code` 稳定码） | 与 app 既有错误体同形，客户端解析不受影响 |
| 9 | 独立服务 额度客户端 409 映射 | 任一 409 → `QuotaReservationConflict(status="closed")` | 仅真实 hold 冲突映射 409；`orchestration_not_primary` → 503；缺省 status `unknown` | 错误码更准确，成功路径不变 |
| 10 | 服务凭据 | 开发环境 `svc_orchestration` 原 secret 已轮换（无法从运行进程回收） | 新 secret 写入 User 级 `ORCHESTRATION_SERVICE_SECRET`，DB `secret_hash` 同步 | 仅 独立服务 使用该凭据；部署环境需各自注入 |

**数据约束检查**：`quota_reservation.hold_id`、`usage_record.idem_key` 唯一约束均已存在；清理前 `orch:` 行全部为本次测试数据，**无历史冲突行**，未改动任何历史数据。

### 16.11 实测结果（以 DB 数值为准）

**A. 原语并发（2 进程 × 10 任务，owner=`org:990013`，`counter_mode=db`）**

| 步骤 | `quota_account.used`(token) | `quota_reservation` | `usage_record` |
|---|---|---|---|
| 初始 | 0 | — | 0 |
| 20 并发 reserve 同 hold（预扣 1000） | 1000 | 1 条 `active`，items 1000 | 0 |
| 再次 20 并发 reserve 同 hold | 1000 | 仍 1 条 `active` | 0 |
| 20 并发 settle 同 `idem_key`（400） | 1000 | `partial`：items 600 / used 400 | 1 条（400）；两进程 `settled` 合计 1 |
| 超额 settle 700（> 余量 600） | 1100 | `settled`：items 0 / used 1100 | 2 条（400 + 700） |
| 结算后 release ×3 | 1100 | `settled` 不变 | 2 |
| 释放后再 settle | 1100 | `settled` | 2（`settled=0`，hold 缺失） |
| 新 hold reserve 1000 → release ×3 | 1100 | `released`（True/False/False） | 2 |
| 释放后 settle | 1100 | `released` | 2（`settled=0`） |

**B. 内部额度 API（HTTP + 服务凭据）**：reserve ×2 同 hold → 200/200 同 `hold_id`，`used` 只 +1000 一次；settle ×2 同 `idem_key` → 第一次 `settled=1`、第二次 `settled=0`；release ×2 → `True/False`；非 `orch:` idem → 400 `quota_idempotency_key_required`；非 `orch:` hold → 400；错误签名 → 401。

**C. app vs 独立服务 全链路对拍**（同一 fixture：session→run→start→step→event→complete）：

| 维度 | app 本进程（`mode=app`） | 独立服务（`mode=proxy`） | 结论 |
|---|---|---|---|
| session | client/owner/status/title/project_key 一致 | 同左 | 一致 |
| run | `succeeded`、reserved 500、model/provider/task_type/summary 一致 | 同左 | 一致 |
| steps | `n1/seq1` + `assistant:2/seq2`，token 100+100 / 50+50 | 同左 | 一致 |
| usage_record | 2 条：`orch:RID:assistant:2:2`=100、`orch:RID:n3:3`=200，source `client`，session_ref=SID | 同左 | 一致 |
| quota_reservation | `released`，items `{}`，used_items `{token:300}`，original 500，source `client` | 同左 | 一致 |
| 审计 | `run.created` / `run.started` / `run.succeeded` 各 1 条，actor `client`，risk `low` | 同左 | 一致 |
| 差异 | 仅 `session_no` / `run_no` / 时间戳 / 自增 id | 同左 | 预期内 |

**D. 门禁与 fail-closed**

- `write_enabled=false`：9 条写路径 409 `orchestration_write_disabled`；读路径 200（实测 run/session GET）。
- `mode=app`（独立进程）：写路径 409 `orchestration_not_primary`（修复前因 `orchestration_config` 未导入误报 500，已修复并复测通过）；读路径 200。
- app 停机：create_run 503 `orchestration_dependency_unavailable`（`ConnectError`），run 行数不变。
- 下游 mock 500：503（`app 额度 reserve 返回 500`）；mock 超时：503（`ReadTimeout`）；两者均无 run/usage/reservation 新增。
- 事件 usage 重复上报：`usage_record` 1 条 → 重复后仍 1 条（第二次 `settled=0`）；complete 释放剩余；终态 start/step/event 409、complete/cancel 200 原 run；会话关闭后建 run 409。

**E. 清理结果**：删除 `p13_` 会话 7 / 运行 6 / 步骤 6 / `orch:` reservation 7 / `orch:` usage 9 / 测试客户端 1；删除 `org:990013` 账户与临时绑定；`usr:4` 回退 1600 token（94765 → 93165）；残留检查全 0。保留 `internal.auth_rejected` 负向测试审计（安全审计只增不删）。

### 16.12 回滚动作（已实测）

| 级别 | 动作 | 实测结果 |
|---|---|---|
| R1 停写 | manifest `write_enabled=false` → 重启 独立服务 | 9 写 409 `orchestration_write_disabled`，读 200；app 保持 `proxy` 会转发到 独立服务 同样 409 |
| R2 切回 app 写 | manifest `mode=app` → 重启 app 与 独立服务 | 独立服务 写 409 `orchestration_not_primary`，读 200；app 恢复本地写路径 |
| R3 代码回退 | 按 §16.1 逆序回退文件 | 无 schema 变更、无数据回滚；`orch:` 在途预占为同库同表行，app `QuotaService` 仍可按 `hold_id` 释放/结算；未完成由 `cleanup_stale_holds`(TTL 3600s) 兜底 |
| 执行顺序 | `write_enabled=false` → 排空在途 → `mode=app` → 重启 → 用新 secret 重新注入 | 全程无“两边同时可写”窗口 |

- manifest 按进程缓存，任何 `mode`/`write_enabled` 变更都必须重启对应进程；切换前排空在途请求。
- 回滚期间 独立服务 心跳（`/runs/{no}/heartbeat`）会因 `ensure_write_enabled` 返回 409——属预期，心跳不是 run 推进。

### 16.13 已知限制与技术债

- **Redis 分支未实测**：本环境未安装 Redis，`counter_mode=db`；Redis 路径的幂等修复仅静态审查 + 进程内锁，需在具备 Redis 的环境复跑同一并发脚本。
- **HTTP 建 run 无请求级幂等键**：`POST /sessions/{no}/runs` 重复提交会生成不同 run（各自独立 `hold_id`），不属于“同一 run 重复扣费”；如需请求级幂等，登记 P2 债务（客户端 `Idempotency-Key` + 请求去重表）。
- **审计来源隔离**：`event_source` 仍与 app 同值（为可比性有意为之），P1.4 再拆分。
- **负向测试审计留痕**：`internal.auth_rejected` 记录保留（安全审计不可删改）。
