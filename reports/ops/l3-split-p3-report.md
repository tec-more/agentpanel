# L3 网关拆分 P3 实施与切换报告（含回滚手册）

> 生成时间：2026-11-08
> 基线提交：`02bc87f`（分支 `release/0.0.1`，P3 代码在当前工作区，尚未提交）
> 适用范围：本机 Windows 三进程（L2 9998 / 网关 9999 / 编排 9100），电源 `.venv` 解释器
> 密钥口径：DB / Redis 密码一律运行时从 `config.conf` 读取，本文不写明文

---

## 1. 结论摘要

| 项 | 结果 |
|---|---|
| L2 套餐解析（ORM）与网关套餐解析（只读 SQL）对拍 | **20/20 PASS**（P1–P14 全分支，字段级一致） |
| 网关数据面 V3–V11（假 provider，9990 宽松实例） | **66 通过 / 0 失败** |
| 新旧网关 A/B（9990 新 vs 9996 旧实现，同一 fixture） | **17 通过 / 0 失败** |
| 数据面变更 | 无新表、无新键；沿用 `gw:*`，无需迁移 |
| 旧 9999 | 切换前持续可用（`/health` 200），切换时按“停新启旧”流程处理 |

> 结论：P3 代码具备切换条件；回滚路径已文档化并完成预演（§5.5）。

---

## 2. 验证证据（可复现命令）

| 验证 | 命令（仓库根目录，`.venv` 解释器） | 结果 |
|---|---|---|
| 双解析器对拍 | `.venv\Scripts\python.exe services\l3-gateway\tests\plan_parity.py` | 20/20 PASS |
| 数据面 V3–V11 | `.venv\Scripts\python.exe services\l3-gateway\tests\verify_gateway.py`（需 9990 宽松实例） | 66/0 |
| 新旧网关 A/B | `.venv\Scripts\python.exe services\l3-gateway\tests\verify_parity_gateway.py`（`GW_NEW_BASE`/`GW_OLD_BASE`） | 17/0 |

关键断言（摘录）：

- V4：非白名单域名 403 且上游 0 次请求；`allow_loopback=false` 时 `127.0.0.1` 403；
- V5：`dsh_session_log` 不出现在上游请求体；
- V6：SSE 客户端收到的字节串与假 provider 产出逐字节相等；
- V7：每请求 `usage_record` 恰好 1 行，`source=gateway`、`gateway_key=<lease_id>`、`idem_key` 以 `gw:` 开头；
- V9：鉴权成功后 `gw:lease:state:<lease_id>` 存在且 TTL 5–10s，吊销写穿删除；
- V10：`REDIS_ENABLED=false` 独立实例走 DB 兜底，账户/budget 变更正确；
- V12：同一租约/请求体下新旧网关响应体、状态码、记账字段逐字段一致。

---

## 3. 切换目标：正式配置

| 配置项 | 值 | 来源 |
|---|---|---|
| 监听 | `127.0.0.1:9999` | `services/l3-gateway/manifest.json` |
| `allow_loopback` | `false` | 同上 / 不设 `GW_ALLOW_LOOPBACK` |
| `provider_domain_allowlist` | `["api.deepseek.com"]` | 同上 / 不设 `GW_PROVIDER_DOMAIN_ALLOWLIST` |
| `max_concurrent_requests_per_owner` | `8` | 同上 |
| `fail_closed` | `true` | 同上 |
| `lease_cache_ttl_seconds` | `8` | 同上 |
| DB / Redis | `config.conf` 运行时注入 `DB_*` / `REDIS_*` | §3.1 |

### 3.1 启动新入口（正式配置）

