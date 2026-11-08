# P2 阶段 3：L2 待删边界、C4 收尾与回滚说明

> 状态：待执行。本阶段**不删除代码**，只列边界、前置条件与回滚动作。
> 关联：`reports/specs/l3-service-split/spec.md` §3（删除边界）、§4.2（读依赖白名单）。

## 0. 当前运行态

| 服务 | 入口 | 监听 | 状态 |
|---|---|---|---|
| L2 业务后端 | `.venv\Scripts\python.exe run.py` | `0.0.0.0:9998` | 运行中（加载 P2 shim 代码） |
| L3 网关 | `-m base.common.gateway.server` | `127.0.0.1:9999` | 运行中（本阶段边界外） |
| L3 编排 | `.venv\Scripts\python.exe services\l3-orchestration\run.py` | `127.0.0.1:9100` | 运行中（P2 新工程） |

旧入口 `-m base.plugins.harness.server` 已停用，按“不双跑”处理，未为它恢复 `is_l3` 分支。

## 1. L2 待删边界

### 1.1 A 组：可删（旧 L3 入口专属，新工程已等价覆盖）

| # | 文件 | 现存调用点 | 删除前置条件 | 删除后会断的路径 |
|---|---|---|---|---|
| A1 | `base/plugins/harness/server.py` | ops 文档 `reports/ops/redis-enable-runbook.md:107,281`；`base/__init__.py:4` 注释 | 新入口在 9100 连续稳定运行；运维脚本改指 `services/l3-orchestration/run.py`；删除时同步改两处文档引用 | `python -m base.plugins.harness.server` 无法启动；9100 必须由新工程提供 |
| A2 | `base/plugins/harness/api/l3/business_router.py`、`write_router.py`、`__init__.py` | 仅 `server.py:34-35` | 先删 A1（否则旧入口启动 `ImportError`） | 旧入口业务读写路由（新工程 `/v1/harness/*` 已覆盖） |
| A3 | `base/plugins/harness/api/internal/router.py`、`__init__.py` | 仅 `server.py:33` | 先删 A1 | 旧入口 `/internal/v1/harness/*`（新工程同名路径已覆盖） |
| A4 | `base/plugins/harness/services/l3_client_auth.py` | 仅 A2 两个 router | 先删 A2 | 旧入口客户端凭据校验（新工程 `app/l3_client_auth.py` 已覆盖） |
| A5 | `base/plugins/harness/services/l3_touch.py` | 仅 `l3_client_auth.py:61`（运行时 import） | 先删 A4 | 旧入口 `last_used_at` 上报（新工程 `app/l3_touch.py` 已覆盖） |
| A6 | `base/plugins/harness/services/orchestration_runtime.py` | 仅 `server.py:36,184` | 先删 A1 | 无其他引用；先删 A1 前删除会导致旧入口 `ImportError` |
| A7 | `base/plugins/harness/services/l2_quota_client.py` | **无调用者**（L2 已改直调 `QuotaService`；L3 用自身 `app/l2_quota_client.py`） | 与 A1 一并删；确认 `rg "l2_quota_client" base/` 为空 | 无（历史模块） |

建议删除顺序：A1 → A2 → A3 → A4 → A5 → A6 → A7，每步后重启 L2 验证 `/health/health` 与 `proxy_l3` 读写。

### 1.2 B 组：迁移期必须保留（有活调用点）

| # | 文件 | 当前调用点 | 可删条件 | 误删后果 |
|---|---|---|---|---|
| B1 | `base/plugins/harness/services/orchestration_proxy.py` | `api/v1/session_router.py`（5 处）、`run_router.py`（8 处）、`policy_router.py`（1 处） | `orchestration.mode` 不再为 `proxy_l3`，且 L2 这些路由改为直连/只读后 | L2 启动 `ImportError`，管理台迁移期读写全部不可用 |
| B2 | `base/plugins/harness/services/orchestration_config.py` | `service_auth.py:21-24`（`auth_timestamp_window_seconds` / `internal_allowed_ips` / `write_enabled` / `orchestration_config`）、`orchestration_proxy.py:9` | L2 内部额度/心跳 API 不再验服务凭据，或改读共享配置 | L2 内部 API 验签失败、代理无法读取下游地址 |
| B3 | `base/plugins/harness/services/readonly_db.py` | `service_auth.py:27,147`（验签读 `service_credential`） | `service_auth` 改用共享只读连接（`packages.agentpanel_common` 内）后 | L2 `/internal/v1/harness/quota*`、`touch` 验签 500 |
| B4 | `base/plugins/harness/services/service_auth.py` | L2 内部额度/心跳路由依赖 | 内部 API 下线或迁出后 | L3→L2 额度调用 401 |
| B5 | `base/plugins/harness/services/quota_backend.py` | 共享分派器（`on_startup` 注入） | 共享 `quota_backend` 改为直连实现后 | L2 额度预占/结算 503（`额度后端未初始化`） |
| B6 | `base/plugins/harness/api/v1/approval_router.py` | L2 管理台审批查询/处理 | 管理台审批迁移到独立前端服务后 | 管理台审批页 404（L3 仅覆盖创建/决策/待办） |

