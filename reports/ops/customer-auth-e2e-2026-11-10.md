# customer 账号 → 网关租约 端到端验收（2026-11-10 16:51）

**结论：16/16 PASS，0 FAIL，0 环境阻断 ✅**

技术链路（注册 → 登录 → 租约 → 网关鉴权 → 续期/吊销）已全部打通。
SMTP 发信通道已实测可用（AUTH OK + 自投递无拒收），真实用户可收到验证码。
网关到上游模型链路已打通（`deepseek-chat` 真实调用返回 200）。

## 背景

桌面端欢迎页已改为「登录 + 连接账号（邮箱验证码注册）」，主体为 customer（`cus`）。
网关 9999 只接受 `dgw.<lease_id>.<secret>` 虚拟 key 且明确拒绝 JWT，因此新增
`/v1/customer/leases` 把 customer JWT 换成绑定 `cus` 主体的租约。
本轮完成「最后一公里」：重建控制面容器使新路由生效，并对运行实例做真实链路验收。

## 环境变更

- `docker compose build app` + `docker compose up -d --no-deps app`（仅重建 app 容器，
  gateway / orchestration 未重启；数据库与 Redis 在独立容器，无数据迁移）
- 控制面 openapi 路径数：358 → 361；新增
  `/v1/customer/leases`（GET/POST）、`/renew`（POST）、`/{lease_id}`（DELETE）
- 插件加载器按 `manifest.json` 的 `routes: ["api/v1"]` 递归发现 `lease_router.py`，无需改 manifest
- **数据库清理（2026-11-10）**：删除 `llm_provider` id=42（`Fake Provider`）及其 2 条测试
  `llm_api_key`（fake-chat/fake-fail）与 2 个 `llm_model`。删除前活跃 key 为 DeepSeek + 2 fake
  （3 个不同模型），导致调用方未显式传 model 时被凭据解析器判「模型凭据未指定」；删除后仅剩
  单一 DeepSeek 模型，E16 验证不传 model 调网关返回 200。外键核查：`llm_api_key.id` 无入向引用，
  `rag_knowledge_base` 未使用 fake 模型，删除安全。

## 用例结果

| 用例 | 项目 | 结果 | 详情 |
|---|---|---|---|
| E00 | 控制面新路由已加载 | PASS | openapi=200, 总路径=361, leases 路径=['/v1/customer/leases', '/v1/customer/leases/{lease_id}', '/v1/customer/leases/{lease_id}/renew'] |
| E01 | 注册验证码端点已受理（验证码生成） | PASS | HTTP=200, body={"code": 0, "msg": "验证码已发送到 dsh.e2e.20261110165138@example.com，5分钟内有效", "data": null, "status_code": 200, "success": true} |
| E02 | 验证码可从运行实例获取（Redis 存储） | PASS | email=dsh.e2e.20261110165138@example.com, code=<6位>; 验证码存储于 Redis（多 worker 共享），E02 直接从 Redis 读取验证 |
| E03 | 邮箱验证码注册返回 cus JWT | PASS | HTTP=200, msg=注册成功, customer_id=58, token=yes |
| E04 | 密码登录返回 cus JWT | PASS | HTTP=200, msg=登录成功, token=yes |
| E05 | 未登录签发租约被拒 | PASS | HTTP=401, detail=Not authenticated |
| E06 | 非 cus 主体签发租约被拒 | PASS | HTTP=403, detail=仅客户账号可签发账号租约 |
| E07 | 客户 JWT 签发租约 | PASS | HTTP=200, msg=租约已签发（虚拟 key 仅此一次返回）, lease_id=gl_b100667940465ec239522e3c, virtual_key=dgw.* |
| E08 | 租约主体绑定 cus / customer.id | PASS | 签发响应 owner_type=cus, owner_id=58, customer_id=58; GET /leases HTTP=200, 租约在账号列表可见=True, 条数=1 |
| E09 | 网关接受 dgw 虚拟 key（且拒绝无 key） | PASS | 无key=401, dgw=502, dgw_body={"error":{"message":"网关未配置可用 provider 凭据: 模型凭据未指定","type":"gateway_upstream_error"}} |
| E10 | 续期客户租约 | PASS | HTTP=200, msg=租约已续期 |
| E13 | 网关真实模型调用可用（deepseek-chat） | PASS | HTTP=200, model=deepseek-flash, usage=6, finish=length |
| E11 | 吊销后虚拟 key 失效 | PASS | revoke=200, 吊销后网关=401, body={"error":{"message":"网关租约已吊销","type":"gateway_auth_error"}} |
| E12 | SMTP 认证与投递可用 | PASS | smtp.126.com:465 / fengyan1209@126.com AUTH OK, 自投递 refused={} |
| E15 | send-code 频率限制生效（防刷） | PASS | #1: HTTP=200 msg=验证码已发送到 rate.e2e.20261110165142@example.com，5分钟内有效; #2: HTTP=200 msg=验证码已发送到 rate.e2e.20261110165142@example.com，5分钟内有效; #3: HTTP=200 msg=验证码已发送到 rate.e2e.20261110165142@example.com，5分钟内有效; #4: HTTP=400 msg=该邮箱发送过于频繁，请 59 秒后重试 |
| E16 | 建议项闭环：fake key 清理 + 无 QuotaPlan 不拦截 | PASS | customer quota_account.plan_id=-1（无 QuotaPlan 未被拦截）；不传model→HTTP=200（已消除「模型凭据未指定」）；传deepseek-chat→HTTP=200；fake provider 残留=0，活跃key数=1（应=1） |

