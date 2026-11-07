# 网关记账与客户端上报对账（Spec）

状态：待评审  
范围：harness 插件 + embedded 网关 + 管理台用量页  
不调用真实 provider；验证使用本地可控数据/假 provider 链路。

## 1. 目标与口径

1. **计费权威**：`usage_record(source=gateway, gateway_key=<lease_id>, idem_key LIKE 'gw:%')`。
2. **客户端佐证**：`usage_record(idem_key LIKE 'harness:%')`，来源可能是 provider/gateway/estimated，仅用于对齐、语义事件与差异排查，**不与网关金额合并计算**。
3. 两侧记录都落在 `usage_record`，但通过 `idem_key` 前缀严格分区：
   - 网关：`gw:{lease_id}:{uuid}`（`base/common/gateway/service.py::record_gateway_usage` 生成）；
   - 客户端：`harness:{run_id}:{node_id}:{seq}`（`QuotaService.default_idem_key` 生成）。
4. 对账只聚合 `source=gateway + gw:` 与 `harness:` 两类；其它来源不参与网关对账。

## 2. 匹配键与对齐规则

- 网关侧：`gateway_key(lease_id)` → `harness_gateway_lease.run_no/session_no/client_id/owner_*`。
- 客户端侧：解析 `idem_key` 第二段得到 `run_id` → `harness_run.run_no/session_no/client_id/owner_*`。
- **能对齐到 run 级**才进入 run 级差异计算；对不齐的分别进 `unmatched_gateway` / `unmatched_client`，不做强制配对。
- 网关记录即使有 `session_ref` 但租约无 `run_no`，也归入未匹配（不按会话猜测 run）。
- 失败/超时：网关 `resource_type=gateway_error` 的记录按租约对齐到 run 后单独产出 `failure_timeout` 差异；金额差异只比较成功的 `resource_type=llm_token` 记录。

## 3. 数据模型

在 `base/plugins/harness/models/harness.py` 末尾新增：

### HarnessReconcileBatch（表 `harness_reconcile_batch`）
| 字段 | 类型 | 说明 |
|---|---|---|
| batch_no | Char(40), unique, index | `urc{YYYYmmddHHMMSS}{4位随机}` |
| trigger | Char(20), default manual | manual/scheduled |
| window_start / window_end | Datetime | 本次窗口（左闭右开） |
| status | Char(20), default running | running/completed/failed |
| stats | JSON | `{diffs, created, updated, consistent_runs, by_category, by_severity}` |
| operator_id | BigInt, null | 手动触发管理员 |
| duration_ms | Int, default 0 | 耗时 |
| error_message | Text, null | 失败原因 |

索引 `(trigger, created_at)`，排序 `-id`。

### HarnessReconcileDiff（表 `harness_reconcile_diff`）
| 字段 | 类型 | 说明 |
|---|---|---|
| fingerprint | Char(180), unique, index | 幂等指纹，规则见 §5 |
| batch_no | Char(40), null, index | 最近一次命中批次 |
| run_no / session_no / client_id | Char, null, index | 对齐维度 |
| owner_type / owner_id | Char(8)/BigInt, null | 租户过滤 |
| gateway_key | Char(128), null, index | lease_id |
| category | Char(30), index | 见 §4 |
| severity | Char(10), index | high/low |
| gateway_amount / client_amount | Float, default 0 | token 口径汇总 |
| diff_amount / diff_rate | Float, default 0 | 客户端 - 网关；rate = diff / max(网关,1) |
| gateway_cost / client_cost | Decimal(14,8)，default 0 | 金额口径 |
| gateway_count / client_count | Int, default 0 | 成功请求数 |
| detail | JSON | 统计明细 + 样本记录（最多 50 条 id/idem_key/amount/cost/error） |
| status | Char(20), default open, index | open/resolved/ignored |
| resolved_by / resolved_at | BigInt/null, Datetime/null | 处理信息 |
| resolve_note | Text, null | 处理备注 |
| last_seen_at | Datetime | 最近一次对账命中 |
| occurrence_count | Int, default 1 | 累计命中次数 |

