# L3 模型数据面独立进程（standalone）规格

## 1. 目标

把网关数据面从「业务 API 的子应用」恢复为可独立启动、独立部署的 L3 进程：

- 独立入口 `base/common/gateway/server.py`，启动命令 `python -m base.common.gateway.server`；
- 复用已有 `base/common/gateway/app.py` 的 `create_gateway_app()`，不重写数据面逻辑；
- `deployment` 支持 `standalone` / `embedded`，默认改为 `standalone`；切换只改配置；
- 保持 fail-closed 启动校验；
- L2（业务 API）只负责租约签发/续期/吊销；L3 只做租约校验、上游转发、记账；
- L2 停止后，L3 仍可用已有租约完成请求并记账。

## 2. 端口与进程

| 角色 | 默认端口 | 入口 | 说明 |
| --- | --- | --- | --- |
| L2 业务 API | 9998 | `python run.py` / `uvicorn base.app_wrapper:app` | 租约控制面 `/v1/harness/gateway/leases` |
| L3 模型数据面 | 9999 | `python -m base.common.gateway.server` | `/chat/completions`、`/health`、`/docs` |
| 内部预留 | 9100 | — | 预留内部端口，不占用 |

- L3 默认监听 `127.0.0.1:9999`，host/port 由 `gateway.host` / `gateway.port` 配置；
- L2 与 L3 共享同一 PostgreSQL 与 Redis（DB 配置 `config.conf` 的 `db.*`，Redis `redis.*`）；
- L3 不执行迁移、不生成表结构，只 `Tortoise.init` 只读/读写共享库。

## 3. 部署形态切换

配置项 `gateway.deployment`：

- `standalone`（默认）：业务 API 不挂载 `/v1/gateway`；L3 独立进程对外提供数据面；
- `embedded`：业务 API 挂载子应用到 `/v1/gateway`（`/v1/gateway/chat/completions`、`/v1/gateway/docs`），
  用于临时退回；不再启动 L3 进程。

客户端 `base_url` 写法：

- standalone：`http://<host>:9999`（请求 `POST /chat/completions`）；
- embedded：`http://<host>:9998/v1/gateway`（请求 `POST /v1/gateway/chat/completions`）。

租约签发响应中的 `base_url` 来自 `gateway.public_base_url`，两种形态需按上表配置。

## 4. 启动顺序

1. PostgreSQL / Redis 就绪；
2. L2 启动（执行迁移、提供租约控制面）；
3. L3 启动（校验配置、连库、连 Redis）；
4. 客户端先向 L2 申请租约，再用租约虚拟 key 调 L3。

L3 不依赖 L2 进程存活：只要共享库/Redis 可达、租约有效，L3 即可转发与记账。

## 5. 独立入口与配置

新增 `base/common/gateway/server.py`：

- `build_app()`：`validate_gateway_config()` fail-closed 校验 → `create_gateway_app()` → 注册
  Tortoise 生命周期（启动 `Tortoise.init` + Redis 预热，退出 `close_connections`）；
- `__main__`：读取 `gateway.host` / `gateway.port`，打印实际监听地址、deployment、fail_closed，
  `uvicorn.run(app, host=..., port=...)`；
- 若当前 `deployment != standalone`，独立入口拒绝启动并提示改用 `python run.py`（避免双数据面）。

启动方式：

```bash
python -m base.common.gateway.server
# 或
uvicorn base.common.gateway.server:app --host 127.0.0.1 --port 9999
```

L3 部署需要的配置：

- `config.conf`：`db.*`（共享库）、`redis.*`（租约缓存/额度计数；不可用时回落 DB）；
- `manifest.json`：`config.gateway`（host/port/deployment/public_base_url/fail_closed/白名单/TTL/上游超时等）；
- 不依赖任何插件启用态，不读取插件运行时状态。

## 6. 启动校验（fail-closed）

`validate_gateway_config()` 在独立入口启动时执行，拒绝启动的情形：

- `runtime.allow_env_fallback=true`（允许环境变量回退 provider key）；
- `runtime.allow_direct_provider=true`（允许内置 key 直连 provider）；
- `gateway.fail_closed=false`；
- `gateway.deployment` 非 `standalone/embedded`；
- `gateway.public_base_url` 非 http(s)；
- `provider_domain_allowlist` 为空；
- 租约 TTL / 租户覆盖 / RPM / 重试与连接池配置非法。

启动日志打印：实际监听地址、`deployment` 模式、`fail_closed` 状态。

## 7. 与业务端的关系

- 租约签发/续期/吊销仍在 L2：`/v1/harness/gateway/leases`；
- L3 只读取 `harness_gateway_lease` / `harness_session` / `harness_run`，写 `usage_record`、
  `harness_gateway_budget`、`harness_gateway_concurrency` 与审计；
