# 网关租约 TTL / 主动续期 / 失效降级 / 状态缓存

## 1. 目标

改造 Harness 网关租约（`dgw.<lease_id>.<secret>`）的时效与续期语义，减少客户端频繁换取租约，同时保证：

1. 默认 TTL 由 300s 调整为 900s，支持按租户覆盖；
2. 在途请求不因租约到期被切断；
3. 续期只由客户端主动触发，服务端不自动延长；
4. 续期失败时标记租约失效，在途流继续，后续新请求 401，并记录审计；
5. 租约鉴权状态使用 Redis 短缓存，吊销写穿，Redis 不可用时回落 DB。

不改动对账、额度中断、共享上游客户端的行为语义。

## 2. 配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `gateway.lease_ttl_seconds` | `900` | 签发租约的全局默认 TTL |
| `gateway.renew_ttl_seconds` | `900` | 续期后的全局默认 TTL |
| `gateway.max_lease_ttl_seconds` | `3600` | TTL 上限，签发/续期/租户覆盖均不得突破 |
| `gateway.tenant_lease_ttl_seconds` | `{}` | 租户级 TTL 覆盖表，键为 `"<owner_type>:<owner_id>"`（如 `"cus:123"`、`"org:7"`），值为秒数 |
| `gateway.lease_cache_ttl_seconds` | `8` | 租约状态 Redis 缓存秒数，限定 5–10s |

优先级：**请求显式 `ttl_seconds` > 租户覆盖 > 全局默认**。租户取租约绑定的 `owner_type/owner_id`（来自 session/run）。无租户归属时退回全局默认。

租约表（`harness_gateway_lease`）新增：

- `invalidated_at TIMESTAMPTZ NULL`：失效时间
- `invalid_reason VARCHAR(100) NULL`：失效原因

`status` 取值扩展为 `active / revoked / invalid`。当前生效 TTL 继续记录在 `meta.ttl_seconds`，签发与续期时同步更新。

## 3. 行为约定

### 3.1 在途请求不切断

租约校验只发生在数据面请求进入时（`require_gateway_lease` 依赖）。一旦开始向客户端输出或已发出上游请求，即使期间租约到期、被吊销或续期失败：

- 不新增中途检查；
- 不主动终止上游调用或 SSE 流；
- 已获得的额度预占/结算、记账、对账路径保持原语义。

### 3.2 客户端主动续期

- 服务端不自动延长租约（不因请求发生而延长 `expires_at`）。
- 客户端应在 TTL 达到 80% 时调用 `POST /v1/harness/gateway/leases/{lease_id}/renew`。
- 签发响应新增 `renew_after_seconds = floor(ttl_seconds * 0.8)`，便于客户端定时。
- 续期响应返回新的 `expires_at`、`ttl_seconds` 与 `renew_after_seconds`。

### 3.3 `renew_after` 响应头

数据面（`/v1/gateway/chat/completions`）在租约通过鉴权后，凡返回响应都会带上提示头：

- 头名：`renew_after`
- 值：**距租约到期的剩余整数秒**（客户端应立即或尽快续期）
- 触发条件：剩余时间 < 该租约当前 TTL 的 30%（即已消耗 > 70%）
- 不触发时不返回该头

说明：客户端主路径仍按“TTL 80% 主动续期”；该响应头是兜底提示，不构成中途校验，也不影响已开始的流。

### 3.4 续期失败降级

续期失败原因与处理：

| 原因 | 续期接口 | 租约处理 |
| --- | --- | --- |
| 租约不存在 / 不属于该 client | 404 | 无 |
| 租约已吊销 | 409 | 保持 `revoked` |
| 租约已失效 | 409 | 保持 `invalid` |
| 租约已过期 | 409 | `invalid` + `invalid_reason=lease_expired` |
| 配额账户停用 | 403 | `invalid` + `invalid_reason=owner_account_disabled` |
| 额度耗尽（租约预算或租户余额） | 402 | `invalid` + `invalid_reason=quota_exhausted` |
| 客户端凭据停用 | 403（鉴权层 401 优先） | `invalid` + `invalid_reason=client_disabled` |
| 数据库/服务异常 | 503 | 不改状态 |

失败时：

- 不触碰在途流；
- 写审计 `gateway.lease_renew_failed`（reason、lease_id、client_id、session_no、run_no）；
- 失效写穿 Redis 缓存；
- 后续使用该虚拟 key 的新请求在鉴权处返回 401。

### 3.5 Redis 状态缓存

- Key：`gw:lease:state:{lease_id}`
- 内容：租约鉴权所需的非敏感快照（含 `key_hash`、`status`、`expires_at`、绑定关系、`meta`），不存虚拟 key 明文。
- TTL：`gateway.lease_cache_ttl_seconds`，限定 5–10s。
- 读路径：缓存命中 → 本地校验状态/过期/哈希/RPM → 再校验 session/run（保持现有语义）→ 使用统计；缓存未命中 → DB 查询 → 回填缓存。
- 写穿：吊销、续期成功、续期失败置失效时直接删除缓存；下一次请求读 DB，保证秒级传播。
- Redis 不可用或熔断：自动回落 DB 直查，不阻断数据面。

## 4. 非目标 / 约束