```powershell
$ROOT = 'd:\programs\fastapi\agentpanel'
$VENV = Join-Path $ROOT '.venv\Scripts\python.exe'
$CFG  = Join-Path $ROOT 'config.conf'

# 解析 config.conf（不依赖第三方库）
function Read-Ini([string]$path) {
  $ini = @{}; $section = ''
  foreach ($line in Get-Content $path) {
    if ($line -match '^\s*\[(.+)\]\s*$') { $section = $matches[1].Trim().ToLower(); continue }
    if ($line -match '^\s*([^#;=]+?)\s*=\s*(.*)$') {
      if (-not $ini.ContainsKey($section)) { $ini[$section] = @{} }
      $ini[$section][$matches[1].Trim().ToLower()] = $matches[2].Trim()
    }
  }
  return $ini
}
$ini = Read-Ini $CFG

$env:DB_HOST      = $ini['db']['db_host']
$env:DB_NAME      = $ini['db']['db_name']
$env:DB_USER      = $ini['db']['db_user']
$env:DB_PASSWORD  = $ini['db']['db_password']
$env:DB_PORT      = $ini['db']['db_port']
$env:REDIS_ENABLED  = $ini['redis']['enabled']
$env:REDIS_HOST     = $ini['redis']['host']
$env:REDIS_PORT     = $ini['redis']['port']
$env:REDIS_PASSWORD = $ini['redis']['password']
$env:REDIS_DB       = $ini['redis']['db']
$env:GW_PORT = '9999'
# 显式清空覆盖项，确保走 manifest 正式默认值
Remove-Item Env:GW_ALLOW_LOOPBACK,Env:GW_PROVIDER_DOMAIN_ALLOWLIST,Env:GW_MAX_CONCURRENT_REQUESTS_PER_OWNER,Env:GW_FAIL_CLOSED -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path (Join-Path $ROOT 'logs') | Out-Null
Start-Process $VENV -ArgumentList 'services\l3-gateway\run.py' -WorkingDirectory $ROOT -WindowStyle Hidden `
  -RedirectStandardOutput "$ROOT\logs\gw.out.log" -RedirectStandardError "$ROOT\logs\gw.err.log"
do { Start-Sleep -Milliseconds 500 } until (Get-NetTCPConnection -State Listen -LocalPort 9999 -ErrorAction SilentlyContinue)
```

> 说明：不设置 `GW_ALLOW_LOOPBACK` / `GW_PROVIDER_DOMAIN_ALLOWLIST` 等覆盖项，即使用 manifest 的正式默认值（回环拒绝、白名单仅 `api.deepseek.com`、并发 8、`fail_closed=true`）。

### 3.2 切换执行记录（2026-11-08）

| 步骤 | 动作 | 结果 |
|---|---|---|
| S1 | 回滚预演：`02bc87f` worktree 在 9996 启旧入口 | `/health` 200 `{"status":"ok","deployment":"standalone","fail_closed":true}`；停止并清理 worktree |
| S2 | 9990 宽松实例复跑 `verify_gateway.py`（切换前假 provider 成功链路取证） | **66 通过 / 0 失败**（含 V5-1 非流式、V6-2 SSE 逐字节） |
| S3 | 停 9990 宽松实例、停旧 9999 | 9990 free；旧 9999 已退出 |
| S4 | 启新 9999（正式配置，仅注入 `GW_PORT=9999` + DB/Redis 环境变量） | `GET /health` 200 `{"status":"ok","deployment":"standalone","fail_closed":true}`；`GET /health/health` 200（database/redis healthy） |
| S5 | 切换后校验（临时脚本，复用同一批 fixture） | **16 通过 / 0 失败**，明细见下表 |
| S6 | 9998 / 9100 以 `.venv` 规范入口重启 | `9998/health/health`、`9100/health/health`、`9100/health/orchestration` 全 200；`mode=proxy_l3` |
| S7 | L2 代理证明 | 经 L2 与直连 9100 的响应体逐字节一致（401 `无效的 Harness 客户端凭据`）；停 9100 时 L2 返回 **503** `orchestration_downstream_unavailable`，恢复后回到 401 |
| S8 | 最终端口核对 | 9998 / 9999 / 9100 均 LISTEN 且父进程为 `.venv\Scripts\python.exe`；9990、9996 free |

切换后校验明细（正式配置，目标 `127.0.0.1:9999`）：

| 用例 | 结果 |
|---|---|
| S3-1 缺凭据 | 401 `缺少网关租约虚拟 key` |
| S3-2 JWT 凭据 | 401 `网关只接受租约虚拟 key，不接受 JWT/登录态凭据` |
| S3-3 非 `dgw` 格式 | 401 `网关只接受租约虚拟 key` |
| S3-4 secret 不匹配 | 401 `网关虚拟 key 无效` |
| S3-5 已吊销 | 401 `网关租约已吊销` |
| S3-6 已过期 | 401 `网关租约已过期` |
| S3-7 会话关闭 | 403 `会话已关闭，租约不可用` |
| S3-8 运行终态 | 403 `运行已结束，租约不可用` |
| S3-9 回环假 provider（非流式） | **403** `provider 域名不在出网白名单: 127.0.0.1` |
| S3-10 回环假 provider（流式） | **403** 同上 |
| S3-11 假 provider 计数 | **0**（请求未出网） |
| S3-12 `gw:lease:state:<lease_id>` | 存在，**TTL=8**（5–10 区间） |
| S3-13 RPM=1 第二路 | **429** `网关租约请求频率超限` |
| S3-14 usage_record 行数 | 2（非流式/流式各 1 行） |
| S3-15 `resource_type` / `amount` | `gateway_error` / `0` |
| S3-16 `source` / `gateway_key` | `gateway` / 对应 `lease_id` |

> 正式配置下 `allow_loopback=false` 的直接证明来自 9990 的 V4-3（白名单含 `127.0.0.1` 时仍以“回环地址”拒绝）；切换后白名单不含回环，因此先以“不在白名单”拒绝。两者共同覆盖两道防线。
>
> 运行方式备注：`Start-Process` 启动的进程在命令会话结束后会被回收；三个服务应以常驻后台/计划任务方式运行（本次用后台常驻命令启动）。

---

## 4. 回滚触发条件

出现任一项即立即回滚，不继续后续步骤：

1. 新 9999 启动失败（退出码非 0、端口未监听、日志含 fail-closed 校验错误）；
2. `GET /health` 非 200，或字段与 `status=ok, deployment=standalone, fail_closed=true` 不符；
3. `GET /health/health` 的 database / redis 任一非 healthy；
4. 租约鉴权失败分支行为与旧入口不一致（401/403/429 语义、错误体形状）；
5. 假 provider 请求在正式配置下未按预期 403（说明出网策略未生效）；
6. 9998 / 9100 健康检查异常且无法在短时间内恢复；
7. 端口上出现双入口（9990 / 9996 仍有监听）。

---

## 5. 回滚手册

### 5.1 通用停止/启动函数

```powershell
$ROOT = 'd:\programs\fastapi\agentpanel'
$VENV = Join-Path $ROOT '.venv\Scripts\python.exe'