索引：`(category, severity, status)`、`(run_no, created_at)`、`(session_no, created_at)`、`(owner_type, owner_id, created_at)`；排序 `-severity, -last_seen_at`。

更新 `base/plugins/harness/models/__init__.py` 导出两个新模型（TORTOISE_ORM 已加载 `harness` 模块）。

## 4. 差异分类与分级

### 分类（run 级）
| category | 触发条件 | 含义 |
|---|---|---|
| only_gateway | 网关成功记录数 > 0 且客户端记录数 = 0 | 客户端漏报/未上报 |
| only_client | 网关记录数 = 0 且客户端记录数 > 0 | 绕过网关直连嫌疑 / 重复上报 |
| value_mismatch | 两侧均有记录，金额/成本不一致，且不满足重复计数条件 | 数值不一致，给出差额与差额率 |
| duplicate_count | 两侧均有记录，`client_count > gateway_count` 且 `client_count >= gateway_count * duplicate_ratio_high` | 同一请求重复计数 |
| failure_timeout | 该 run 存在 `gateway_error` 记录 | 失败/超时请求 |
| unmatched_gateway | 网关记录无法解析到 lease 或 lease 无 run_no | 未匹配（网关侧） |
| unmatched_client | 客户端记录无法解析 run_id 或 run 不存在 | 未匹配（客户端侧） |

> 说明：网关记账当前 `cost=0`，因此成本差只在两侧 `cost>0` 时参与 `value_mismatch` 判定与 `diff_cost_high` 分级；token 用量差额始终参与判定。

一个 run 可同时产生 `failure_timeout` 与用量类差异（失败记录金额为 0，不参与金额差）。

### 分级（高/低，可配置）
| category | high 条件 | 否则 |
|---|---|---|
| only_client | 一律 high（直连嫌疑） | — |
| only_gateway | `gateway_amount >= missing_amount_high` | low |
| value_mismatch | `abs(diff_amount) >= diff_amount_high` 或 `abs(diff_rate) >= diff_rate_high` 或 `abs(cost_diff) >= diff_cost_high` | low |
| duplicate_count | 分类条件已满足（计数 >= 倍数阈值） | low |
| failure_timeout | — | low |
| unmatched_gateway / unmatched_client | — | low |

一致（两侧 count 相同且 amount 与 cost 差值为 0）不产出差异，只计入 `consistent_runs`。

## 5. 幂等指纹与重复执行

- `run:{run_no}:only_gateway`
- `run:{run_no}:only_client`
- `run:{run_no}:value_mismatch`
- `run:{run_no}:duplicate_count`
- `run:{run_no}:failure_timeout`
- `gwrec:{usage_record.id}`（未匹配网关记录）
- `client:{idem_key 或 usage_record.id}`（未匹配客户端记录）

写入规则（`update_or_create` 语义，但**不覆盖处理状态**）：
1. 不存在 → 新建，`status=open`，`occurrence_count=1`。
2. 已存在 → 更新数值、明细、severity、batch_no、`last_seen_at`、`occurrence_count += 1`；
   `status/resolved_by/resolved_at/resolve_note` 保持不变。
3. 重复执行同一窗口不会新增同指纹行；历史批次全部保留。
4. `resolved/ignored` 的差异再次命中时仍保留原状态（不自动重开）。

## 6. 配置

`base/common/gateway/config.py` 新增 `RECONCILE_DEFAULTS`：

```python
{
  "enabled": True,
  "interval_seconds": 600,
  "window_hours": 24,
  "max_window_hours": 168,
  "diff_amount_high": 1000.0,       # token 差额高阈值
  "diff_rate_high": 0.10,           # 差额率高阈值（10%）
  "diff_cost_high": 1.0,            # 金额差额高阈值
  "missing_amount_high": 1000.0,    # 仅网关有的高阈值
  "duplicate_ratio_high": 2.0,      # 客户端计数倍数阈值
}
```

