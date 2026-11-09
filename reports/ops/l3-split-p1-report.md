# P1 差异清单：共享包抽取 / manifest 三拆 / 配置契约

> 对应 Spec：`reports/specs/l3-service-split/spec.md` 第 12 章（P1 实施规格）
> 对应任务：`tasks.md` T1.1–T1.8
> 范围声明：只做搬运 + 兼容 + 配置契约 + 三入口验证；不含 `domain/*` 下沉、`credential_resolver` 抽取、打包、`services/*` 物理迁移、Docker。

---

## 1. 搬走了什么（`packages/common`）

| 分类 | 新路径 | 原路径 | 说明 |
|---|---|---|---|
| 模型基类 | `packages/common/models/base.py` | `base/common/model.py` | `BaseModel`/`TimestampMixin`；去掉 `base.common.setting` 依赖，`DATETIME_FORMAT` 内置常量 |
| 额度模型 | `models/quota.py`、`models/binding.py`、`models/reservation.py` | `base/common/quota/models/*` | 表名/类名未改 |
| Harness 模型 | `models/harness.py`、`models/model_price.py`、`models/service_credential.py` | `base/plugins/harness/models/*` | 表名/类名未改 |
| 脱敏 | `masking.py` | `base/common/masking.py` | 零依赖，原样搬运 |
| 上游客户端 | `upstream/{__init__,client,config,egress}.py` | `base/common/upstream/*` | 内部 import 改指共享包 |
| 网关契约 | `gateway/constants.py`、`gateway/contracts.py` | `base/common/gateway/constants.py` + 新增 | `contracts.py`：错误码、`gw:`/`harness:` 幂等前缀、`gw:lease:state:` 缓存前缀 |
| 日志 | `log.py` | `base/common/log.py` | `setup_logging()` 参数化（app_name/debug/log_dir/elk/level） |
| 配置契约 | `config.py` | 新增 | `ConfigError`/`coerce`/`_FILE` 读取/`L2Config`/`L3CommonConfig`/manifest loader |
| DB | `db.py` | 新增 | 模型模块清单、`build_tortoise_orm()`、`init_db/close_db`、asyncpg 补丁、共享字段稳定化 |

共享包共 20 个文件；`grep -R "from base\|import base" packages/common` 为空（无反向依赖）。

## 2. 留了什么（`base/`）

- 全部业务代码：`base/common/gateway/*`（service/auth/router/budget/audit/config）、`base/plugins/harness/{api,services,schemas}`、`base/common/quota/services`、`base/core/*`。
- `base/common/plugin_manager.py` 与全局单例（C4）原样保留，仅 L2 使用。
- `base/common/{cache,health,exceptions,setting}.py`、`run.py`、两个 L3 入口。
- `base/plugins/harness/manifest.json` 的元数据/routes/models/schemas/permissions 未动。

## 3. 6 组 shim 的实际落点（共 13 个文件，全部 `import *` 单来源转发）

| # | 落点 | 转发目标 |
|---|---|---|
| 1 | `base/common/masking.py` | `packages.common.masking` |
| 2 | `base/common/upstream/__init__.py`、`client.py`、`config.py`、`egress.py`（4 文件） | `packages.common.upstream.*` |
| 3 | `base/common/gateway/constants.py` | `services.gateway.common.constants`（并转发 `contracts`） |
| 4 | `base/common/model.py` | `packages.common.models.base` |
| 5 | `base/common/quota/models/{quota,binding,reservation}.py`（3 文件） | `packages.common.models.*` |
| 6 | `base/plugins/harness/models/{harness,model_price,service_credential}.py`（3 文件） | `packages.common.models.*` |

**结论：既有 `from base...` 的 import 一个都没改** —— 引用上述 shim 目标的 import 语句共 **167 处 / 145 个文件**，全部经兼容层继续生效。模型类 `__module__` 变为 `packages.common.models.*`，表名/字段不变。

## 4. import 变更数量

- `base/` 下引用共享包的代码行：**40 行 / 20 个文件**；其中 **13 个是 shim 文件**，真正改动的非 shim 文件 **7 个**：
  - `base/common/setting.py`（`get_model_list()` 改指共享模型路径 + DB 变量 env-first）
  - `base/common/log.py`（薄封装调用共享 `setup_logging`）
  - `base/common/database.py`（asyncpg 补丁改调共享实现）
  - `base/common/gateway/config.py`（`gateway_config()` 数据面 loader + `issuance_config()` 签发 loader）
  - `base/common/gateway/server.py`（L3 env 配置 + 共享模型 init）
  - `base/plugins/harness/server.py`（同上）
  - `base/plugins/harness/services/orchestration_config.py`（独立 manifest loader，不再 import plugin_manager）
