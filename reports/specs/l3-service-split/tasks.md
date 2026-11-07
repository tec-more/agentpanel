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

| ID | 任务 | 验收 |
|---|---|---|
| T1.1 | 建包骨架：`pyproject.toml`、版本、`agentpanel_common` 命名空间 | `pip install -e packages/agentpanel_common` 成功 |
| T1.2 | 迁 `platform/*`：log、exceptions、response、cache、health、masking、security（去 `config.conf`/`plugin_manager` 依赖，构造参数注入） | 单测通过；无 `plugin_manager` import |
| T1.3 | 迁 `upstream/*`（client/config/egress），L2 改为 re-export | L2 LLM 插件与网关导入同一实现；单测通过 |
| T1.4 | 迁 `models/harness.py`、`model_price.py`、`service_credential.py`、quota 三模型 | L2 原路径保留 shim；`Tortoise.describe_model()` 与 T0.3 契约一致 |
| T1.5 | 迁 `domain/*`（run/event/policy/policy_rule/approval/audit/pricing）与 `quota_backend` 接口 | 域单测通过；L2 侧行为不变（回归脚本全绿） |
| T1.6 | 抽 `credential_resolver`（只读解析/解密），L2 保留 CRUD/掩码读 | 解析结果与现状一致；无明文日志 |
| T1.7 | `env.py`：环境变量配置模型（§5.2/5.3/5.4），含必填/默认/校验 | 缺失必填项启动失败的单测 |
| T1.8 | `db.py`：Tortoise 配置工厂（仅建连接，不迁移、不建表） | 以 env 连接当前库成功；不含 aerich/migrations |
| T1.9 | 契约测试：模型对比 `contracts/db_schema.json`；共享包版本变更需升版校验 | CI 脚本可失败演示（改列不升版 → 失败） |
| T1.10 | L2 兼容层收口：`base/*` 改为 import 共享包，不改对外路由 | 三进程启动、health、G1 全绿 |

**阶段出口**：共享包可独立构建 wheel；L2 功能等价；模型单一来源生效。

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

| ID | 任务 | 验收 |
|---|---|---|
| T3.1 | 建工程骨架：`app/main.py`、lifespan（Tortoise + Redis 预热）、uvicorn 入口 | 本地 `.venv` 可启动 9999 |
| T3.2 | 迁 `gateway/app.py`、`router.py`、`auth.py`、`lease_auth.py`、`service.py` | 租约校验/转发/记账行为不变 |
| T3.3 | 迁 `budget.py`、`audit.py`、`logging.py` | 预算/并发/额度耗尽/审计来源 `gateway` 不变 |
| T3.4 | 重写 `gateway/config.py`：env 配置 + 原 fail-closed 规则；删除 embedded/runtime 分支 | 非法配置启动失败单测 |
| T3.5 | 凭据解析改共享 `credential_resolver`（无 L2 运行时依赖） | 停 L2 后网关仍可转发（mock provider） |
| T3.6 | 新增/补齐 `/health/health`（DB/Redis 子项），保留 `/health` | 两项探针真实反映依赖 |
| T3.7 | 移除网关对 `plugin_manager`、manifest、`base.common.gateway` 旧路径的依赖 | `grep plugin_manager services/l3-gateway` 为空 |
| T3.8 | 单测：租约签发→调用、吊销、RPM/并发、预算耗尽、上游重试 | 全部通过 |
| T3.9 | 本地联调：租约→网关→mock upstream + 记账 | `usage_record` 唯一、`gw:lease:state` 存在 |

**阶段出口**：9999 可独立启动；L2 仍保留 embedded 网关代码（用于回滚）。

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
| T6.1 | 基础健康：两容器 healthy、9100 `/health/health`、9999 `/health`（建议含 `/health/health`） | Spec §8.1 全过 |
| T6.2 | 依赖连通：PG 只读/写拒绝、Redis 别名、schema 断言正/负向 | §8.2 全过 |
| T6.3 | 业务链路：L2→L3 代理读、L3 停时 503、租约→网关、预占/结算 | §8.3 全过 |
| T6.4 | G1 20 并发复跑（容器形态） | A/B/C 三项数值与单仓基线一致 |
| T6.5 | 容器安全：非 root、无密钥文件、镜像层扫描、端口回环 | §8.4 全过 |
| T6.6 | 故障注入：Redis down、L2 down、错误密钥、`write_enabled=false` | 行为符合 fail-closed |
| T6.7 | 重启语义：网关重启后 8s 缓存失效；吊销延迟记录 | 结论写入验收记录 |
| T6.8 | 验收报告：逐项数值、截图/命令输出、遗留问题 | `reports/ops/l3-split-acceptance.md` |

**阶段出口**：所有硬项通过，才允许把 L2 旧 L3 代码删除（P4 与 P5/P6 顺序可按灰度调整，但删除必须在容器验收通过后）。

> 实施顺序建议：P0 → P1 → P2/P3（可并行）→ P4（先保留旧代码做 A/B，验收后删除）→ P5 → P6 → 灰度 → 删除收口。若采用“先删后验”，回滚成本显著上升，不推荐。

---

## P7 文档、灰度与回滚演练

| ID | 任务 | 验收 |
|---|---|---|
| T7.1 | 更新运维 runbook：容器启停、secret 轮换、网络附加、日志 | 可按文档从零拉起 |
| T7.2 | 回滚演练：`pre-l3-physical-split` 起回单仓三进程 | 30 分钟内恢复、health 全绿 |
| T7.3 | 灰度方案：L2 `mode=proxy_l3` 保留期、切流比例、回切条件 | 有明确阈值与责任人 |
| T7.4 | 监控/告警：两容器 health、5xx、预占失败、租约缓存命中 | 指标可见 |
| T7.5 | 收口：删除灰度开关与旧代码、更新架构图 | 仓库无 L3 运行代码残留 |

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
