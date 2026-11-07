# Harness 网关额度耗尽中断机制 Spec

状态：待评审
适用插件：harness（embedded 网关，挂载 `/v1/gateway`）
关联任务：第 2 项「额度耗尽的中断机制」

## 1. 目标

在网关数据面建立一套**共享存储、原子扣减、可中断**的额度控制链路：

1. 转发前预检租约预算与租户/组织配额，余额不足直接拒绝，不发上游请求；
2. 流式转发时按已收增量估算用量，越过预算主动断开上游、向客户端发终止信号，记账标 `partial` 并写审计；
3. 额度耗尽可自动/手动吊销租约，新请求立即 401，吊销留审计且只影响目标租约/租户；
4. 计数与并发判断全部走共享存储，Redis 优先、DB 兜底，多副本不各算一份；
5. 单请求 max output token 上限 + 单租户并发上限；
6. 看板展示已用/剩余/预计可支撑请求数，以及拒绝/截断次数。

## 2. 明确边界

- 已经发给 provider 的 token 收不回来，截断只限制超支幅度，**不承诺零超支**。
- 不调用真实 provider；验证只用本地假 provider（loopback override）。
- 现有网关记账/对账链路（`record_gateway_usage`、`harness_reconcile_*`）保持兼容，不重做。
- Redis 未启用时使用 DB 兜底；两种后端都必须是**跨进程共享**的，禁止退化为进程内计数。

## 3. 设计决策

### 3.1 共享额度存储（Redis 优先 / DB 兜底）

新增服务 `base/common/gateway/budget.py`：`GatewayBudgetService`。

Redis key 与语义：

| key | 类型 | 字段/值 | 说明 |
| --- | --- | --- | --- |
| `gw:budget:lease:{lease_id}` | hash | `budget`,`used`,`reserved`,`requests`,`rejected`,`truncated` | 租约级预算与计数 |
| `quota:{ot}:{oid}:token:{period}` | float | 已结算 used | 复用 QuotaService 的租户配额 key |
| `quota_held:{ot}:{oid}:token:{period}` | float | 在途预占 held | 复用 QuotaService 的租户配额 key |
| `gw:conc:{ot}:{oid}` | int | 在途请求数（TTL 60s 看门狗） | 单租户并发 |

原子性：预检「检查 + 预占」用一个 Lua 脚本完成（租约预算 + 租户 `used+held` 双校验后 `HINCRBYFLOAT reserved` / `INCRBYFLOAT held`，任一超限返回拒绝且不写入）。结算/释放各用一个 Lua 脚本做 `reserved→used` 与 `held→used` 转换，避免多副本竞态。

DB 兜底（Redis 不可用）：

- 新模型 `HarnessGatewayBudget`（`harness_gateway_budget`）：`lease_id` 唯一，`owner_type/owner_id`、`budget_tokens/used_tokens/reserved_tokens`、`request_count/rejected_count/truncated_count`、`status(active/exhausted)`、`last_settled_at`。
- 新模型 `HarnessGatewayConcurrency`（`harness_gateway_concurrency`）：`(owner_type, owner_id)` 唯一，`inflight`，`updated_at`；超过 60s 未更新的行在下次获取时归零（崩溃恢复）。
- DB 预检使用事务 + `SELECT ... FOR UPDATE`，语义为「预占先计入 used」：`HarnessGatewayBudget.used_tokens += reserve`、`QuotaAccount.used["token"] += reserve`；结算按 `actual - reserved` 差额修正，释放按 `-reserved` 回退。计数只存在 DB，多个副本读同一行，天然共享。

租户配额解析复用 `PlanService.resolve_plan` 的 `quota_items["token"]`；无套餐绑定视为不限额（保持现有语义），账户 `status != active` 时拒绝。

### 3.2 入口预检

`base/common/gateway/router.py::chat_completions` 在**解析凭据与发送上游请求之前**调用 `GatewayBudgetService.grant(lease, body)`：

- prompt 估算：遍历 `messages` 文本（字符串或 content 数组 text），`ceil(chars / estimate_chars_per_token)`，默认 2.0（宁高不低）。
- 单请求输出上限：`cap = gateway.max_output_tokens_per_request`（默认 4096）；请求自带 `max_tokens` / `max_completion_tokens` 时取更小值。
- 可用额度 `remaining = min(lease 剩余, 租户剩余)`；`allowance = min(cap, requested, remaining - prompt_est)`。
- `allowance < 1` 或租约/租户余额不足时拒绝；否则以 `prompt_est + allowance` 作为本次预留额度原子预占。
- 回溯请求体，把 `max_tokens` / `max_completion_tokens` 夹紧为 `allowance`（缺失时补 `max_tokens`），确保 provider 侧也受限。
- 成功后获取租户并发槽（`max_concurrent_requests_per_owner`，默认 8）。

拒绝错误（HTTP 直接返回，不发上游）：

```json
{"error":{"message":"...","type":"quota_exceeded","code":"quota.balance_insufficient","remaining":N,"requested":N,"lease_id":"gl_x","resource":"token"}}
```