- 新增 `reconciliation_config()`：读取 `gateway.reconciliation`，与默认值合并并做非负/区间校验（`interval_seconds>=30`、`window_hours<=max_window_hours`）。
- `base/plugins/harness/manifest.json` 的 `config.gateway.reconciliation` 显式写入上述默认值，便于运维修改。
- 不满足时回退默认值并打印告警，不阻断启动（对账不是数据面 fail-closed 通道）。

## 7. 后端服务

新增 `base/plugins/harness/services/reconcile_service.py`：

```python
class HarnessReconcileService:
    @classmethod
    async def execute(cls, window_start=None, window_end=None,
                      trigger="manual", operator_id=None) -> dict
    @classmethod
    async def list_diffs(cls, *, run_no=None, session_no=None, client_id=None,
                         owner_type=None, owner_id=None, severity=None,
                         category=None, status=None, date_from=None,
                         date_to=None, page=1, page_size=20) -> dict
    @classmethod
    async def diff_detail(cls, diff_id) -> dict
    @classmethod
    async def mark_diff(cls, diff_id, status, note=None, operator_id=None) -> dict
    @classmethod
    async def list_batches(cls, limit=20) -> list
    @classmethod
    async def summary(cls, limit=20) -> dict
```

`execute` 步骤：
1. 解析窗口（默认 `now - window_hours` 到 `now`，超 `max_window_hours` 截断）；生成 batch。
2. 查询窗口内 `UsageRecord`：
   - 网关成功：`source=gateway`、`resource_type=llm_token`、`idem_key startswith gw:`；
   - 网关失败：`source=gateway`、`resource_type=gateway_error`、`idem_key startswith gw:`；
   - 客户端：`idem_key startswith harness:`（任意 source）。
3. 批量加载租约与 run 映射，聚合到 run（count/amount/cost/tokens_in/out/errors/sample ids）。
4. 按 §4 生成差异列表与一致计数；未匹配单独生成。
5. 按 §5 upsert，统计 `created/updated/by_category/by_severity/consistent_runs`。
6. 更新 batch 为 completed；异常时 failed 并记录 error_message。
7. 返回 `{batch_no, window_start, window_end, trigger, stats, diffs:[...]}`。

`summary` 返回 `{open, high_open, by_category, by_severity, latest_batch, top_diffs(limit)}`，用于 `/anomalies` 合并展示。

## 8. API（`base/plugins/harness/api/v1/dashboard_router.py`）

| 方法/路径 | 说明 | 参数 |
|---|---|---|
| `POST /dashboard/reconcile/gateway` | 执行网关对账 | `window_start?`、`window_end?`、`trigger=manual`（管理员） |
| `GET /dashboard/reconcile/diffs` | 差异列表 | `run_no/session_no/client_id/owner_type/owner_id/severity/category/status/date_from/date_to/page/page_size` |
| `GET /dashboard/reconcile/diffs/{diff_id}` | 差异明细 | diff_id |
| `POST /dashboard/reconcile/diffs/{diff_id}/resolve` | 标记处理 | `status=resolved|ignored`、`note?` |
| `GET /dashboard/reconcile/batches` | 批次历史 | `limit` |
| `GET /dashboard/anomalies` | 扩展返回 `gateway_reconcile=summary()`，与失败 run/超期预占同响应 | limit |

所有接口继续使用 `require_superuser()` 与 `success_response/fail_response`。

## 9. 管理台（`web/src/views/harness/Usage.vue` + `web/src/api/harness.js`）

- 在现有“异常明细”卡片内新增 tab **“网关对账差异”**，与失败运行/超期预占/缺价格/高危拒绝同页同卡片。
- 卡片 header 增加按钮 **“执行网关对账”**（调用 `POST /dashboard/reconcile/gateway`，完成后刷新）。
- 顶部展示 `gateway_reconcile` 摘要：未处理总数、high 数、最近批次统计。
- 筛选：级别、分类、状态、run_no、session_no、client_id、时间范围；分页。
- 表格：run/会话/客户端/分类/级别/网关金额/客户端金额/差额/差额率/状态/最近命中/操作。
- 操作：详情弹窗（展示 detail JSON）、标记已处理、忽略。
- 级别用 high=danger、low=info 标签；分类中文映射。
- API 新增：`runGatewayReconcile`、`getReconcileDiffs`、`getReconcileDiffDetail`、`resolveReconcileDiff`、`getReconcileBatches`。

