"""共享配额域（P3 D-P3-2=B）。

- `plan_service`：套餐解析；客户等级/用户角色来源由入口显式注入唯一共享实现
  `plan_resolver.SqlPlanResolver`（app 与网关共用，黄金用例 `tests/plan_golden.py`）。
- `quota_service`：预占/结算/释放/并发/看板（Redis 优先、DB 兜底）。
"""