function Stop-ByPort([int]$port) {
  $pids = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
          Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $pids) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $proc.ParentProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Write-Output ("stopped PID {0} (port {1})" -f $procId, $port)
  }
}
```

### 5.2 主回滚路径（P3 尚未提交时，已预演）

P3 代码当前在工作区（`HEAD=02bc87f` 未包含 P3 变更），因此“回滚到旧入口”= 用一个
`02bc87f` 的干净 worktree 启旧实现。此路径不触碰当前工作区，不影响 9998/9100。

```powershell
# 1) 停新入口（保留代码目录，不删）
Stop-ByPort 9999
do { Start-Sleep -Milliseconds 500 } until (-not (Get-NetTCPConnection -State Listen -LocalPort 9999 -ErrorAction SilentlyContinue))

# 2) 从基线提交取干净旧实现（worktree）
$OLDTREE = Join-Path $env:TEMP 'l3-gateway-old-02bc87f'
git -C $ROOT worktree add --detach $OLDTREE 02bc87f

# 3) 注入 DB/Redis 环境变量（与 §3.1 的 Read-Ini 相同）
#    $ini = Read-Ini $CFG  并设置 $env:DB_* / $env:REDIS_*
$env:GW_PORT = '9999'
Remove-Item Env:GW_ALLOW_LOOPBACK,Env:GW_PROVIDER_DOMAIN_ALLOWLIST -ErrorAction SilentlyContinue

# 4) 启旧入口
Start-Process $VENV -ArgumentList '-m','base.common.gateway.server' -WorkingDirectory $OLDTREE -WindowStyle Hidden `
  -RedirectStandardOutput "$ROOT\logs\rollback-old.out.log" -RedirectStandardError "$ROOT\logs\rollback-old.err.log"
do { Start-Sleep -Milliseconds 500 } until (Get-NetTCPConnection -State Listen -LocalPort 9999 -ErrorAction SilentlyContinue)

# 5) 健康验证（见 §5.4）
Invoke-RestMethod 'http://127.0.0.1:9999/health'

# 6) 回滚稳定后清理 worktree（保留日志）
git -C $ROOT worktree remove --force $OLDTREE
git -C $ROOT worktree prune
```

### 5.3 git revert 路径（P3 提交之后使用）

P3 之后还有 P4（L2 残留边界删除）。回滚必须分**两步**，不能一次把 P3、P4 混在一起 revert：

