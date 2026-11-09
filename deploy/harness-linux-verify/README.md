# Harness Linux 容器验证

临时验证环境，用于补齐 Windows 上无法验证的四项行为。**不修改业务代码、不改动开发服务、不占用 9998/9999。**

- 基础镜像：`python:3.12-slim`（Linux x64）
- 锁定版本：`deepseek-harness-sdk==0.1.5rc1`
- 镜像 / 容器：`agentpanel-dsh-verify:0.1.5rc1` / `agentpanel-dsh-verify`
- 端口：假 provider 仅监听容器内 `127.0.0.1:18080`（高位非默认），不向宿主机暴露
- 真实 provider：**不调用**。`DEEPSEEK_BASE_URL` 指向本机假 provider，key 使用占位值 `sk-agentpanel-verify-placeholder`
- 网络：容器以 `--network none` 运行，切断外部出网；`--add-host api.deepseek.com:127.0.0.1` 把白名单域名指向假 provider

## 构建与运行

```powershell
# 在项目根目录执行
powershell -ExecutionPolicy Bypass -File deploy\harness-linux-verify\run.ps1
```

等价的 Docker 命令：

```powershell
docker build -t agentpanel-dsh-verify:0.1.5rc1 -f deploy\harness-linux-verify\Dockerfile deploy\harness-linux-verify

docker run --rm --name agentpanel-dsh-verify `
  --network none `
  --security-opt seccomp=unconfined `
  --add-host api.deepseek.com:127.0.0.1 `
  -v "${PWD}\deploy\harness-linux-verify\out:/out" `
  -v "${PWD}\services\gateway\common\service.py:/opt/project_gateway_service.py:ro" `
  -v "${PWD}\packages\agentpanel_common\upstream\egress.py:/opt/project_gateway_egress.py:ro" `
  agentpanel-dsh-verify:0.1.5rc1
```

说明：
- `seccomp=unconfined` 用于放开 `unshare`，让 bubblewrap/landlock 沙箱能启动；若宿主机内核禁用非特权 user namespace，沙箱可能退化，结果文件会记录具体错误。
- 只读挂载 `services/gateway/common/service.py` 与 `packages/agentpanel_common/upstream/egress.py` 仅为调用真实的 `assert_egress_allowed`，不给容器写权限。
- 输出写到 `deploy/harness-linux-verify/out/`；若 Windows 挂载权限异常，可去掉 `-v`，运行后 `docker cp agentpanel-dsh-verify:/out ./out`（需先去掉 `--rm`）。

## 验证项

| 场景 | 触发方式 | 判定 |
|---|---|---|
| `hook_deny` | Claude Code 兼容 `PreToolUse` 钩子经 dsh 桥接到 `tools/pre-execute`，拒绝危险 bash 命令 | 钩子子进程被调用、出现 deny 决策、目标文件不存在 |
| `bash_escape` | 假 provider 让模型调用 bash 写 `/tmp` | `/tmp` 标记文件不存在，工具结果含阻断错误 |
| `fs_escape` | 假 provider 让模型调用写文件工具写 `/tmp` 与 `../` | 两个标记文件都不存在 |
| `approval_allow` | 假 provider 让模型调用需要审批的 bash，客户端收到 `session/request_permission` 后选择 allow | 收到审批请求、出现 `approval/asked`、放行后命令实际执行 |
| `egress_ok` | 假 provider 让模型抓取 `http://api.deepseek.com:18080/egress-ok` | 假 provider 收到请求（白名单域名可达） |
| `egress_deny` | 假 provider 让模型抓取 `http://example.com/...` | 请求失败（容器网络层不可达） |
| `gateway_allowlist` | 只读加载业务侧 `assert_egress_allowed` | 白名单放行、非白名单/非法协议/默认 loopback 拒绝 |

## 输出

```text
out/
  environment.json                 容器/内核/bwrap 信息
  results.json                     四项结论 + 原始证据
  transcript_<scenario>.json       每个场景的完整事件与 incoming request
  fake_provider_requests.jsonl     假 provider 收到的请求（不含 Authorization）
  exception.json                   仅初始化/驱动异常时出现
```

钩子子进程日志写在容器 workspace `/work/ws/.agentpanel_hook_calls.jsonl`（沙箱内 `/out` 不可写），
汇总后的调用次数已写入 `results.json`。

联网对照（仅验证 dsh `web_fetch` 是否自带域名白名单）：

```powershell
docker run --rm --name agentpanel-dsh-egress `
  --security-opt seccomp=unconfined `
  -e VERIFY_SCENARIOS=egress_public_ok,egress_public_deny `
  -v "${PWD}\deploy\harness-linux-verify\out-network:/out" `
  agentpanel-dsh-verify:0.1.5rc1
```

`VERIFICATION.md` 为本次实际运行结论与证据摘要。

构建说明：当前网络直连 `docker.io` 会 IPv6 超时，`FROM` 默认使用本地已有的
`docker.m.daocloud.io/library/python:3.12-slim`；如需官方镜像可加
`--build-arg BASE_IMAGE=python:3.12-slim`。

## 清理

```powershell
docker rm -f agentpanel-dsh-verify 2>$null
docker rmi agentpanel-dsh-verify:0.1.5rc1
```
