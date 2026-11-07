# Spec：DeepSeek 模型凭据走项目自身 LLM 配置

## 1. 目标与边界

- 启用 `llm` 插件（仅 `llm`；`agent` / `approval` 保持关闭）。
- 后台可录入 `LLMProvider` / `LLMModel` / `LLMApiKey`（provider、model、base_url、api_key）；现有页面已具备 provider/model/endpoint_url/api_key 字段，本次只补 base_url 显式标注、校验与脱敏。
- Harness 运行时创建 dsh 子进程时，从上述配置解析 `api_key` / `base_url` / `provider` / `model` 并注入子进程环境；不写死、不读父进程全局环境变量兜底（除非 manifest 显式开启 `allow_env_fallback`，默认关闭）。
- 密钥安全：日志、审计事件、异常信息、接口返回均不得出现明文 key；写入前做长度/格式校验；回显统一脱敏。
- 未配置 key 时 fail-closed，明确返回/抛出「未配置模型凭据」，不静默使用默认或空 key。

## 2. 现状核查结论（已读代码）

| 项 | 现状 | 结论 |
|---|---|---|
| llm 插件 | `base/plugins/llm/manifest.json` 中 `is_installed/is_enabled=false` | 改为 true |
| LLM 模型注册 | `base/common/setting.py::get_model_list()` 无论启停都注册插件模型 | 无需改模型注册 |
| 录入接口 | `api/v1/provider.py`、`model.py`、`api_key.py` 完整 | 复用，补校验与脱敏 |
| 录入页面 | `web/src/views/llm/api-keys/index.vue` 已有 provider/model/api_key/endpoint_url | 复用，补 base_url 语义 |
| 密钥回显 | `api_key`/`api_secret` 已脱敏；`access_token` 明文；列表/详情多处返回 | 全部脱敏 |
| 审计泄露点 | `orm_event_service.get_instance_dict()` 原样落 `data_change_log`；`audit_middleware` 把 POST body 写入 `audit_log.request_params` | 两处必须脱敏 |
| dsh 子进程 | 全仓库无任何 subprocess/Popen 代码，harness 仅做事件接入口 | 新增运行时启动器，作为注入点 |

## 3. 详细改动

### 3.1 启用 llm 插件

文件：`base/plugins/llm/manifest.json`
- `is_installed: true`、`is_enabled: true`。
- 其余菜单/权限/路由不动；启动后由 `PluginManager.load_enabled_plugins()` 注册 `/v1/llm` 路由并同步菜单权限。
- 状态同步：启动后调用现有 `/v1/extension/plugins/sync`（或 `PluginService.sync_plugin`）把 DB `plugin` 行同步为 `is_installed/is_enabled=true`，避免后台「插件管理」页仍显示未启用；不改同步逻辑本身。

### 3.2 公共脱敏工具

新增：`base/common/masking.py`

```python
SENSITIVE_FIELD_NAMES = {"password", "api_key", "api_secret", "access_token",
                         "app_secret", "client_secret", "refresh_token", "secret_key"}

def mask_secret(value, head=4, tail=4) -> str:
    # 空 -> ""；长度 < head+tail+4 或 < 8 -> "****"
    # 否则 value[:head] + "****" + value[-tail:]

def is_masked(value) -> bool:      # 含 "****"
def fingerprint(value) -> str:     # sha256(value)[:12]，空返回 ""
def validate_secret(value, field="api_key") -> str | None:
    # None/"" -> None；strip 后 8..512；禁止空白/控制字符；禁止 "****"
    # 违规抛 ValueError(f"{field} 长度或格式不合法")，异常信息不回显原值
def redact_fields(data: dict) -> dict:
    # 按键名命中 SENSITIVE_FIELD_NAMES 时替换为 mask_secret(value)
```

### 3.3 llm 写入校验与回显脱敏

**字段口径（修正）**：需求中的 `base_url` 不再借道 `endpoint_url` 让调用方自行理解，而是接口与界面显式使用 `base_url`；存储层继续复用 `llm_api_key.endpoint_url`（不新增列、不做迁移），响应同时返回 `base_url` 与 `endpoint_url` 两个别名。

文件：`base/plugins/llm/schemas/llm.py`
- 引入 `field_validator`。
- `ApiKeyBase` 增加可选 `base_url`（max_length=512），`ApiKeyUpdate` 增加可选 `base_url`。
- `ApiKeyBase` 与 `ApiKeyUpdate` 的 `api_key/api_secret/access_token` 增加 validator：
  - 调用 `validate_secret`；失败抛 `ValueError`（FastAPI 自动 422，消息不含原值）。
  - `ApiKeyUpdate` 输入为遮蔽值（含 `****`）时不在这里拦截，交由路由层丢弃（保证前端旧值不被覆盖）。