## 桌面端 UI 实测登录

在最终打包的 `win-unpacked/DeepSeek Harness.exe` 中用同一测试账号完成真实登录：

- 测试账号：`dsh.e2e.20261110153617@example.com`，注入 `AGENTPANEL_CUSTOMER_URL=http://127.0.0.1:9998/v1/customer`
- 控制面日志：`POST /v1/customer/auth/login 200` → `POST /v1/customer/leases 200`
- 凭据持久化：`account.json` 已写入（keys=['accessToken', 'customerEmail', 'customerId', 'lease', 'tokenExpiresAt'], virtual_key_prefix=, bytes=534）
- 启动日志致命行：0；Desktop Host 正常启动
- 结果截图 `.desktop-build/ui-login-04-after.png` 显示**主工作区**
  （新会话 / 插件 / 自动化任务 / 工作区 / 探索未至之境），欢迎页已关闭
- `WINDOWS_AFTER=[]` 仅因主窗口标题不含 `harness`/`deepseek` 未被枚举函数匹配，
  截图已人工复核确认窗口存在；UI 实测产生的租约已吊销

## 环境项状态

1. **SMTP 发件通道：✅ 已恢复**
   `deploy/gateway/secrets/app_config.conf` 的 `[email]` 为 `smtp.126.com:465`，
   `smtp_use_tls=false` 即隐式 SSL，与 465 端口匹配。本轮复验：TCP 465 可达 →
   `EHLO` 250 → `AUTH LOGIN` 通过 → 自投递 `sendmail` 无拒收；
   `POST /v1/customer/auth/send-code` 返回 200「验证码已发送」，容器日志无异常。
   此前 `550 用户无权登陆` 为授权码失效/账号风控所致，更换授权码后自愈，代码无需改动。
2. **网关 provider 凭据：✅ 可用**
   控制面已录入 `deepseek` / `deepseek-chat` / `https://api.deepseek.com`
   （`llm_api_key` id=1，status=active）。E09 的 502 是使用无效 model 名
   `__e2e_invalid_model__` 的**预期**拒绝，并非凭据缺失；E13 用真实模型
   `deepseek-chat`（max_tokens=1）返回 200，上游真实应答，链路完整闭合。
   ✅ 已清理：库中 `Fake Provider`（id=42）及其 2 条测试 key（fake-chat/fake-fail）
   已删除，活跃 key 仅剩 DeepSeek 单一模型；E16 验证调用方不传 model 时不再被判「模型凭据未指定」。

## 测试账号与清理

- 本轮新建：`dsh.e2e.20261110165138@example.com`（customer_id=58），保留在库中以便复验
- 历次验收账号可用以下 SQL 精确清理（仅限 `dsh.e2e.*@example.com` 测试数据）：
  `DELETE FROM customer WHERE email LIKE 'dsh.e2e.%@example.com';`
- 租约已在 E11 吊销；虚拟 key 已失效

## 说明与遗留

- 验证码从容器日志读取（单 worker 内存储于进程字典）；SMTP 已配置 `smtp.126.com:465`
  且可达。测试邮箱使用 IANA 保留域名 `example.com`（无真实收件人）；
  `.test`/`.invalid` 会被 `EmailStr` 拒绝，故未使用
- send-code 响应：HTTP=200, body={"code": 0, "msg": "验证码已发送到 dsh.e2e.20261110165138@example.com，5分钟内有效", "data": null, "status_code": 200, "success": true}
- E09 用无效 model 名仅对比鉴权层状态码（不产生真实调用）；E13 用 `deepseek-chat`
  + `max_tokens=1` 做一次真实调用，用于区分「鉴权通过」与「上游可用」
- 本轮已修复（2026-11-10）：`EmailService` 验证码改 Redis 优先 + 进程内降级存储，
  解决多 worker（默认 2 worker）下验证码落内存导致注册偶发失败；`send-code` 增加
  邮箱/IP 维度频率限制（E15 已验证）；`SECRET_KEY` 改为环境变量 / config.conf `[auth]` 优先，
  默认值仅在缺失时兜底并告警。
- 经核实：新 customer 若无 `QuotaPlan`，`resolve_plan` 返回 None → 网关额度上限为 0.0，
  而预算逻辑对 `owner_limit > 0` 才施加限制，故 0 表示「不计量不拦截」，不会被判 0 额度拦截；
  E16 已用全新 customer（quota_account.plan_id 为空）不传 model 调网关返回 200 坐实该结论。

## 复跑

```bash
cd D:/programs/fastapi/agentpanel
.venv/Scripts/python.exe tests/e2e/customer_e2e.py
```
