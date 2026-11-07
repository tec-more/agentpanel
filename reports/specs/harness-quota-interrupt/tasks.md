# 任务清单：Harness 网关额度耗尽中断机制

> 依据 `spec.md` 执行；任务间尽量按顺序，q2 完成后可并行 q3/q5/q6。

## T0 消除 `base/common/gateway` 对 `base/plugins/harness` 的反向依赖（前置任务）

- [x] 新增 `base/common/gateway/lease_auth.py`：以 raw SQL 校验
  `harness_gateway_lease` / `harness_session` / `harness_run`，
  覆盖格式/存在/状态/过期/SHA-256 常量时间比对/RPM/session open/run 终态；
  不导入任何 `base.plugins.harness` 服务或模型。
- [x] `base/common/gateway/auth.py` 改为调用 common 校验，不再延迟导入插件服务。
- [x] harness `GatewayLeaseService.authenticate` 改为委托 common 校验；
  签发/续期/吊销/RPM 策略字段与业务语义仍保留在 harness 服务。
- [x] 复验 40 项边界矩阵：`40/40 PASS`（格式 13、租约 7、session 4、run 8、RPM 3、正常 5）。
- [x] 模拟 harness 插件未加载：网关可导入/启动，无效租约与 JWT 均返回 401。

## T1 配置与指标

- [x] `base/common/gateway/config.py`：`DEFAULTS` 增加
  `lease_budget_tokens=0`、`max_output_tokens_per_request=4096`、
  `max_concurrent_requests_per_owner=8`、`estimate_chars_per_token=2.0`、
  `min_output_allowance_tokens=1`、`auto_revoke_on_exhausted=True`、
  `gateway_quota_ttl_seconds=86400`。
- [x] `base/plugins/harness/manifest.json` 同步同名配置。
- [x] `base/common/quota/metrics.py` 增加
  `gateway_quota_reject_total{reason}`、`gateway_quota_truncate_total{reason}`
  及 `inc_gateway_quota_reject/ inc_gateway_quota_truncate`（重复注册保护）。

验证：`python -c "from base.common.gateway.config import gateway_config; print(gateway_config()['max_output_tokens_per_request'])"`

## T2 共享额度存储（模型 + 服务）

- [x] `base/plugins/harness/models/harness.py` 新增：
  - `HarnessGatewayBudget`：`lease_id`(unique)、`owner_type/owner_id`、
    `budget_tokens/used_tokens/reserved_tokens`、`request_count/rejected_count/truncated_count`、
    `status`、`last_settled_at`；表 `harness_gateway_budget`。
  - `HarnessGatewayConcurrency`：`owner_type/owner_id` unique_together、`inflight`；
    表 `harness_gateway_concurrency`。
- [x] `migrations/harness_create_table_gateway_budget_<ts>.sql`：幂等
  `CREATE TABLE IF NOT EXISTS`（PG 语法，后端起服务时执行）。
- [x] 新增 `base/common/gateway/budget.py`：
  - `GatewayQuotaError(status_code, code, message, detail)`、`BudgetGrant`；
  - `estimate_prompt_tokens(body)`、`request_output_limit(body)`；
  - `grant(lease, body)`：Redis Lua 原子「租约 + 租户」双校验与预占；
    额度不足时按 `remaining - prompt` 收缩 allowance 重试一次；
    DB 兜底走事务行锁预扣；成功后获取并发槽；
  - `settle(lease, grant, *, usage, estimated_completion, truncated, over_budget)`；
  - `release(lease, grant)`；
  - `snapshot(lease)`、`list_dashboard(...)`、`summary(limit)`；
  - `record_reject(lease, reason)`、`record_truncate(lease, reason)`；
  - `maybe_auto_revoke(lease, reason)`（仅目标 lease）。
- [x] Redis Lua：
  - 预检脚本返回 `{ok, reason, used, held, limit}`；超限不写；
  - 结算脚本 `reserved→used`、`held→used`；
  - 释放脚本回退 `reserved/held`；
  - 计数器 `HINCRBY rejected/truncated`。
- [x] 并发槽：Redis `INCR gw:conc:{ot}:{oid}` + TTL 60s，超限回退；
  DB `HarnessGatewayConcurrency` 行锁 + 60s 过期归零。

验证：单进程调用 `grant/settle/release`，检查 Redis/DB 中 `used+reserved` 与 `held` 一致；
停 Redis（本机默认未启用）时走 DB 路径，值落在 `harness_gateway_budget` 与 `quota_account.used`。

## T3 入口预检与输出夹紧

- [x] `base/common/gateway/router.py::chat_completions`：解析 body 后、解析凭据前调用 `grant`；
  捕获 `GatewayQuotaError` → 审计 + 计数 + 自动吊销 + 返回 `type=quota_exceeded` 错误 JSON。