文件：`base/plugins/llm/api/v1/api_key.py`
- 删除本地 `mask_secret`，改为 `from base.common.masking import mask_secret, is_masked, validate_secret, fingerprint`。
- 创建/更新：`base_url` 与 `endpoint_url` 归一到 `endpoint_url`（显式 `base_url` 优先；两者都传且不一致时以 `base_url` 为准）；入库前 `strip().rstrip("/")`。
- 列表 / 详情 / 创建 / 更新 响应中：`api_key`/`api_secret` 遮蔽（已有），`access_token` 同样遮蔽；新增 `base_url` 字段（等于 `endpoint_url`）。
- 创建：对 `api_key/api_secret/access_token` 先 `validate_secret`（再兜底一次），并 `strip()`；`api_key` 不得为遮蔽值。
- 更新：`update_data` 中若值 `is_masked()` → 删除该字段（保持旧值），避免把 `sk-a****z` 写库；其余值 `strip()`。
- 任何异常 detail 不回显密钥。

文件：`web/src/views/llm/api-keys/index.vue`
- 表单「端点URL」label 改为「Base URL」，绑定 `form.base_url`，placeholder `https://api.deepseek.com`。
- 列表新增 `Base URL` 列显示 `row.base_url || row.endpoint_url`；api_key 列仍显示后端遮蔽值。
- 编辑时 `form.base_url = row.base_url ?? row.endpoint_url ?? ''`。

### 3.4 审计链路脱敏（防明文落库）

文件：`base/plugins/audit/services/orm_event_service.py`
- `get_instance_dict()` 中，字段名命中 `SENSITIVE_FIELD_NAMES` 时用 `mask_secret` 处理后写入；其它字段不变。
- 效果：`llm_api_key` 的 create/update/delete 变更日志不再包含明文。

文件：`base/plugins/audit/middleware/audit_middleware.py`
- 新增模块常量 `SENSITIVE_REQUEST_FIELDS = sorted(SENSITIVE_FIELD_NAMES)`。
- 写入 `request_params` 前统一调用 `_mask_sensitive_fields(...)`，POST/PUT/PATCH 的 body 也先脱敏。
- 不改变审计开关、字段结构。

文件：`base/plugins/audit/manifest.json`
- `config.sensitive_fields` 追加 `api_key`、`api_secret`、`access_token`、`app_secret`、`client_secret`（供后台配置页展示；运行时以公共工具为准）。

### 3.5 Harness 模型凭据解析（fail-closed）

新增：`base/plugins/harness/services/model_credential_service.py`

```python
class ModelCredentialNotConfigured(Exception):
    # message 固定为「未配置模型凭据」/「未配置模型访问地址」等，不含任何密钥

@dataclass
class ModelCredential:
    provider: str            # name_en
    provider_name: str
    model: str               # model_id
    base_url: str
    api_key: str = field(repr=False, default="")
    api_key_id: int | None = None
    def redacted(self) -> dict:  # provider/model/base_url/api_key=mask/fingerprint
```

`HarnessModelCredentialService.resolve(provider=None, model=None) -> ModelCredential`
- 读取 `plugin_manager.get_manifest("harness")["config"]`：
  - `model_credential.provider` / `model_credential.model` 作为缺省值；
  - `runtime.allow_env_fallback` 默认 `false`。
- 选择逻辑：
  1. `LLMProvider` 状态 `active`，按 `name_en` 或 `name` 精确匹配传入 provider；
  2. `LLMModel` 状态 `active`，按 provider + `model_id`/`model_name` 匹配传入 model（未传时取该 provider 唯一 active 模型）；
  3. `LLMApiKey` 状态 `active`、`model_service_type="llm"`、provider 匹配；优先 `model_id == 选中模型`，其次 `model_id is null`；
  4. 校验 `is_available`（过期/配额耗尽视为不可用）。
- 失败矩阵（全部抛 `ModelCredentialNotConfigured`）：
  - 无 provider / 无模型 / 无 key / key 为空或仅空白 →「未配置模型凭据」；
  - `base_url` 为空（取 `api_key.endpoint_url` → `model.endpoint_url`）→「未配置模型访问地址」；
  - 多个可用候选且未显式指定 provider/model →「模型凭据未指定」。
- 仅当 `allow_env_fallback=true` 时才读取 `runtime.env_names` 对应的进程环境变量；当前 manifest 保持 `false`，即**不读全局环境变量**。
- 日志/审计只允许使用 `redacted()` 或 `fingerprint()`。

### 3.6 Harness 运行时启动器（子进程注入点）

新增：`base/plugins/harness/services/runtime_service.py`

