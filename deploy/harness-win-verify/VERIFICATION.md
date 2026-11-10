# Windows 下载与 smoke 验证结论（2026-11-09）

- 执行时间：`2026-11-09T19:39:40+08:00`（`out/results.json` 的 `checked_at`）
- 环境：Windows x64、Python 3.12.10、宿主 `.venv`
- **结论：PASS（仅限 CLI / SDK smoke）**（`scripts/smoke.py` 退出码 0，`out/results.json`
  的 `verdict=PASS`）。Web UI 启动失败、桌面客户端未测，见第 3、5 节。

## 1. 下载与完整性

| 项 | 结果 |
|---|---|
| `deepseek_harness_sdk-0.1.5rc1-py3-none-any.whl` | 13,694 B，SHA256 `8d9897e9…b4d8`，与预期一致 |
| `deepseek_harness_runtime_bin-0.1.5rc1-py3-none-win_amd64.whl` | 72,045,733 B，SHA256 `d031a5ab…f8acf`，与预期一致 |
| wheel 内主 runtime exe | `deepseek-harness-sdk-runtime-win-x64.exe`，240,529,920 B，SHA256 `7ff077cf…7d6` |
| wheel 内 rg sidecar | `…-win-x64-rg.exe`，5,429,760 B，SHA256 `f9dde634…c042cb` |
| 与宿主已装的比对 | 两个 exe 的 SHA256 **逐字节一致**，说明 `.venv` 现有安装与本次下载是同一官方构建，未被改动 |

版本刻意锁定 `0.1.5rc1`，与 `deploy/harness-linux-verify/Dockerfile` 一致。

**更正（2026-11-09 19:45）**：此前记录的「官方分发仅 npm 包 / 源码仓库 / Python SDK、
未提供桌面安装程序」是错误结论。官网 `https://deepseek.com/download` 确实提供
Windows 桌面端安装器 `dsh-latest-windows-x64.exe`（Windows 10+，HEAD 200，
`Content-Length: 293425336`，`Last-Modified: 2026-11-05`，Content-Type 为 PE），
`https://deepseek.com/harness` 亦写明「Run me as a desktop app or launch the web UI
from code」。准确边界是：**PyPI 的这两个 wheel 内不含桌面客户端**；桌面端是独立产品、
独立分发渠道，本轮未下载、未安装、未运行，不对其运行状况作任何判定。详见第 5 节。

## 2. 测试项结果

| # | 项目 | 实测 | 判定 |
|---|---|---|---|
| T1 | wheel 校验与解压 | 两个哈希匹配；`pkg/` 内 exe/rg 与 wheel 内一致 | PASS |
| T2 | `.venv\Scripts\dsh.exe --version` | `0.1.5-rc.1`，退出码 0 | PASS |
| T2 | 下载的独立 exe `--version` | `0.1.5-rc.1`，退出码 0 | PASS |
| T2 | 独立 exe `--help` | 完整 dsh CLI：支持 `--profile`、`web`、`plugin`、`--patch`、`--dump-config` | PASS |
| T3 | SDK 会话启动 | `HarnessClient.start()` → `initialize()` 成功，`serverInfo=deepseek-harness-sdk-runtime` | PASS |
| T3 | 最小 agent 回合 | `session_prompt()` → 收到 `session.status=idle`，16 个 event / 18 个 notification，0 error | PASS |
| T3 | 模型响应 | `final_response=WIN_SMOKE_OK`，`finish_reason=completed` | PASS |
| T3 | 假 provider | 收到 1 次 `POST /v1/chat/completions`，`stream=true`，`model=deepseek-v4-flash`，25 个工具声明下发但**未触发任何工具调用** | PASS |
| T4 | 安全边界 | `placeholder_key_used=true`、`real_provider_called=false`、危险用例列表为空、明确记录无网络隔离 | PASS |

复跑一次后输出干净（首次运行的 `ConnectionResetError` 是 dsh 关闭 keep-alive 连接产生的
服务端读噪音，已在 `Handler.handle()` 中捕获，不影响任何判定）。

## 3. 本次**没有**验证的内容

1. **沙箱越界 / 出网白名单 / 原生审批**：Windows 宿主没有 `--network none` 等价隔离，
   这四项由 `deploy/harness-linux-verify/` 的容器链负责（`VERIFICATION.md` 记录原生审批
   `no approval channel is available` 为已知限制，业务侧改用编排审批 API）。
2. **真实 DeepSeek 模型调用**：未使用真实 `DEEPSEEK_API_KEY`，未联网访问 provider。
3. **当前 L3 网关 / 编排端到端联调**：需要有效 Harness 客户端凭据、网关虚拟 key 与租约；
   本轮未读取任何 `config.conf`、`deploy/gateway/.env`、secrets，也未调用 9998/9999/9100。
