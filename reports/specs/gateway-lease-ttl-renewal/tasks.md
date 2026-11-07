# 任务清单：网关租约 TTL / 主动续期 / 失效降级 / 状态缓存

- [x] T1 配置：`lease_ttl_seconds`/`renew_ttl_seconds` 默认 900；新增 `tenant_lease_ttl_seconds` 与 `lease_cache_ttl_seconds`；启动校验覆盖值范围。
- [x] T2 模型与迁移：`harness_gateway_lease` 增加 `invalidated_at`、`invalid_reason`；status 支持 `invalid`。
- [x] T3 签发：按“显式 > 租户覆盖 > 全局默认”解析 TTL；响应增加 `renew_after_seconds`；`meta.ttl_seconds` 记录生效值。
- [x] T4 续期：只由客户端触发；校验过期/吊销/失效/客户端/配额账户/额度；失败标记 `invalid` + 原因 + 审计 `gateway.lease_renew_failed`；成功返回新 TTL 与 `renew_after_seconds`。
- [x] T5 鉴权缓存：`lease_auth` 增加 Redis 短缓存（5–10s），吊销/续期/失效写穿，Redis 不可用回落 DB；401 文案区分 revoked/invalid。
- [x] T6 数据面提示：`chat/completions` 成功/错误响应头按剩余 <30% TTL 输出 `renew_after`；不新增流中检查。
- [x] T7 验证：假 provider + 临时数据覆盖 spec 第 5 节 9 类场景；回归额度中断与共享上游客户端。
- [x] T8 清理：删除临时脚本与数据，manifest 还原生产配置；更新 spec 验收结果。
