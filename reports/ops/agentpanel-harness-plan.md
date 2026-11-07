# AgentPanel → DeepSeek Harness 业务支撑系统：现状盘点与技术方案

> 版本：v0.1（只读盘点，未改动代码）
> 范围：账号（用户/组织/RBAC）、日志（运行日志与 trace）、安全审计（谁在何时对 harness 做了什么/审批/危险操作留痕）、Token（配额/预估/预占/结算/用量统计）
> 约束：沿用现有插件化结构、`migrations/*.sql` 幂等机制与 `generate_schemas(safe=True)`，不另起一套 ORM/权限/配额体系。

---

## 0. 结论摘要

**能直接用的（约 60% 底座已具备）**

- 账号与组织：`user` / `department`（公司-部门树）/ `role` / `permission` / `menu` + 数据权限（self/dept/dept_tree/custom/all）+ `require_permission` / `require_owner` 双主体鉴权，完整可用。
- 客户侧组织：`customer` / `customer_organization` / `customer_organization_member`，可承载"组织"语义。
- Token 计量：`quota_plan` / `quota_account` / `usage_record` / `quota_plan_binding` + `QuotaService.quota_estimate`（原子预占）/ `quota_settle`（按 `(execution_id,node_id,seq)` 幂等结算）/ 每分钟对账与悬挂预占清理，生产级实现。
- HTTP 审计：`audit_log` 中间件自动落库；ORM `save` 钩子 → `data_change_log`；`login_log`；`audit_config` 保留期与敏感字段；前端审计 7 个页面已存在。
- 审批：`approval_flow/instance/task/record` + 引擎 + `gate_write` 门禁 + 通过后回调执行器，代码完整。
- Trace：`trace_event` + `TraceService`（批量缓冲、seq 单调、cursor 分页），但仅服务于 agent 工作流执行。

**必须补的（当前结构性缺口）**

1. **没有 Harness 接入层**：无客户端凭据/服务账号、无外部身份映射到本地 `user`、无 `session/run` 实体。
2. **配额预占不持久化**：hold 只存 Redis + 进程内 `_mem_holds`，多 worker 或进程重启会丢预占；无 `quota_reservation` 表。
3. **`usage_record` 不适用于 Harness**：幂等键 `(execution_id,node_id,seq)` 依赖工作流执行实例且两列可空（PG 中 NULL 互不冲突），无 `source/session/model/price` 字段，无法跨来源去重、无法算钱。
4. **`trace_event` 与 `workflow_execution.id` 强绑定**：Harness 独立执行无 trace；`TraceEvent` 无 `session_id`/`source`，且无保留期清理任务。
5. **审计只到 HTTP/ORM 层**：没有"工具调用/文件写/外部请求/密钥读取"等语义动作的事件模型、风险等级、审批联动；`AuditMiddleware` 与 `TraceMiddleware` 会重复写 `audit_log`。
6. **Approval / agent / llm 插件当前均 `is_installed=false, is_enabled=false`**：审批与 Agent 能力实际未上线。
7. **组织级配额缺失**：`owner_type` 仅 `cus/usr`，无法按部门/客户组织计量与汇总。
8. **前端无 Token 与 Harness 页面**：无套餐管理、配额看板、计量流水、用量统计、会话/运行查看。

---

## 1. 现有能力盘点

### 1.1 插件化框架与迁移机制

| 能力 | 实现位置 | 状态 |
|---|---|---|
| manifest 定义/加载 | `base/common/plugin_manager.py` | 可用 |
| manifest 字段 | `name/display_name/version/route_prefix/routes/models/schemas/menus/permissions/config/hooks/is_installed/is_enabled` | 可用 |
| 路由装配 | manifest `routes` → 递归加载 `{file}_router`，按 `route_prefix` 挂载 | 可用 |
| 模型注册 | `base/common/setting.py::get_model_list()`：**所有插件模型无论启停都注册**，另显式注册 `base.common.quota.*`、`base.common.authz.resource_grant` | 可用 |
| 菜单/权限自动同步 | `plugin_manager` 调用 `MenuService`/`PermissionService` 按 manifest 创建 | 可用 |
| SQL 迁移 | `base/common/database.py::_run_sql_migrations()`：文件名 `{plugin}_{action}_{table}[__{field}]_{ts}.sql`，按插件 `is_enabled` 门控，在 `generate_schemas` **之前**执行 | 可用 |
| 建表 | `Tortoise.generate_schemas(safe=True)`（`database.py`） | 可用 |
| 当前启用插件 | `product / sales / crm / customer / audit / mail` | 已启用 |
| 当前未启用 | `agent / approval / llm / thirdparty / finance ...` | 未上线 |

