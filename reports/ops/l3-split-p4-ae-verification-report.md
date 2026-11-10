# P4 A–E 组汇总验证报告

> 范围：A–E 组；cost 组（`c6e4239`）已有单独汇报，本报告不重复。
> 复核基线：`release/0.0.1`，`HEAD=c6e4239`；复核时 9998 / 9999 / 9100 三服务均 healthy。
> 证据快照（P4 开始前采集，仍保留在 `%TEMP%`）：
> - `l2_openapi_before.json`：app 358 paths / 450 ops
> - `l3_orch_openapi_before.json`：旧 9100 16 paths / 18 ops
> - `plugin_order_before.txt`：`audit,customer,product,sales,crm,harness,llm,mail`

## 0. 结论速览

| 组 | 结论 | 关键证据 | 缺口 / 口径偏差 |
|---|---|---|---|
| A | 新编排入口接管 9100，旧入口删除；路由 19/21，app 代理可用 | 9100 与重跑 9101 预演 diff=0；旧快照→当前仅新增 3 条审批路由；9100 停/起时 app 分别返回 503/401 | 原始切换没有保留带时间戳的日志；本报告重跑了 9101 预演，只能证明同代码下 9100/9101 路由等价 |
| B | `base/common/gateway` 整目录已删除，`base/` 引用为 0 | `git grep`：33 行（`e87e6cf^`）→ 0（`HEAD`）；消费方 18 处改指 / 10 处新增共享 import | “28 处”无法复现，见 §2.3 |
| C | `orchestration_runtime` 无代码引用；`proxy` 保留 | `*.py` grep **0 命中**（`21387bd` 清理后）；17 处 `proxy` 配置/写主判断全部保留 | 无（清理前曾剩 1 行 docstring，已单独清理） |
| D | 358 条路由 method+path 集合零变化；插件顺序一致 | 358/358 paths、450/450 ops，removed=0、added=0；插件 8 个顺序完全一致 | 无 |
| E | 唯一 SQL 实现生效；黄金用例 20/20 | `plan_golden.py` 实测 20 通过 / 0 失败，EXIT=0；旧模块路径均不存在 | “20 处引用”无法复现；实际生产 import 7 处 / 6 文件，见 §5.2 |
| 回滚 | 两步 revert 路径可用 | 在 HEAD=`c6e4239` 的临时 worktree 重跑：两步 EXIT=0，`git diff --stat` 均为 0 行 | 无 |

---

## 1. A 组：9100 切换与旧入口下线

### 1.1 提交与删除范围

`33b9883 refactor(l3): 旧编排入口下线，9100 改由 services/orchestration 提供`

```
D base/plugins/harness/server.py
D base/plugins/harness/api/l3/__init__.py
D base/plugins/harness/api/l3/business_router.py
D base/plugins/harness/api/orchestration/write_router.py
D base/plugins/harness/api/internal/__init__.py
D base/plugins/harness/api/internal/router.py
M base/__init__.py
M reports/ops/redis-enable-runbook.md
8 files changed, 4 insertions(+), 525 deletions(-)
```

### 1.2 切换时序

实际执行顺序：

1. 在 **9101** 启动 `services/orchestration/run.py`（同一份新代码，仅换端口），检查健康与 OpenAPI。
2. 停止旧 9100 进程（`base/plugins/harness/server.py` 入口）。
3. 在 **9100** 启动新入口 `services/orchestration/run.py`。
4. 立即验证 9100 路由、app→9100 代理行为。

复核时重跑了第 1 步（9101 预演），输出：

```
REHEARSAL_9101_PATHS=19 OPS=21
DIFF_9100_vs_9101_REMOVED=0 ADDED=0
```

预演实例随后已停止，当前只监听 9100。

### 1.3 路由 diff

旧入口快照 vs 当前 9100：

```
ORCH_PATHS_BEFORE=16 ORCH_PATHS_NOW=19
ORCH_OPS_BEFORE=18 ORCH_OPS_NOW=21
ADDED GET /v1/harness/approvals/pending
ADDED POST /v1/harness/approvals/{approval_no}/decision
ADDED POST /v1/harness/approvals/request
REMOVED（无）
```

即：只多出 3 条审批路由，其余 18 个操作原样保留；9100 与 9101 预演的 method+path 集合完全相同。

### 1.4 旧入口删除后 app 代理

- 9100 停止期间，app 代理返回 **503**：

```
STATUS=503
{"code":503,"msg":"编排服务不可用（下游不可达或超时）","data":{"error_code":"orchestration_downstream_unavailable","downstream":"orchestration","upstream":"http://127.0.0.1:9100/v1/harness/runs/x","reason":"ConnectError: All connection attempts failed"},"status_code":503,"success":false}
```

