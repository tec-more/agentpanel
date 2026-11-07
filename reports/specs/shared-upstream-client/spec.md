# 共享上游 HTTP 客户端（第 4 项）— Spec

## 1. 目标

将网关（`base/common/gateway`）与 llm 插件（`base/plugins/llm/services`）中重复的上游模型 HTTP 调用逻辑抽取到 `base/common/upstream`，统一：连接池、连接/读/总时长超时、重试策略、TLS/代理、请求头透传。流式与非流式均覆盖，且不改变现有对外行为。

## 2. 非目标 / 硬约束

- 不改网关字节级透传：流式仍 `aiter_bytes()` 原样转发、不缓冲、不聚合；SSE 旁路解析仅用于 usage/估算。
- 不改 llm 的流式重拼装：chunk 解析与 `chat_service.chat_stream` 的组装/用量记录逻辑保持原样，**不得改成透传**。
- 保持网关：`dsh_session_log` 剥离、出网白名单、`fail_closed`、上游超时 504、连接失败 502、上游 >=400 按原状态透传、失败也记账、预占释放。
- 不得调用真实 provider，验证使用本机可控假 provider。
- 有副作用/已开始向客户端输出的请求不得重放；流式请求在收到响应头之后一律不重试。

## 3. 新增模块 `base/common/upstream/`

### 3.1 `config.py`

`UpstreamConfig` dataclass（frozen），字段与默认值：

| 字段 | 默认 | 说明 |
|---|---|---|
| `connect_timeout` | 10.0 | 连接超时（秒） |
| `read_timeout` | 300.0 | 读超时（秒），流式表示相邻数据块间隔 |
| `total_timeout` | 0.0 | 单次尝试总时长，<=0 关闭（流式不跨响应体计时） |
| `max_connections` | 100 | 连接池上限 |
| `max_keepalive_connections` | 20 | 保活连接数 |
| `keepalive_expiry` | 30.0 | 保活时长 |
| `verify_tls` | True | TLS 校验 |
| `proxy_url` | "" | 显式代理；空表示不设置 |
| `trust_env` | False | 是否读取环境变量代理（网关 False，llm 保持 True 以兼容原行为） |
| `follow_redirects` | False | 不跟随重定向 |
| `http2` | False | 保持 HTTP/1.1 |
| `retry_attempts` | 1 | 总尝试次数，>=1；1 表示不重试 |
| `retry_backoff` | 0.5 | 指数退避基数 |
| `retry_max_backoff` | 4.0 | 退避上限，同时用于截断 `Retry-After` |
| `retry_statuses` | (429,500,502,503,504) | 可重试状态码 |

- `signature()` 返回用于连接池缓存的稳定 key（全部字段）。
- `httpx_timeout(read_timeout=None, total_timeout=None)` 返回 `httpx.Timeout(connect=..., read=..., write=connect, pool=connect)`。

### 3.2 `client.py`

异常体系：
- `UpstreamError(Exception)`；`kind` 属性（`connect`/`read`/`write`/`timeout`/`status`）。
- `UpstreamTimeout(UpstreamError)`：`timeout_kind` ∈ `connect|read|total`。
- `UpstreamConnectError(UpstreamError)`：请求**未发出**（DNS/拒绝连接/连接超时/池耗尽）。
- `UpstreamReadError(UpstreamError)`：请求已发出、读取响应失败。
- `UpstreamStatusError(UpstreamError)`：携带 `status_code`、`body`（bytes）、`response`。

连接池：
- 模块级 `_clients: Dict[str, httpx.AsyncClient]` + `asyncio.Lock`。
- `async def get_client(cfg) -> httpx.AsyncClient`，按 `cfg.signature()` 复用，不随单请求关闭。
- `async def close_upstream_clients()`：关闭并清空；供应用生命周期/测试收尾。
- `async def upstream_client_context()`：asynccontextmanager 版本，仅导出，不改现有启动流程。

方法（全部接收显式 `cfg`，不读全局配置，便于 llm/网关各自配置）：