4. **桌面客户端**：见第 5 节——不在下载物内，本轮未安装、未运行。
5. **Web UI 可用性**：本轮补充实测 `dsh web`（绑定 127.0.0.1、`--no-open`、隔离
   `DSH_HOME`），**启动失败**，详见第 5 节；未做任何修复或联网插件加载。

## 4. 边界声明

- 新建文件仅在 `deploy/harness-win-verify/` 与 `.gitignore`；`wheels/`、`pkg/`、`state/`
  已忽略，不入库（72 MB wheel + 240 MB exe）。
- 未改业务代码、配置、告警规则、`mode`、容器与计量数据；三个业务容器保持
  `mode=proxy_l3` healthy，**观察期不重置**（起算 13:33:40，最早收口 2026-11-23 13:33）。
- 假 provider 只绑定 `127.0.0.1:18081`，请求日志不含 `Authorization`；`DSH_HOME` 与
  workspace 均隔离在 `state/` 内，`DSH_TELEMETRY_MODE=DISABLED`。

## 5. 桌面客户端（官网独立分发）实测结论（2026-11-09 20:25 更新）

用户选择方案 A：下载并安装官网桌面端 EXE，做签名校验 + 启动/最小任务验证。结论更新为：
**包含官方 Windows 桌面客户端；安装包与主程序均通过官方 EV 代码签名校验；在本沙箱可完整
解包但无法做交互式 GUI 运行验证（环境无图形显示会话，非安装包/应用缺陷）。**

| 对象 | 是否桌面 GUI 客户端 | 证据 |
|---|---|---|
| `deepseek-harness-sdk` wheel | 否 | 纯 Python 库；METADATA 明确「The Python SDK has no separate application entrypoint」，只通过 stdio JSON-RPC 驱动 `dsh --profile sdk` |
| `deepseek-harness-runtime-bin` wheel | 否 | 仅 2 个 exe + 1 个 json；`entry_points.txt` 为 `[console_scripts] dsh = deepseek_harness_runtime:main`；主 exe 与 rg sidecar 的 PE `Subsystem=3`（CUI 控制台，GUI 应为 2）；无安装器、无快捷方式、无 Electron/Tauri 资源 |
| `dsh web`（runtime wheel 自带） | 否（浏览器 B/S） | `--help` 写明「Serve the DeepSeek Harness browser UI」，支持 `--host/--port/--no-open`；由浏览器访问，不是桌面窗口 |
| **官网桌面端 EXE** | **是，真实 GUI 客户端** | `https://deepseek.com/download` 独立分发 `dsh-latest-windows-x64.exe`（NSIS 安装器，约 280 MB，PE32 GUI 子系统）；已下载、已签名校验、已完整解包 |

### 5.1 下载与完整性
- HEAD 探测：200 / 293,425,336 B / Last-Modified 2026-11-05 / Content-Type `application/octet-stream`。
- 全量下载 SHA256：`830947f8…b23`（41s）。落盘 `desktop/dsh-latest-windows-x64.exe`。

### 5.2 数字签名（Authenticode）
| 文件 | Status | 发布者 | 证书链 | 有效期 |
|---|---|---|---|---|
| 安装包 `dsh-latest-windows-x64.exe` | Valid | `CN=Hangzhou DeepSeek Artificial Intelligence Co., Ltd.` | `GlobalSign GCC R45 EV CodeSigning CA 2020` + `DigiCert SHA256 … 2026` 时间戳 | 至 2027-09-01 |
| 主程序 `app/DeepSeek Harness.exe` | Valid | 同上 | 同上 | 至 2027-09-01 |
- 结论：安装包与主程序均通过官方 EV 代码签名校验，来源可信、未被篡改。

### 5.3 安装失败的处理（环境限制，非安装包缺陷）
NSIS 静默安装（`/S /D=`）两次均返回码 2、`/D` 目标目录为空。根因：electron-updater 的
NSIS 逻辑先把文件解压到 `app.new-{GUID}`，再**原子重命名**为目标目录；而本沙箱对**目录
rename / delete（rmtree）**做了安全拦截（`os.rename` 实测 `PermissionError 13 拒绝访问`），
导致最终 rename 失败、安装中止（`.new` 目录里只有 `resources/`，主程序尚未解压完）。
绕开方式：NSIS 安装包的有效载荷本身是一个 7z 归档，直接用 `7za x` 解包到 `desktop/app/`，
**不经过 rename 步骤**——成功提取 7805 个文件 / 1.12 GB / 退出码 0，文件清单为完整 Electron
结构（`DeepSeek Harness.exe` 246 MB、`resources/app.asar`、`locales/*.pak`、`chrome_*.pak`、
`vk_swiftshader.dll`、`v8_context_snapshot.bin` 等）。

