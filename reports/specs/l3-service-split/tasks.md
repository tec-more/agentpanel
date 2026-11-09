# Tasks：L3 编排与网关物理拆分（Docker 交付）

> 配套 spec：`reports/specs/l3-service-split/spec.md`（下称 Spec）。
> 本文件只做任务拆解；评审通过前不改代码、不建容器。
> 约束：每个阶段结束都必须保持“可回滚、可验证”，不出现半开状态。

## 决策门（先于 P1）

| ID | 决策 | 推荐 | 阻塞任务 |
|---|---|---|---|
| D1 | 仓库形态：monorepo 子目录 vs 独立仓库 | monorepo 子目录 | P1、P2、P3 |
| D2 | 共享包抽取方式；模型凭据解析路径（共享 resolver vs 内部 API） | 共享包 + 共享 resolver（只读直连） | P1 |
| D3 | 镜像形态：两个镜像 vs 单镜像双入口 | 两个镜像 | P5 |
| D4 | Redis 接入：附加 `agentpanel-net` + 别名 vs 其他 | 网络别名 | P5、P6 |
| D5 | L2→L3 代理保留期与 `internal_allowed_ips` 放行网段 | 迁移期保留代理，灰度后删除 `mode` | P4、P5 |
| D6 | 密钥注入：compose secrets vs 纯环境变量 | compose secrets（开发用 `.env`） | P5 |

---

## P0 基线冻结与契约准备（不改运行代码）