- 9100 恢复后，app 代理返回 **401** 透传：

```
STATUS=401
{"code":401,"msg":"无效的 Harness 客户端凭据","data":null}
```

**缺口**：原始切换动作没有保留带时间戳的进程日志；本报告用“重跑 9101 预演 + 当前 9100 实机探测”作为可复核证据。影响：无法证明历史切换的精确秒数，但能证明切换前后的路由集合与代理行为。

---

## 2. B 组：`base/common/gateway` 整目录删除与启动期显式注入

### 2.1 目录与引用

```
GATEWAY_DIR_EXISTS=False
git grep "base.common.gateway" e87e6cf^ -- base/  -> 33 行
git grep "base.common.gateway" HEAD -- base/      -> 0 行（退出码 1，无匹配）
```

删除文件（`e87e6cf`）：

```
D base/common/gateway/__init__.py
D base/common/gateway/app.py
D base/common/gateway/audit.py
D base/common/gateway/auth.py
D base/common/gateway/budget.py
D base/common/gateway/constants.py
D base/common/gateway/lease_auth.py
D base/common/gateway/logging.py
D base/common/gateway/router.py
D base/common/gateway/server.py
D base/common/gateway/service.py
```

`base/common/gateway/config.py` 以 rename 方式迁到 `base/plugins/harness/services/gateway_config.py`（app 唯一实现）。

### 2.2 消费方改指清单（按提交 diff 统计）

| 文件 | 旧引用 → 新目标 |
|---|---|
| `base/common/security.py` | `gateway.constants.is_gateway_virtual_key` → 共享包同名模块 |
| `base/plugins/harness/api/v1/dashboard_router.py` | `gateway.budget.GatewayBudgetService` → 共享包 |
| `base/plugins/harness/services/dashboard_service.py` | 同上 |
| `base/plugins/harness/services/gateway_lease_service.py` | `lease_auth/audit/budget/logging/lease_revoke` → 共享包；`issuance_config` 改从本地 `gateway_config` 导入（5 处减为 4 处） |
| `base/plugins/harness/services/service_auth.py` | `gateway.constants` → 共享包；签名工具 → `common.security` |
| `base/start.py` | 删除 `import base.common.gateway.*`；新增共享套餐注入与 `configure_shared_runtime()`（5 处减为 2 处）；embedded 挂载仍用 `services.gateway.common.app` |
| `base/plugins/harness/__init__.py` | 删除 shim 再导出（-1），改为本地 `gateway_config.validate_issuance_config` |
| `base/plugins/harness/services/egress_policy_service.py` | 删除 shim 引用（-1），改为本地 `gateway_config.issuance_config/upstream_allowlist` |
| `base/plugins/harness/services/reconcile_service.py` | 删除 shim 引用（-1），改为本地 `gateway_config.reconciliation_config` |
| `base/plugins/harness/services/runtime_service.py` | 删除 shim 引用（-1），改为本地 `gateway_config.issuance_config/gateway_enabled` |

统计结果：

```
消费方文件：-18 处旧 import，+10 处共享包 import（10 个文件）
整个提交（含被删 shim 内部引用）：-41 行含 base.common.gateway，+19 行含共享 gateway
```

### 2.3 口径偏差：无法复现“28 处”

可复现的数字是：`base/` 目录引用 33 行（删除前）→ 0 行（当前）；生产消费方 import 改指 18 处。**“28 处”在本仓库当前历史中找不到对应口径**（可能来自某个中间状态的临时 grep）。影响：不影响“引用已清零”的结论，但引用清单数量应以本节表格为准。

### 2.4 启动期显式注入点

app 导入期（`base/start.py` L18–L31）：

```python
import base.common.cache
from packages.common.quota.services import plan_service as _shared_plan_service
from packages.common.quota.services.plan_resolver import SqlPlanResolver
_shared_plan_service.configure(SqlPlanResolver())
from base.plugins.harness.services.gateway_config import configure_shared_runtime
configure_shared_runtime()
init_plugin_manager()
```

其中 `configure_shared_runtime()`（`gateway_config.py` L219–L231）做三件事：

```python
_runtime.configure(
    config_provider=gateway_config,
    upstream_provider=gateway_upstream_config,
    lease_ttl_provider=lambda cfg=None: lease_cache_ttl_seconds(cfg or gateway_config()),
)
```

网关进程在 `services/gateway/app/main.py` 也有同名 `_configure_shared_runtime()`，注入 `gateway_config` / `gateway_upstream_config` / `lease_cache_ttl_seconds` 与 `SqlPlanResolver`。

### 2.5 验证方式

在独立进程导入 `base.start` 后直接探测注入结果：

