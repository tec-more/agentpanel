# 业务逻辑回归测试报告（agentpanel / harness 客户端 / 网关 / 编排）

- 测试时间：2026-11-11 10:16 – 10:21（Asia/Shanghai）
- 测试对象：控制面 agentpanel（9998）、模型透传网关（9999）、编排服务（9100）、harness 桌面客户端（0.2.2-rc.1）
- 测试类型：业务逻辑回归（只读巡检 + 写路径/配额路径 + 网关数据面全量 + 客户端单测与真实 GUI 登录）
- 结论：**全部套件 PASS，未发现产品业务逻辑缺陷；发现并修复 1 处测试脚本缺陷（窗口定位误命中浏览器）**

## 1. 结果总览

| 组件 | 套件 | 结果 | 用时 |
|---|---|---|---|
| 运行环境 | `deploy/gateway/scripts/observe_check.py`（只读巡检） | 12 PASS / 0 FAIL / 2 WARN | — |
| agentpanel 控制面 + 网关真实链路 | `tests/e2e/customer_e2e.py` | 16 PASS / 0 FAIL / 0 BLOCKED | ~90s |
| 网关数据面 | `services/gateway/tests/verify_gateway.py`（V3–V11） | 66 PASS / 0 FAIL | ~40s |
| 编排写主链路 | `services/orchestration/tests/verify_write_path.py` | 39 PASS / 0 FAIL | 3.3s |
| 编排配额链路 | `services/orchestration/tests/verify_quota_path.py` | 28 PASS / 0 FAIL | 2.3s |
| harness 客户端（单测） | `agentpanel-account-backend.spec.ts` + `account-backend.spec.ts` | 11 PASS / 0 FAIL | 1.2s |
| harness 客户端（登录/欢迎页单测） | `welcome-*.spec.ts(x)`（4 文件） | 55 PASS / 0 FAIL | 9.5s |
| harness 客户端（打包版真实 GUI 登录） | `tests/e2e/customer_ui_login.py` | PASS（账号落盘 + 进入工作区） | ~45s |

合计自动化断言：**215 项通过 / 0 失败**（另有 GUI 登录 1 条端到端流程）。

## 2. 环境与版本

| 项 | 值 |
|---|---|
| 容器 | `agentpanel-app` / `agentpanel-gateway` / `agentpanel-orchestration` 均 healthy（Up 2h） |
| 端口 | 9998 控制面、9999 网关、9100 编排（仅 127.0.0.1 绑定） |
| 依赖 | openGauss 15432、agentredis 6379 正常 |
| 编排模式 | `mode=proxy`，`write_enabled=True` |
| 桌面产物 | `deepseek-harness-0.2.2-rc.1-win-x64-unsigned.exe` 303.4 MB，`app.asar` 215.9 MB，FileVersion 0.2.2-rc.1 |
| Node / 测试运行器 | Node v24.20.0，vitest v4.1.11（`dshw/node_modules/.bin`） |

## 3. 各组件覆盖点与关键实证

### 3.1 agentpanel 控制面（customer 认证 / 租约）

- E00：openapi 314 条路径，`/v1/customer/leases` 三个路由已加载
- E01–E04：邮箱验证码受理 → 验证码从 **Redis** 直读 → 注册返回 `cus` JWT → 密码登录返回 JWT
- E05–E06：未登录 401、`usr` 主体 403（主体隔离生效）
- E07–E10：JWT 签发 `dgw.*` 租约、`owner_type=cus` 绑定 customer.id、列表可见、续期 200
- E11：吊销后网关立即 401「网关租约已吊销」
- E12：SMTP `smtp.126.com:465` AUTH OK、自投递无拒收
- E15：同一邮箱第 4 次 `send-code` 触发「发送过于频繁」（限流生效）
- E16：无 QuotaPlan 的新 customer 不被 0 额度拦截；不传 model 调网关 200；fake provider 残留 0、活跃 key=1

### 3.2 网关数据面（独立实例 9990 + 本地假 provider，不影响 9999 运行实例）