1. `async def request_json(method, url, *, json=None, headers=None, cfg, read_timeout=None, total_timeout=None, replay=False) -> httpx.Response`
   - 非流式（响应体已读完）。默认用于 `post_json` / `get_json`。
   - 每次尝试：`asyncio.timeout(total)`（若 >0）包裹 `client.request(...)`。
   - 重试规则：
     - `httpx.ConnectError/ConnectTimeout/PoolTimeout` → 映射 `UpstreamConnectError`，**总是可重试**（请求未发出）。
     - `httpx.ReadTimeout` → `UpstreamTimeout(timeout_kind="read")`，**不重试**。
     - `httpx.ReadError/RemoteProtocolError` → `UpstreamReadError`，**不重试**。
     - `asyncio.TimeoutError`（total 超时）→ `UpstreamTimeout(timeout_kind="total")`，**不重试**（无法判定是否已发出/已消费）。
     - 响应状态 ∈ `cfg.retry_statuses` 且 `replay=True` 且还有尝试次数 → 关闭该响应后重试；`replay=False` 直接返回该响应，由调用方决定（llm 保持原有 `raise_for_status` 语义）。
     - `Retry-After`（秒）参与退避，上限 `retry_max_backoff`；退避 `retry_backoff * 2**n`。
   - 尝试耗尽：最后一次为响应则返回响应；否则抛对应异常。
2. `async def post_json(...)` / `async def get_json(...)`：`request_json` 的薄封装，签名同名透传。
3. `async def send_stream(url, *, json=None, headers=None, cfg, read_timeout=None, total_timeout=None) -> httpx.Response`
   - `client.build_request` + `client.send(stream=True)`；`total_timeout` 仅约束到收到响应头。
   - 仅在**尚未拿到响应**时对 `UpstreamConnectError` 重试；**拿到响应后永不重试**（即使状态码在可重试集合）。
   - 调用方负责 `response.aclose()`。
4. `def ensure_success(response, *, label: str) -> None`
   - `>=400` 时 `await response.aread()`（若未读）并抛 `UpstreamStatusError`，`body=raw`；llm 用 `label` 保持既有报错前缀（如 `"OpenAI API调用失败"`），网关不用它。
5. `async def iter_sse_data(response) -> AsyncIterator[str]`
   - 逐行读取 `aiter_lines()`；跳过空行与非 `data:` 行；去掉 `data:` 前缀与一个可选前导空格；遇 `[DONE]` 结束；其余原样 yield。
   - 供 openai/deepseek/zhipu/localai/anthropic。阿里/百度逐行 JSON 不走该函数（直接 `response.aiter_lines()`）。
6. `def is_timeout_error(exc) / is_connect_error(exc)`：网关错误映射辅助。

安全语义写入模块 docstring：连接建立前失败才可重试；响应体已消费、流式已下发、有副作用请求不重放。

### 3.3 出网校验（强制、不可绕过）

依据 Linux 容器实测结论：dsh 自身的 `web_fetch` 无 provider 域名白名单（`example.com` 可直连 200），出网管控只能由后端/网关承担。因此共享上游客户端内置**强制**出网校验：

- `EgressPolicy` dataclass：
  - `allowed_hosts: FrozenSet[str]`
  - `allow_loopback: bool`
  - `allow_private: bool`（仅本地模型 provider 使用）
  - `require_https: bool`
  - `enforce_allowlist: bool`（网关为 True；llm 为 False 时仍执行协议/私网校验）
- `check(url)` 规则（每次发送前由 `request_json` / `send_stream` **无条件调用**，无任何 `skip_egress`/`egress_enabled` 配置开关）：
  1. scheme 必须为 `http`/`https`；拒绝 userinfo（`user:pass@host`）。
  2. `enforce_allowlist=True` 时 host 必须命中 `allowed_hosts`；**白名单为空则全部拒绝**（fail-closed，网关启动校验已要求非空）。
  3. `allow_loopback=False` 时拒绝 `localhost/127.0.0.0/8/::1`。
  4. `allow_private=False` 时拒绝字面量私网 IP（10/8、172.16/12、192.168/16、169.254/16、fc00::/7 等）。
  5. `require_https=True` 时拒绝 `http`（仅非本地 provider 使用）。
  6. 失败抛 `UpstreamEgressError(status_code=403)`。
- 策略来源：
  - 网关：`EgressPolicy.from_gateway_config()`，host 来自 `gateway.provider_domain_allowlist`，`allow_loopback` 来自 `gateway.allow_loopback`；即使路由层已调用 `assert_egress_allowed`，共享客户端仍再校验一次（纵深防御，且不改变原 403 响应文案）。
  - llm：`EgressPolicy.for_provider(kind, endpoint_url)`：公共 provider（openai/deepseek/zhipu/anthropic/alibaba/baidu/tencent/doubao）要求公网 host，拒绝 loopback/私网；`local` provider 显式允许 loopback/私网。该策略由代码固定，**不可由配置关闭**。