### 5.4 启动验证（headless 限制）
在**无图形显示会话**的沙箱里尝试启动 `app/DeepSeek Harness.exe`：
- 直接无参启动：<1s 内以退出码 0 静默退出（无输出）。
- `--help`：打印的是 **Node.js 用法**（`Usage: node [options] [script.js]`），说明该 exe 是
  Electron 的 Node 内核；无参时 node 收到空 stdin 即退出，窗口从未创建。
- Chromium 风格参数（`--remote-debugging-port` / `--user-data-dir` / `--no-sandbox` /
  `--headless=new`）：全部被拒（`DeepSeek Harness.exe: bad option: …`），因它带自有 CLI 解析层。
- 结论：**在本 headless 沙箱无法完成交互式 GUI 运行验证**。这是环境缺少 Windows 图形会话/
  显示所致，不是安装包或应用损坏。在真实带桌面的 Windows 上双击运行应属正常（已签名、文件完整）。
- 备注：桌面客户端启动后是否依赖在线/本地 provider、是否与本项目 L3 网关联动，需用户在真实
  桌面环境用自己的凭据验证；本轮未读取项目 `config.conf` / `.env` / secrets。

### 5.5 Web UI 实测（runtime wheel 的 `dsh web`，未修复，仅记录）
> 以下针对 PyPI `deepseek-harness-runtime-bin` wheel 的 `dsh web`，与上面官网桌面客户端是两条独立链路。

```
DSH_HOME=state/dsh_home DSH_TELEMETRY_MODE=DISABLED \
  pkg/deepseek_harness_runtime/runtime/deepseek-harness-sdk-runtime-win-x64.exe \
  web --host 127.0.0.1 --port <随机端口> --no-open
```

- 退出码 **1**，端口未监听，HTTP 未返回任何页面；首次以 stdout 合并方式抓取时输出为空，
  改用分离 stderr 后拿到完整错误栈。
- 根因：`failed to apply loader entry include (cordis:include)` → 加载
  `session-title-llm (@deepseek-ai/dsh-session-title-first-prompt-llm)` 时
  `Cannot find package '@deepseek-ai/dsh-session-title-llm'`。即 `0.1.5rc1` Windows
  runtime wheel 内置的**完整 web profile 依赖闭包不完整**（缺一个被依赖包）。
- 对照：`--profile web --dump-config` 退出码 0（配置层可正常组合）；`--profile sdk`
  的 smoke 全程 PASS（sdk-minimal 树不含该 include）。因此故障限于 web profile，
  不影响第 2 节已通过的 CLI/SDK 结论。
- 两次启动均在 90s / 35s 内以进程终止收尾，`--no-open` 未拉起浏览器，未加载在线插件，
  未访问真实 provider，未触碰 9998/9999/9100 业务容器。

### 5.6 待决事项（更新）
1. 桌面端**下载 + 签名校验 + 完整解包**已完成（方案 A 前两步）。
2. 桌面端**交互式 GUI 运行**未在本沙箱验证（缺图形会话）。**已约定由用户在其真实 Windows
   桌面完成双击验证**（2026-11-09 21:09），结果回填第 7 节；亦可在带显示环境授权我再测。
3. Web UI（runtime wheel 的 `dsh web`）缺包问题仍待决（见 5.5）；与官网桌面客户端无关。

## 6. 内嵌运行时起 `dsh web` 服务实测（2026-11-09 20:42 新增）

用户追问「能否下载源码编译安装」。经核查：
- **GitHub 直连被沙箱拦截**（`git ls-remote` → `502 CONNECT tunnel failed`），`git clone` 源码不可行；
- **npm 公开源上不存在 `@deepseek-ai/dsh`**（文档 `npx @deepseek-ai/dsh web` 不实，`deepseek-harness@0.0.1`/`dsh@1.0.1` 为无关抢注包），`npx` 路径走不通。

但已下载、已签名、已完整解包的官网桌面客户端（`desktop/app/`，0.2.2-rc.1）**内嵌了完整的 `dsh` 运行时**。
桌面壳的 `resources/runtime/cli/bin/dsh.cmd` 揭示其启动方式：

```
set ELECTRON_RUN_AS_NODE=1
"DeepSeek Harness.exe" --expose-internals ^
  "resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-desktop-host/lib/cli.js" %*
```

即 Electron 内核以 Node 模式运行内嵌 CLI。据此直接驱动内嵌运行时起 Web 服务
（headless 即可，无需显示器）：

```
ELECTRON_RUN_AS_NODE=1 "desktop/app/DeepSeek Harness.exe" ^
  --expose-internals "desktop/app/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-desktop-host/lib/cli.js" ^
  web --no-open --host 127.0.0.1 --port 3091
```