> 关键点：新增表优先靠 `generate_schemas` 自动建；给存量表加列/索引才需要幂等 SQL（用 `DO $$ ... information_schema ... $$` 包裹，避免 `ON CONFLICT`，兼容 openGauss）。

### 1.2 账号 / 组织 / RBAC

| 能力 | 表 / 模型 | 路由 / 权限 | 状态 |
|---|---|---|---|
| 用户 | `user`（`base/core/users/models/users.py`）：username/email/phone/password/is_active/is_superuser/last_login/dept_id | `/v1/users`、`/v1/auth/*` | 可用 |
| 组织/部门树 | `department`：parent_id/type(company/department)/level/leader_id/sort/is_active | `/v1/departments` | 可用 |
| 角色 | `role`：code/name/parent_id/data_scope/custom_dept_ids | `/v1/rbac/roles/*`，`role:list` | 可用 |
| 权限点 | `permission`：name/code/module/is_active | `/v1/rbac/*`，`require_permission("...")` | 可用 |
| 权限组 | `permission_group` + `permission_group_permission` | `/v1/rbac` | 可用 |
| 菜单 | `menu`：path/component/menu_type/permission/is_visible | `/v1/menus/*` | 可用 |
| 用户-角色-权限 | `user_role` / `role_permission` / `role_permission_group` | 缓存：`get_user_permissions_cached` | 可用 |
| 数据权限 | `data_scope` + `data_permission_rule` + `resolve_scope` | `base/common/authz/scope.py` | 可用 |
| 认证 | JWT 双主体 `typ=cus/usr`，`require_owner` → `OwnerContext` | `base/common/authz/context.py` | 可用 |
| 权限装饰器 | `require_permission` / `require_any_permission` / `require_role` / `require_superuser` | `base/common/permissions.py` | 可用 |
| 客户组织 | `customer` / `customer_organization` / `customer_organization_member` | customer 插件 | 可用（客户域语义） |

> `identity_link`（`base/plugins/customer/models/identity_link.py`）是 **客户↔后台用户 1:1 唯一绑定**，状态 `prompted/linked/dismissed`，只能走"提示→确认→验证"，不能当通用外部身份表使用。

### 1.3 Token 配额与计量

| 能力 | 实现 | 状态 |
|---|---|---|
| 套餐 | `quota_plan`：code/name/scope(cus/usr/both)/quota_items(JSON)/status | 可用 |
| 账户 | `quota_account`：`UNIQUE(owner_type,owner_id)`、period_start/end、used JSON、status | 可用 |
| 绑定 | `quota_plan_binding`：bind_type(membership_level/role)/bind_key/plan_id/priority | 可用 |
| 流水 | `usage_record`：owner/execution_id/node_id/seq/resource_type/amount/tokens_in/tokens_out/cost，`UNIQUE(execution_id,node_id,seq)` | 部分可用（见缺口 3） |
| 预估 | `estimator.estimate_tokens`：字符启发式 + 输出预留 | 可用（精度一般） |
| 预占 | `QuotaService.quota_estimate`：Redis `incrbyfloat` 原子校验 + 补偿回退；失败降级 DB `SELECT FOR UPDATE` | 可用但 hold 不持久 |
| 结算 | `quota_settle`：先查 `usage_record` 去重，再 held→used，落流水 | 可用 |
| 看板 | `GET /v1/quota`（`require_owner`） | 可用 |
| 管理 | `GET/POST/PUT/DELETE /v1/quota-plans`、`GET /v1/usage-records`（`require_superuser`） | 可用 |
| 对账 | `quota_reconcile_task`（每分钟）、`quota_hold_cleanup_task` | 可用 |
| 资源授权 | `resource_grant`：`(owner_type,owner_id)×(resource_type,resource_id)→allow/expires_at` | 可用（执行侧有复核回调） |

> 当前 `hold_id = str(execution_id)`（有 execution_id 时）。同一 run 内多步并发预估会互相覆盖同一 hold key，Harness 多步计量必须改 hold 键规则。

### 1.4 日志与 Trace