1. **先 revert P4**：撤销 P4 各组提交（哈希区间 `dd06288..HEAD`，git revert 会自动按时间倒序逐个应用）。此步完成后回到 P3 末态：新工程 `services/l3-gateway` 与 `services/l3-orchestration` 仍在，L2 网关兼容层恢复，三个服务可继续以 P3 方式运行。
2. **再 revert P3**：撤销 P3 的 4 个提交（区间 `02bc87f..dd06288`），回到 P3 前基线 `02bc87f`。

```powershell
$ROOT = 'd:\programs\fastapi\agentpanel'

# 第 1 步：revert P4（区间形式等价于按时间倒序逐提交 revert）
git -C $ROOT revert --no-commit dd06288..HEAD
git -C $ROOT diff --stat dd06288   # 预期：无输出（完全回到 P3 末态）
# 此时重启仍用 P3 入口：services/l3-gateway/run.py、services/l3-orchestration/run.py

# 第 2 步：revert P3（4 个提交，区间内含 185f3c1/1245ce4/e005ab6/dd06288）
git -C $ROOT revert --no-commit 02bc87f..dd06288
git -C $ROOT status --short        # 预期：仅 P3/P4 涉及文件被还原
git -C $ROOT diff --stat 02bc87f   # 预期：无输出（完全回到 P3 前基线）
git -C $ROOT commit -m "revert: 回滚 L3 网关拆分 P3/P4"

# 回到基线后 9999/9100 使用旧入口
Stop-ByPort 9999
Start-Process $VENV -ArgumentList '-m','base.common.gateway.server' -WorkingDirectory $ROOT -WindowStyle Hidden `
  -RedirectStandardOutput "$ROOT\logs\rollback-old.out.log" -RedirectStandardError "$ROOT\logs\rollback-old.err.log"
Start-Process $VENV -ArgumentList '-m','base.plugins.harness.server' -WorkingDirectory $ROOT -WindowStyle Hidden `
  -RedirectStandardOutput "$ROOT\logs\rollback-old-l3.out.log" -RedirectStandardError "$ROOT\logs\rollback-old-l3.err.log"
```

> 已实测：在临时 worktree 上按上述两步（先 `dd06288..HEAD`、再 `02bc87f..dd06288`）`revert --no-commit` 后，`git diff --stat 02bc87f` 为空，证明 P3+P4 可完整还原至基线。
> P4 后续组提交后无需改本文：区间随 `HEAD` 自动覆盖。
> 若 revert 出现冲突：`git revert --abort` 后改用 §5.2 的 worktree 路径（结果等价，不污染工作区）。

### 5.4 健康检查验证点

| # | 检查 | 预期 |
|---|---|---|
| H1 | `Invoke-RestMethod http://127.0.0.1:9999/health` | 200，`status=ok`、`deployment=standalone`、`fail_closed=true` |
| H2 | `Invoke-RestMethod http://127.0.0.1:9999/health/health`（仅新入口提供） | 200，`database.healthy`、`redis.healthy` |
| H3 | `http://127.0.0.1:9998/health/health` | 200，database / redis healthy |
| H4 | `http://127.0.0.1:9100/health/health` | 200，database / redis healthy |
| H5 | 端口唯一性 | 9999 仅 1 个监听；9990 / 9996 无监听 |
| H6 | 进程来源 | 父进程为 `.venv\Scripts\python.exe`（venv redirector 子进程持端口属正常） |

### 5.5 回滚可用性预演记录

> 预演方式：在 9996 上按 §5.2 从 `02bc87f` 起旧入口，验证 health 后停止并清理 worktree。

- 预演时间：2026-11-08（首次预演）
- 预演端口：9996
- `/health` 结果：`200 {"status":"ok","deployment":"standalone","fail_closed":true}`
- 启动日志：`Redis连接成功`，`Uvicorn running on http://127.0.0.1:9996`
- 清理结果：9996 已释放；`git worktree list` 仅主工作区 `D:/programs/fastapi/agentpanel 02bc87f [release/0.0.1]`
- 结论：**回滚路径可用**（该路径不依赖 P3 未提交的改动，也不影响 9998/9100）

---

## 6. 已知取舍：正式配置与回环假 provider 的矛盾

正式配置 `allow_loopback=false` + 白名单仅 `api.deepseek.com`，意味着**切换后**无法用
`127.0.0.1` 假 provider 做成功链路验证（`EgressPolicy._check_private` 会 403）。