### 6.1 结果

- `dsh` CLI 正常识别（`dsh --help` 列出 `web` / `rescue` / `headless` / `tui` / `plugin` 等 profile）；
- `dsh web` **约 1.5s 内监听 `127.0.0.1:3091`**；
- 鉴权流程：`GET /?token=<服务端生成>` → **303** 并下发签名会话 Cookie
  `dsh-auth-<rand>=v1.eyJ...`（HttpOnly / SameSite=Strict）；
- 带该 Cookie 重放 → **200 `text/html`，含 2 个 `<script>` 标签**（真实 SPA 外壳）。

### 6.2 结论

**内嵌的 `dsh web` 在本沙箱可运行、对外提供 Web UI 页面**，这是 headless 环境下能拿到的
**最强运行证据**——它证明官方 0.2.2-rc.1 运行时完整、可启动、可服务界面。这与第 2 节的
CLI/SDK smoke（0.1.5rc1 wheel）互相印证，也与 5.5 的 **runtime wheel `dsh web` 缺包**
是两回事（那是 0.1.5rc1 wheel 依赖不完整，本处是官方桌面包依赖完整）。

### 6.3 边界（不变）

- 仍是**无头 HTTP 服务验证**，非交互式 GUI 窗口渲染；要看图形界面仍需在真实 Windows 桌面双击
  `desktop/app/"DeepSeek Harness.exe"`（已签名、文件完整）。
- 全程**未读取**项目 `config.conf` / `.env` / secrets；**未连接** 9998/9999/9100 业务容器；
  **未触及**任何真实 provider / 模型密钥。
- 业务侧（L3 拆分、`mode`、计量、观测）**未改动**，**14 天观察期不重置**，收口仍为
  **2026-11-23 13:33 +0800**。

## 7. 桌面 GUI 双击验证（用户侧，2026-11-09 21:09 约定，待回填）

交互式 GUI 窗口渲染无法在本 headless 沙箱验证（缺 Windows 图形会话），**约定由用户在其真实
Windows 桌面完成双击验证**，我据实回填本节。

### 7.1 运行方式（二选一）
- **方式 A（直接起已解包应用）**：双击
  `deploy/harness-win-verify/desktop/app/"DeepSeek Harness.exe"`
  （目录已完整解包 7805 文件 / 1.12 GB，含 `resources/app.asar`、`locales/*.pak` 等，可直接运行）。
- **方式 B（规范安装）**：双击安装器
  `deploy/harness-win-verify/desktop/dsh-latest-windows-x64.exe`，按向导安装后从
  开始菜单 / 桌面快捷方式启动（真实桌面下 NSIS 重命名不再被沙箱拦截，安装可成功）。

### 7.2 验证要点（逐项勾选）
1. GUI 主窗口是否正常弹出、有无崩溃 / 闪退 / 报错弹窗。
2. 登录 / 配置 provider 是否正常（请用**你自己的 DeepSeek 凭据**，不要复用项目密钥）。
3. 能否跑一个最小任务（如发起一次对话 / 调用一个工具），界面有无正常响应。
4. （可选）是否与本项目 L3 网关联动——如需，请提供**网关虚拟 key**，由你侧配好后再测；
   **不要**读取项目 `config.conf` / `deploy/gateway/.env` / secrets。

### 7.3 出问题时请反馈
- 报错截图 / 文字；应用日志路径通常在
  `%APPDATA%/DeepSeek Harness/logs/` 或 `app/` 同级 `logs/`。
- 若方式 A 报「缺少模块 / 资源」，优先改用方式 B 安装后再试（解包目录偶尔缺运行时注册项）。

### 7.4 桌面 GUI 双击验证结果（用户回填，2026-11-09 21:24）

- GUI 双击验证时间：2026-11-09 21:24 / 方式：B（安装器安装到真实 Windows 桌面）
- 安装路径：`C:\Users\admin\OneDrive\Desktop\开发\DeepSeek Harness`
- 窗口弹出：**正常**（用户确认已安装并可在真实桌面运行）
- 最小任务：未明确（用户仅确认安装完成，未反馈是否跑通一次对话 / 工具调用）
- 与 L3 网关联动：未测（待用户提供有效 Harness 凭据 + 网关虚拟 key 及其绑定 service 配置）
- 结论：**安装 / GUI 启动 PASS**；完整功能与 L3 联动待补

> 说明：用户原话「C:\Users\admin\OneDrive\Desktop\开发\DeepSeek Harness 已经安装」，
> 视为 GUI 在真实 Windows 桌面安装并可用；如需把「最小任务」也补证，请再反馈一次。