- 另改动：`base/__init__.py`（清空 eager import）、`base/start.py` 与 3 个 harness 服务/插件入口（`gateway_config` → `issuance_config` 调用点，共 5 处）。

## 5. manifest 三拆

| 文件 | 归属 | config 内容 |
|---|---|---|
| `base/plugins/harness/manifest.json` | L2 | 保留 `hold_ttl_seconds/fail_closed/lock_runtime_version/session_format*/model_credential/runtime/egress/approval`，新增 `gateway_issuance`（租约签发、TTL、RPM、域名白名单、回环、对账）；删除 `gateway` 与 `orchestration` |
| `services/gateway/manifest.json` | L3 网关 | `config.gateway` 数据面全量键 |
| `services/orchestration/manifest.json` | L3 编排 | `config.orchestration` 全量键 |

- 网关：`gateway_config()` = DEFAULTS + L3 manifest + `GW_*` 环境变量；L2 签发路径 `issuance_config()` = DEFAULTS + L2 manifest。
- 编排：`orchestration_config()` = DEFAULTS + L3 manifest + `ORCH_*` 环境变量。
- `grep plugin_manager` 在网关/编排配置路径为空（`base/plugins/__init__.py` 的传递性加载见 §8 C4）。

## 6. 配置契约

- 共享 `config.py` 统一解析：`coerce()` 支持 str/int/float/bool/list/int_list/json；类型不符或必填缺失 → `ConfigError`，消息只列字段名、不含值。
- L2：继续读 `config.conf`（`load_l2_config()`），DB 变量允许环境变量覆盖（便于同机联调）。
- L3 两入口：只读环境变量；`DB_HOST/DB_NAME/DB_USER/DB_PASSWORD` 必填，`DB_PASSWORD`/`REDIS_PASSWORD` 支持 `<ENV>_FILE`；`REDIS_ENABLED=true` 时 `REDIS_PASSWORD` 必填；其余有默认值。
- 启动失败：`print("❌ [gateway|orchestration] ...")` + `SystemExit(2)`。
- L2 专有字段（JWT 密钥等）不出现在 L3 契约中；L3 契约字段见 Spec §12.5。

## 7. 三个入口启动与健康验证（实测）

| 入口 | 命令 | 结果 |
|---|---|---|
| L2 业务 API | `python run.py` | `GET /health/health` → **200** `status=healthy`，database/redis/qdrant 全 healthy |
| L3 网关 | `python -m base.common.gateway.server`（env 注入 DB/Redis） | `GET /health` → **200** `status=ok`、`deployment=standalone`、`fail_closed=true` |
| L3 编排 | `python -m base.plugins.harness.server`（env 注入 DB/Redis） | `GET /health/health` → **200** healthy；`GET /health/orchestration` → **200** `mode=proxy_l3`、`write_enabled=true` |

负向 fail-closed：去掉 `DB_PASSWORD` → `ConfigError: 缺少必填字段 [DB_PASSWORD]`，退出码 **2**，未进入运行态。

### 业务链路回归

| 场景 | 结果 |
|---|---|
| L2 → L3 代理读（`GET /v1/harness/sessions/{no}`） | **200**，返回 L3 侧数据 |
| L2 → L3 代理写（`POST /v1/harness/sessions`） | **200**，返回 `session_no`；再经 L2 读回 **200** |
| L3 编排停机时 L2 代理 | **503** `error_code=orchestration_downstream_unavailable`，L2 自身 `/health/health` 仍 200 |
| 网关租约校验 | 正确租约 **200**（真实上游补全，8 tokens）；错误 secret **401**；非法 JSON **400**；匿名 **401** |
| 网关用量记账 | `usage_record` 新增 `idem_key=gw:lse_p1verify_2026:*`，`source=gateway`；失败路径记 `gateway_error` |
| 编排预占/结算 | `POST /v1/harness/sessions/{no}/runs` → hold `orch:hr_...`；步骤/完成 **200**；`quota_reservation.counter_mode=redis`、`status=released`、`used=50` |
| L3 内部接口鉴权 | 匿名 / 用户 JWT → **401**；服务凭据 HMAC 通过 |