- `web_fetch`/`web_search`：仓库内无对应后端实现，属于 dsh 工具侧、可绕过网关的直接出网通道；本项不新增调用，并在规格与汇报中明确它们必须由 dsh 工具禁用/容器网络策略兜底，后端不承担其放行。
- 审批：共享客户端不调用任何审批 API、不等待审批通道；无审批通道时的现状（`outcome=unavailable`、fail-closed）不依赖、不改变。

### 3.4 `__init__.py`

导出上述公开符号。

## 4. 网关改造

### 4.1 `base/common/gateway/config.py`

- `DEFAULTS` 新增：
  `total_timeout_seconds: 0`、`retry_max_attempts: 3`、`retry_backoff_seconds: 0.5`、`retry_max_backoff_seconds: 4.0`、`retry_statuses: [429,500,502,503,504]`、`verify_tls: True`、`proxy_url: ""`、`trust_env: False`、`max_connections: 100`、`max_keepalive_connections: 20`、`keepalive_expiry_seconds: 30`。
- 新增 `gateway_upstream_config() -> UpstreamConfig`：由 `gateway_config()` 映射；`trust_env=False`、`follow_redirects=False`（保持现状）。
- `validate_gateway_config()` 增加轻量校验：`retry_max_attempts >= 1`、`retry_statuses` 为合法 4xx/5xx 列表、`total_timeout >= 0`，非法时抛 `GatewayConfigError`（fail-closed）。现有校验条目不变。

### 4.2 `base/common/gateway/router.py`

- 删除 `_timeout()` 与本模块 `httpx.AsyncClient` 直接构造。
- `_forward_non_stream`：
  - `upstream = await upstream_client.post_json(url, json=body, headers=headers, cfg=gateway_upstream_config(), replay=True)`。
  - `except UpstreamTimeout` → 原 504 分支（释放预占、`record_gateway_usage(status_code=504, error="upstream_timeout:<kind>")`、返回原错误体）；`except UpstreamError` → 原 502 分支（`upstream_unreachable:<type>`）。
  - 成功/>=400 分支逻辑逐行保持：`upstream.content`、`_downstream_headers`、usage 提取、settle、记账、`Response` 返回。
- `_forward_stream`：
  - `upstream = await upstream_client.send_stream(url, json=body, headers=headers, cfg=gateway_upstream_config())`。
  - 异常映射同上（504/502）。
  - `>=400` 分支：`aread + aclose` 后原样返回，保持原状态码与 body。
  - `relay()` 不变；**不得在 relay 内重试**；只关闭 `upstream`，不再关闭 client。
  - `_finalize_stream` 移除 `client` 参数与关闭逻辑（连接池由模块管理）。
- 流式旁路、watchdog、截断帧、记账全部不变。

## 5. llm 插件改造

统一模式（每个 service）：
- 构造 `_upstream()` 返回 `UpstreamConfig(read_timeout=..., total_timeout=0, trust_env=True)`；非流式 chat 使用 `read_timeout=60`（tencent/doubao fallback 保持原值），流式 `read_timeout=120`。
- `chat`：`response = await post_json(...)`；`ensure_success(response, label=...)`；`return response.json()`；异常文案保持：
  - `UpstreamStatusError` → `Exception(f"{label}: {e.body_text}")`（与原 `e.response.text` 等价）
  - 其他 → 原 `"...服务异常: {e}"` 日志与重抛。
- `chat_stream`：`response = await send_stream(...)`；`ensure_success`；`async for data in iter_sse_data(response)` → `json.loads`，解析失败保留 warning 并 `continue`；`finally: await response.aclose()`。
- `create_embedding`（仅 openai）：`post_json` + `ensure_success`，错误文案不变。

逐文件改动：
- `openai_service.py`：`chat`、`chat_stream`、`create_embedding`。
- `deepseek_service.py`、`zhipu_service.py`、`localai_service.py`：`chat`、`chat_stream`（保留各自 header 与 payload）。
- `anthropic_service.py`：`chat`、`chat_stream`（保留 `x-api-key`/`anthropic-version`；流式仍仅 yield 含 `delta` 的 chunk）。
- `alibaba_service.py`：`chat`、`chat_stream`；流式仍逐行 `json.loads`（DashScope 非 SSE），不使用 `iter_sse_data`。
- `baidu_service.py`：access token 改用 `get_json`；对话/流式改用 `post_json`/`send_stream`；流式仍逐行 JSON。
- `tencent_service.py`：`chat` 与模拟 `chat_stream`（单次非流式请求）改用 `post_json`。
- `doubao_service.py`：两处 SDK 不可用 fallback（约 148-183、348-396）改用 `post_json`/`send_stream`，payload、返回结构与异常文案不变。
- `chat_service.py` **不改**（流式重拼装与 usage/cost 记录保持）。