## 10. 定时任务（`base/start.py`）

- 在配额定时任务之后，仅当 harness 插件启用、`gateway_enabled()` 且 `reconciliation_config().enabled` 时启动 `gateway_reconcile_task()`。
- 循环：`await asyncio.sleep(interval_seconds)` → `HarnessReconcileService.execute(trigger="scheduled")`。
- 捕获 `CancelledError` 退出；其它异常打印堆栈，不终止循环。
- 与手动接口复用同一服务，保证幂等。

## 11. 验证方案（不调用真实 provider）

环境：项目 venv + PostgreSQL；后端重启加载新表/新路由/新定时任务。

造数原则：
- 网关侧记录使用 `base/common/gateway/service.py::record_gateway_usage` 或等价字段写入（`source=gateway`、`idem_key=gw:*`、`gateway_key=<真实租约>`）；
- 客户端侧按 `idem_key=harness:{run_id}:...` 直接写入（模拟 JSONL 上报）；
- 不发起任何真实 provider 请求；如需验证网关会计链路，使用本地假 provider（`upstream_base_url_override` 指向 127.0.0.1 + `allow_loopback=true` 临时配置，验证后还原）。

场景与期望：

| # | 场景 | 期望 |
|---|---|---|
| 1 | 一致 | 无差异，`consistent_runs+1` |
| 2 | 客户端漏报（仅网关有） | `only_gateway`，金额低于阈值时 low，超阈值 high |
| 3 | 客户端多报（仅客户端有） | `only_client`，severity=high（直连嫌疑） |
| 4 | 金额偏差 | `value_mismatch`，diff_amount/diff_rate 正确；超阈值 high，否则 low |
| 5 | 重复计数 | 网关 1 条、客户端 2 条同 run → `duplicate_count`，high |
| 6 | 失败/超时 | 网关 `gateway_error` → `failure_timeout`，low |
| 7 | 未匹配 | 无 run 绑定 lease / 不存在的 run_id → `unmatched_gateway`/`unmatched_client`，不强行配对 |
| 8 | 幂等 | 同窗口执行两次，差异总行数不变，`occurrence_count` +1 |
| 9 | 已处理保留 | 标记 resolved 后再执行，状态仍 resolved，历史保留 |
| 10 | 同页可见 | `/anomalies` 返回 `gateway_reconcile`；前端“网关对账差异”tab 可见并可按 run/会话/租户/时间/级别过滤 |

验证后清理测试租约/run/usage_record/reconcile 数据，还原 manifest 与本地假 provider配置，重启后端确认启动正常。

## 12. 文件改动清单

- `base/plugins/harness/models/harness.py`：新增两个模型
- `base/plugins/harness/models/__init__.py`：导出
- `base/common/gateway/config.py`：对账配置默认值与合并/校验
- `base/plugins/harness/manifest.json`：`gateway.reconciliation` 配置
- `base/plugins/harness/services/reconcile_service.py`：新增
- `base/plugins/harness/api/v1/dashboard_router.py`：新增接口 + anomalies 合并
- `base/plugins/harness/services/dashboard_service.py`：anomalies 增加 `gateway_reconcile`
- `base/start.py`：定时任务
- `web/src/api/harness.js`：API 封装
- `web/src/views/harness/Usage.vue`：新 tab、筛选、详情、标记、执行按钮

## 13. 非目标

- 不改动网关转发、鉴权、记账主流程。
- 不把客户端与网关数值合并成一份账单。
- 不做自动清零/自动修正计费，只提供差异与人工处理标记。
- 不引入 APScheduler 等新依赖。