- V3 鉴权 11 项：缺凭据 / JWT / 非 dgw 格式 / secret 错误 / 已吊销 / 已过期 → 401；会话关闭、运行终态 → 403；鉴权失败 0 次触达上游；RPM=1 首次放行、第二次 429
- V4 出网白名单：非白名单域名 403、`allow_loopback=false` 拒绝 127.0.0.1，均不触达上游
- V5 请求剥离：`dsh_session_log` 不进入上游请求体，其余字段原样转发
- V6 流式：SSE 361B 逐字节一致；自动补 `include_usage`；usage_record 2 行，`source=gateway`、`gateway_key=lease_id`、幂等键每次唯一、用量口径 12/8/20
- V7 失败记账：资源类型 `gateway_error`、amount=0、每请求恰好 1 行
- V8 预算/并发/截断：402 `lease_budget_exhausted` + 自动吊销；并发上限 429 `concurrency_limit`；流式越界截断 partial 并显式标记
- V9 Redis 短路缓存：TTL 8s，吊销写穿删除
- V10 DB 兜底（Redis 关闭实例）：预检/结算/记账正常，账户用量 +20、并发计数归零
- V11 审计：auth_rejected / quota_rejected / lease_revoked / stream_truncated 事件齐全，不落虚拟 key 明文
- 真实上游（9999 运行实例）：`deepseek-chat`、`max_tokens=1` 调用 200，usage=6 tokens，链路完整

### 3.3 编排服务

写主链路（39 项）：
- 负向鉴权：无凭据 / 缺 secret / secret 错误均 401
- 直连 9100：会话 → 运行 → 启动 → 步骤 → 事件（坏行容忍）→ 心跳 → 审批（tier=ask）→ 结束 → 查询 → 关闭
- 经 app 9998 代理：同一路径全链路通过，证明 `ORCH_APP_BASE_URL` 生效
- 取消路径释放预占；终态运行再审批 409 状态机护栏
- DB 一致性：会话 2 行均 closed、运行 3 行（2 succeeded / 1 cancelled）、步骤 2 行、审计 18 行、审批 1 行；清理后 0 残留

配额链路（28 项）：
- 预占 1500 → `quota_reservation` 落行、Redis `quota_held` +1500、hold_id 形如 `orch:hr_*`
- 结算：用量流水 amount=150 / 幂等键 `orch:*` / source=client；预占行 partial→released；Redis used=150、held 归零
- 取消释放：预占行 released、不产生用量流水
- 超限：429 `quota_exceeded`（remaining=9850），不落 run、不落预占
- 清理后 DB/Redis 均 0 残留

### 3.4 harness 客户端

- 账号后端单测（11）：邮箱验证码注册/登录、JWT→cus 租约交换、`account.json` 0o600 持久化、续期与吊销、网关拒绝时过期处理
- 欢迎页/窗口单测（55）：登录/注册页面渲染、8 语言文案、IPC 参数校验、启动焦点不串页
- 打包版真实 GUI 登录（PASS）：
  - 窗口 `DeepSeek Harness` → 点击「登录」→ 填邮箱/密码 → 提交
  - 主窗口标题切换为 `DSH 本地构建`（进入工作区）
  - `account-store/account.json` 落盘 534B：`accessToken`(196 字符)、`customerEmail=dsh.e2e.20261111101706@example.com`、`customerId=60`、`lease{leaseId,expiresAt,ttlSeconds,virtualKey}`，虚拟 key 前缀 `dgw.`
  - 启动日志 2 行、0 条 fatal；测试后用该账号调 API 吊销租约（200「租约已吊销」）

## 4. 发现的问题与处置

| 编号 | 类型 | 现象 | 处置 |
|---|---|---|---|
| T1 | 测试脚本缺陷（已修复） | `customer_ui_login.py` 按窗口标题含 `deepseek/harness` 匹配，首轮误命中用户 Chrome（标题「DeepSeek 开放平台 - Google Chrome」），点击全部落到浏览器，登录未发生（`account.json` 未生成） | 改为按进程可执行文件名 `DeepSeek Harness.exe` 精确匹配 PID 再枚举窗口；复跑后正确命中应用窗口并登录成功 |
| E2 | 环境 WARN（既有） | Prometheus 9090 不可达，巡检「Prometheus 抓取」WARN | 监控辅助组件未运行，属已知预期；不影响业务链路 |
| E3 | 环境 WARN（预期） | 「used 基线对比」新增 `quota:cus:52..60` 计量键 | 均为历次 customer E2E 真实调用产生（含本轮 cus:60 = 18 tokens）；已登记来源，非异常写入 |
| — | 预期行为（非缺陷） | E09 用无效 model 名调用网关返回 502「模型凭据未指定」 | 用于区分「鉴权通过」与「上游可用」，鉴权判定以状态码为准；E13 真实模型调用 200 |

