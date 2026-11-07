# Tasks：DeepSeek 模型凭据走 LLM 配置

> 依赖顺序：T1 → T2 → T3/T4 → T5 → T6 → T7 → T8（验收）

- [ ] T1 启用 llm 插件
  - 改 `base/plugins/llm/manifest.json`：`is_installed=true`、`is_enabled=true`
  - 确认 `agent`/`approval` 的 manifest 未变
  - 重启后确认 `/v1/llm/providers|models|api-keys` 已注册
  - 调用现有 `/v1/extension/plugins/sync` 同步 DB plugin 状态为已启用

- [ ] T2 新增公共脱敏工具
  - 新增 `base/common/masking.py`：`mask_secret` / `is_masked` / `fingerprint` / `validate_secret` / `redact_fields` / `SENSITIVE_FIELD_NAMES`
  - 要求：校验失败异常不含原值；空值与遮蔽值规则明确

- [ ] T3 llm 录入校验 + 回显脱敏
  - `base/plugins/llm/schemas/llm.py`：新增显式 `base_url` 入参；`ApiKeyBase`/`ApiKeyUpdate` 三字段 validator
  - `base/plugins/llm/api/v1/api_key.py`：`base_url` 归一到 `endpoint_url` 并回显别名；复用公共工具；`access_token` 脱敏；更新时丢弃遮蔽值；创建时 strip+校验
  - `web/src/views/llm/api-keys/index.vue`：Base URL 表单/列表
  - 验收：短 key 422；列表无明文 access_token；遮蔽值不覆盖旧值；`base_url` 可读写

- [ ] T4 审计链路防明文
  - `base/plugins/audit/services/orm_event_service.py::get_instance_dict` 按敏感字段名遮蔽
  - `base/plugins/audit/middleware/audit_middleware.py` 写 `request_params` 前调用 `_mask_sensitive_fields`
  - `base/plugins/audit/manifest.json` sensitive_fields 追加 api_key/api_secret/access_token/app_secret/client_secret
  - 验收：创建/更新 key 后查 `data_change_log`、`audit_log` 无明文

- [ ] T5 Harness 凭据解析
  - 新增 `base/plugins/harness/services/model_credential_service.py`
  - `resolve()` 选 provider→model→key（model 关联优先，provider 级 key 兜底）
  - 缺失/空/base_url 缺失/多候选 → `ModelCredentialNotConfigured`（fail-closed）
  - `redacted()` 只输出 mask + fingerprint；dataclass 的 api_key 设 `repr=False`
  - 验收：无 key 模型返回「未配置模型凭据」

- [ ] T6 Harness 运行时注入
  - 新增 `base/plugins/harness/services/runtime_service.py`：`build_env` / `launch` / `verify_injection`
  - env 仅白名单 OS 变量 + manifest `runtime.env_names`；剔除父进程 `DEEPSEEK_*`/`DSH_*`
  - `launch` 不写死命令，取 `runtime.dsh_command`
  - 审计 `runtime.launch` 只写 base_url + mask + fingerprint
  - `services/__init__.py` 导出
  - 验收：注入指纹匹配；父进程假 key 被忽略

- [ ] T7 Harness 管理接口
  - `admin_router.py` 增加 3 个 `/admin/model-credentials*` 接口（require_superuser）
  - 未配置统一 400 + 「未配置模型凭据」
  - 验收：effective/verify 均无明文

- [ ] T8 链路验证与汇报
  - 重启后端（现有后台进程需按实际 PID 重启，不改端口 9998）
  - 用占位 key 走 HTTP 全链路：录入 → effective → verify → 库内检索明文=0
  - 额外用例：父进程注入假 `DEEPSEEK_API_KEY` 仍 fail-closed
  - 汇报结果后，再继续 P2 剩余部分

## 环境事实（影响验证方式）

- 本机 `where dsh` 无结果，仓库内也无 subprocess 代码；因此 dsh 启动器是本次新增的**唯一注入点**，`runtime.dsh_command` 可配置。
- 真实 dsh 不存在时 `launch()` 会因找不到命令而失败（fail-closed，不伪造成功）；注入链路用 `verify_injection()` 的真实子进程探针验证。

## 回滚点

- 仅 T1 改插件状态；回滚将 llm manifest 改回 false 即可。
- T2–T4 为纯新增/局部遮蔽，无表结构变更，无 SQL 迁移。
- T5–T7 为 harness 新增服务与只读/探针接口，不影响既有 P1/P2 链路。
