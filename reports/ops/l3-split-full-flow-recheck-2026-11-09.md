# L3 拆分后全流程复检报告（2026-11-09 17:48–17:56 +0800）

- 触发：用户「重新检测整个项目流程，查看是否流程是否完整，并记录」
- 方式：**端到端只读复检**（代码/配置静态核对 + 运行态 HTTP 探测 + 只读巡检脚本 + 规则单测）
- 结论：**核心 `proxy_l3` 链路完整且当前全绿（巡检 16/16 PASS）；外围存在 6 项未闭环，均不阻断观察链路，但收口前必须处理或书面接受**
- **后续修复（18:00–18:10，用户授权「修复新发现的关键问题」）**：F1 / F2 / F4 已修复并验证，F3 / F5 / F6 保持登记，详见 §6
- 观察期口径不变：起算 `2026-11-09 13:33:40 +0800`，最早收口 `2026-11-23 13:33:40 +0800`，**不提前收口、不重置计时、不回切**

---

## 1. 检测范围与边界

按「构建 → 配置 → 运行态 → 业务链路 → 指标/告警 → 留痕与收口」六层逐层核对：

| 层 | 检测对象 | 手段 |
|---|---|---|
| 构建 | `services/gateway`、`services/orchestration`、`packages/agentpanel_common`、4 份 Dockerfile | AST 解析、import 方向、COPY 契约 |
| 配置 | `deploy/l3/docker-compose.yml`、`.env` 端口契约、secrets 存在性、nginx 路由、监控栈配置 | 文件核对（敏感内容不读取） |
| 运行态 | 14 个容器、端口发布、健康端点 | `docker ps/inspect`、HTTP GET |
| 业务链路 | L2 代理、编排写主闸门、只读库、配额 Redis 基线 | 只读探测 + 代码约束核对 |
| 监控告警 | Prometheus targets/rules/alerts、Alertmanager、webhook 落盘、R6 单测 | API + `promtool test rules` |
| 留痕收口 | 观察日志 §3/§4/§5、收口预案、基线文件 | 台账核对 |

**本次明确未做**：不重启/重建容器、不改任何配置或代码、不动计量数据、不执行 `observe_check.py --append`（避免覆盖 §3 当日 17:43 台账行）、不读取 `config.conf` / `deploy/l3/secrets/*` / `.env` 中的凭据内容、不执行 T7.5 删除动作。

---

## 2. 逐层结果

### 2.1 构建与代码一致性 — PASS

| 检查 | 结果 |
|---|---|
| Python 语法（`services`/`packages`/`base`/`monitoring`/`deploy/l3/scripts`） | 829 个 `.py` 全部 `ast.parse` 通过，语法错误 0 |
| 共享包依赖方向 | `packages/agentpanel_common` 对 `services.*` / `base.*` 的反向 import **0**（已排除 `from .base import` 这类相对导入） |
| 目录布局 | `services/gateway/common/`（网关领域包）、`services/orchestration/app/`、`packages/agentpanel_common/`（跨进程内核）；无 `services/l3-gateway`、`services/l3-orchestration` 实体目录 |
| 常量单一来源 | `gateway_constants.py` 定义，`services/gateway/common/constants.py` 仅 re-export；L2/网关/编排三处均 import 共享包，编排 Dockerfile 已无需 COPY 网关包 |
| Dockerfile | `Dockerfile.l2` / `services/{gateway,orchestration}/Dockerfile` / `deploy/app/Dockerfile` 的 COPY 边界与当前目录一致；L3 两镜像 `read_only` + `/tmp` tmpfs、非 root 用户、HEALTHCHECK 齐备 |
| 悬空引用 | 运行代码中无旧路径 import；仅 1 处测试文件注释残留（见 F4） |

### 2.2 配置完整性 — PASS（附带 F2/F3）