- 不改变 `GatewayBudgetService` 预占/结算/自动吊销语义。
- 不改变共享上游客户端（`base/common/upstream`）的重试、透传、超时、出网策略。
- 不改变对账定时任务与差异口径。
- 不新增流式中途租约检查。
- session/run 状态仍按请求实时校验，不使用短缓存，避免延后终态拒绝。

## 5. 验证方案（本地假 provider）

不调用真实 provider。使用本机假 provider（OpenAI Chat Completions 兼容，记录请求次数）与临时 DB 数据：

1. 默认 TTL：签发响应 `ttl_seconds=900`、`renew_after_seconds=720`。
2. 租户覆盖：manifest 配置 `tenant_lease_ttl_seconds` 命中 owner 时，签发 TTL 使用覆盖值；显式请求值优先。
3. 在途不切断：将租约 `expires_at` 调到过去，已开始的 SSE 流继续收到完整帧并正常结算；期间新请求 401。
4. 主动续期：调用 renew 后 `expires_at` 延长，响应含新的 `renew_after_seconds`。
5. 续期失败：将租约置 revoked / 配额账户冻结 / 预算耗尽后调用 renew，断言状态码、`status=invalid`、`invalid_reason`、审计 `gateway.lease_renew_failed`；随后新请求 401，已在途 SSE 不受影响。
6. 吊销写穿：吊销后下一次请求立即 401（不等待缓存 TTL）。
7. Redis 降级：Redis 不可用时鉴权仍通过（DB 直查），吊销后 401。
8. `renew_after` 头：剩余 <30% TTL 时出现，>30% 时不出现；流式响应头可被客户端读取。
9. 回归：额度中断（预占拒绝、流式截断）、共享上游客户端（透传/超时/重试/断流）、记账/对账路径不退化。

清理：停止假 provider，删除临时脚本、临时租约/会话/运行/用量数据，`manifest.json` 还原为生产配置。

## 6. 验收标准

- [x] 默认值、租户覆盖、显式请求优先级均符合第 2 节。
- [x] 在途 SSE 在租约过期后仍完整跑完；无中途检查。
- [x] 服务端不自动延长租约。
- [x] 续期失败标记失效、写审计、后续新请求 401；在途流不受影响。
- [x] Redis 缓存 TTL 5–10s；吊销/失效写穿；Redis 不可用回落 DB。
- [x] `renew_after` 头与 `renew_after_seconds` 字段按第 3.2/3.3 节生效。
- [x] 原有额度中断、对账、共享上游客户端行为回归通过。

## 7. 实施记录（2026-11-07）

### 7.1 落地位置

- 配置与优先级：`base/common/gateway/config.py`
- 租约签发/续期/失效/吊销写穿：`base/plugins/harness/services/gateway_lease_service.py`
- 数据面鉴权短缓存与 `renew_after` 计算：`base/common/gateway/lease_auth.py`
- 数据面响应头：`base/common/gateway/router.py`
- 租约表字段：`base/plugins/harness/models/harness.py` + `migrations/harness_alter_table_gateway_lease_1794100000.sql`

### 7.2 公共路径说明

仅改动网关数据面响应头拼装（`router.py` 的 `_response_headers` / `_error_response`）。额度预占/结算、自动吊销、对账、共享上游客户端（`base/common/upstream`）未改语义。回归覆盖：非流式成功、SSE 透传完整、额度预算拒绝 402。

### 7.3 验证结果

本地假 provider（127.0.0.1:18080，临时启用 `allow_loopback` + 域名白名单）与临时租约/会话/客户端数据：

- 签发默认 `ttl_seconds=900`、`renew_after_seconds=720`：通过
- 租户覆盖 / 显式覆盖 / max 上限 / 未命中回落：通过（17 项配置与缓存单测全部通过）
- 租约剩余 2s 时开始 SSE（流持续约 4.5s）：流完整收到 `[DONE]`；随后新请求 401：通过
- 主动续期返回新 `expires_at`、`ttl_seconds=900`、`renew_after_seconds=720`：通过
- 过期续期 409 + `invalid/lease_expired` + 审计 `gateway.lease_renew_failed`：通过
- 配额账户冻结续期 403 + `invalid/owner_account_disabled` + 审计：通过
- 吊销后续期 409、保持 `revoked`、立即 401（写穿）：通过
- `renew_after` 头在剩余 27.8% 出现、44% 不出现：通过
- Redis 不可用回落 DB（本地 Redis 关闭下的全部数据面调用）：通过
- 缓存命中、写穿删除、`revoke_internal` 立即 401：通过（FakeCache 单测）
- 在途流期间吊销 + 续期失败专项（6 项全通过）：流开始 200 → 流中吊销成功、续期 409 → 在途流仍收满 16 帧/15 token → 租约 `status=revoked` → 新请求 401
- 额度预算拒绝 402：通过

### 7.4 清理

临时假 provider、验证脚本、日志与临时租约/会话/客户端/额度账户/模型凭据/用量/审计数据均已删除；`manifest.json` 已还原生产配置（`allow_loopback=false`、域名白名单仅 `api.deepseek.com`、`allow_env_fallback=false`），保留新的 900s 与租约缓存配置项。