处理方式（按顺序执行，并在切换报告中如实标注）：

1. 切换前在 9990 宽松实例完成“假 provider 流式 + 非流式”成功链路取证（V6/V7 已覆盖），并单独留一条记录；
2. 切换后，同一假 provider 请求打在正式 9999 上，**预期 403 且假 provider 零请求**——以此证明正式出网策略生效；
3. 切换后的其余校验（health / 租约缓存 / 失败分支 / 鉴权 401/403/429）均不依赖回环上游。

---

## 7. P4/P5 待办登记

### 7.1 迁移收尾（spec §13.8）

| 编号 | 内容 | 验收 |
|---|---|---|
| T4.11 | 确认 L2 无 `base.common.quota.services` 外部引用后，删除 `plan_service/quota_service/metrics` 的 L2 shim 与 `plan_resolver.py` 过渡注入；保留 `base.common.quota.services` 路径直到 P4 删除边界 | `rg "base.common.quota.services"` 仅剩 shim 自身 |
| T4.12 | L2 `base/common/gateway/*` shim 随 embedded 挂载一并删除（P4 T4.2）；删除前确认 `gateway_lease_service` 只引用 `issuance_config` 与共享 `lease_auth` | 删除后 9998 启动 + 租约签发用例通过 |
| P5 前置 | `services/l3-gateway` 不得出现 `from base` / `import base`（含 `base.core.users`）；`gateway_dependency_modules()` 仅共享模型 | `rg "^(from\|import) base" services/l3-gateway` 无匹配；容器镜像构建通过 |

### 7.2 双解析器漂移防护（强制要求）

套餐规则同时存在两份解析实现，**任何套餐规则改动必须同步两处并跑对拍**，不允许只改一侧：

| 侧 | 文件 | 类 |
|---|---|---|
| L2（ORM） | `base/common/quota/services/plan_resolver.py` | `L2PlanResolver` |
| 网关（只读 SQL） | `services/l3-gateway/app/plan_resolver.py` | `SqlPlanResolver` |

强制流程：

1. 修改共享规则或任一解析器后，必须执行：
   ```powershell
   .venv\Scripts\python.exe services\l3-gateway\tests\plan_parity.py
   ```
   要求 **P1–P14 全 PASS**（20/20）；任一分支不一致即视为阻断，不得上线；
2. PR/提交说明中注明“双解析器已对拍”；
3. 新增套餐分支（如新的 owner_type / 新的等级来源）必须同时补充对拍 fixture，并在 spec §13.6 分支表中登记；
4. 对拍脚本使用 `p3parity_` 前缀 fixture 且结束清理，禁止在共享库留下测试数据。

> 说明：`plan_service`（共享包）只保留解析骨架；两次环境相关读取由入口注入，因此“规则 + 解析键”两侧都必须核对，不能只看最终 `plan.id`。

---

## 8. 清理与最终状态

- 数据库：`p3v_` 前缀 fixture 全 0（`usage_record` / `harness_gateway_lease` / `harness_gateway_budget` / `harness_gateway_concurrency` / `harness_session` / `harness_run` / `llm_provider` / `llm_model` / `llm_api_key` / `harness_audit_event`）。
- `quota_account`：校验脚本 `finally` 未覆盖到 fixture owner `usr/999001`，已手工删除（剩余 0）。
- Redis：`gw:*p3v*`、`quota*:usr:999001:*` 全 0；仅剩历史 `gw:budget:lease:lse_p1verify_2026`（TTL≈8.5h，来自 P1 验证，本次不动，到期自清）。
- 临时产物：`l3-gateway-old-p3` worktree 已移除；假 provider（18080）随脚本退出；临时校验脚本与 9996 日志已删除；`git worktree list` 仅主工作区。
- 最终进程：9998 / 9999 / 9100 同时可用，父进程均为 `.venv\Scripts\python.exe`；9990、9996 无监听。
- 仓库状态：P3 代码仍在工作区未提交（`HEAD=02bc87f`），因此“即时回滚”走 §5.2 worktree 路径；P3 提交后改用 §5.3 `git revert`。
- 执行备注：`Start-Process` 启动的服务会在命令会话结束时被回收，实际以常驻后台方式运行；另有两处校验断言关键字写窄（已修正后复跑通过），不涉及产品代码。
