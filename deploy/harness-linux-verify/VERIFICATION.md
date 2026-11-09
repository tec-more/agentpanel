# Linux 容器验证结果（agentpanel / dsh）

- 运行时间：2026-11-07
- 镜像：`agentpanel-dsh-verify:0.1.5rc1`（`python:3.12-slim` Linux x64 + `deepseek-harness-sdk==0.1.5rc1`）
- 容器内核：`Linux 6.18.33.2-microsoft-standard-WSL2 x86_64`，`bubblewrap 0.12.0` 可用
- 运行用户：`verifier`（UID 10001，非 root）
- 模型：**未调用真实 provider**。`DEEPSEEK_BASE_URL=http://127.0.0.1:18080/v1` 指向容器内假 provider，key 为占位值 `sk-agentpanel-verify-placeholder`
- 网络：主验证容器 `--network none`，仅 loopback；另跑一次联网对照容器（仅 web_fetch 域名策略）
- 业务代码：未修改；仅只读挂载 `packages/agentpanel_common/gateway/service.py` 与 `packages/agentpanel_common/upstream/egress.py` 调用真实 `assert_egress_allowed`

## 结论速览

| # | 验证项 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | `tools/pre-execute` 进程内拦截 | **通过** | `hook/invoked` + `hook/result decision=deny`；工具返回 `blocked by PreToolUse hook`；目标文件未创建 |
| 2 | workspace 越界写 | **通过** | bash 写 `/work` 父目录报 `Read-only file system`；fs 工具报 `FS_SANDBOX_DENIED`（绝对路径与 `../` 两次均拒绝） |
| 3 | 实际出网拦截 | **dsh 层不通过；网关层通过** | 联网时 `example.com` 返回 HTTP 200（dsh 无域名白名单）；网关 `assert_egress_allowed` 5 个用例全部符合预期；隔离网络下非白名单请求失败 |
| 4 | dsh 原生审批通道 | **不通过（未下发到客户端）** | `approval/asked` 与 `approval/decided` 均产生，但 outcome=`unavailable`；客户端 0 次 `session/request_permission`；工具报 `no approval channel is available` |

## 逐项证据

### 1. Pre-execute 钩子能在进程内真正拦住危险调用 —— 通过

做法：通过 patch 挂载 `@deepseek-ai/dsh-hooks-claude-code`，`PreToolUse` 钩子匹配 `bash`，外部子进程识别危险命令后输出 `permissionDecision=deny`。假 provider 让模型调用：

```bash
touch /work/should_not_exist_hook.txt
```

结果：

- `hook/invoked`、`hook/result` 事件存在，`decision=deny`，钩子子进程被调用 4 次；
- 工具结果为 `Error: agentpanel verify: blocked by PreToolUse hook`；
- `/work/should_not_exist_hook.txt` 不存在。

结论：钩子确实进入了 dsh 的 `tools/pre-execute` 瀑布，并在工具执行前否决调用，不是仅后端判定。

### 2. workspace 越界写被阻断 —— 通过

越界目标特意选 `/work`（workspace 为 `/work/ws`）：该目录对运行用户可写，因此失败只能来自 dsh 沙箱。

| 方式 | 目标 | 结果 |
|---|---|---|
| bash | `/work/agentpanel_escape_bash.txt` | `bash: ... Read-only file system`，文件不存在 |
| fs 工具 | `/work/agentpanel_escape_fs.txt` | `FsError / FS_SANDBOX_DENIED`，提示 workspace-write 下拒绝，文件不存在 |
| fs 工具 | `../agentpanel_escape_fs_rel.txt` | 同上，文件不存在 |

补充发现：`/tmp` 在沙箱内是隔离的临时视图，命令写 `/tmp` 会“成功”但文件不会出现在容器 `/tmp`，因此不能用 `/tmp` 作为越界判定目标。

### 3. 实际出网拦截 —— dsh 自身不拦截，网关层通过

**隔离网络（`--network none`）**

- `http://example.com/agentpanel-egress-deny`：`getaddrinfo EAI_AGAIN`，请求失败；
- 配置的 provider 端点（本机假 provider）可直达，共 14 次 LLM 请求；
- `http://api.deepseek.com:18080/egress-ok` 经 `--add-host` 指向 `127.0.0.1` 后被 dsh 拒绝：`WEB_BLOCKED_URL: resolves to a non-public IP address`（dsh 自带私网/回环 SSRF 防护）。

**联网对照容器（默认 bridge）**

| URL | HTTP 状态 | 说明 |
|---|---|---|
| `https://api.deepseek.com/` | 401 | 白名单 provider 域名可达（未带 key，401 即网络可达） |
| `https://example.com/` | 200 | 非白名单公网域名同样可达 |

结论：`dsh` 的 `web_fetch` **没有 provider 域名白名单**，只有私网/回环 SSRF 防护。生产上不能依赖 dsh 拦截出网；必须保证 dsh 的模型请求只指向业务网关，由网关执行白名单，并用容器/网络策略兜底。

**网关白名单函数（只读加载业务代码）**

| URL | 期望 | 实际 |
|---|---|---|
| `https://api.deepseek.com/v1/chat/completions` | 放行 | 放行 |
| `https://example.com/v1/chat/completions` | 拒绝 | 403 provider 域名不在出网白名单 |
| `http://127.0.0.1:18080/...`（默认 allow_loopback=false） | 拒绝 | 403 |
| `ftp://api.deepseek.com/...` | 拒绝 | 403 协议不被允许 |
| `http://127.0.0.1:18080/...`（allow_loopback=true） | 放行 | 放行 |