## 6. 验证方案（假 provider，不触真实网络）

临时脚本（执行后删除）：
- `tmp_verify_upstream/fake_provider.py`：uvicorn 假 provider，行为由请求头/路径控制：
  - `/v1/chat/completions`：正常 200 JSON（含 usage）；`?mode=slow` 延迟超读超时；`?mode=500` 前 N 次 500 后 200；`?mode=drop` 返回响应头后写 1 个 chunk 即断连；SSE 模式逐帧输出并回显收到的 body 供 `dsh_session_log` 检查。
  - 记录每次请求（次数、body、路径）供断言。
- `tmp_verify_upstream/run_gateway.py`：直接调用 `gateway_data_router` 依赖覆盖（伪造 lease）或经运行中服务（127.0.0.1:9998）用租约客户端；覆盖：
  1. 正常非流式：200，body 字节与假 provider 返回一致，usage 记账 1 条；
  2. 慢响应：读超时 → 504，预占释放，记账 1 条失败；
  3. 连接中断（端口关闭）→ 502，记账 1 条；
  4. 中途断流：客户端收到已转发字节，转发后不重试（假 provider 请求计数 = 1），失败记账/截断语义符合现状；
  5. 5xx 重试（非流式 replay=True）：500→500→200，最终 200，上游请求计数 = 3，记账 1 条；
  6. 流式已输出后不重试：假 provider 记录请求数 = 1；状态码 500 的流式响应按原状态透传且不重试；
  7. `dsh_session_log` 剥离：假 provider 回显 body 中无该字段；
  8. 出网白名单：非白名单域名 → 403；`allow_loopback` 关闭时不放行 127.0.0.1；`ftp://` 拒绝；白名单清空时全部拒绝（fail-closed）；确认不存在可关闭出网校验的配置键；
  9. SSE 字节一致：假 provider 输出固定帧序列，客户端收到的字节完全相同且逐帧（不缓冲）；
  10. 额度中断回归：复用 `harness-quota-interrupt` 既有用例（预占拒绝、流式越界截断、失败记账）复跑。
- `tmp_verify_upstream/run_llm.py`：`OpenAIService(api_key="test", endpoint_url=fake)` 跑 `chat` 与 `chat_stream` 各一次，断言对话内容与 chunk 序列；再用 `ChatService`（若依赖可注入）或直接比对 `chat_service` 未改动；至少验证 llm 侧非流式返回 dict、流式 chunk 顺序与用量字段解析不受影响。
- 清理：停止假 provider、删除临时脚本与临时 usage 记录/租约。

通过标准：
- 上述 10 类网关场景全部 PASS；
- llm `chat` 与 `chat_stream` PASS；
- 网关原有 504/502/透传/记账/白名单/剥离行为与改造前一致；
- `python -c "import base.common.upstream"` 与后端启动导入无错误。

## 7. 风险与决策

- 连接池共享后，响应必须由调用方关闭；网关 `_finalize_stream`、llm `finally` 均已覆盖。
- 重试只发生在“请求未发出”或“非流式且显式 replay”两种情形；流式响应头已到即不再重试，满足“开始输出后不得重试”。
- llm 默认 `retry_attempts=1`，保持原有“不重试”行为；网关默认 3 次。
- 网关 `total_timeout_seconds` 默认 0（关闭），避免改变长流式语义；非流式可用配置开启。
- 出网校验无开关：策略对象是调用必填参数，缺少策略视为编程错误并拒绝发送。llm 公共 provider 若配置了私网/回环 `endpoint_url` 将被拒绝（安全收紧，符合“出网管控只能靠后端/网关”的结论）；`local` provider 不受影响。
- `web_fetch`/`web_search` 无法由本模块管控（不在后端代码中），作为残余风险记录，需由 dsh 工具禁用或容器网络策略兜底。
- 审批通道不作为可用前提：共享客户端不等待审批，失败即 fail-closed。