## 5. 测试后状态复核

- `observe_check.py` 复跑：12 PASS / 0 FAIL / 2 WARN（与测试前一致）
- `held` 全 0、`quota_holds_index` 为空（无悬挂预占）
- 编排写路径 / 配额路径套件自带清理，DB 与 Redis 残留均为 0
- 客户端 UI 测试租约已吊销

## 6. 未覆盖项与风险提示

1. 本轮未重跑 `tests/e2e/desktop_e2e.py`（打包产物完整性/入口冒烟 20 项），以免覆盖其硬编码的 `desktop-autotest-2026-11-10.md` 报告；产物存在性与版本已单独核验。
2. 网关套件使用**临时 9990 实例 + 本地假 provider**，与 9999 运行实例配置不同（白名单/回环/并发=1）；9999 的真实上游仅覆盖 `deepseek-chat` 单模型。
3. `send-code` 验证码仍依赖 Redis（不可用时降级进程内字典），多 worker 场景需保持 Redis 可用。
4. `used` 计量键随 E2E 增长属预期，长期观察期需继续按既有台账登记来源。

## 7. 复跑命令

```bash
# 只读巡检
.venv/Scripts/python.exe deploy/gateway/scripts/observe_check.py --json

# 控制面 + 网关真实链路
.venv/Scripts/python.exe tests/e2e/customer_e2e.py

# 编排（容器内执行，PowerShell 用管道喂 stdin）
Get-Content -Raw -Encoding UTF8 services/orchestration/tests/verify_write_path.py | docker exec -i agentpanel-orchestration python -
Get-Content -Raw -Encoding UTF8 services/orchestration/tests/verify_quota_path.py | docker exec -i agentpanel-orchestration python -

# 网关数据面（需先起 9990 临时实例，允许本地假 provider，并设 GW_MAX_CONCURRENT_REQUESTS_PER_OWNER=1）
.venv/Scripts/python.exe services/gateway/tests/verify_gateway.py

# 客户端单测
cd dshw && ./node_modules/.bin/vitest.CMD run apps/desktop/tests/agentpanel-account-backend.spec.ts apps/desktop/tests/account-backend.spec.ts
cd dshw && ./node_modules/.bin/vitest.CMD run apps/desktop/tests/welcome-renderer.client.spec.tsx apps/desktop/tests/welcome-window.spec.ts apps/desktop/tests/welcome-startup.spec.ts apps/desktop/tests/welcome-host.spec.ts

# 客户端打包版真实 GUI 登录（会短暂打开窗口，结束时自动关闭；加 --keep-open 可人工观察）
.venv/Scripts/python.exe tests/e2e/customer_ui_login.py
```

## 8. 变更记录

| 时间 | 变更 | 范围 | 回滚 |
|---|---|---|---|
| 2026-11-11 10:19 | 修复 `tests/e2e/customer_ui_login.py` 窗口定位：由标题模糊匹配改为按 `DeepSeek Harness.exe` 进程 PID 精确匹配 | 仅测试脚本，未触碰产品代码 | 还原该文件即可 |
| 2026-11-11 10:19 | 吊销 GUI 登录测试产生的租约 `gl_05c1...`（通过 `/v1/customer/leases/{id}`） | 运行态数据 | 重新登录签发即可，无需回滚 |

> 测试账号 `dsh.e2e.20261111101706@example.com`（customer_id=60）保留在库中，可按既有 SQL
> `DELETE FROM customer WHERE email LIKE 'dsh.e2e.%@example.com';` 清理。敏感凭据（JWT、虚拟 key、SMTP 授权码）在本报告中均未落明文。