### 1.3 本阶段边界外

`base/common/gateway/**`（9999 网关）仍驻留 L2 仓库，属 spec §3.2 的 P3 边界，本阶段不列入删除清单。

## 2. C4 收尾

已闭环项：

1. 共享 `packages/agentpanel_common/domain/policy_service.py` 不再 import `plugin_manager`，审批配置改为 `configure_approval()` 显式注入。
2. L2 注入点在 `base/plugins/harness/__init__.py:13-16`（`on_startup` 内 `quota_backend.configure_l2()` + `policy_service.configure_l2()`），无 import 副作用。
3. L3 注入点在 `services/l3-orchestration/app/main.py`（lifespan 内 `quota_backend.configure_l3()`）。
4. 实测：屏蔽 `base.*` 命名空间后导入 L3 全部模块 → `blocked_base_imports: none`，19 条路由正常构建。
5. `rg "from base\.|import base\.|plugin_manager"` 在 `services/l3-orchestration/` 与 `packages/agentpanel_common/` 仅命中 docstring。

未闭环项（需决策，本阶段未动）：`base/plugins/__init__.py` 的传递性模块加载与 `plugin_manager` 单例仍服务 L2 插件装配。编排侧已不再触达它；若要求物理移除，需重构 L2 插件注册为显式清单，属独立阶段，不属于 P2 范围。

## 3. 回滚说明（可执行）

### 3.1 回滚到 P2 之前（代码级，推荐）

```powershell
# 按提交逆序回退（新建 revert 提交，不改写历史）
git revert --no-edit 7aaf3a8 aeebf9a 6f75e51 79c4f32

# 重启三服务
Get-NetTCPConnection -LocalPort 9998,9999,9100 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
$env:ORCHESTRATION_SERVICE_SECRET=[Environment]::GetEnvironmentVariable('ORCHESTRATION_SERVICE_SECRET','User')
Start-Process .venv\Scripts\python.exe -ArgumentList 'run.py' -WorkingDirectory d:\programs\fastapi\agentpanel
Start-Process .venv\Scripts\python.exe -ArgumentList '-m','base.common.gateway.server' -WorkingDirectory d:\programs\fastapi\agentpanel
Start-Process .venv\Scripts\python.exe -ArgumentList '-m','base.plugins.harness.server' -WorkingDirectory d:\programs\fastapi\agentpanel
```

验证：

```powershell
Invoke-RestMethod http://127.0.0.1:9998/health/health
Invoke-RestMethod http://127.0.0.1:9999/health
Invoke-RestMethod http://127.0.0.1:9100/health/health
Invoke-RestMethod http://127.0.0.1:9100/health/orchestration
```

### 3.2 仅回切 9100 入口（不 revert，只读降级）

```powershell
$p=(Get-NetTCPConnection -LocalPort 9100 -State Listen).OwningProcess; Stop-Process -Id $p -Force
$env:ORCHESTRATION_SERVICE_SECRET=[Environment]::GetEnvironmentVariable('ORCHESTRATION_SERVICE_SECRET','User')
Start-Process .venv\Scripts\python.exe -ArgumentList '-m','base.plugins.harness.server' -WorkingDirectory d:\programs\fastapi\agentpanel
```

限制：P2 代码下旧入口不调用任何 `configure()`，**只读路径可用，写路径（预占/结算）会 503**（`额度后端未初始化`，实测 `QuotaUnavailable`）。因此它只适合临时排障，不是有效回滚目标。

### 3.3 放弃 P2 分支（需人工确认，破坏性）

```powershell
git reset --hard 2701386   # 丢弃本阶段 4 个提交，工作区回到 P1 末态
```

仅在明确放弃 P2 时执行；执行前确认无未提交产出（当前仅 `reports/ops/l3-split-p2-stage3-report.md` 与 `deploy/harness-linux-verify/out*/` 未跟踪）。

### 3.4 数据侧

无需回滚：P2 未新增/修改表结构与迁移，`schema_check` 只读断言；验证期间产生的 `hcli_p2verify` 客户端、测试组织/身份/会话/运行/审批/预占记录已全部回收。

## 4. 遗留决策点

1. `base/plugins/__init__.py` 传递性加载 / `plugin_manager` 单例是否在后续阶段物理移除（见 §2）。
2. `orchestration_proxy` 及 `mode=proxy_l3` 的退役时点（决定 B1/B2 何时可删）。
3. L2 内部额度/心跳 API 是否保留独立只读连接（决定 B3 何时可删）。
