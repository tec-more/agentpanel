# L2 出网收敛：策略来源与客户端快照

> 状态：已实现（接口 + 审计 + 文档），验证见 §7。
> 范围：L2 业务 API（9998）。**不改动** L3 数据面、网关白名单/出网校验语义、对账、额度、租约逻辑。

## 1. 定位：策略来源，不是执行边界

本能力把「业务层希望客户端遵守的出网策略」整理成可版本化、可校验的快照，供本机 dsh 拉取并自行应用。

**它不能、也没有阻断出网。** 以下方式仍可绕过，不能把本文档读成「已阻止出网」：

- 客户端管理员修改 dsh profile / tools 配置，重新启用直连工具；
- 客户端自行发起原始套接字连接（HTTP/3、QUIC、IPv6 直连等）；
- 跳过 dsh 工具注册表直接调用 provider SDK；
- 任何不读取本快照的其它进程。

真正的执行边界必须落在终端网络策略（防火墙 / 强制代理 / DNS 策略）或容器网络策略（NetworkPolicy、出网网关）。本接口只负责「把策略说清楚、可校验、可审计」，并明确要求客户端 fail-closed。

## 2. 单一白名单来源（实施前已说明的方案）

- `provider_domain_allowlist` **不在 `config.egress` 里重复配置**；
- 快照中的白名单直接读取 `harness.manifest.config.gateway.provider_domain_allowlist`
  （代码经 `base.common.gateway.config.gateway_config()` / `upstream_allowlist()`），
  与 L3 网关数据面校验共用同一份配置；
- 网关侧 `assert_egress_allowed` / `egress_policy()` 未做任何修改，语义保持不变；
- 快照 `source` 字段显式标注白名单来源，便于排查两处漂移（当前不存在第二处）。

## 3. 策略项与默认值

manifest：`base/plugins/harness/manifest.json` → `config.egress`

| 字段 | 默认值 | 说明 |
|---|---|---|
| `version` | `1` | 策略版本号；内容变化时由运维递增 |
| `min_supported_version` | `1` | 低于此版本的客户端必须 fail-closed |
| `allow_client_non_gateway` | `false` | 是否允许客户端绕过网关直连 provider，默认禁用 |
| `tool_denylist` | `["web_fetch","web_search","browser","http_request"]` | 直连出网工具禁用清单 |
| `snapshot_ttl_seconds` | `300` | 快照缓存时间（30–86400），用于 `Cache-Control: max-age` |

`provider_domain_allowlist` 由网关配置派生（见 §2），不出现在 `config.egress`。

### 3.1 快照内容

```json
{
  "compatible": true,
  "policy_version": 1,
  "min_supported_version": 1,
  "content_hash": "sha256:<hex>",
  "hash_algorithm": {
    "algorithm": "sha256",
    "canonicalization": "json sort_keys=True,separators=(',',':'),ensure_ascii=False",
    "prefix": "sha256:"
  },
  "cache_ttl_seconds": 300,
  "policy": {
    "version": 1,
    "allow_client_non_gateway": false,
    "tool_denylist": ["web_fetch", "web_search", "browser", "http_request"],
    "provider_domain_allowlist": ["api.deepseek.com"],
    "gateway": {
      "deployment": "standalone",
      "public_base_url": "http://127.0.0.1:9999",
      "lease_issue_endpoint": "/v1/harness/gateway/leases"
    },
    "enforcement": "policy_source_only"
  },
  "source": {
    "config": "harness.manifest.config.egress",
    "provider_domain_allowlist": "harness.manifest.config.gateway.provider_domain_allowlist"
  },
  "disclaimer": "<策略来源，不是执行边界；真正阻断依赖终端/容器网络策略>"
}
```

内容哈希计算方式：对 `policy` 对象做 `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)` 后取 SHA-256，前缀 `sha256:`。客户端可本地复算并与 `content_hash` 比对。