| ID | 任务 | 产出 | 验收 |
|---|---|---|---|
| T0.1 | 冻结拆分前基线：创建 `pre-l3-physical-split` tag | tag | `git tag -l` 可见；工作区干净（允许已知未提交改动另行处理） |
| T0.2 | 生成路由清单：L3 编排（/internal/v1/harness/*、/v1/harness/* 中由 L3 提供者）、L3 网关（/health、/chat/completions） | `contracts/routes.md` | 每条路由标注方法/鉴权/归属 |
| T0.3 | 生成 DB schema 契约 `contracts/db_schema.json`（表/列/类型/索引） | 契约文件 + 生成脚本 | 与当前库对比一致 |
| T0.4 | 记录配置基线：`config.gateway` / `config.orchestration` 全部键与默认值 | `contracts/config.md` | 与 Spec §5 对齐 |
| T0.5 | 建立回归脚本基线（G1 并发脚本、health/lease/预占检查） | `tests/l3_split/*.py`（只读/测试用） | 当前单仓形态全部通过 |

**阶段出口**：Spec 决策 D1–D6 至少 D1/D3/D4/D5 已确认；基线全套回归可重复执行。

---

## P1 共享包抽取（`packages/agentpanel_common`）

> P1 范围为 Spec §12 已冻结版本：**只做搬运 + 兼容 + manifest 三拆 + 配置契约 + 三入口验证**；
> `domain/*`、`credential_resolver`、`pyproject.toml/wheel` 推迟到 P2/P3/P5（Spec §12.2、§12.8）。

| ID | 阶段 | 任务（精确文件见 Spec §12） | 验收（每阶段完成即报告） |
|---|---|---|---|
| ✅ T1.1 | 契约与共享包 | 建 `packages/__init__.py`、`packages/agentpanel_common/{__init__,config,log,db}.py`、`masking.py`、`upstream/*`、`gateway/{constants,contracts}.py`、`models/{base,quota,binding,reservation,harness,model_price,service_credential}.py`；共享包内禁止 import `base` | 导入成功；`grep -R "from base\|import base" packages/agentpanel_common` 为空；`ConfigError` 缺失/类型错单测通过 |
| ✅ T1.2 | 兼容层与 import 修正 | 6 组 `base/*` shim（Spec §12.3）；`base/common/setting.py::get_model_list()` 改指共享模型路径；`base/common/log.py` 改为调用共享 `setup_logging()` | 原 167 处 import 无需改；`HarnessRun.__module__` 为 `packages.agentpanel_common.models.harness`；`describe_model()` 表名不变 |
| ✅ T1.3 | manifest 拆分 | 三份 manifest（Spec §12.4）；`base/common/gateway/config.py` 拆出 `gateway_config()`（共享 loader，读 `services/l3-gateway/manifest.json` + env）与 `issuance_config()`（L2 manifest `config.gateway_issuance`）；`orchestration_config.py` 改共享 loader；`gateway_lease_service.py` 签发字段改 `issuance_config()` | `grep plugin_manager` 在网关/编排配置路径为空；两入口配置文件互不读取 |
| ✅ T1.4 | L2 启动验证 | `.venv\Scripts\python.exe run.py` → 9998 | `GET /health/health` → `status=healthy`；原有路由/插件加载正常 |
| ✅ T1.5 | 网关启动验证 | 注入 `DB_*`/`REDIS_*` 后 `-m base.common.gateway.server` → 9999 | `GET /health` → `status=ok`、`deployment=standalone`、`fail_closed=true`；负向缺 `DB_PASSWORD` 退出码 2 |
| ✅ T1.6 | 编排启动验证 | 注入 `DB_*`/`REDIS_*`/`ORCHESTRATION_SERVICE_SECRET` 后 `-m base.plugins.harness.server` → 9100 | `GET /health/health`、`/health/orchestration` healthy；只读写拒绝自检通过 |
| ✅ T1.7 | 业务链路回归 | L2→L3 代理读写、租约→网关→记账、编排预占/结算（L2 内部 API） | 代理读返回 L3 数据（L3 停 → 503）；`usage_record` 唯一且 `gw:` 幂等键；`quota_reservation.counter_mode=redis` |
| ✅ T1.8 | 差异清单报告 | `reports/ops/l3-split-p1-report.md` | 搬走/留下/import 变更面/health 证据/耦合点 C1–C4/回滚方式齐全 |

**阶段出口**：三入口均可独立启动且 `/health` 正常；L2 代理与网关记账、编排预占结算链路全部通过；模型单一来源生效；无 `plugin_manager` 在 L3 配置路径残留。

**P1 不包含（顺延）**：`domain/*` 下沉、`credential_resolver` 抽取（阻塞项 C1）、`pyproject.toml`/editable/wheel 打包、`services/l3-*` 物理目录迁移、Docker。

---

## P2 L3 编排独立工程（`services/l3-orchestration`）

| ID | 任务 | 验收 |
|---|---|---|
| T2.1 | 建工程骨架：`app/main.py`、lifespan、uvicorn 入口、固定 `l3` 角色 | 本地 `.venv` 可启动 9100 |
| T2.2 | 迁 `api/l3/business_router.py`、`api/l3/write_router.py` | 路由清单与 T0.2 一致；鉴权行为不变 |
| T2.3 | 迁 `api/internal/router.py` + 服务凭据验签中间件（共享 `security/signing.py`） | whoami/自检通过；错误密钥 401 |
| T2.4 | 迁 `readonly_db.py`（只读连接 + 写拒绝） | 写语句被拒自检通过 |
| T2.5 | 迁 `l2_quota_client.py`、`l3_client_auth.py`、`l3_touch.py` | 指向 L2 的 reserve/settle/release、touch 成功 |
| T2.6 | 重写配置：`orchestration_config` → `env.py`；`host=0.0.0.0` + `allow_remote_bind` | fail-closed 单测：缺 secret、非法 host、非 http base_url 均拒绝启动 |
| T2.7 | 加 `schema_check.py` 启动断言（表/列/最低版本） | 伪造版本 → 启动失败；正常库 → 通过 |
| T2.8 | 移除 L3 对 `plugin_manager`、`base.plugins.harness.manifest` 的全部依赖 | `grep plugin_manager services/l3-orchestration` 为空 |
| T2.9 | 单测：策略三档、审批联动、额度 503 fail-closed、状态机契约 | 全部通过 |
| T2.10 | 本地三进程联调：L2(9998) + 新 L3(9100) + 网关(9999) | 现有回归脚本全绿 |

**阶段出口**：9100 可在无业务插件机制下独立启动；L2 仍保留原 L3 代码（用于对照/回滚）。

---

## P3 L3 网关独立工程（`services/l3-gateway`）

> 实施规格：`spec.md` §13（含依赖取舍 G1–G10、决策 D-P3-1..5、验证矩阵 V1–V13、对拍 P1–P14、回滚步骤）。
> **决策结果（用户已确认）**：D-P3-1=A 共享 Redis client / D-P3-2=B 配额域迁共享+双解析器对拍 / D-P3-3=A llm 模型迁共享 / D-P3-4=A 租约校验与吊销共享化 / D-P3-5=A L2 网关 12 模块全部 shim。

| ID | 任务 | 验收 |
|---|---|---|
| ✅ T3.1 | 建工程骨架：`run.py`、`app/{config,http,health,logging,constants,app,main}.py`，lifespan（Redis configure + Tortoise + 预热） | `GW_PORT=9990` 可启动；`/health`、`/health/health` 正常；旧 9999 不受影响 |
| ✅ T3.2 | 迁 `gateway/{router,auth,audit,service,app}.py` 到 `app/`，import 改共享包 | 租约校验/转发/记账行为不变 |
| ✅ T3.3 | 迁 `gateway/{budget,lease_auth,constants}.py`；`budget` 改共享模型/cache/配额域；`lease_auth` 薄封装共享 `domain/lease_auth.py` | 预算/并发/额度耗尽/自动吊销/审计来源 `gateway` 不变 |
| ✅ T3.4 | 重写 `app/config.py`：数据面 `DEFAULTS` + `GW_*` 覆盖 + 原 fail-closed 规则；删除 issuance/runtime/embedded 分支 | V2 负向全部退出码 2 |
| ✅ T3.5 | 抽共享 `domain/credential_resolver.py`；llm 模型迁共享包；L2 `model_credential_service` 改 shim + `configure_l2()` | 网关不 import `base.plugins.harness`；停 L2 仍可转发（假 provider） |
| ✅ T3.6 | 抽共享 `cache.py`（`RedisCache` + 显式 `configure`），`base/common/cache.py` 改 shim | L2 行为不变；网关不读 `config.conf` |
| ✅ T3.7 | 抽共享 `domain/lease_auth.py` 与 `domain/lease_revoke.py`；L2 `lease_auth` shim、`gateway_lease_service.revoke_internal` 委托 | L2 签发/吊销路径引用不变；网关去 `base.plugins.harness.services` |
| ✅ T3.8 | `grep plugin_manager|manifest 旧路径|base.common.gateway` in `services/l3-gateway` | 为空 |
| ✅ T3.9 | 单测/脚本按 V3–V11：鉴权、白名单、剥离、SSE 逐字节、usage 唯一、预算/并发、Redis 缓存、DB 兜底、审计 | 全部通过，且只用本地假 provider |
| ✅ T3.10 | 等价对照 V12：同一租约/请求分别打 9990（新）与 9999（旧） | 状态码/响应体/记账字段一致 |
| ✅ T3.11 | 切换 9999：停旧进程 → 启新入口；报告阶段 1/2/3 | `/health` 正常；`gw:lease:state` 生成；回滚命令可用 |
| ✅ T3.12 | 清理与回滚说明；P4/P5 待办登记（T4.11 等） | 报告含可执行回滚动作；临时假 provider/脚本清理 |

**阶段出口**：9999 可独立启动（新入口）；L2 仍保留 embedded 网关代码（用于回滚）；任一验证失败可按 §13.6 在分钟级回滚。

---

## P4 L2 删除边界与内部 API 收口

| ID | 任务 | 验收 |
|---|---|---|
| T4.1 | 删除 `base/plugins/harness/server.py`、`api/l3/*`、`api/internal/*` | L2 不再暴露 9100 入口 |
| T4.2 | 删除 embedded 网关挂载（`start.py` / `app_wrapper.py` 的 `/v1/gateway`） | L2 启动无网关路由；`base/common/gateway` 不再被 L2 import |
| T4.3 | 删除 `orchestration_runtime` 角色分支与 `quota_backend` 的 L3 分支 | L2 直调 `QuotaService`；无 `is_l3()` |
| T4.4 | 保留并验证 `l2_quota_router` / `l2_touch_router` | L3→L2 内部 API 全通；401/幂等行为不变 |
| T4.5 | 保留 L2 管理面：租约签发/策略 CRUD/模型凭据/出网策略/看板 | 管理台 6 页面可用（登录 + 列表/详情） |
| T4.6 | `dashboard_service` 去 L3 运行时依赖（只读表/SQL） | 看板数据与拆分前一致 |
| T4.7 | 删除 `orchestration.mode`（或按 D5 保留灰度开关，明确删除条件） | `mode` 无引用/仅灰度路径引用 |
| T4.8 | 删除 L3 专用依赖（aerich 保留给 L2；L3 相关包不进 L2 依赖锁定） | 依赖清单无冗余 |
| T4.9 | 回归：L2 单独启动、三进程（新 L3）联调、G1 | 全绿 |
| T4.10 | 重构 `base/plugins/__init__.py` 传递性加载与 `plugin_manager` 单例为显式注册（C4 最后一项，P2 阶段已确认编排侧不再触达） | L2 插件装配无 import 副作用；`plugin_manager` 无全局单例隐式创建；L2 启动与插件路由不变 |
| T4.11 | 清理过渡层：确认 L2 无外部引用后删除 `base/common/quota/services/{quota_service,plan_service,plan_resolver}.py` 与 `metrics.py` 的 shim；保留路径至 P4 删除边界 | `grep "base.common.quota.services" --include=*.py` 仅剩 P4 计划内引用 |
| T4.12 | 随 T4.2 删除 `base/common/gateway/*` shim；删除前确认 `gateway_lease_service` 仅引用 `issuance_config` 与共享 `lease_auth` | L2 无 `base.common.gateway` 运行引用 |
| T4.13 | 网关 `usage_record` 成本计算落地（见 Spec §14）：6 位舍入、缺价记 0 + `missing_price`、归零标记 `rounded_to_zero` 并存未舍入值 | 假 provider 构造 usage 验证正常计价/缺价/归零三分支；三服务 healthy |

> T4.10 来源：P2 阶段 3 遗留决策，用户确认延后至 P4 删边界时一并处理，本阶段不动代码。
> T4.11/T4.12 来源：P3 决策 D-P3-2=B / D-P3-5=A 产生的过渡层收口。

**阶段出口**：业务仓库不含 L3 运行代码；L2 仍可独立运行；回滚 tag 可用。

---

## P5 Docker 交付

| ID | 任务 | 验收 |
|---|---|---|
| T5.1 | `.dockerignore`（排除 `.venv`、`web`、`reports`、`config.conf*`、`.env*`、`secrets/`、`migrations`） | 构建上下文不含敏感文件 |
| T5.2 | `services/l3-orchestration/Dockerfile`：多阶段、非 root、HEALTHCHECK | 构建成功；`id -u` ≠ 0 |
| T5.3 | `services/l3-gateway/Dockerfile`：同上 | 同上 |
| T5.4 | `requirements.lock`：共享包 wheel + 服务依赖精确锁定 | 可离线安装；无编译期依赖 |
| T5.5 | `deploy/l3/docker-compose.yml`（Spec §6.4）：两服务 + secrets + 固定网段 | `docker compose config` 校验通过 |
| T5.6 | Redis 网络接入：`agentpanel-net` + `docker network connect agentredis` | 容器内 `PING agentredis` 成功；`aipanel-redis` 无变化 |
| T5.7 | secrets 目录与 `.env.example`；`.gitignore` 覆盖 `deploy/l3/secrets/*` | secret 不入库 |
| T5.8 | 宿主 port 发布仅 `127.0.0.1`；`read_only` + `tmpfs` | `docker port` 无 `0.0.0.0` |
| T5.9 | 镜像安全扫描：层历史/文件扫描关键词 | 无 `requirepass`/secret/明文密码 |

**阶段出口**：两个镜像可构建；compose 可拉起；容器 healthy。

---

## P6 验证与验收

| ID | 任务 | 验收 |
|---|---|---|
| ✅ T6.1 | 基础健康：三容器 healthy、9100 `/health/health`、9999 `/health` 与 `/health/health` | Spec §8.1 全过；`9999/health/health` 已实现 |
| ✅ T6.2 | 依赖连通：PG 只读/写拒绝、Redis 别名、schema 断言正/负向 | §8.2 全过；负向以 `ORCH_SCHEMA_MIN_VERSION=2` 启动失败（退出码 3）通过 |
| ✅ T6.3 | 业务链路：L2→L3 代理读、L3 停时 503、租约→网关、预占/结算 | §8.3 全过 |
| ✅ T6.4 | G1 20 并发复跑（容器形态） | A/B/C 三项数值与单仓基线一致 |
| ✅ T6.5 | 容器安全：非 root、无密钥文件、镜像层扫描、端口回环 | §8.4 全过 |
| ✅ T6.6 | 故障注入：Redis down、L2 down、错误密钥、`write_enabled=false` | 行为符合 fail-closed（P6 当次注入；P7 未重复破坏性注入） |
| ✅ T6.7 | 重启语义：网关重启后 8s 缓存失效；吊销延迟记录 | 结论写入验收记录：缓存实际由 Redis 承载，非进程内存 |
| ✅ T6.8 | 验收报告：逐项数值、截图/命令输出、遗留问题 | `reports/ops/l3-split-acceptance.md` |

**阶段出口**：所有硬项通过，才允许把 L2 旧 L3 代码删除（P4 与 P5/P6 顺序可按灰度调整，但删除必须在容器验收通过后）。

> 实施顺序建议：P0 → P1 → P2/P3（可并行）→ P4（先保留旧代码做 A/B，验收后删除）→ P5 → P6 → 灰度 → 删除收口。若采用“先删后验”，回滚成本显著上升，不推荐。

---

## P7 文档、灰度与回滚演练

| ID | 任务 | 验收 |
|---|---|---|
| ✅ T7.1 | 更新运维 runbook：容器启停、secret 轮换、网络附加、日志 | `reports/ops/l3-split-p7-runbook.md`；含从零拉起步骤 |
| ✅ T7.2 | 回滚演练：`pre-l3-physical-split` 起回单仓三进程 | 两条路径均实测：容器旧端口恢复 18.0s、宿主三进程约 33s；恢复后三容器 healthy（见 `reports/ops/l3-split-p7-report.md`） |
| ✅ T7.3 | 灰度方案：L2 `mode=proxy_l3` 保留期、切流比例、回切条件 | `reports/ops/l3-split-p7-grayscale.md`；保留期 14 天、部署级二元切换、阈值与角色责任人齐全 |
| ⏳ T7.4 | 监控/告警：两容器 health、5xx、预占失败、租约缓存命中 | **未实现**：L3 网关/编排无 `/metrics`，仅有 HEALTHCHECK 与 `/health*`；5xx/预占失败/缓存命中未暴露，无告警规则（已列入验收报告已知限制） |
| ⏳ T7.5 | 收口：删除灰度开关与旧代码、更新架构图 | **未开始**：旧编排代码与 `mode` 开关仍在仓库，架构图未改；需 T7.4 补齐并完成 14 天观察期后执行 |

---

## 依赖关系（简图）

```
D1..D6 ─▶ P0 ─▶ P1 ─┬─▶ P2 ─┐
                     └─▶ P3 ─┴─▶ P5 ─▶ P6 ─▶ 灰度 ─▶ P4 收口 ─▶ P7
```

## 验收硬门槛（任一不满足不得收口）

1. 两容器 healthy，且 9100/9999 探针真实反映 DB/Redis；
2. 镜像内无密钥文件、非 root、宿主仅回环发布；
3. L2→L3 代理与 L3→L2 额度 API 全链路通过；
4. G1 20 并发在 Redis 路径全部通过；
5. 回滚演练成功且数据无迁移；
6. 业务仓库删除 L3 运行代码后，L2 独立启动与三进程联调均通过。
