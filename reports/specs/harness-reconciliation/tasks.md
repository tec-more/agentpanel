# 对账任务清单

- [x] T1 模型与注册
  - [x] `base/plugins/harness/models/harness.py` 追加 `HarnessReconcileBatch`、`HarnessReconcileDiff`（字段/索引按 spec §3）
  - [x] `base/plugins/harness/models/__init__.py` 导出两个模型
  - [x] 确认 `harness` 模型模块加载、`generate_schemas(safe=True)` 自动建表

- [x] T2 配置
  - [x] `base/common/gateway/config.py` 新增 `RECONCILE_DEFAULTS` 与 `reconciliation_config()`
  - [x] `base/plugins/harness/manifest.json` 的 `config.gateway.reconciliation` 写入默认值
  - [x] 区间/非负校验与非法值回退

- [x] T3 对账服务
  - [x] 新建 `base/plugins/harness/services/reconcile_service.py`
  - [x] `execute()`：窗口、查询分区（`gw:` / `harness:`）、租约/run 对齐、聚合
  - [x] 分类：only_gateway/only_client/value_mismatch/duplicate_count/failure_timeout/unmatched_*
  - [x] 分级：阈值可配置，high/low 按 spec §4
  - [x] 指纹 + upsert：不覆盖 status/resolved_*，occurrence_count+1
  - [x] `list_diffs/diff_detail/mark_diff/list_batches/summary`

- [x] T4 后端接口
  - [x] `dashboard_router.py` 新增 5 个接口（spec §8）
  - [x] `dashboard_service.anomalies()` 合并 `gateway_reconcile`
  - [x] 参数解析与 404 处理、`require_superuser`

- [x] T5 定时任务
  - [x] `base/start.py` 新增 `gateway_reconcile_task()` 并在 lifespan 条件启动
  - [x] 手动/定时复用同一服务，异常不退出循环

- [x] T6 管理台
  - [x] `web/src/api/harness.js` 新增 5 个 API
  - [x] `Usage.vue` 新增“网关对账差异”tab（与现有异常同一卡片）
  - [x] 摘要条、筛选（run/会话/客户端/租户/时间/级别/分类/状态）、分页
  - [x] 详情弹窗、标记已处理/忽略、执行对账按钮

- [x] T7 验证与清理
  - [x] 重启后端，确认建表与接口注册
  - [x] 构造六类场景 + 两类未匹配，核对 category/severity/diff_amount/diff_rate
  - [x] 同窗口执行两次验证幂等（行数不变、occurrence_count 增加）
  - [x] 标记 resolved 后再执行，状态保留
  - [x] `/anomalies` 返回 `gateway_reconcile`；前端同页 tab 可见
  - [x] 全程不调用真实 provider（本地假 provider 仅在需要时临时启用并还原）
  - [x] 清理测试数据、还原 manifest、重启确认无回归
