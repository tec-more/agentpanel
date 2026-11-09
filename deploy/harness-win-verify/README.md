# DeepSeek Harness Windows 下载与验证

在 Windows 宿主侧验证**官方 PyPI 发行的 Windows x64 runtime** 能下载、能启动、能完成一次
最小 agent 会话。与 `deploy/harness-linux-verify/` 互补：那一套用于验证 Windows 上无法验证的
沙箱/网络隔离行为，本目录只做下载与 smoke，不重复也不宣称等价。

## 分发来源与选型

- 包：`deepseek-harness-sdk==0.1.5rc1` + `deepseek-harness-runtime-bin==0.1.5rc1`
  （平台 wheel `py3-none-win_amd64`），与 Linux 验证链 Dockerfile 锁定的版本一致。
- 索引：清华 TUNA PyPI 镜像 `https://pypi.tuna.tsinghua.edu.cn/simple`，与 Linux 验证链一致。
- runtime wheel 内含单文件可执行 `deepseek-harness-sdk-runtime-win-x64.exe`（约 240 MB）
  与 ripgrep sidecar `...-rg.exe`，无需系统 Node.js。
- **本目录不包含 Windows 桌面客户端**。官方另有独立的桌面端安装器，由官网
  `https://deepseek.com/download` 提供（`dsh-latest-windows-x64.exe`，Windows 10+，
  2026-11-05 版响应头 `Content-Length: 293425336`），属于官网分发渠道，与 PyPI 的
  这两个 wheel 无关。本轮**未下载、未安装、未运行**桌面客户端，因此不对其运行状况作
  任何结论。
- 更正：此前记录的「官方分发只有 npm 包、源码仓库与 Python SDK，未提供桌面安装程序」
  是错误结论。准确边界是「PyPI 的 SDK/runtime wheel 内不含桌面安装程序」；桌面端确实
  存在，只是不在本次下载范围内。本目录仍只使用可校验哈希的 PyPI 官方 wheel。

下载命令（PowerShell，项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m pip download --no-deps --only-binary=:all: `
  --platform win_amd64 --implementation py3 --abi none `
  -i https://pypi.tuna.tsinghua.edu.cn/simple `
  -d deploy\harness-win-verify\wheels `
  "deepseek-harness-sdk==0.1.5rc1" "deepseek-harness-runtime-bin==0.1.5rc1"
```

| 文件 | 大小 | SHA256 |
|---|---|---|
| `deepseek_harness_sdk-0.1.5rc1-py3-none-any.whl` | 14 KB | `8d9897e97e8a95fd738cb2c3e2c563951d824e43847ec6f3b0fb172c0729b4d8` |
| `deepseek_harness_runtime_bin-0.1.5rc1-py3-none-win_amd64.whl` | 72 MB | `d031a5ab4919c572fd7e48c7ef19ec8b1896e93d93c44b0937bb958c528f8acf` |

`wheels/`、`pkg/`（解压产物）、`state/`（DSH_HOME 与 workspace）体积大且可再生，
已在 `.gitignore` 中排除；`scripts/`、`README.md`、`VERIFICATION.md`、`out/` 入库。

## 运行

```powershell
.\.venv\Scripts\python.exe deploy\harness-win-verify\scripts\smoke.py
```

`smoke.py` 会校验两个 wheel 的 SHA256，解压到 `pkg/`，然后用**下载的 exe**
（而不是 `.venv` 里已装的那份）作为 `dsh_bin` 驱动 SDK。

## 测试项与判定

| # | 项目 | 判定 |
|---|---|---|
| T1 | 下载完整性 | 两个 wheel 的 SHA256 与预期一致；解压出的 exe/rg 与 wheel 内哈希一致 |
| T2 | CLI 可启动 | `.venv\Scripts\dsh.exe --version` 与下载的独立 exe `--version` 均能启动并退出 0（需显式 `DSH_HOME`） |
| T3 | 最小 agent 会话 | `HarnessClient.start()` → `initialize()` → `session_prompt()` → 收到 `session.status=idle`；假 provider 至少收到 1 次请求；最终文本含 `WIN_SMOKE_OK` |
| T4 | 边界留痕 | 占位 key、未调用真实 provider、无危险用例、明确记录 Windows 无网络隔离 |

结果写入 `out/results.json` 与 `out/fake_provider_requests.jsonl`（请求记录不含
`Authorization`）。本次实际结论见 `VERIFICATION.md`。

## 安全边界（重要）

- 假 provider 只监听 `127.0.0.1:18081`，返回固定文本、不触发任何工具调用。
- `DEEPSEEK_API_KEY` 用占位值 `sk-agentpanel-verify-placeholder`；**不读取**项目的
  `config.conf`、`deploy/l3/.env`、secrets，也不使用真实模型凭据。
- `DSH_HOME` 与 workspace 都限制在 `state/` 内，`DSH_TELEMETRY_MODE=DISABLED`。
- **Windows 宿主没有 `--network none` 等价隔离**，因此这里不跑出网对照，也不跑
  `bash_escape` / `fs_escape` / `web_fetch` / 原生审批用例；那四项由 Linux 容器验证链负责。
- 本目录不接触 9998/9999/9100 三个业务容器，不改动 `mode`、代码、配置或计量数据。