```
PLAN_RESOLVER=SqlPlanResolver
GW_INJECTED_KEYS=deployment,fail_closed,port,public_base_url
GW_PORT=9999
```

说明 `plan_service` 已绑定唯一 SQL 解析器，共享网关运行时也已拿到 app 配置 provider。另有 app 重启后 358 paths/450 ops 零变化（见 §4）。

---

## 3. C 组：`orchestration_runtime` 删除与 `proxy` 保留

### 3.1 删除证据

`6a7aed8` 删除 `base/plugins/harness/services/orchestration_runtime.py`（此前无任何代码调用点）。

全仓 `*.py` grep 结果（清理前/后）：

```
清理前：ORCH_RUNTIME_CODE_HITS=1（仅 quota_backend.py:7 一行 docstring 历史说明）
清理后（21387bd）：ORCH_RUNTIME_CODE_HITS=0
```

**口径说明**：`6a7aed8` 删除模块后，代码已无 import/调用；残留的 1 行 docstring 已由 `21387bd` 单独清理，现为字面清零。

### 3.2 `proxy` 保留现状

按 T4.7 决策只删 `orchestration_runtime`，`proxy` 未动。当前 17 处引用，关键项：

- `base/plugins/harness/services/orchestration_config.py`：默认 `mode=proxy`，校验仅允许 `app/proxy`
- `base/plugins/harness/services/orchestration_proxy.py`：仅 `proxy` 启用代理/跳过 app 本地鉴权
- `base/plugins/harness/services/service_auth.py`：写主判断（`mode=proxy` 才允许写）
- `services/orchestration/app/config.py`、`app/auth.py`：独立编排进程固定 `proxy` 写主
- `base/plugins/harness/api/app_internal/quota_router.py`：`primary` 判定

---

## 4. D 组：358 条路由与插件顺序

### 4.1 method+path 集合对比

快照 vs 当前 app OpenAPI：

```
L2_PATHS_BEFORE=358 L2_PATHS_NOW=358
L2_OPS_BEFORE=450   L2_OPS_NOW=450
REMOVED=0 ADDED=0
```

消失 0 条、新增 0 条，method+path 集合完全一致，全部在预期内（本组不应改变对外路由）。

### 4.2 插件加载顺序

来源：app 启动日志中的 `插件加载成功: <name>` 行，与 `plugin_order_before.txt` 对比。

```
PLUGIN_ORDER_BEFORE=$1audit,$1customer,$1product,$1sales,$1crm,$1harness,$1llm,$1mail
PLUGIN_ORDER_NOW=audit,customer,product,sales,crm,harness,llm,mail
```

去掉快照里的 PowerShell 前缀 `$1` 后，8 个插件及顺序完全一致。

---

## 5. E 组：套餐解析唯一实现

### 5.1 删除 / 迁移证据

`42efb46` 相关变更：

```
D base/common/quota/services/plan_resolver.py        (47 行，app ORM 版)
D base/common/quota/services/plan_service.py         (11 行，app shim)
R services/gateway/app/plan_resolver.py -> packages/common/quota/services/plan_resolver.py
R services/gateway/tests/plan_parity.py  -> services/gateway/tests/plan_golden.py
```

当前路径检查：

```
base/common/quota/services/plan_resolver.py      -> False
base/common/quota/services/plan_service.py       -> False
services/gateway/app/plan_resolver.py         -> False
services/gateway/tests/plan_parity.py         -> False
```

口径说明：`plan_parity.py` 在 git 里表现为 **rename 后重写** 为 `plan_golden.py`，不是单纯删除文件；旧路径已不存在。

### 5.2 引用改指清单

生产代码当前指向共享包的 import 共 **7 处 / 6 个文件**：

| 文件 | 引用 |
|---|---|
| `base/start.py` | `plan_service` + `plan_resolver.SqlPlanResolver`（2 处，启动注入） |
| `base/common/quota/api/admin.py` | `plan_service.PlanService` |
| `base/common/quota/services/__init__.py` | `plan_service.PlanService` |
| `base/common/quota/services/org_quota_service.py` | `plan_service.PlanService` |
| `base/plugins/agent/services/execution_service.py` | `plan_service.PlanService` |
| `services/gateway/app/main.py` | `plan_resolver.SqlPlanResolver` |

对已删除模块的残留引用：

```
grep "base.common.quota.services.(plan_service|plan_resolver)" -> 0 命中
```

**口径偏差**：“20 处引用”无法复现。真正需要改指的 plan 解析引用是上述 7 处；仓库里其余 `base.common.quota.services` 引用指向未删除的 `quota_service / metrics / estimator / org_scope`，不属于本次改指范围。影响：引用清理本身完整，但数量说法应以实测为准。

