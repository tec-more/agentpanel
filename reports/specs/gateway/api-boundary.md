# 接口归属说明：Gateway / LLM / Harness

> 目的：明确三类接口的边界与凭据类型，避免对接时混用。
> 当前部署形态：网关为 **embedded 独立子应用**，随业务 API 启动。

## 1. 路径归属

| 前缀 | 归属 | 用途 | 凭据 |
|---|---|---|---|
| `/v1/gateway/*` | 模型透传数据面（独立子应用） | dsh 调模型：`POST /v1/gateway/chat/completions`、`GET /v1/gateway/health` | **仅**租约虚拟 key `dgw.<lease_id>.<secret>` |
| `/v1/llm/*` | llm 插件（业务 API） | 后台录入 provider/model/api_key；`/v1/llm/client/*` 供登录用户内部聊天 | JWT 登录态 / 超级管理员 |
| `/v1/harness/*` | harness 插件（业务 API） | 客户端凭据、session/run、事件上报、审批、配额；`/v1/harness/gateway/leases` 签发/续期/吊销租约 | Harness 客户端凭据 `client_id.secret` |

## 2. 双向拒绝（强制）

- 网关侧：`/v1/gateway/*` 只接受 `dgw.*` 虚拟 key。
  - JWT（`eyJ...` 三段式）→ `401`，`error.type=gateway_auth_error`，并写入
    `harness_audit_event`（`event_source=gateway`, `action=gateway.auth_rejected`, `reason=jwt_not_allowed`）。
  - 其它格式 / 缺凭据 → `401`。
- 业务侧：`/v1/llm/*`、`/client/*`（即 `/v1/llm/client/*`）基于 `get_current_user_id`，
  收到 `dgw.*` 虚拟 key → `401`，detail=`该接口不接受网关租约虚拟 key`。
- harness 客户端接口使用 `client_id.secret`，同样不接受 JWT 或 `dgw.*`。

## 3. 隔离边界

| 维度 | 网关 | 业务 API |
|---|---|---|
| 鉴权依赖 | `require_gateway_lease`（独立依赖树） | `get_current_user_id` / `require_harness_client` |
| 中间件 | 排除于业务审计 / 链路追踪 / owner 上下文与 F8 限流 | 正常参与 |
| 记账 | `usage_record(source=gateway, gateway_key=<lease_id>)`，成功 `llm_token`、失败 `gateway_error` | 各自业务表 |
| 审计 | `harness_audit_event(event_source=gateway)` | `audit_log` / `input_layer_log` |
| 日志 | `logs/gateway.log`（`component=gateway`） | `logs/info.log` / `logs/error.log` |
| 限流 | 按 `lease_id` 计数（`_gateway_rate_windows`） | 按 owner identity 计数（F8） |
| 配置 | `harness.manifest.config.gateway` | 各自插件配置 |

## 4. 启动与文档

- 部署形态由 `harness.manifest.config.gateway.deployment` 决定，默认 `standalone`：
  - 独立服务 数据面独立进程：`python -m base.common.gateway.server`，监听 `127.0.0.1:9999`；
  - app 业务 API：`python run.py`，监听 `127.0.0.1:9998`，**不挂载** `/v1/gateway`。
- 数据面文档：`http://127.0.0.1:9999/docs`（OpenAPI：`/openapi.json`）。
- 业务文档：`http://127.0.0.1:9998/docs`，**不包含**网关路径。
- 退回方式：将 `gateway.deployment` 改为 `embedded` 并重启 app，数据面回到
  `http://127.0.0.1:9998/v1/gateway`（文档 `/v1/gateway/docs`），无需改代码。

## 5. 桌面端 dsh 调用约定

- 客户端 `base_url` 取租约签发响应中的 `base_url`（即 `gateway.public_base_url`），
  standalone 下为 `http://127.0.0.1:9999`。
- 探活 `GET /health`、请求 `POST /chat/completions`（embedded 时分别为 `/v1/gateway/health`、
  `/v1/gateway/chat/completions`）。
- 请求头只需 `Authorization: Bearer dgw.*`；**不需要**任何用户 JWT / 登录 token。
- 模型流量不经过 `/v1/harness/*`，业务 API 只负责签发租约与事件上报。
- 客户端还应在启动时拉取 `GET /v1/harness/egress-policy/snapshot?client_version=<n>`
  （Harness 客户端凭据）以获取出网策略快照，并按快照 fail-closed。

## 6. 出网策略来源（app，非执行边界）

- `GET /v1/harness/egress-policy/snapshot` 下发可版本化、可哈希校验的策略快照：
  工具禁用清单（`web_fetch` / `web_search` 等）、`allow_client_non_gateway`（默认 `false`）、
  网关 `base_url`，以及 provider 域名白名单。
- 白名单**唯一来源**是 `gateway.provider_domain_allowlist`，快照直接读取同一份配置，
  网关侧校验语义不变，不存在第二份清单。
- 该接口只是**策略来源**，不阻断出网；客户端管理员、原始套接字、IPv6/QUIC 等仍可绕过，
  真正阻断依赖终端网络策略或容器网络策略。
- 版本未知/过低返回 `426` 且 `compatible=false`；客户端必须 fail-closed。
- 策略变更、快照下发、版本拒绝均写入 `harness_audit_event`（`event_source=policy`）。
- 完整契约与客户端对接示例见 `reports/specs/harness-egress-policy/spec.md`。