## 4. 下发接口

`GET /v1/harness/egress-policy/snapshot?client_version=<int>`

鉴权：Harness 客户端凭据（`X-Harness-Client-Id` + `X-Harness-Secret`，或 `Authorization: Bearer <client_id>.<secret>`）。不接受 JWT 或 `dgw.*` 租约 key。

| 场景 | HTTP | 响应 |
|---|---|---|
| 版本兼容 | `200` | 业务包装 `{code,msg,data,success}`，`data` 为 §3.1 快照；带 `ETag`、`Cache-Control: private, max-age=N`、`X-Egress-Policy-Version`、`X-Egress-Policy-Hash` |
| `If-None-Match` 命中 | `304` | 无响应体，保留版本/哈希/缓存头（仍记审计，`cache_hit=true`） |
| `client_version` 缺省 / `unknown` / 非整数 | `426` | `data={compatible:false,decision:"deny",fail_closed:true,reason:"client_version_unknown",...}` |
| `client_version < min_supported_version` | `426` | `reason:"client_version_too_old"` |
| 服务端 `min_supported_version > version` | `426` | `reason:"server_policy_below_min_supported"` |
| `config.egress` 非法 | `503` | `reason:"server_policy_config_invalid"`，fail-closed |

客户端约定：**任何非 200/304、`compatible=false`、哈希校验失败、网络失败，都必须停止使用出网能力（fail-closed）**，不得回退到直连 provider。

缓存约定：客户端按 `Cache-Control: max-age` 缓存；重新拉取时带 `If-None-Match: "<content_hash>"`，304 表示继续使用本地快照。

## 5. 审计

全部写入 `harness_audit_event`，`event_source=policy`，`target_type=policy`，可用现有管理员接口查询：
`GET /v1/harness/audit-events?action=<action>`。

| action | 触发 | actor | 关键 detail |
|---|---|---|---|
| `egress.policy.changed` | 策略内容（版本/哈希）相对上次审计变化 | `system` / `harness.manifest` | `change_kind`(initial/update)、`previous_version`、`previous_hash`、`new_version`、`new_hash`、`changed_fields`、`policy_before`、`policy_after`、`note` |
| `egress.policy.snapshot` | 每次快照下发（含 304） | `client` / `client_id` | `policy_version`、`content_hash`、`client_version`、`cache_ttl_seconds`、`cache_hit`，以及请求 IP/UA/request_id |
| `egress.policy.incompatible` | 版本未知/过低拒绝 | `client` / `client_id` | `reason`、`client_version`、`policy_version`、`min_supported_version`、`content_hash`、`decision=deny` |

诚实边界：manifest 由拥有文件系统权限的运维修改，接口只能记录「系统 / manifest」。**具体是谁改的**需由配置管理、Git 提交记录或堡垒机审计追溯，本条已写入变更事件的 `note`。

策略变更检测在进程内缓存最近已留痕哈希；重启后首次快照会与库中最新变更事件对比，若不一致则补记。manifest 变更需重启 L2 才生效（`plugin_manager` 按进程缓存 manifest）。

## 6. 客户端对接约定（需要 dsh 侧配合，不能假设已具备）

### 6.1 必须消费的配置项

客户端应把快照落到本机 profile，并在启动时校验：

| 快照字段 | 客户端消费位置 | 要求 |
|---|---|---|
| `policy.gateway.public_base_url` | 模型 base_url（如 `DEEPSEEK_BASE_URL` / profile `base_url`） | 必须指向网关 `http://127.0.0.1:9999`，不得指向 provider |
| `policy.tool_denylist` | 工具注册表禁用列表（如 profile `tools.disabled` 或 patches 注入） | 列出的工具必须不可调用 |
| `policy.allow_client_non_gateway` | 直连开关（如 `allow_direct_provider` / 任何 provider 直连配置） | 为 `false` 时禁止任何非网关出网 |
| `policy.provider_domain_allowlist` | 若客户端仍保留受管直连能力，作为其唯一域名白名单 | 只允许清单内域名；**不是**替代网关 |
| `policy_version` / `content_hash` | profile 的 `egress_policy` 段 | 启动时校验哈希；不匹配或 426 则拒绝启动 |
| `cache_ttl_seconds` | 本地缓存过期与刷新周期 | 到期或哈希变化需重新拉取 |