### 4. 原生审批通道是否下发、放行后执行是否走得通 —— 不通过

做法：先让 bash 越界写被沙箱拒绝，再按 dsh 约定携带 `sandbox_permissions=danger-full-access` + `justification` 重试同一命令，触发原生审批。

结果：

- `approval/asked` 1 次：`toolName=bash`、`callId=call_agentpanel_verify`、reason 为升级到 `danger-full-access`；
- `approval/decided` 1 次，`outcome=unavailable`；
- 客户端收到 `session/request_permission` **0 次**；
- 工具结果：`Error: sandbox escalation to "danger-full-access" requires approval, but no approval channel is available`；
- 放行后目标文件不存在。

原因：`dsh-user-approval` 的 `ask` 策略把请求交给 `approval/request` 瀑布的“终端 answerer”；SDK profile 未组合任何 answerer，因此请求在 seam 内直接以 `unavailable` 失败关闭（fail-closed）。原生审批 seam 确实被触发，但**没有下发到 SDK 客户端**，“客户端放行后执行”这条路在当前 profile 下走不通。

与 Windows 的差异：Windows 上只能确认“审批插件未注册/未生效”；Linux 上进一步确认 seam 存在、事件成对落库，但终端 answerer 缺失，结论是 fail-closed 而非静默放行。

## 生产兜底结论

1. **进程内拦截**：`tools/pre-execute` + Claude Code 兼容钩子可在工具执行前硬拒绝，可作为 dsh 侧第一道防线；但不能替代后端策略，钩子配置仍在运行环境内。
2. **文件边界**：`workspace-write` 沙箱在 Linux 上对 bash 与 fs 工具都真实生效；生产需保证 workspace 根正确、backend 不退化到 unconfined，失败时保持 fail-closed（本次未出现 unconfined 放行）。
3. **出网**：dsh 自身不做域名白名单。生产必须让 dsh 的 `base_url` 只指向 `/v1/gateway`，由网关 `assert_egress_allowed` 执行白名单；同时对 `web_fetch`/`web_search` 这类绕过网关的工具做禁用或网络策略限制。容器/主机网络策略作为最后兜底。
4. **审批**：不能依赖 dsh 原生审批通道（SDK profile 无 answerer，结果是 `unavailable`）。继续使用现有后端侧拦截：`approval/asked`/`approval/decided` 事件落库、5 分钟超时拒绝、单次授权、fail-closed。若要启用原生通道，需额外组合一个终端 answerer（本次未做，属于扩展项）。

## 限制与未覆盖

- 未调用真实 provider；模型请求全部由假 provider 响应。
- 网关只验证了真实 `assert_egress_allowed` 函数，未启动完整 embedded 网关（需 DB/Redis 与业务应用），因此未覆盖“网关 HTTP 端到端拒绝/放行”路径。
- 联网对照容器依赖宿主机 IPv4 出网；`example.com` HTTP 200 是本次判断 dsh 无域名白名单的直接证据。
- 原生审批只在“无 answerer”的 SDK profile 下验证；未实现自定义 answerer，因此“有 answerer 时放行后执行”未被实测。
- 容器使用 `--security-opt seccomp=unconfined` 让 bubblewrap/unshare 可用；生产需按宿主内核与权限单独评估。

## 复现

```powershell
# 主验证（隔离网络）
powershell -ExecutionPolicy Bypass -File deploy\harness-linux-verify\run.ps1

# 联网对照（仅验证 dsh web_fetch 域名策略）
docker run --rm --name agentpanel-dsh-egress `
  --security-opt seccomp=unconfined `
  -e VERIFY_SCENARIOS=egress_public_ok,egress_public_deny `
  -v "${PWD}\deploy\harness-linux-verify\out-network:/out" `
  agentpanel-dsh-verify:0.1.5rc1
```

原始证据（**已纳入版本控制**，2026-11-09 起随仓库保留）：

- `out/results.json`、`out/transcript_*.json`、`out/fake_provider_requests.jsonl`
- `out-network/results.json`、`out-network/transcript_*.json`

证据使用注意：

- 上述输出是本次运行的**唯一原始事件流**；`run.ps1` 通过 `-v out:/out` 挂载，重新运行会**直接覆盖**现有文件。需要保留历史时请先提交或另存目录。
- `out-network/environment.json` 与 `out-network/results.json` 中的 `network_mode_expected: "none"` 是 `run_all.py` 写死的元数据，**与联网对照容器的实际网络模式不符**（该次运行为默认 bridge、无 `--network none`）。联网可达性判定请以 `out-network/results.json` 的 `allowlisted_http_status: [401]` / `non_allowlisted_http_status: [200]` 与对应 transcript 为准，不要依据该元数据字段。
- 输出不含凭据：假 provider 请求记录已剥离 `Authorization`，占位 key 未写入任何输出文件。

## 构建环境说明

- `docker.io` 直连在当前网络下 IPv6 超时，首次构建失败；改用本地已有镜像 `docker.m.daocloud.io/library/python:3.12-slim`（`BASE_IMAGE` 可覆盖）。
- Debian apt 与 PyPI 使用清华镜像；Linux runtime wheel `deepseek_harness_runtime_bin-0.1.5rc1-py3-none-manylinux_2_28_x86_64.whl` 正常安装，`dsh` 在容器内可执行。