| 检查 | 结果 |
|---|---|
| compose 服务 | `l2` / `l3-gateway` / `l3-orchestration` 三服务；`RUN_DB_MIGRATIONS=false`、编排固定 IP `172.28.0.10`、`ORCH_INTERNAL_ALLOWED_IPS` 精确匹配、`ORCH_L2_BASE_URL=http://l2:9998` |
| 端口契约 | 宿主 `127.0.0.1:9998/9999/9100`；`.env`、`.env.example`、`prepare-secrets.ps1` 三处 `GW_PUBLIC_BASE_URL=9999`、`ORCH_PUBLIC_BASE_URL=9100` 一致（旧 19999/19100 遗留已消除） |
| secrets | `db_password` / `redis_password` / `orchestration_service_secret` / `l2_config.conf` 四个文件齐备；仅核对文件名与大小，**未读取内容**；`.gitignore` 已忽略 `deploy/l3/secrets/`、`deploy/l3/.env`、`monitoring/alert-sink/` |
| 规则文件 | `monitoring/alert_rules.yml` 共 14 条：`aipaneladmin_alerts=4` + `l3_split_alerts=10`（巡检要求「≥10」）；R6 低流量保护 `and sum(rate(...401...[5m])) > 0.05` 生效 |
| 前端产物 | 宿主 `web/dist` 存在；L2 容器内 `/app/web/dist` 也存在（来自基础镜像），**但两者 hash 不一致**，见 F2 |

### 2.3 运行态 — PASS

```
agentpanel-l3-l2-1              Up (healthy)   127.0.0.1:9998->9998
agentpanel-l3-l3-gateway-1      Up (healthy)   127.0.0.1:9999->9999
agentpanel-l3-l3-orchestration-1 Up (healthy)  127.0.0.1:9100->9100
prometheus / alertmanager / alert-webhook-logger / agentredis / opengauss / qdrant / rabbitmq  Up
aipanel-app / aipanel-nginx / aipanel-dsh / aipanel-redis  Up 2 days（legacy，见 F1）
```

健康端点全部符合 runbook 基线：

| 端点 | 实测 |
|---|---|
| `9998/health/health` | 200，database / redis / qdrant 全 healthy |
| `9999/health` | 200，`status=ok`、`deployment=standalone`、`fail_closed=true` |
| `9999/health/health` | 200，database / redis healthy |
| `9100/health/health` | 200，database / redis healthy，qdrant skipped |
| `9100/health/orchestration` | 200，`mode=proxy_l3`、`write_enabled=true`，只读库 `transaction_read_only=on` 且写探测被拒 |
| `9998/api/v1/harness/runs/nope` | **401**（代理链路正常，非 503） |
| `9090/-/healthy`、`9093/-/healthy` | 200 |

### 2.4 业务链路约束 — PASS（代码级 + 只读探测）

- `base/plugins/harness/services/orchestration_proxy.py`：`proxy_l3` 才启用；下游不可达/超时统一 **503 fail-closed，不回落本进程查询、不返回空数据**；注释明确「只代理、不双写」。
- 双写闸门：`base/plugins/harness/services/service_auth.py:257` 与 `services/orchestration/app/auth.py:255` 的 `ensure_write_enabled()` 同时校验 `write_enabled` 与 `mode == proxy_l3`；写接口逐路由调用。
- 配额真账：只读巡检显示 `used` 3 键与 `observation-baseline.json` 起算基线一致（`450` / `93294` / `12`）、`held` 全 0、`quota_holds_index` 空，本次未做任何写入。
- SSE：网关 `router.py` 使用 `StreamingResponse(media_type=text/event-stream)`；`main.py` 采用纯 ASGI 指标中间件（不包装流式响应）；nginx 配置 `proxy_buffering off` + 1h 读超时。

### 2.5 指标与告警闭环 — PASS（附带 F3）