| 能力 | 实现 | 状态 |
|---|---|---|
| 执行记录 | `workflow_execution`：workflow/status/input/output/error/started_at/completed_at/owner_type/owner_id/version_id/kind | 可用（仅工作流，无 session_id 列） |
| Trace 事件 | `trace_event`：execution_id/seq/event_type/node_id/payload，索引 `(execution_id,seq)` | 可用（仅 agent 执行链路） |
| Trace 写入 | `TraceService.create_writer` + 批量 `bulk_create` + 失败重试丢弃 | 可用 |
| Trace 查询 | `GET /v1/agent/u/executions/{execution_id}/trace`（cursor+limit） | 可用（agent 插件未启则不挂载） |
| HTTP 全链路 | `TraceMiddleware`：注入 `X-Trace-ID`，写 `audit_input_layer` + `audit_output_layer` + `audit_log` | 可用（与 AuditMiddleware 重复） |
| 执行层日志模型 | `audit_execution_layer`（tool_call/api_call/data_read/write/permission_check） | 模型可用，**未接线**（无自动写入方） |
| 前端 | `web/src/views/audit/trace.vue`、`agent/executions.vue` | 已有页面 |

### 1.5 安全审计与审批

| 能力 | 实现 | 状态 |
|---|---|---|
| HTTP 审计 | `AuditMiddleware` → `audit_log`：user/module/operation/method/path/ip/ua/params/status_code/duration/level | 可用（`response_data` 恒为空；`trace_id` 恒为 None） |
| 登录审计 | `login_log` + `user.login/logout` 事件订阅 | 可用 |
| 数据变更 | ORM `save` monkey-patch → `model.created/updated/deleted` → `DataChangeHandler` → `data_change_log`（前后值/变更字段/操作人/trace_id） | 可用 |
| 审计配置 | `audit_config`：模块开关、敏感字段、保留天数、告警规则；种子行 `data_change` | 可用 |
| 清理任务 | `audit_cleanup_task`（每日，排除授权类表） | 可用 |
| 风险审计 | `audit_risk_record`：risk_type + risk_level(low/medium/high/critical) + 处理流 | 模型可用，**无自动产生来源** |
| 审计报告 | `audit_report` + 生成/下载路由 | 可用 |
| 审计 API | `/v1/audit/audit-logs/*`、`/data-changes/*`、`/login-logs/*`、`/risks/*`、`/reports/*`、`/audit-configs/*`、`/trace/*`；鉴权仅 `get_current_user_id`，**未挂 manifest 权限码** | 可用但鉴权偏弱 |
| 审批模型 | `approval_flow/instance/task/record`（实例含 business_type/business_id/business_data/action/status/current_node） | 可用 |
| 审批门禁 | `gate_write(model, action, payload...)`：命中规则建实例并抛 `NeedApprovalError`；异常默认放行 | 可用但风险 |
| 审批回调 | `register_executor` + `ApprovalExecutor.execute` | 可用，**无业务登记** |
| 审批前端 | `approval/Index.vue`、`FlowRule.vue`、`InstanceDetail.vue`、`ApprovalPrompt.vue` | 已有页面 |

### 1.6 LLM 与计费相关

| 能力 | 实现 | 状态 |
|---|---|---|
| LLM 用量 | `llm_usage_record`：customer_id/model_id/record_type/tokens/cost/时间 | 可用（客户域，字段不含 in/out 拆分） |
| API Key 配额 | `llm_api_key`：max_quota/used_quota/quota_reset_date/is_available | 可用（日配额，非 token 账户体系） |
| 调用网关 | `base/plugins/agent/services/engine/llm_gateway.py` | 可用（agent 插件未启） |

---

## 2. 缺口清单（按需求四块）

### A. 账号（用户/组织/RBAC）

| 编号 | 缺口 | 影响 | 优先级 |
|---|---|---|---|
| A1 | 无 Harness 接入凭据（client_id/secret、scopes、IP 白名单、服务账号） | Harness 无法安全调用业务系统 | P0 |
| A2 | 无外部身份映射（Harness 用户/租户 → 本地 user/customer） | 审计无法定位"谁"，配额无法归属 | P0 |
| A3 | `owner_type` 仅 `cus/usr`，无部门/客户组织主体 | 无法做组织级配额与用量汇总 | P2 |
| A4 | `require_owner` 只认 JWT `typ/sub`，不支持服务账号 + 代理用户头 | 需要新增鉴权依赖而非改造现有 | P0 |

### B. 日志（运行日志与 Trace）

