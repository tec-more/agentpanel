# 验收清单：Harness 网关额度耗尽中断机制

> 全部以本地假 provider（127.0.0.1:18080）验证，未调用真实 provider。

- [x] 余额不足时无上游请求，返回 402 + 可识别 code（`quota.lease_budget_exhausted` / `quota.balance_insufficient`），审计 `gateway.quota_rejected` 与拒绝计数可见。
- [x] 流式超预算时主动断开上游并发送截断终止帧（`truncated/estimated/partial=true` + `[DONE]`），记账 `usage_kind=partial`，`price_snapshot.billing_status=partial`，审计 `gateway.stream_truncated` 与截断计数可见。
- [x] 自动/手动吊销后目标租约立即 401，其他租户租约不受影响（验证为 200），吊销写审计 `gateway.lease_revoked`。
- [x] 多进程并发预占只有一份共享计数（`used=100` 而非 200），原子扣减无超发；结算后可再次申请。
- [x] 单请求输出上限夹紧到 `max_output_tokens_per_request=4096`；单租户并发超限返回 429 `quota.concurrency_limit`。
- [x] 看板返回 used/remaining/estimated_requests/rejected/truncated，汇总与明细字段完整。
- [x] 全程未调用真实 provider；测试数据已清理，manifest loopback 覆盖已还原。
- [x] 验证过程中修复 DB 兜底并发槽的时区判定缺陷（`_is_stale` 统一按 UTC 比较），否则并发上限在 DB 路径永不生效。