| 检查 | 结果 |
|---|---|
| Prometheus targets | `aipaneladmin` / `l3-gateway` / `l3-orchestration` / `prometheus` **up**；`pushgateway` / `node_exporter` down（容器未启动，已知白名单） |
| 规则加载 | 2 组、14 条，`health=ok` |
| R6 单测 | `promtool test rules r6_rules_test.yml` → **SUCCESS**（低流量探测不触发 / 真实凭据故障触发两场景） |
| 告警外发 | Prometheus `activeAlertmanagers=1 / dropped=0`；AM 活跃告警 2 条（均为 `ServiceUnavailable` 辅助组件）；`alert-webhook-logger` healthy |
| 落盘留痕 | `monitoring/alert-sink/alert-events.jsonl` 6 条事件，最后一条 `received_at=2026-11-09T09:41:54Z`（=17:41:54 +0800，`L3InternalAuth401RateHigh` resolved），字段 `status/alerts/group_labels/alert_count` 可解析 |
| 只读巡检 | `observe_check.py --json @17:54:05` → **verdict PASS，P16/F0/W0/S0**；`mode=proxy_l3`、代理 401、used 基线、非预期告警各项均 PASS |

### 2.6 观察期与收口条件 — 合规，未满足

- `mode=proxy_l3` 未回切；本次未改业务分支、未删旧代码、未重置计时。
- `reports/ops/l3-split-p7-observation-log.md` §3 当日行 `17:43 PASS (P16/F0/W0/S0)`；§4 第 1 周 G1-A/B/C 实测通过（待负责人签字复核），第 2 周未开始。
- §5 五项准入 **全部未勾选**：14 天计时中（第 1 天）、R1–R7 人工复核待做、每日巡检仅 1 行（需补齐 14 行）、第 2 周 G1 未做、三方签字未签。
- `reports/ops/l3-split-t75-closeout-plan.md` 状态为「预案 / 未执行」；本次未执行其中任何删除动作。

---

## 3. 发现项（按影响排序）