| 编号 | 缺口 | 影响 | 优先级 |
|---|---|---|---|
| B1 | 无 Harness `session` / `run` / `step` 实体 | 无会话与执行生命周期，无法按 run 追溯 | P0 |
| B2 | `trace_event.execution_id` 语义绑定 `workflow_execution`，无 `source`/`session_id` | Harness 执行无法落 trace | P0 |
| B3 | 无 trace 保留期清理（文档要求 30 天） | 表无限增长 | P1 |
| B4 | `workflow_execution` 无 `session_ref` | Harness 调工作流时无法归入会话 | P3 |
| B5 | `audit_execution_layer` 有模型无写入 | 工具/API 级日志空缺 | P1 |

### C. 安全审计（谁/何时/做了什么、审批、危险操作）

| 编号 | 缺口 | 影响 | 优先级 |
|---|---|---|---|
| C1 | 无语义动作审计事件（action/target/risk/decision/policy 版本） | 只能看到 HTTP 路径，看不到"读了哪个文件、调了哪个工具" | P0 |
| C2 | 无危险操作分级与策略表 | 无法统一 allow/deny/需审批 | P1 |
| C3 | 审批与 Harness 未接线；`gate_write` 异常默认放行 | 危险操作可能绕过审批 | P1 |
| C4 | `AuditMiddleware` + `TraceMiddleware` 重复写 `audit_log`，`trace_id` 不一致 | 审计噪音、关联断链 | P1 |
| C5 | 审计 API 未挂 manifest 权限码 | 任何登录用户可看审计 | P1 |
| C6 | `risk_audit_record` 无产生来源 | 风险看板空转 | P2 |

### D. Token（配额/预估/预占/结算/统计）

| 编号 | 缺口 | 影响 | 优先级 |
|---|---|---|---|
| D1 | 预占不持久（Redis + 进程内存），无 `quota_reservation` | 多 worker/重启丢预占，可能超发 | P0 |
| D2 | `hold_id` 仅按 `execution_id`，多步冲突 | 同一 run 多步预占互相覆盖 | P0 |
| D3 | `usage_record` 幂等键依赖可空列，无 `source/idem_key` | Harness 结算无法可靠去重 | P0 |
| D4 | 无模型价格表与价格快照 | `cost` 由调用方随意传入，无法审计 | P1 |
| D5 | 无用量聚合统计（日/人/组织/模型）与导出 | 只有原始流水 | P1 |
| D6 | 预估为字符启发式，无模型 tokenizer | 预占偏差 | P2 |
| D7 | 无 Harness 会话级并发/速率限制（仅有工作流并发槽） | 可能打爆后端 | P1 |

---

## 3. 落地方案

### 3.1 模块划分

新增一个插件 `harness`，不改造既有模块语义：

```
base/plugins/harness/
├── manifest.json            # route_prefix=/v1/harness, models=[...], menus, permissions
├── models/                  # harness_client / identity / session / run / step / audit_event / action_policy
├── schemas/
├── services/
│   ├── client_auth_service.py     # 凭据校验、签名、IP 白名单
│   ├── identity_service.py        # 外部身份 → OwnerContext
│   ├── session_service.py         # 会话生命周期
│   ├── run_service.py             # run 生命周期 + step 上报
│   ├── meter_service.py           # 预估/预占/结算/释放（包 QuotaService）
│   ├── policy_service.py          # 危险操作分级与决策
│   └── audit_service.py           # 语义审计事件写入
├── api/v1/
│   ├── ingress_router.py          # 给 Harness 调用（服务账号鉴权）
│   ├── admin_router.py            # 控制台
│   └── stats_router.py
```

公共层改动（最小侵入）：

- `base/common/quota`：新增 `quota_reservation` 模型；`quota_estimate` 支持显式 `hold_key`（`source:execution_id:seq`）；`quota_settle` 支持 `idem_key`。
- `base/plugins/audit`：`audit_log` 增补语义字段；统一 `trace_id` 写入，去掉双中间件重复写。
- `base/plugins/approval`：启用插件，登记 `harness_action` 执行器。
- `base/plugins/agent`：可选启用；`workflow_execution` 增补 `session_ref`。

### 3.2 新增表与字段

#### 新增表（靠 `generate_schemas` 自动建）