验证用的临时 service credential / lease / harness client 已从库中删除（含已知明文密钥）。

## 8. 过程中发现并处理的问题（Spec 未覆盖）

1. **asyncpg `UNLISTEN` 兼容补丁只在 L2**
   L2 的 `base/common/database.py` 有一套 GaussDB/openGauss 补丁；L3 入口从未加载，编排只读池释放连接时报 `FeatureNotSupportedError: UNLISTEN statement is not yet supported`，启动自检失败。已把补丁移入 `packages/common/db.py::patch_asyncpg_reset()`（单一来源），L2 改为调用共享实现，行为不变。
2. **`base/__init__.py` 的 eager import 破坏入口独立性**
   原文件 eager import `start/core/cli`，任何 `import base.common.x` 都会把 L2 装配拖进 L3 进程（并导致多进程抢同一日志文件）。已清空，保留 docstring。
3. **Tortoise 抽象基类字段浅共享（新增风险）**
   `BaseModel` 的 `id` 与 `TimestampMixin` 字段对象在子类间是共享的，最后一个定义类的 `.model` 会覆盖绑定。L2 注册全部模型因而无感；L3 网关经 C1/C2 懒加载会定义未注册的 L2 领域模型（`LLMUsageRecord`、`SystemSetting`、`User` 等），导致共享字段指向未注册类，查询抛 `default_connection ... cannot be None`。
   处理：共享 `db.py` 增加 `stabilize_shared_model_fields()`（把指向未注册类的字段重绑到已注册模型，同一 `models` app 连接）；网关在 `Tortoise.init` **之前**预热 C1/C2 模块，避免 init 之后再定义模型。
4. **网关模型清单比 P1 前收窄**
   P1 前网关 standalone 用整份 L2 `TORTOISE_ORM`；P1 收窄为共享模型 + llm 依赖后，`plan_service._user_role_codes` 查 `User` 失败并降级。为保持与 P1 前等价，`GATEWAY_DEPENDENCY_MODEL_MODULES` 补注册 `base.core.users.models.users` 与 `.rbac`（仅注册，不引入业务逻辑）。

## 9. C1–C4 现状与后续处理建议

| 编号 | 耦合点（现状） | P1 处置 | 后续建议 |
|---|---|---|---|
| C1 | `base/common/gateway/service.py::_resolve_provider_credential` → `model_credential_service` → `base.plugins.llm.models.*` + `plugin_manager` | 保留懒加载；网关注册 llm 三模型；init 前预热；共享字段稳定化 | P3 T3.5 抽 `credential_resolver` 到共享包（只读直连），网关删除对 `base.plugins.harness.services` 的 import |
| C2 | `base/common/gateway/audit.py` 懒加载 `HarnessAuditService` | 保留；init 前预热 | P3 用独立 audit writer（只写 `harness_audit_event`），或改经 L2 内部 API |
| C3 | `base/common/gateway/budget.py` → `base.common.quota.services.{plan_service,quota_service}` | 保留；补注册 `User`/`rbac` 维持 P1 前语义 | P3 改为调用 L2 内部额度 API（与编排一致），网关不再直接查 L2 认证表 |
| C4 | `plugin_manager` 全局单例；`base.plugins.__init__` 对 `base.plugins.*` 传递性加载 | 配置文件已完全不引用；代码层仍传递性加载 | P2/P3 把 `base/plugins/__init__.py` 改为惰性 `__getattr__`，或 L3 服务移出 `base.plugins` 命名空间（P4 前完成） |

## 10. 回滚方式

1. `git revert` 本阶段提交（未改 `config.conf`、未做 DB 迁移、未改表结构）。
2. 三个入口仍可用原命令启动；`packages/` 为新增目录，删除后 shim 会失效，因此回滚必须整批恢复（shim 与共享包同提交）。
3. 若只回滚 manifest：恢复 `base/plugins/harness/manifest.json` 的 `config.gateway`/`config.orchestration` 与 `gateway_config()` 旧实现即可，不涉及数据。

## 11. 遗留（不属 P1 范围）

- 验证期间创建的一次运行产生了 1 条 `quota_reservation`（hold `orch:hr_917a...`，因步骤载荷 422 未完成结算）；L2 的「配额对账/悬挂预占清理」定时任务会按 TTL 回收。
- `services/*` 目录目前只有 `manifest.json`，代码仍在 `base/` 下（P2/P3 物理迁移）。