- L3 不提供租约签发接口，也不接受 JWT / 登录态凭据。

## 8. 验证方案（本地假 provider）

不调用真实 provider。临时启用 `allow_loopback` + `127.0.0.1` 白名单，验证后还原。

1. `deployment=standalone` 时 L2 启动日志不挂载 `/v1/gateway`，L3 独立进程启动成功；
2. L3 `/health`、`/docs`、`/openapi.json` 可用；
3. L2 签发租约 → **停止 L2** → L3 仍可用该租约完成非流式请求并写 `usage_record`；
4. SSE 透传与假 provider 输出逐字节一致；
5. 额度拒绝（租约预算耗尽）返回 402；
6. 续期、吊销（需 L2 运行）与 `renew_after` 头；
7. 配置不合规（如清单为空）时独立入口拒绝启动。

## 9. 验收标准

- [x] 独立入口可启动，复用 `create_gateway_app()`；
- [x] standalone 下业务 API 不挂载 `/v1/gateway`；embedded 仍可挂载；
- [x] fail-closed 校验生效，启动信息完整；
- [x] L2 停止后 L3 可服务并记账；
- [x] 对账、额度中断、共享上游客户端语义未改变；
- [x] 临时测试数据、进程、配置全部清理还原。

## 10. 实施记录（2026-11-07）

改动文件：

- 新增 `base/common/gateway/server.py`：独立入口（配置校验 → `create_gateway_app(lifespan=...)`
  → `Tortoise.init` 共享库 → Redis 预热 → uvicorn 监听）；
- `base/common/gateway/app.py`：`create_gateway_app(lifespan=None)` 支持注入生命周期，其余不变；
- `base/common/gateway/config.py`：`deployment` 默认改为 `standalone`，同步更新模块说明；
- `base/plugins/harness/manifest.json`：`deployment=standalone`、`public_base_url=http://127.0.0.1:9999`；
- `base/start.py`：仅更新部署形态注释，`embedded` 挂载逻辑不变。

行为一致性：

- 未改数据面转发、SSE 透传、出网白名单、额度预检/结算、对账与共享上游客户端语义；
- 公共路径仅新增独立入口与 `create_gateway_app` 的 lifespan 入参（默认 None，业务侧调用不变）。

验证（本机假 provider，21 项全通过）：

1. `deployment=standalone` 下 L2 `/v1/gateway/health` 返回 404（未挂载）；
2. L2 签发默认 TTL 900 租约、小预算租约、待吊销租约；续期 200、吊销 200；
3. 停止 L2 后启动 L3：`/health`、`/docs`、`/openapi.json` 均 200；
4. 使用 L2 已签发租约完成非流式请求 200，响应内容与上游一致；
5. SSE 4 个 data 帧与假 provider 输出逐帧一致，且包含 `data: [DONE]`；
6. 非流式与流式各产生一条 `usage_record`（amount=15，source=gateway）；
7. 租约预算不足请求 402（`quota.lease_budget_exhausted`）；
8. 已吊销租约 401；非法虚拟 key 401；
9. 剩余 14s/60s（<30%）时响应头出现 `renew_after: 14`；充足时不出现；
10. 启动日志包含监听地址、`deployment: standalone`、`fail_closed: True`；
11. `deployment=embedded` 时独立入口拒绝启动（退出码非 0）。

清理：临时假 provider、测试脚本、日志目录已删除；`manifest.json` 已还原
（`allow_loopback=false`、白名单仅 `api.deepseek.com`）；测试租约/客户端/LLM 凭据/用量记录清零。

## 11. 上线状态（2026-11-07）

生产配置（`deployment=standalone`、`public_base_url=http://127.0.0.1:9999`）下实际启动：

- L3：`python -m base.common.gateway.server`，监听 `127.0.0.1:9999`；
  `GET /health` → `{"status":"ok","deployment":"standalone","fail_closed":true}`。
- L2：`python run.py`，监听 `127.0.0.1:9998`；业务接口 `/v1/install/status` 200；
  `/v1/gateway/health` → 404（standalone 下不挂载）。
- 租约签发响应 `base_url` 实测为 `http://127.0.0.1:9999`。
- 收尾冒烟（假 provider，7 项全通过）：非流式 200、SSE 4 帧 + `[DONE]`、`usage_record` 2 条
  （amount=15、source=gateway）、短租约（剩余 15s/60s）返回 `renew_after: 14`。

重启动作：先停 9998/9999 旧进程 → 启 L3（9999）→ 启 L2（9998）；客户端 `base_url`
跟随 `gateway.public_base_url`，无需单独改客户端配置。