| 表 | 关键字段 | 说明 |
|---|---|---|
| `harness_client` | `client_id`(unique)、`name`、`secret_hash`、`owner_type`/`owner_id`（默认真实主体）、`scopes` JSON、`ip_allowlist` JSON、`status`、`expires_at`、`last_used_at` | Harness 接入凭据 |
| `harness_identity` | `issuer`、`external_subject`、`display_name`、`owner_type`、`owner_id`、`status`、`meta` JSON；`UNIQUE(issuer, external_subject)`；index `(owner_type,owner_id)` | 外部身份 → 本地主体 |
| `harness_session` | `external_session_id`、`client_id`、`owner_type`/`owner_id`、`title`、`status`(active/paused/closed)、`started_at`、`last_active_at`、`closed_reason`、`total_tokens`、`meta` JSON；`UNIQUE(client_id, external_session_id)` | 一次 Harness 会话 |
| `harness_run` | `session` FK、`client_id`、`trigger_type`、`model`、`status`(queued/running/paused/succeeded/failed/cancelled/interrupted)、`input_digest`、`input_summary`、`output_summary`、`error_code`/`error_message`、`tokens_in/out`、`cost`、`quota_hold_id`、`approval_instance_id`、`trace_id`、`started_at`/`completed_at`；index `(session,created_at)`、`(status,created_at)` | **`run.id` 即对外的 `execution_id`** |
| `harness_step` | `run` FK、`seq`、`step_type`(llm/tool/http/file/db/subagent)、`name`、`node_id`、`status`、`started_at`/`ended_at`、`latency_ms`、`tokens_in/out`、`cost`、`risk_level`、`policy_decision`、`approval_instance_id`、`input_digest`/`output_digest`、`error`；`UNIQUE(run, seq)` | 可查询的步骤摘要 |
| `harness_audit_event` | `event_no`、`session_ref`、`run_ref`、`step_ref`、`actor_type`(usr/cus/service/system)、`actor_id`、`actor_name`、`action`、`target_type`/`target_id`、`risk_level`、`decision`(allow/deny/approval_required)、`reason`、`approval_instance_id`、`trace_id`、`ip`/`ua`、`policy_version`、`payload_redacted` JSON；`UNIQUE(run_ref, event_no)` | 语义审计（合规用） |
| `harness_action_policy` | `action_pattern`、`resource_type`、`risk_level`、`require_approval`、`approval_flow_id`、`approver_role_code`、`redact_fields` JSON、`priority`、`enabled`；`UNIQUE(action_pattern, resource_type)` | 危险操作分级策略 |
| `model_price` | `provider`、`model`、`currency`、`unit_tokens`(1000/1M)、`input_price`、`output_price`、`effective_from`、`effective_to`、`status`；`UNIQUE(provider,model,effective_from)` | 计价基准 |
| `quota_reservation` | `hold_id`(unique)、`owner_type`/`owner_id`、`plan_id`、`items` JSON（预占）、`charged` JSON（已结算）、`status`(held/partial/settled/released/expired)、`source`(agent/harness)、`execution_ref`、`expire_at`；index `(status,expire_at)`、`(owner_type,owner_id)` | 持久化预占（替代内存 hold） |

#### 存量表增补（幂等 SQL）

| 表 | 增补字段 | 目的 |
|---|---|---|
| `usage_record` | `source` varchar(20) default 'agent'；`idem_key` varchar(160) unique；`session_ref`、`model`、`provider`、`currency`、`price_snapshot` JSON | 跨来源计量、稳定去重、可审计计价 |
| `trace_event` | `source` varchar(20) default 'agent'；`session_ref`；index `(source,execution_id,seq)`、`(source,created_at)` | Harness trace 复用同一事件流 |
| `audit_log` | `actor_type`、`action_code`、`risk_level`、`decision`、`approval_instance_id`、`session_ref`、`run_ref`、`payload_hash` | 语义审计与审批关联（`level`/`business_no` 已有，可兼容） |
| `workflow_execution` | `session_ref` varchar(100) nullable | Harness 调工作流时归入会话（P3） |
| `audit_config` | 新增 `harness_action` 模块种子行 | 危险动作保留期/敏感字段配置 |

> 迁移写法：`DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns ... ) THEN ... END IF; END $$;`，索引用 `CREATE INDEX IF NOT EXISTS` / 唯一索引前先查 `pg_indexes`；不使用 `ON CONFLICT`、不原地删除旧唯一约束（openGauss 兼容）。新表不写建表 SQL，交给 `generate_schemas(safe=True)`。

### 3.3 后端接口清单

