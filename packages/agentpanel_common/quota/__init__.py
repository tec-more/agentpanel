"""共享配额域（P3 D-P3-2=B）。

- `plan_service`：套餐解析；客户等级/用户角色来源由入口注入 resolver
  （L2 注入 ORM 版 `plan_resolver`，网关注入只读 SQL 版，两者必须逐字段对拍）。
- `quota_service`：预占/结算/释放/并发/看板（Redis 优先、DB 兜底）。
"""