错误码映射：

| 场景 | HTTP | code |
| --- | --- | --- |
| 租户/组织余额不足 | 402 | `quota.balance_insufficient` |
| 租约预算不足 | 402 | `quota.lease_budget_exhausted` |
| 配额账户停用 | 403 | `quota.account_frozen` |
| 单租户并发超限 | 429 | `quota.concurrency_limit` |

拒绝时：`gateway.quota_rejected` 审计（risk=medium, decision=deny）、拒绝计数 +1、Prometheus 计数 +1；若租约/租户已耗尽且 `auto_revoke_on_exhausted=true`，触发自动吊销。

### 3.3 流式看门狗

`router._scan_sse_chunk` 扩展为同时累计输出字符数（`choices[].delta.content`、`reasoning_content`、`tool_calls[].function.arguments`），保留原 usage 帧解析。

`_forward_stream.relay()` 每转发一个 chunk 前检查：

```text
estimated_total = prompt_estimate + ceil(output_chars / estimate_chars_per_token)
若 grant.limit_tokens > 0 且 estimated_total > grant.limit_tokens → 截断
```

截断动作：

1. `break` 停止读取，`await upstream.aclose()` 主动断开上游；
2. 向客户端发送**可识别终止帧**（不是正常结束）：
   ```text
   data: {"error":{"message":"额度预算耗尽，流式输出被截断（估算触发）","type":"quota_exceeded","code":"quota.lease_budget_exhausted","partial":true,"estimated":true,"truncated":true}}

   data: [DONE]
   ```
3. 记账：`usage_record` 保留 `resource_type="llm_token"`、`usage_kind="partial"`、`amount=估算总 token`、`price_snapshot={truncated:true,truncation_reason:"estimated_budget_exceeded",estimated:true,billing_status:"partial"}`；
4. 审计 `gateway.stream_truncated`（risk=high），截断计数 +1，Prometheus +1；
5. 结算预算并释放并发槽；耗尽时自动吊销租约。

非流式请求无法中途截断，按实际（provider usage 优先，缺失用估算）结算；若实际超过预留，在 `price_snapshot` 标 `over_budget=true` 并计入截断/超支统计，不伪装成正常。

### 3.4 租约吊销联动

- `GatewayLeaseService.revoke_internal(lease_id, *, reason, actor_type, actor_id, event_source)`：状态置 `revoked`、写 `revoked_at`、审计 `gateway.lease_revoked`（detail: reason/actor/source）；幂等；只改目标 lease 行。
- 自动吊销：预算服务在「租约预算耗尽 / 租户余额耗尽 / 流式截断」时调用，reason 分别 `lease_budget_exhausted` / `balance_insufficient` / `stream_truncated`；受 `auto_revoke_on_exhausted` 控制。
- 手动应急吊销：新增 `POST /v1/harness/dashboard/gateway/leases/{lease_id}/revoke?reason=...`（superuser），审计 actor 为管理员。
- 现有客户端吊销接口 `DELETE /v1/harness/gateway/leases/{lease_id}` 复用 `revoke_internal` 并补审计。
- 吊销后新请求由现有 `GatewayLeaseService.authenticate` 返回 401「网关租约已吊销」。

### 3.5 上限保护

- `max_output_tokens_per_request`：默认 4096，单请求夹紧。
- `max_concurrent_requests_per_owner`：默认 8，共享并发槽；所有结束路径（正常/失败/截断/客户端断开）都释放；Redis TTL 60s、DB `updated_at` 过期归零兜底。
- 租约签发新增可选 `budget_tokens`，写入 `lease.meta`；缺省取 `gateway.lease_budget_tokens`（0=不设租约级上限，仅租户配额）。

### 3.6 可观测

- `GatewayBudgetService.snapshot(lease)`：返回 `budget_tokens / used_tokens / reserved_tokens / remaining_tokens / request_count / rejected_count / truncated_count / avg_tokens_per_request / estimated_requests`（`estimated_requests = remaining / max(avg,1)`）。
- 新增 `GET /v1/harness/dashboard/gateway/quota`（superuser，支持 `client_id/owner_type/owner_id/active_only/limit`），返回 `summary + items`。
- `HarnessDashboardService.anomalies()` 增加 `gateway_quota` 摘要（租约数、拒绝数、截断数、已耗尽租约数），与既有异常清单同页。
- Prometheus：`gateway_quota_reject_total{reason}`、`gateway_quota_truncate_total{reason}`。
- 前端 `Usage.vue` 新增「网关额度中断」tab：汇总标签 + 租约表（预算/已用/剩余/预计请求数/拒绝/截断/状态），并支持手动吊销。

### 3.7 记账改动

`service.record_gateway_usage` 新增参数：`usage_kind="normal"`、`truncated=False`、`truncation_reason=None`、`estimated=False`、`over_budget=False`。partial 记录仍为 `llm_token`，金额为估算值，`price_snapshot` 保留截断语义；失败请求仍按 `gateway_error` 记 0。