### 5.3 黄金用例实测

本次重新执行 `services/gateway/tests/plan_golden.py`：

```
PASS P1 无绑定(org): null
PASS P4 组织套餐: "p4golden_org"
PASS P5 客户等级键: "vip"
PASS P5 客户等级套餐: "p4golden_vip"
PASS P6 过期会员键: "regular"
PASS P6 过期回落 regular: "p4golden_regular"
PASS P7 无会员记录键: "regular"
PASS P7 无会员记录回落 regular: "p4golden_regular"
PASS P8 等级为空键: "regular"
PASS P8 等级为空回落 regular: "p4golden_regular"
PASS P14 过期时间键: "regular"
PASS P14 过期时间回落 regular: "p4golden_regular"
PASS P13 客户不存在键: "regular"
PASS P13 客户不存在回落 regular: "p4golden_regular"
PASS P9/P10 用户角色键（排除未激活，按 role.id 升序）: ["p4golden_role_low", "p4golden_role_high"]
PASS P2 多角色取高优先级: "p4golden_role_high"
PASS P3 priority 并列取 plan_id 大者: "p4golden_tie_large"
PASS P11 用户不存在键: []
PASS P11 用户不存在: null
PASS P12 套餐 disabled: null

结果：20 通过 / 0 失败
EXIT=0
```

### 5.4 写路径 / 事务语义是否有变化

`packages/common/quota/services/plan_resolver.py` 只有两次只读查询：

```python
conn = connections.get("postgres")
rows = await conn.execute_query_dict("SELECT ...", [customer_id])
rows = await conn.execute_query_dict("SELECT ...", [user_id])
```

- 没有 `INSERT / UPDATE / DELETE`，没有 `in_transaction()`，没有 `save()`；解析器本身对数据库零写入。
- 异常语义不变：客户解析异常 → `None`，用户角色异常 → `[]`。
- 与旧 ORM 版相比的两点确定性变化：
  1. 显式 `ORDER BY cm.id` / `ORDER BY r.id`，多行时结果从“依赖 DB 自然顺序”变为“最小 id 优先”。
  2. 裸 SQL 走默认连接，不参与调用方已打开的事务上下文；旧 ORM 查询会使用当前事务连接。
- 当前调用点（`quota_service.py` 215/258/1113、`gateway/budget.py` 290、`execution_service.py` 174）都不在 `in_transaction()` 内，现有行为不受第 2 点影响；若未来在事务内调用并依赖未提交数据，需要重新评估。
- `is_expired` 口径一致：旧模型对 naive `expire_time` 也按 UTC 处理，新 SQL 版同样按 UTC。

---

## 6. 回滚：两步 revert 实测

文档位置：`reports/ops/l3-split-p3-report.md` §5.3（L205–L234）。

本次在 **HEAD=`c6e4239`**（包含 cost 提交）的临时 worktree 重跑，未触碰当前工作区：

```
git worktree add --detach <TEMP>/p4-revert-check HEAD
cd <TEMP>/p4-revert-check
git revert --no-commit dd06288..HEAD
REVERT_STEP1_EXIT=0
STEP1_DIFF_STAT_LINES=0

git revert --no-commit 02bc87f..dd06288
REVERT_STEP2_EXIT=0
STEP2_DIFF_STAT_LINES=0

git worktree remove --force <TEMP>/p4-revert-check
git worktree list -> 仅主工作区
```

即在当前 HEAD 上，“先 revert P4（`dd06288..HEAD`）再 revert P3（`02bc87f..dd06288`）”两步均无冲突，且分别回到 `dd06288` / `02bc87f` 的树状态（`git diff --stat` 为空）。

---

## 7. 缺口与影响汇总

| 项 | 缺口 | 影响 |
|---|---|---|
| A 原始切换时序 | 没有保留带时间戳的切换日志 | 只能重跑 9101 预演并实测当前 9100/代理；路由等价与 503/401 行为可复核，精确切换秒数不可复核 |
| B “28 处” | 与仓库历史不符 | 已给出可复现口径：删除前 33 行引用、消费方 18 处改指；结论“base/ 引用清零”不受影响 |
| C grep 空 | 无（`21387bd` 已清理） | 清理前仅 1 行 docstring，无运行引用 |
| E “20 处” | 与实测不符 | 实际生产 import 7 处 / 6 文件；删除模块残留引用为 0，结论不受影响 |
| D | 无缺口 | 路由与插件顺序均零差异 |
| 回滚 | 无缺口 | 已在含 cost 的 HEAD 上实测两步空 diff |
| cost | 按用户要求不纳入本报告 | 见 `c6e4239` 单独汇报 |
