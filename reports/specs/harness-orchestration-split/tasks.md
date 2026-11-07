# P1.3 任务清单：额度副作用编排接口迁移

> 依据：`spec.md` §16（2026-11-07 用户确认范围与 6 条硬条件）。
> 规则：每项完成后勾选；验证以最终 DB 状态为准，不只看 HTTP。

## A. L2 额度幂等原语（前置，未通过不得继续）

- [x] A1 `base/common/quota/services/quota_service.py`
  - 新增 64 路分条带 `_hold_lock(hold_id)`；
  - `quota_estimate`：锁内先查 `QuotaReservation` active/partial，存在则直接返回 `hold_id`；`_persist_reservation` 唯一冲突时补偿 Redis 并返回已存在预占；
  - `quota_settle`：锁内先写 `usage_record`（`idem_key` 唯一抢占），仅对写入成功条目累加计数；`IntegrityError` 视为重复跳过；
  - `quota_release`：锁内重读 hold，与 settle 互斥；`used` 以 `max(0, …)` 回退。
  - 验证：同一 `hold_id` reserve 3 次 → 1 条 reservation、held 计数只加一次；同一 `idem_key` settle 20 并发 → 1 条 usage、计数只加一次。
- [x] A2 并发首建账户修复：`ensure_account` 捕获 `IntegrityError` 后回读；周期滚动/plan 更新改 `save(update_fields=...)`，禁止整行覆盖并发 `used`。
  - 验证：2 进程 × 10 任务并发 reserve，账户首建不再 500，`used` 不丢失。

## B. L2 内部额度 API

- [x] B1 新增 `base/plugins/harness/api/l2_internal/quota_router.py`，根路径挂载到 `base/start.py`：
  - `POST /internal/v1/harness/quota/reserve|settle|release`、`GET /status`；
  - 服务凭据 + scope `quota:operate`；
  - `mode!=proxy_l3` 时写操作 409 `orchestration_not_primary`；
  - settle 强制 `idem_key` 以 `orch:` 开头，否则 400 `quota_idempotency_key_required`。
- [x] B2 DB `service_credential` 给 `svc_l3_orchestration` 追加 `quota:operate`；开发环境原 secret 不可回收，已轮换并同步 `secret_hash`。
- [x] B3 验证：无凭据/错误 scope 401/403；重复 reserve 不增预占；429 体与 L2 本地同形；非 `orch:` hold/idem → 400；错误签名 → 401。

## C. L3 额度客户端与共享服务改造

- [x] C1 新增 `orchestration_runtime.py`（角色 l2/l3），`server.py` 导入即置 `l3`。
- [x] C2 新增 `l2_quota_client.py`（HMAC 服务凭据，超时 = `internal_timeout_seconds`；429→`QuotaError`；超时/5xx→`QuotaUnavailable`，不重试；`orchestration_not_primary` → 503）。
- [x] C3 新增 `quota_backend.py` 按角色分派。
- [x] C4 `run_service.py`：预扣/结算/释放走 backend；`hold_id=orch:{run_no}`；`source=client`；`idem_key=orch:{run_no}:{node}:{seq}`；`QuotaUnavailable`→503 `orchestration_dependency_unavailable`。
- [x] C5 `event_service.py`：结算走 backend；同上幂等键；失败 503 且不确认批次。
- [x] C6 部分成功补偿：预扣成功但 run 落库失败 → 立即 release；release 失败落 ERROR 日志并保留原始错误；崩溃由 `cleanup_stale_holds`/对账兜底。

## D. L3 写路由与开关

- [x] D1 新增 `api/l3/write_router.py`，注册到 `server.py`：`POST /sessions`、`/sessions/{no}/runs`、`/runs/{no}/start|steps|events|complete|cancel`、`/policies/evaluate`、`/sessions/{no}/close`；复用现有 service，保持状态机/错误码同源。
- [x] D2 路由顺序：客户端凭据校验 → `ensure_write_enabled()`（false 时 409 `orchestration_write_disabled`）。
- [x] D3 验证：`write_enabled=false` 全部写 409、读 200。
- [x] D4 单写者第二道闸：`ensure_write_enabled()` 在 `mode != proxy_l3` 时 409 `orchestration_not_primary`；修复 `orchestration_config` 未导入导致的 500，复测通过。

## E. L2 代理与兼容读取

- [x] E1 `api/v1/session_router.py`/`run_router.py`/`policy_router.py`：`mode=proxy_l3` 下 9 条写路径 `proxy_to_orchestration`，不本地落库；失败 503 `orchestration_downstream_unavailable`。
- [x] E2 `dashboard_service.py`：`run_usage` 双前缀、reservation `source__in=["harness","client"]`。
- [x] E3 `reconcile_service.py`：`_client_run_id` 兼容 `harness:<id>:` 与 `orch:<run_no>:`，`_load_runs` 双键装载。
- [x] E4 验证：历史 `harness:` 数据仍被对账/看板识别，不双写。

## F. 验证与收尾

- [x] F1 基线对拍：等价 fixture 分别打 9998(`mode=l2`) 与 9100(`mode=proxy_l3`,`write_enabled=true`)，run/step/session/usage_record/quota_reservation/审计最终状态逐项一致（仅编号/时间戳/id 不同）。
- [x] F2 重复提交（complete/cancel/event ×3）不重复扣；第二次 `settled=0`。
- [x] F3 并发提交（2 进程 × 10 并发 reserve / settle）不双计、不悬挂；DB 数值见 §16.11。
- [x] F4 跨进程超时/停 L2 → 503，无新增 run/usage/reservation，无本地扣减。
- [x] F5 下游 5xx mock → 503 fail-closed，不重试。
- [x] F6 单写者与切换 runbook 演练：`write_enabled=false` 与 `mode=l2` 均 409，任一时刻只有一侧可写。
- [x] F7 L2 只读边界行指纹：除经 L2 API 的合法额度变更与 `last_used_at` 外零变更。
- [x] F8 清理 `p13_` 测试数据与临时脚本；残留检查全 0；`usr:4` 回退 1600 token。
- [x] F9 回填 `spec.md` §5 对照表“实际落点”、§5.2 与 §16.10–§16.13（行为变化、实测数值、回滚动作、已知限制）。

## G. 待补（非本批阻塞）

- [ ] G1 Redis 模式复跑同一并发幂等脚本（当前环境未安装 Redis，仅验证 `counter_mode=db`）。
- [ ] G2 评估 HTTP 建 run 请求级幂等（客户端 `Idempotency-Key` + 去重表），登记 P2 技术债。