## 4. 配置项（gateway.config DEFAULTS + manifest）

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `lease_budget_tokens` | 0 | 租约默认 token 预算，0=不限 |
| `max_output_tokens_per_request` | 4096 | 单请求输出上限 |
| `max_concurrent_requests_per_owner` | 8 | 单租户并发请求上限 |
| `estimate_chars_per_token` | 2.0 | 流式估算比率（宁高不低） |
| `min_output_allowance_tokens` | 1 | 允许开始流式输出的最小额度 |
| `auto_revoke_on_exhausted` | true | 耗尽时自动吊销当前租约 |
| `gateway_quota_ttl_seconds` | 86400 | Redis 预算/计数 key TTL |

## 5. 改动文件清单

| 文件 | 改动 |
| --- | --- |
| `base/common/gateway/budget.py` | 新增：共享存储、Lua 原子预占/结算/释放、估算、快照、看板、自动吊销 |
| `base/common/gateway/router.py` | 入口预检、输出夹紧、流式看门狗与终止帧、结算/释放接线 |
| `base/common/gateway/service.py` | `record_gateway_usage` 增加 partial/估算/截断标记 |
| `base/common/gateway/audit.py` | 新增额度拒绝/截断审计写入 helper |
| `base/common/gateway/config.py` | 新增 7 项默认配置 |
| `base/common/quota/metrics.py` | 新增拒绝/截断计数器 |
| `base/plugins/harness/models/harness.py` | 新增 `HarnessGatewayBudget`、`HarnessGatewayConcurrency` |
| `base/plugins/harness/services/gateway_lease_service.py` | 签发支持 `budget_tokens`；`revoke_internal` + 审计 |
| `base/plugins/harness/services/dashboard_service.py` | anomalies 增加 `gateway_quota` |
| `base/plugins/harness/api/v1/dashboard_router.py` | 额度看板、手动吊销接口 |
| `base/plugins/harness/api/v1/gateway_router.py` | 签发 schema 增加 `budget_tokens` |
| `base/plugins/harness/manifest.json` | gateway 配置项 |
| `migrations/harness_create_table_gateway_budget_<ts>.sql` | 幂等建两张新表（保证存量库升级） |
| `web/src/api/harness.js` | 额度看板/吊销 API |
| `web/src/views/harness/Usage.vue` | 新增「网关额度中断」tab |

## 6. 验证方案（假 provider，可控余额）

1. 启动本地假 provider（`127.0.0.1:<port>`，`/chat/completions`，支持 stream/non-stream、记录请求次数、可忽略 `max_tokens` 输出指定长度）。
2. 临时修改 manifest：`gateway.allow_loopback=true`、`gateway.upstream_base_url_override=http://127.0.0.1:<port>`；重启后端；测试结束还原。
3. 造数据：harness client、session/run（owner 指向测试租户）、租约；必要时创建临时 QuotaPlan + 绑定。
4. 四类场景：
   - **余额不足拒绝**：租约预算 100，prompt 估算 >100 或租户 token 限额 50；断言 HTTP 402 + code，假 provider 请求数仍为 0，审计 `gateway.quota_rejected`，拒绝计数 +1。
   - **中途截断**：租约预算 120、prompt≈20、cap=200 → allowance≈100；假 provider 忽略 `max_tokens` 输出 300 token；断言 SSE 含 `"truncated":true`、`"estimated":true` 错误帧，上游连接被断开，`usage_record.usage_kind=partial`，审计 `gateway.stream_truncated`，截断计数 +1，租约自动吊销。
   - **吊销后 401**：管理员手动吊销另一租约；该 key 新请求 401；另一租户租约仍可用（非 401），验证不影响其他租户。
   - **多副本共享计数**：用两个独立 Python 进程初始化 Tortoise 后对同一租约并发调用 `grant`；预算 100，各申请 80 → 第二个被拒；先结算后再申请成功；确认 DB/Redis 中只有一份权威计数（不随进程各自翻倍）。
5. 可观测校验：`GET /dashboard/gateway/quota` 中 used/remaining/estimated_requests 与拒绝/截断次数正确；前端 tab 可加载。
6. 清理：删除测试 usage_record、audit、lease、临时 plan/binding/model/provider/key，还原 manifest，重启后端。

## 7. 验收标准

- [ ] 余额不足时无上游请求，返回 402 + 可识别 code，审计与计数可见。
- [ ] 流式超预算时主动断开上游并发送截断终止帧，记账 `usage_kind=partial` 且明确标估算截断，审计与计数可见。
- [ ] 自动/手动吊销后目标租约立即 401，其他租户租约不受影响，吊销有审计。
- [ ] 多进程并发预占只有一份共享计数，原子扣减无超发。
- [ ] 单请求输出上限与单租户并发上限生效。
- [ ] 看板展示已用/剩余/预计可支撑请求数及拒绝/截断次数。
- [ ] 全程未调用真实 provider，测试数据已清理。