```python
class HarnessRuntimeLauncher:
    @classmethod
    async def build_env(cls, credential) -> dict
        # 1) 仅复制非敏感 OS 变量白名单：PATH/PATHEXT/SYSTEMROOT/TEMP/TMP/HOME/
        #    USERPROFILE/HOMEDRIVE/HOMEPATH/COMSPEC/LANG/LC_ALL
        # 2) 显式剔除任何 DEEPSEEK_* / DSH_* 变量，防止父进程环境兜底
        # 3) 按 manifest runtime.env_names 注入：
        #    api_key -> DEEPSEEK_API_KEY, base_url -> DEEPSEEK_BASE_URL,
        #    provider -> DSH_PROVIDER, model -> DSH_MODEL
    @classmethod
    async def launch(cls, *, provider=None, model=None, cwd=None,
                     command: list[str] | None = None) -> tuple[Process, ModelCredential]
        # command 缺省取 manifest runtime.dsh_command（默认 ["dsh"]）
        # 先 resolve（失败即抛，不启动）；再 asyncio.create_subprocess_exec
        # stderr/stdout 不直接透传日志；若捕获，先 mask_secret 原文再记录
        # 写审计 runtime.launch：target=provider/model，detail 仅 base_url+masked+fingerprint
    @classmethod
    async def verify_injection(cls, *, provider=None, model=None) -> dict
        # 用 sys.executable 启动一次性探针子进程，子进程只输出 JSON：
        # {has_key, key_fingerprint, base_url, provider, model}
        # 父进程比对 fingerprint，返回 match；绝不返回明文 key
```

`base/plugins/harness/manifest.json` 增加 config：

```json
"runtime": {
  "dsh_command": ["dsh"],
  "env_names": {
    "api_key": "DEEPSEEK_API_KEY",
    "base_url": "DEEPSEEK_BASE_URL",
    "provider": "DSH_PROVIDER",
    "model": "DSH_MODEL"
  },
  "allow_env_fallback": false
},
"model_credential": {"provider": null, "model": null}
```

### 3.7 Harness 管理接口

文件：`base/plugins/harness/api/v1/admin_router.py`，全部 `require_superuser()`：

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | `/admin/model-credentials` | 列出 `llm` 类型凭据：id/provider/model/base_url/status/`api_key`(mask)/`key_fingerprint` |
| GET | `/admin/model-credentials/effective?provider=&model=` | 返回 `redacted()`；未配置返回 400 `{"code":40001,"message":"未配置模型凭据"}` |
| POST | `/admin/model-credentials/verify?provider=&model=` | 调用 `verify_injection`，返回 `{configured,injected,key_fingerprint_match,env_names,provider,model,base_url}`；未配置同上 400 |

文件：`base/plugins/harness/services/__init__.py`
- 导出 `HarnessModelCredentialService`、`ModelCredentialNotConfigured`、`HarnessRuntimeLauncher`。

## 4. 安全约束（验收必须逐条检查）

1. 明文 key 不得出现在：`audit_log.request_params`、`data_change_log.before/after_data`、`HarnessAuditEvent.detail`、应用日志、异常 detail。
2. 所有接口返回中的 key 只能是对外遮蔽值（前 4 + `****` + 后 4，短 key 全 `****`）；`access_token` 同样。
3. 子进程 env 只从解析结果注入；父进程已存在的 `DEEPSEEK_API_KEY` / `DSH_*` 必须被剔除，验证用例须覆盖。
4. 未配置 key：解析与启动均失败，错误消息为「未配置模型凭据」，HTTP 400；不得启动子进程。

## 5. 验证步骤（占位 key，无需真实 key）

1. 重启后端，确认 `/v1/llm` 路由与插件 `is_enabled=true`；`agent`/`approval` 仍关闭（检查 manifest 未变）。
2. 管理员登录后经 `/v1/llm/providers`、`/models`、`/api-keys` 录入：provider=deepseek、model=deepseek-chat、endpoint_url=`https://api.deepseek.com`、api_key=`sk-placeholder-verify-0123456789`。
3. `GET /v1/llm/api-keys`：`api_key` 为 `sk-p****6789`，`access_token` 遮蔽；DB 中 `llm_api_key.api_key` 仍为原值（说明只脱显存）。
4. `GET /v1/harness/admin/model-credentials/effective`：返回遮蔽 key + fingerprint + base_url；无明文。
5. `POST /v1/harness/admin/model-credentials/verify`：`injected=true`、`key_fingerprint_match=true`；探针输出不含明文。
6. 新建一个无 key 的模型，调用 effective/verify：HTTP 400，message=「未配置模型凭据」；在父进程注入假 `DEEPSEEK_API_KEY` 后重试，结果仍为 400（证明无环境变量兜底）。
7. 直接查库：`audit_log`、`data_change_log`、`harness_audit_event` 中检索占位 key 明文，命中数必须为 0。
8. 短 key（如 `sk-123`）创建：422/400，消息不包含原值。
9. 本机无 dsh 可执行文件，真实 `launch()` 会失败；以探针子进程验证 env 注入链路，真实 dsh 命令通过 `runtime.dsh_command` 指定（不做伪成功）。

## 6. 明确不做

- 不改 `agent` / `approval` 插件启用状态。
- 不改审批 fail-closed 行为。
- 不引入密钥加密存储/ KMS（当前库字段明文存储为既有实现，本阶段只保证不泄露、不回显、不落审计）。
- 内部网关（虚拟 key 归属）已按 P2 落地为 **embedded** 形态：随业务 API 启动，无需独立进程；数据面路径 `/v1/gateway/chat/completions`，配置见 `base/plugins/harness/manifest.json` 的 `config.gateway`（`deployment=embedded`、`public_base_url=http://127.0.0.1:9998/v1/gateway`）。`standalone` 仅保留配置位，当前不提供独立入口脚本。