| 编号 | 级别 | 发现 | 证据 | 影响与建议 |
|---|---|---|---|---|
| **F1** | 中 | **对外反向代理入口与三容器部署脱节** | `deploy/nginx/conf.d/agentpanel.conf` upstream 为 `app:9998`；`aipanel-nginx:8080` → legacy `aipanel-app`（`app_default` 网络）。只读探测：`8080/health/health` 返回 `status=unhealthy`（Tortoise default 别名未初始化）、`8080/api/v1/harness/runs/nope` 返回 **404**；而当前 P7 链路直连 `127.0.0.1:9998/9999/9100` | 从 8080 进入会落到不健康的旧单体，且该入口不在 `observe_check.py` 覆盖范围。收口前须明确正式对外入口：或将 nginx upstream 指向新 L2（需改网络/重建），或书面确认 8080 仅作遗留调试入口并停止使用。**改动需授权并登记，观察期内不擅自执行** |
| **F2** | 中 | **L2 容器前端产物版本滞后** | `deploy/l3/Dockerfile.l2` 只 COPY `run.py`/`base`/`packages`/`services` 片段，**未 COPY 当前 `web/dist`**；容器内 `/app/web/dist/index.html` 来自基础镜像 `aipanel-app@sha256:aaac04f3…`（11-05 构建）。sha256：容器 `3717b5a4…` ≠ 宿主 `acc16e92…`。`/panel` 返回 200，但是旧页面 | `deploy/app/Dockerfile` 有 web-builder 阶段覆盖 dist，L3 的 L2 镜像没有等价契约；前端源码变更后新 L2 容器不会同步。建议在 `Dockerfile.l2` 增加 `COPY web/dist/ /app/web/dist/` 并在构建时确认版本一致；**涉及镜像重建，需授权** |
| **F3** | 低 | **监控栈不完整，存在常驻噪声告警** | `pushgateway` / `node_exporter` 未启动，Prometheus 两个 target down，2 条 `ServiceUnavailable` 持续 firing，被巡检 `EXPECTED_FIRING_JOBS` 白名单忽略；`alertmanager.yml` 只有本地 webhook 落盘 | 白名单会削弱「非预期告警」判据的灵敏度；外部短信/邮件值班渠道仍未接入（观察日志 §6 第 1 项）。建议运维启动辅助组件或把两个 job 从 scrape 配置移除，并明确外部通知渠道或书面接受边界 |
| **F4** | 低 | 文档残留旧路径 | `services/gateway/tests/plan_golden.py:8` 用法注释仍写 `.venv\Scripts\python.exe services\l3-gateway\tests\plan_golden.py` | 不影响运行（仅注释），复制粘贴会失败。建议改为 `services\gateway\tests\`，属低风险文档修正，仍需授权后执行 |
| **F5** | 低 | settle 用 0 播种 used 缓存 | `packages/agentpanel_common/quota/services/quota_service.py:763` 与 `:794` `await redis.set(used_key, 0, ex=ttl)` | 与 17:20 的 `used` 缓存键 WARN 相关；读取不写回、settle 可能从 0 起算。收口后改进项，观察期内不改业务代码 |
| **F6** | 流程 | 收口准入未满足 | §5 五项全未勾选、第 2 周 G1 未做、三方未签、`config.conf` 线下核对未完成 | **T7.5 不得提前执行**；保留 `mode` 开关与旧代码，按灰度方案 §2 顺延 |

> 结论口径：F1/F2 属于「交付/发布契约」缺口，F3/F4/F5 属于外围完善项，F6 是流程状态而非缺陷。**当前 `proxy_l3` 业务链路本身自洽、可运行、可观测、可留痕**，没有发现双写、回落、凭据失效或计量真账偏差。

---

## 4. 主要命令与输出索引

| 目的 | 命令（摘要） | 关键输出 |
|---|---|---|
| 语法/依赖方向 | `.venv/Scripts/python.exe` AST 遍历 | `PY_FILES_PARSED=829 SYNTAX_ERRORS=0`；`COMMON_UPWARD_IMPORTS(corrected)=0` |
| 运行态 | `docker compose -f deploy/l3/docker-compose.yml --env-file deploy/l3/.env ps` | 3/3 healthy |
| 健康端点 | 8 个 HTTP GET | 全部符合 runbook 基线，`mode=proxy_l3` |
| 只读巡检 | `observe_check.py --json` | `PASS 16/0/0/0 @17:54:05+08:00` |
| 规则单测 | `MSYS2_ARG_CONV_EXCL='*' docker run --rm -v <repo>/monitoring:/rules:ro --entrypoint promtool prom/prometheus:latest test rules /rules/r6_rules_test.yml` | `SUCCESS` |
| 告警链路 | `/api/v1/targets`、`/api/v1/rules`、`/api/v1/alerts`、`/api/v1/alertmanagers`、`/api/v2/alerts` | 3 个 L3 job up；14 条规则；2 条已知 firing；AM active=1 / dropped=0 |
| 落盘 | `monitoring/alert-sink/alert-events.jsonl` | 6 条，末条 17:41:54 +0800 |

---

## 5. 下一步建议（均需另行授权）

1. **F1 / F2**：改 nginx upstream 与 `Dockerfile.l2` 的 dist COPY 契约，会重建容器并改变运行态，需在观察窗口内登记影响评估后执行。
2. **F3**：运维决定「启动 pushgateway/node_exporter」还是「移除 job」，并落实外部值班通知渠道或书面接受。
3. **F4**：一行注释修正，可与下一次文档维护合并。
4. **F5**：列入 T7.5 收口后改进清单。
5. **F6**：自 11-10 起每日 `--append` 补齐 14 行巡检；第 2 周 G1 抽查；到期复核 R1–R7；三方签字后方可收口。

> 复检阶段（17:48–17:56）**未修改任何运行态、配置、代码或计量数据**；18:00–18:10 的授权修复见 §6。

---

## 6. 授权修复记录（2026-11-09 18:00–18:10 +0800）

用户明确选择「切换 8080 到新 L2」并授权修复关键问题。只处理 F1（对外入口）、F2（前端发布契约）、F4（文档残留）；F3 需运维决策与外部渠道、F5 观察期内不改业务代码、F6 是时间/人工准入，均保持登记状态。

### 6.1 F2：L2 镜像前端改为源码编译（已修复）

| 项 | 内容 |
|---|---|
| 变更 | `deploy/l3/Dockerfile.l2` 增加 `web-builder` 多阶段（node:20-alpine + `npm ci` + `npm run build`），`RUN rm -rf /app/web/dist`，新增 `COPY --from=web-builder /build/dist /app/web/dist` 与 chown |
| 为什么不直接 COPY 本地 dist | `web/dist` 未入库（`git ls-files` = 0）且被 `.dockerignore` 的 `**/dist/` 排除；固化本地残留会让镜像不可复现。改用与 `deploy/app/Dockerfile` 相同的构建时编译范式 |
| 构建 | `docker build --provenance=false -f deploy/l3/Dockerfile.l2 -t agentpanel-l2:local .` → 18 秒成功，Vite 5 编译 417 个 assets |
| 运行态切换 | `docker compose ... up -d --no-deps --force-recreate --wait l2` → L2 healthy；**网关 / 编排容器未动**（仍 Up 2 hours） |
| 验证 | 新镜像与运行中容器内 `index.html` sha256 均为 `acc16e92…`，与宿主当前源码产物**完全一致**（修复前容器为 `3717b5a4…`）；`9998/panel` 200；`9998/health/health` 200；`9100/health/orchestration` 仍 `mode=proxy_l3`；巡检 **PASS 16/16 @18:06:52** |
| 影响 | L2 进程内 Counter 第 4 次归零（同 15:50 / 16:08 / 16:30 口径，`rate()` 窗口注意）；Redis 计量真账与基线未动 |

### 6.2 F1：对外 8080 切到新 L2（已修复）

**新发现的前提**：运行中的 `aipanel-nginx` 不是本仓库 compose 起的，其 compose 来源为
`D:\programs\fastapi\aipaneladmin\deploy\app\docker-compose.yml`，配置挂载自该目录的
`deploy/nginx/conf.d/`。因此只改本仓库配置不会生效。

| 步骤 | 结果 |
|---|---|
| 备份 | 外部 `aipanel.conf` → `aipanel.conf.bak-20261109-1807` |
| 网络热接入 | `docker network connect --alias agentpanel-l2 app_default agentpanel-l3-l2-1`；L2 现同时在 `agentpanel-net`（别名 `l2`）与 `app_default`（别名 `agentpanel-l2`），**未重启任何容器** |
| 配置 | 外部 `aipanel.conf` upstream `server app:9998` → `server agentpanel-l2:9998`；`nginx -t` 通过，`nginx -s reload` 成功 |
| 验证 | `8080/health/health` **200 healthy**（原 `unhealthy`）、`8080/api/v1/harness/runs/nope` **401**（原 404，证明走 `proxy_l3` 代理）、`8080/panel` 200、`8080/` 200 |

配套文档：本仓库 `deploy/nginx/conf.d/agentpanel.conf` 头部加 F1 说明（**保留 `app:9998` upstream 值**，因为该文件属 legacy 单体栈，改值会让本仓库默认部署无法解析；混用两套部署才是原问题）；`reports/ops/l3-split-p7-runbook.md` 新增 §4.1 记录命令、验证基线与持久化警告。

> **持久化注意**：网络别名是容器级临时状态，**L2 容器一旦重建就会丢失**，8080 会退回 502。重建后须重跑 §4.1 第 1 步。刻意不把 `app_default` 写进 `deploy/l3/docker-compose.yml`，避免三容器部署硬依赖另一套 legacy compose 的网络。

### 6.3 F4：注释旧路径（已修复）

`services/gateway/tests/plan_golden.py:8` 的 `services\l3-gateway\tests\` → `services\gateway\tests\`，仅注释，不影响运行。

### 6.4 修复后复核与边界

- 三业务容器 healthy、7 个关键端点（8080 + 9998/9999/9100）全部符合基线；巡检 **PASS 16/16 (P16/F0/W0/S0)**。
- 未改 `mode`、未删旧代码、未动计量数据、未读敏感配置内容、未提前收口、**不重置计时**（起算 13:33:40 / 最早收口 2026-11-23 13:33:40 不变）。
- F3（pushgateway / node_exporter 未启动、外部值班通知渠道）、F5（`_settle_redis_counters` 0 播种）、F6（五项准入未满足）仍未闭环，按原报告建议处理。
- legacy `aipanel-app` / `aipanel-nginx` / `dsh` / `redis` 容器保持运行，未停止、未删除；8080 已不再把流量送给 unhealthy 的旧单体。