### 6.2 dsh profile 示例（字段名是建议契约，需客户端实现/映射）

```json
{
  "profile": "agentpanel",
  "env": {
    "DEEPSEEK_BASE_URL": "http://127.0.0.1:9999",
    "DSH_PROVIDER": "deepseek"
  },
  "egress_policy": {
    "version": 1,
    "content_hash": "sha256:...",
    "source": "http://127.0.0.1:9998/v1/harness/egress-policy/snapshot"
  },
  "tools": {
    "disabled": ["web_fetch", "web_search", "browser", "http_request"]
  },
  "allow_direct_provider": false
}
```

### 6.3 patches 注入示例（只改工具开关，不改 dsh 代码）

```json
{
  "patches": [
    {"op": "add", "path": "/tools/disabled/-", "value": "web_fetch"},
    {"op": "add", "path": "/tools/disabled/-", "value": "web_search"},
    {"op": "replace", "path": "/allow_direct_provider", "value": false},
    {"op": "replace", "path": "/env/DEEPSEEK_BASE_URL", "value": "http://127.0.0.1:9999"}
  ]
}
```

> 以上仅为对接约定示例：dsh 当前是否支持 `tools.disabled` / `allow_direct_provider` / patches 注入字段，需客户端侧确认并实现。若不支持，客户端至少要在启动流程中执行 §6.1 的校验并对不兼容版本 fail-closed。

## 7. 验证记录（假数据，不调用真实 provider）

验证方式：本地临时 Harness 客户端凭据 + 直连 L2（9998）真实接口，33 项检查全部通过，结束后删除测试客户端与本轮 9 条测试审计。

- 策略读取：`GET /v1/harness/egress-policy/snapshot?client_version=1` 返回 `compatible=true`、`policy_version=1`、
  `min_supported_version=1`、`allow_client_non_gateway=false`，工具清单含 `web_fetch`/`web_search`；
  白名单 `["api.deepseek.com"]` 与 `gateway.provider_domain_allowlist` 完全一致，`source` 标注为网关配置。
- 网关地址：`policy.gateway.public_base_url=http://127.0.0.1:9999`，`enforcement=policy_source_only`。
- 内容哈希：按 §3.1 算法本地复算为 `sha256:8f5582...a87bb`，与服务端一致；重复请求哈希稳定。
- 缓存：`ETag`、`Cache-Control: private, max-age=300`、`X-Egress-Policy-Version`、`X-Egress-Policy-Hash` 均返回；
  带 `If-None-Match` 返回 `304` 且响应头保留，审计 `cache_hit=true`。
- 版本不兼容：`client_version=0` → `426 client_version_too_old`；缺省 / `unknown` / `abc` →
  `426 client_version_unknown`；均 `compatible=false`、`fail_closed=true`，且不返回策略内容。
- 鉴权：无客户端凭据 → `401`。
- 策略变更审计：合成内容变更（追加 `ssh_proxy`）后写入 `egress.policy.changed`，
  `change_kind=update`、`changed_fields=["tool_denylist"]`，`previous_hash`/`new_hash` 正确；
  重复调用不产生重复审计（进程内哈希缓存生效）。
- 审计落库：`egress.policy.snapshot`（含 200 与 304）、`egress.policy.incompatible`（4 条，均 `decision=deny`）、
  `egress.policy.changed` 均可从 `harness_audit_event` 查到。
- 未验证 / 不在本期范围：真实出网阻断（本能力不提供）、dsh 侧实际应用效果。