**Harness 侧（服务账号鉴权，`/v1/harness`）**

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/v1/harness/sessions` | 开启/恢复会话，返回 `session_id` + 配额快照 |
| POST | `/v1/harness/sessions/{id}/close` | 关闭会话 |
| POST | `/v1/harness/runs` | 开启一次执行：预估 → 预占 → 返回 `run_id`、`hold_id`、`policy_flags` |
| POST | `/v1/harness/runs/{run_id}/steps` | 上报步骤（start/finish 合并批量，按 `seq` 幂等） |
| POST | `/v1/harness/runs/{run_id}/usage` | 批量结算真实 token（`tokens_in/out/model/step_seq`） |
| POST | `/v1/harness/runs/{run_id}/complete` \| `/fail` \| `/cancel` | 收尾：释放余额、写审计、落状态 |
| POST | `/v1/harness/actions/check` | 危险动作决策：`allow/deny/approval_required` + `approval_instance_id` |
| GET | `/v1/harness/runs/{run_id}/trace?cursor=&limit=` | trace 分页 |
| GET | `/v1/harness/quota` | 当前主体配额看板（含 held） |
| GET | `/v1/harness/stats/usage?from=&to=&group_by=` | 用量聚合（day/user/org/model） |

**控制台（RBAC 权限码）**

| 方法 | 路径 | 权限码 |
|---|---|---|
| GET/POST/PUT/DELETE | `/v1/harness/clients` | `harness:client:manage` |
| GET/POST/PUT/DELETE | `/v1/harness/identities` | `harness:identity:manage` |
| GET | `/v1/harness/sessions`、`/sessions/{id}` | `harness:session:view` |
| POST | `/v1/harness/sessions/{id}/close` | `harness:session:manage` |
| GET | `/v1/harness/runs`、`/runs/{id}` | `harness:run:view` |
| GET | `/v1/harness/audit-events` | `harness:audit:view` |
| GET/POST/PUT/DELETE | `/v1/harness/policies` | `harness:policy:manage` |
| GET | `/v1/quota/reservations` | `quota:reservation:view` |
| POST | `/v1/quota/reservations/{hold_id}/release` | `quota:reservation:release` |
| 复用 | `/v1/quota-plans`、`/v1/usage-records`、`/v1/quota` | `quota:plan:manage` / `quota:usage:view` |
| 复用 | `/v1/approval/*`（启用插件） | `approval:*` |

> 新增权限码写入 `harness/manifest.json` 的 `permissions[]`，由插件启用流程自动建权限点与菜单。

### 3.4 `session_id` / 一次执行 的映射关系

```
Harness 外部会话 (external_session_id)
        └─ harness_session（本地会话，唯一锚点，绑定 owner=usr:{user_id} 或 cus:{customer_id}）
              ├─ harness_run #1  (run.id → execution_id)
              │     ├─ harness_step seq=1 (llm)  ─ trace_event(seq=1) ─ usage_record(node_id="llm", seq=1)
              │     ├─ harness_step seq=2 (tool) ─ trace_event(seq=2) ─ usage_record(node_id="tool:x", seq=2)
              │     └─ harness_audit_event（风险/拒绝/审批事件）
              └─ harness_run #2  ...
（可选）harness_run → workflow_execution.id（session_ref 回填），复用 agent 执行链路
```

约定：
- `trace_id` 在 ingress 生成，随响应返回并由 Harness 回传；`audit_log.trace_id`、`trace_event.payload.trace_id`、`harness_audit_event.trace_id` 三处一致。
- `execution_id = harness_run.id`；同一 run 内 `seq` 全局单调递增，作为 `trace_event.seq`、`harness_step.seq`、`usage_record.seq` 共用。
- `usage_record.idem_key = "harness:{run_id}:{node_id}:{seq}"`；`node_id` 取 step 名称/工具名（如 `llm`、`tool:file_write`）。
- 一个 Harness 会话可跨多个 run；配额按 `owner`（用户）账户累计，会话只做展示与汇总。

### 3.5 Token 计量口径（预占 → 结算 → 释放）

**预估（进入外部调用之前）**

```
items = {
  "token": estimate_tokens(prompt + system, reserve_output=max_output_tokens),
  "concurrency": 1              # 套餐配置项，用于会话级并发
}
```
- 现有 `estimator.estimate_tokens` 为字符启发式，P0 直接沿用；P2 引入按模型 tokenizer/比例表（`model_price` 同表可加 `tokenizer_ratio`）。
- 预估宁高不低：`reserve_output` 必须大于模型最大输出。

**预占（一次 run 一次 hold）**

```
hold_id = f"harness:{run_id}"
QuotaService.quota_estimate(owner, items, execution_id=run_id, hold_key=hold_id)
```
- 需要给 `quota_estimate` 增加 `hold_key` 参数（否则内部仍用 `str(execution_id)`，同一 run 多步会覆盖）。
- 预占成功后先写 `quota_reservation(status=held)`，Redis 只做加速；每次预占/结算落 DB，保证多 worker 可恢复。

**结算（每个 step 完成后）**

```
usage = [{
  "execution_id": run_id,
  "node_id": "llm" | "tool:xxx",
  "seq": step_seq,
  "resource_type": "llm_token",
  "amount": tokens_in + tokens_out,
  "tokens_in": n, "tokens_out": m,
  "model": "...", "idem_key": f"harness:{run_id}:{node_id}:{seq}"
}]
QuotaService.quota_settle(hold_id, usage, owner=owner)
```
- 去重优先查 `usage_record.idem_key`（新增），老链路仍兼容 `(execution_id,node_id,seq)`。
- `held` 按真实用量转 `used`，差额继续留作后续 step 预占；所有 step 完成后余额释放。
- 成本：结算时按 `model_price` 取生效记录，`cost = tokens_in/unit*input_price + tokens_out/unit*output_price`，把价格快照写入 `usage_record.price_snapshot`，避免调价影响历史账单。

**释放与兜底**

| 场景 | 动作 |
|---|---|
| run 正常结束 | `quota_release(hold_id)` 释放剩余；`quota_reservation.status=settled` |
| run 失败/取消 | 已产生用量先结算，再释放剩余；写 `harness_audit_event(decision=deny/cancel)` |
| 服务崩溃 | 每分钟 `cleanup_stale_holds` 扫描 `quota_reservation(status=held, expire_at<now)` 释放，并把 run 置 `interrupted` |
| 周期滚动 | 沿用 `quota_reconcile_task`；`quota_account.period_start/end` 由套餐 `token` 周期决定 |

**口径表**

| 资源 | resource_type | amount | 备注 |
|---|---|---|---|
| 模型 token | `llm_token` | in+out | 主计量项 |
| 工具调用 | `tool_call` | 1 次 | 可选套餐项 |
| 检索 | `kb_search` | 1 次 | 复用现有 |
| 向量写入 | `vector_write` | 条数 | 复用现有 |
| 工作流运行 | `workflow_run` | 1 次 | 复用现有 |

### 3.6 审计事件模型

**三层落库，避免重复**

1. HTTP 层 → `audit_log`（已有，补齐 `actor_type/action_code/risk_level/decision/session_ref/run_ref`；统一由 TraceMiddleware 写，关闭 AuditMiddleware 重复写）。
2. 语义动作层 → `harness_audit_event`（谁在何时对哪个对象做了什么、策略判定、审批实例）。
3. 数据变更层 → `data_change_log`（已有，配置/权限/策略变更自动留痕）。

**事件字段语义**

| 字段 | 取值示例 |
|---|---|
| `action` | `session.open` / `run.start` / `llm.call` / `tool.invoke` / `file.read` / `file.write` / `http.call` / `secret.read` / `policy.update` |
| `target_type` / `target_id` | `file` / `/data/report.xlsx`；`tool` / `shell.exec`；`model` / `deepseek-v3` |
| `risk_level` | `low/medium/high/critical`（复用 `RiskAuditRecord` 枚举） |
| `decision` | `allow` / `deny` / `approval_required` / `approved` / `rejected` |
| `actor_type` | `usr`（后台用户）/ `cus`（客户）/ `service`（Harness 客户端）/ `system` |
| `payload_redacted` | 按 `audit_config.sensitive_fields` 与策略 `redact_fields` 打码；默认只存摘要哈希 |

**危险操作策略（`harness_action_policy` 种子）**

| action_pattern | risk_level | require_approval | 说明 |
|---|---|---|---|
| `file.write` / `file.delete` | high | true / 可配置 | 文件落盘 |
| `shell.exec` / `db.write` | critical | true | 命令与库写入 |
| `http.call`（非白名单域名） | high | false（先 deny） | 外联 |
| `secret.read` / `credential.*` | critical | true | 密钥读取 |
| `llm.call` / `kb.search` | low | false | 常规 |

审批走既有 `approval_flow`：`business_type='harness_action'`、`action='execute'`，`business_data` 存动作快照；通过后由 `register_executor("harness_action","execute", ...)` 回放（默认只记录放行，不自动执行危险动作）。

### 3.7 前端页面清单

| 模块 | 页面 | 状态 |
|---|---|---|
| 账号 | 用户、部门/组织、角色、权限、菜单 | 已有（`user/department/role/permission`），可直接复用 |
| 接入 | Harness 客户端管理、外部身份映射 | 新增 `harness/clients.vue`、`harness/identities.vue` |
| 运行 | 会话列表、会话详情（run 时间线）、运行详情（步骤 + trace + token + 审批链接） | 新增 `harness/sessions.vue`、`harness/runs.vue`、`harness/run-detail.vue` |
| Token | 套餐管理、配额看板、计量流水、用量统计、预占管理 | 新增 `quota/plans.vue`、`quota/board.vue`、`quota/usage.vue`、`quota/stats.vue`、`quota/reservations.vue` |
| 审计 | 审计日志、数据变更、登录审计、风险审计、审计配置、全链路追踪 | 已有（`audit/*`），补 `harness/audit-events.vue` |
| 审批 | 审批中心、流程规则、实例详情 | 已有（`approval/*`），启用插件即可 |

菜单挂到现有 `/system` 或新增一级 `/harness`，权限码与 `manifest.json` 同步。

---

## 4. 分阶段实施顺序与依赖

```
P0 地基（阻塞后续）
 ├─ 1. 启用 approval 插件（只启用不接线）
 ├─ 2. 新增 harness 插件骨架 + manifest（models/permissions/menus）
 ├─ 3. harness_client / identity / session / run / step 五表 + 服务账号鉴权
 ├─ 4. quota_reservation 持久化 + quota_estimate(hold_key) + usage_record(idem_key,source)
 └─ 5. ingress 六个接口（sessions/runs/steps/usage/complete/trace）
        ↓
P1 计量与审计（可并行）
 ├─ A. 计价 model_price + 结算接入 + 用量聚合 stats + 预占管理 API
 └─ B. harness_audit_event + audit_log 语义字段 + 危险动作 policy + 审计页
        ↓
P2 审批与体验
 ├─ C. actions/check → 审批门禁 + 执行器登记 + 风险记录
 └─ D. 前端五类页面（接入/运行/Token/审计/审批）
        ↓
P3 组织与 Agent 集成
 ├─ E. 组织级 owner（dept/customer_organization）与汇总
 └─ F. 启用 agent，workflow_execution.session_ref，run↔execution 双向可查
```

**关键依赖与并行度**

- P0-3 是全部后续的前置；P0-1/2 可与 P0-3 并行。
- P1-A（Token）与 P1-B（审计）无交集，可两人/两线并行；都依赖 P0 的表与接口契约冻结。
- P2-D 前端可在 P1 接口契约确定后提前并行，按 mock 先行。
- P3-E 依赖 `owner_type` 扩展与 `PlanService.resolve_plan` 改造；P3-F 依赖 agent 插件启用与 `trace_event` 增列完成。
- 不建议先做 P3：Harness 独立执行不依赖 Agent 工作流，先把 P0/P1 打通即可交付可用系统。

---

## 5. 风险与待确认决策

1. **Harness 的角色定位**：本文按"Harness 是外部调用方，通过 `/v1/harness/*` 上报会话/步骤/用量"设计。若 Harness 反过来要由本系统驱动（下发任务），需增加 outbound 队列与回调，P0 范围会扩大。
2. **多 worker 部署**：现有 hold 依赖进程内 dict，必须落 `quota_reservation`；若确定单 worker 可降级为 P2，但重启丢预占风险仍在。
3. **审计双写**：`AuditMiddleware` 与 `TraceMiddleware` 同时启用会重复写 `audit_log`；建议 P1 统一为 TraceMiddleware 单写，`AUDIT_LOG_HTTP_REQUESTS` 与 `TRACE_ENABLED` 互斥。
4. **`gate_write` 异常默认放行**：安全场景应改为 fail-closed（至少 high/critical 动作），需要确认是否影响既有业务。
5. **openGauss 兼容**：所有存量表变更必须 `DO $$ + information_schema` 幂等；唯一索引先查存在再建；禁止 `ON CONFLICT`。
6. **配额口径**：token 是否按 `in+out` 合计、输出是否倍率计价、是否区分模型价格，需要产品确认后写入 `model_price`。
7. **历史数据**：`usage_record`/`trace_event` 新增 `source` 默认 `agent`，存量无需回填；`idem_key` 允许为空，仅 Harness 新写入强制非空。