- [x] 扩展 `_error_response` 支持 `code/extra`（remaining/requested/lease_id/resource）。
- [x] `apply_caps` 把 `max_tokens/max_completion_tokens` 改为 `allowance`。
- [x] 失败路径（凭据/上游超时/不可达/非 2xx/客户端断开）调用 `release` 释放预占与并发槽。
- [x] `base/common/gateway/audit.py` 增加 `record_gateway_quota_event(...)`。

验证：假 provider 请求计数为 0（余额不足），响应 402 且 code 可识别。

## T4 流式看门狗与 partial 记账

- [x] `_scan_sse_chunk` 累计 `delta.content/reasoning_content/tool_calls.arguments` 字符数。
- [x] `_forward_stream.relay()` 每 chunk 估算总量，超过 `grant.limit_tokens` 时：
  断上游 → 发截断错误帧 + `[DONE]` → 标记 `state.truncated`。
- [x] `_finalize_stream` 以估算 usage 调 `settle(truncated=True)` 与 `record_gateway_usage(usage_kind="partial", ...)`；
  写审计 `gateway.stream_truncated`；截断计数 +1；自动吊销。
- [x] `service.record_gateway_usage` 增加 partial/estimated/truncation_reason/over_budget 参数。
- [x] 非流式：usage 优先用 provider 值，缺失用估算；超预留标 `over_budget`。

验证：假 provider 忽略 `max_tokens`；SSE 含 `"truncated":true`，上游在预算点被断开；
`usage_record` 有 `usage_kind=partial` 且 `price_snapshot.estimated=true`。

## T5 租约吊销联动

- [x] `GatewayLeaseService.issue` 支持 `budget_tokens`（写入 `meta`）。
- [x] `GatewayLeaseService.revoke_internal(lease_id, *, reason, actor_type, actor_id, event_source)`：
  幂等置 revoked + `revoked_at` + 审计 `gateway.lease_revoked`。
- [x] 客户端 `revoke()` 改走 `revoke_internal`（reason=`client_request`）。
- [x] `base/plugins/harness/api/v1/gateway_router.py` 签发 schema 增加 `budget_tokens`。
- [x] `base/plugins/harness/api/v1/dashboard_router.py` 新增
  `POST /dashboard/gateway/leases/{lease_id}/revoke`（superuser + reason）。
- [x] 自动吊销仅作用于当前 lease_id，不批量影响其他租户。

验证：吊销后同 key 401；另一租户租约仍通过鉴权。

## T6 上限保护

- [x] 单请求输出上限在 T3 夹紧。
- [x] 单租户并发上限在 T2 并发槽实现；`grant` 获取、所有收尾路径释放。
- [x] 租约默认预算从配置读取，签发放行 `budget_tokens`。

验证：并发上限设为 1 时第二个请求 429 `quota.concurrency_limit`。

## T7 可观测与看板

- [x] `base/common/gateway/budget.py::list_dashboard/summary`：租约预算/已用/剩余/预计请求数/拒绝/截断。
- [x] `base/plugins/harness/api/v1/dashboard_router.py` 新增 `GET /dashboard/gateway/quota`。
- [x] `HarnessDashboardService.anomalies()` 增加 `gateway_quota`。
- [x] `web/src/api/harness.js` 增加 `getGatewayQuota`、`revokeGatewayLease`。
- [x] `web/src/views/harness/Usage.vue` 增加「网关额度中断」tab（汇总标签 + 表 + 吊销按钮）。

验证：接口返回 used/remaining/estimated_requests/rejected/truncated；前端 build 通过。

## T8 假 provider 四类场景验证

- [x] 本地假 provider：`/chat/completions`，支持 stream、可配置输出 token 数、忽略 `max_tokens`、统计请求数。
- [x] 临时 manifest：`allow_loopback=true`、`upstream_base_url_override=http://127.0.0.1:<port>`；
  必要时插入临时 LLM provider/model/key 以便凭据解析（测试后删除）。
- [x] 造 harness client + session/run + lease（含 `budget_tokens`，必要时临时 QuotaPlan 绑定租户）。
- [x] 场景 1 余额不足拒绝：402 + code，假 provider 0 次，审计/计数存在。
- [x] 场景 2 中途截断：SSE 截断帧，partial 记账，审计/计数，自动吊销。
- [x] 场景 3 吊销后 401：目标租约 401，其他租户租约不受影响。
- [x] 场景 4 多副本共享计数：两个独立 Python 进程并发 `grant`，第二个被拒；结算后可再申请；
      确认共享存储只有一份权威值。
- [x] 场景 5 可观测接口数值正确。
- [x] 清理测试数据、还原 manifest、重启后端。

验证命令（示例）：
```powershell
.\.venv\Scripts\python.exe <临时验证脚本>.py
.\.venv\Scripts\python.exe -m compileall base/common/gateway base/plugins/harness
cd web; npm run build
```

## T9 汇报

- [x] 汇总改动文件、四类场景 PASS/FAIL、可观测指标截图/数值、遗留边界（超支不归零）。
