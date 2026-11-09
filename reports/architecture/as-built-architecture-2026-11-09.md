# 现状架构说明（As-Built）：L3 物理拆分后

- 日期：2026-11-09
- 状态：**代码现状快照**，非目标态设计稿
- 依据：2026-11-09 工作区代码、`deploy/l3/docker-compose.yml`、`monitoring/`，以及 P6 验收与 T7.4 实测报告
- 关联：`reports/specs/l3-service-split/spec.md`、`reports/ops/l3-split-acceptance.md`、`reports/ops/l3-split-p7-metrics.md`、`reports/ops/l3-split-p7-observation-log.md`

> **边界声明（重要）**
> 1. 本文是**新增文档**，**不修改、不替换** `reports/architecture/agentpanel-architecture.mmd`、`agentpanel-architecture.html` 与 `target-architecture-local-agent.md`。那三份是拆分前的目标态/方向稿资产。
> 2. 正式「更新架构图」属于 T7.5，受 14 天灰度观察期约束（起算 2026-11-09 13:33:40 +0800，最早 2026-11-23 收口）。本文在观察期内提供**可读的现状说明**，不构成 T7.5 的执行，也不改 tasks/checklist 中 T7.5 的状态。
> 3. 判定以**代码为准**。旧图与 spec 中个别「宿主进程」「目标态」表述已过时，差异汇总见 §10。

---

## 1. 结论先行

单仓（monorepo）多进程：一个共享代码包 + 三个独立容器。**控制面留在 L2，模型数据面与编排面各拆一个进程**，三者共享同一套 PostgreSQL 与 Redis，但**数据库迁移只由 L2 执行**；在 `mode=proxy_l3` 下，客户端的编排请求经 L2 只代理到 L3 编排，额度写主仍回呼 L2 内部 API，从而避免同一 run 双写。Prometheus 作为旁路抓取三个进程的 `/metrics`。

## 2. 分层总览

```mermaid
flowchart TB
  C["L1 桌面端 / dsh 客户端<br/>本机执行工具与文件操作"]
  subgraph SVC["服务层 · 三个独立容器（端口均绑定 127.0.0.1）"]
    direction LR
    L2["L2 主应用 :9998<br/>控制面 / 唯一迁移方"]
    GW["L3 网关 :9999<br/>数据面 / SSE 透传"]
    OR["L3 编排 :9100<br/>会话·run·审批·额度"]
  end
  CM["共享代码 packages/agentpanel_common<br/>models / gateway / quota / db / domain / upstream / prometheus / l3_metrics"]
  subgraph ST["数据与外部依赖"]
    direction LR
    PG[("PostgreSQL :15432")]
    RD[("Redis :6379")]
    EXT["上游 api.deepseek.com<br/>域名白名单"]
  end
  PM["Prometheus :9090<br/>抓取 /metrics · 2 组 14 条规则"]

  C -->|"控制面 /api/v1/harness/*"| L2
  C -->|"数据面 Bearer dgw.*"| GW
  L2 -->|"proxy_l3 只代理、不双写"| OR
  OR -.->|"HMAC 服务凭据回呼额度"| L2
  L2 -.->|import| CM
  GW -.->|import| CM
  OR -.->|import| CM
  L2 --> PG
  L2 --> RD
  OR --> PG
  OR --> RD
  GW --> PG
  GW --> RD
  GW -->|"白名单 HTTPS + SSE"| EXT
  PM -.->|"抓取 /metrics"| L2
  PM -.-> GW
  PM -.-> OR
```

共享包是**唯一来源**：三个镜像各自 `COPY packages/`（未打 wheel，`run.py` 注入 `sys.path`），导入名统一 `packages.agentpanel_common.*`；L2 通过 `base/*` shim 兼容 re-export，共享包禁止反向 `import base.*`。这是拆分能成立的依赖前提。

## 3. 三个服务

| 服务 | 代码入口 | 容器启动命令 | 端口 | 健康端点 | 职责 |
|---|---|---|---|---|---|
| **L2 主应用** | `base/start.py` 建 app → `base/app_wrapper.py` 加 `/api` 前缀 → `run.py` 起 uvicorn | `CMD ["python","run.py"]`（`deploy/l3/Dockerfile.l2:56`） | `9998` | `/health/health`、`/api/health/health` | 租约签发、策略/凭据/出网策略 CRUD、看板与报表、对 L3 暴露内部额度与心跳 API；**唯一执行 aerich 迁移的进程**；`/metrics`（`start.py:733`） |
| **L3 网关** | `services/l3-gateway/run.py` → `app/main.py` | `CMD ["python","services/l3-gateway/run.py"]` | `9999` | `/health`、`/health/health`、`/health/live` | `dgw.*` 虚拟 key 鉴权、provider 转发 SSE 透传、`usage_record` 记账、预算/并发/额度耗尽预检 |
| **L3 编排** | `services/l3-orchestration/run.py` → `app/main.py` | 同构；compose 覆盖 command 注入 secret 后 `exec run.py`（`docker-compose.yml:134-137`） | `9100` | `/health/health`、`/health/live`、`/health/ready`、`/health/orchestration` | 会话/run/step 编排、策略评估、审批、审计；额度**不自己写主**，经 L2 内部 API |

编排的路由前缀：`/v1/harness`（`api/business.py:24` 读、`api/write.py:32` 写）、`/v1/harness/approvals`（`api/approval.py:13`）、`/internal/v1/harness`（`api/internal.py:11`，含 `/whoami`）。`/metrics` 不纳入业务鉴权（`main.py:167-172`）。

### `orchestration.mode` 二元灰度开关

| 取值 | 写主 | 行为 |
|---|---|---|
| `l2` | L2 本地 | 维持 L2 行为；L3 在 `mode != proxy_l3` 时拒绝写（409），避免同一 run 双写 |
| `proxy_l3`（当前） | L3 编排 | L2 对已迁移编排路径**只代理、不双写**；下游不可达统一 503，不回落本进程 |

校验仅允许这两个值（`services/l3-orchestration/app/config.py:122-123`）。这是**部署级整机二元切换**，没有按比例/按租户切流；切流与回切都是整机行为。

## 4. 共享包 `agentpanel_common` 子系统

| 模块 | 职责 |
|---|---|
| `config.py` | INI / ENV / `*_FILE` 契约，缺失即 fail-closed（退出码 2） |
| `db.py`、`models/`、`domain/` | Tortoise 连接工厂、模型单一来源、run/event/policy/approval/audit/pricing 等领域对象 |
| `gateway/`（13 模块） | `router.py`（`/health`、`/chat/completions`）、`lease_auth.py`（租约缓存）、auth / budget / audit / service / runtime / contracts / constants / lease_revoke 等 |
| `quota/` | `quota_service.py`（预占/结算/释放）、`plan_service.py`、`plan_resolver.py`、`metrics.py` |
| `upstream/` | `client` / `config` / `egress`，强制出网域名白名单，无绕过开关 |
| `security.py` | HMAC-SHA256 服务凭据签名，L2 与 L3 共用 |
| `prometheus.py` | 共享 registry、HTTP 指标与 `metrics_endpoint`（L2 使用） |
| `l3_metrics.py` | T7.4 新增：纯 ASGI HTTP 中间件、业务计数器、`/metrics` 端点构造（两个 L3 服务使用） |
| `cache.py` / `log.py` / `masking.py` | Redis 缓存封装、日志、脱敏 |

**为什么用纯 ASGI 中间件**：`gateway/router.py` 的 `/chat/completions` 用 `StreamingResponse` 边读边转发；共享包里的 `PrometheusMiddleware` 基于 `BaseHTTPMiddleware`，会包装响应并可能缓冲 SSE。T7.4 因此新增 `L3HttpMetricsMiddleware`（纯 ASGI），并用 `scope["path_params"]` 折叠动态段控制标签基数。

## 5. 运行时链路

### 5.1 编排链路（`mode=proxy_l3`）

```mermaid
sequenceDiagram
  participant C as 客户端
  participant L2 as L2 :9998
  participant OR as L3 编排 :9100
  participant Q as L2 内部额度 API
  participant R as Redis / PostgreSQL
  C->>L2: GET/POST /api/v1/harness/*
  Note over L2: 剥离 /api，proxy_to_orchestration
  L2->>OR: 转发 method/path/query/body/headers
  Note over L2: 只代理、不双写；连接失败或超时统一 503
  OR->>OR: 会话 / run / 策略评估 / 审批
  OR->>Q: HMAC 服务凭据 /internal/v1/harness/quota/*
  Q->>R: QuotaService 预占 / 结算 / 释放
  R-->>Q: used / held 原子计数
  Q-->>OR: 额度结果
  OR-->>L2: 原样透传下游状态码
  L2-->>C: 响应
```

关键实现：`base/plugins/harness/services/orchestration_proxy.py:56-102`（转发与 503 收敛）；L2 内部额度路由 `base/plugins/harness/api/l2_internal/quota_router.py:21`（`prefix=/internal/v1/harness/quota`）；编排侧客户端 `services/l3-orchestration/app/l2_quota_client.py`（超时/5xx → 503）。

**为什么额度要回呼 L2**：让配额写主保持单点，L3 编排持只读 DB 账号 + `information_schema` schema 断言 fail-closed，避免两个进程同时写账本。

### 5.2 网关链路（数据面）

```mermaid
sequenceDiagram
  participant C as 客户端
  participant G as L3 网关 :9999
  participant R as Redis
  participant U as 上游 api.deepseek.com
  participant P as PostgreSQL
  C->>G: POST /chat/completions（Bearer dgw.*）
  G->>G: require_gateway_lease，缺失或非 dgw.* 即 401
  G->>R: gw:lease:state:<lease_id>（TTL 8s）
  R-->>G: 命中 / 未命中（T7.4 埋点）
  G->>G: 预算、并发、额度预检，替换真实 provider key
  G->>U: HTTPS（域名白名单，无绕过开关）
  U-->>G: SSE 流
  G-->>C: StreamingResponse 边读边转发，不缓冲
  G->>P: usage_record 记账
```

两条链路彼此解耦：L2 **不参与任何 SSE 帧**；网关不参与编排业务。

### 5.3 内部鉴权

服务凭据由 `orchestration_service_secret` secret 分发，L3 编排侧 `app/auth.py` 只接受 HMAC 签名（`ServiceAuthError` 默认 401），与共享 `security.py` 共用签名算法。L2 侧 `service_auth.py` 与 `quota_router.py` 在非 `proxy_l3` 时拒绝内部额度调用。编排容器固定 IP `172.28.0.10`，配合 `ORCH_INTERNAL_ALLOWED_IPS` 精确匹配（不能写 CIDR）。

## 6. 数据模型与 Redis key

| 类别 | 键 / 表 | 用途 |
|---|---|---|
| 配额 used | `quota:{ot}:{oid}:{item}:{period}` | 原子计数（`quota_service.py`，`counter_mode=redis`） |
| 配额 held | `quota_held:{ot}:{oid}:{item}:{period}` | 预占中的量 |
| 单次预占 | `quota_hold:{hold_id}` | hash，TTL 3600s |
| 悬挂索引 | `quota_holds_index`（zset） | 过期扫描与对账 |
| 并发槽 | `conc:{ot}:{oid}` / `conc:global` | 并发限制 |
| 租约缓存 | `gw:lease:state:<lease_id>` | TTL 8s（限 5–10s），吊销后最多 8s 内仍可能被接受，是已记录的语义边界 |
| 事实源 | PG `usage_record` / `quota_reservation` | 计费权威账本；`quota_reservation.hold_id` 唯一约束兜底幂等 |
| 幂等前缀 | `gw:` / `harness:` / `orch:` | 请求幂等键 |

PostgreSQL 位于 `host.docker.internal:15432`（Tortoise ORM + asyncpg），Redis 网络别名 `agentredis:6379`。**Redis 是硬依赖，不是可选项**。

## 7. 部署拓扑

`deploy/l3/docker-compose.yml` 三个服务：

- 端口全部绑定宿主 `127.0.0.1`（`9998/9999/9100`），容器内 `0.0.0.0`；`restart: unless-stopped`，`no-new-privileges:true`，json-file 日志轮转 10m×3。
- external 网络 `agentpanel-net`（需预先 `docker network create --subnet 172.28.0.0/16 agentpanel-net` 并热接入 `agentredis`）；编排固定 IP `172.28.0.10`；三个服务都加 `host.docker.internal:host-gateway`。
- L3 网关与编排 `read_only: true` + `/tmp` tmpfs；编排 `depends_on: l2: service_healthy`。
- 4 个 secrets（`deploy/l3/secrets/`，不入库）：`db_password`、`redis_password`、`orchestration_service_secret`、`l2_config`（挂为 `/app/config.conf`，mode 0444）。配置通过 `*_FILE` 读取。
- `RUN_DB_MIGRATIONS: "false"`，迁移不随容器启动执行，需一次性任务单独跑。
- `prepare-secrets.ps1` 生成的 `.env` 仍写旧端口 `19999/19100`（第 140-141 行），重建 secrets 后需手工改为 `9999/9100`——已知遗留缺陷。

## 8. 可观测（T7.4 之后）

| 项 | 现状 |
|---|---|
| 指标端点 | L2 `9998/metrics`、L3 网关 `9999/metrics`、L3 编排 `9100/metrics`；两 L3 复用共享 registry，DB/Redis 健康 Gauge 随抓取刷新 |
| 抓取 job | `monitoring/prometheus.yml` 共 6 个：`prometheus`、`aipaneladmin`(9998)、`l3-gateway`(9999)、`l3-orchestration`(9100)、`pushgateway`、`node_exporter` |
| 告警规则 | `monitoring/alert_rules.yml`：2 组共 14 条 —— `aipaneladmin_alerts` 4 条、`l3_split_alerts` 10 条（对齐灰度 R1–R6） |
| 通知 | `alerting.alertmanagers` 的 targets **为空**，规则求值但不外发通知，需人工查看 `/alerts` |
| 端口避让 | `node_exporter` 宿主 `9101:9100`（9100 已被 L3 编排占用）；`alert_rules.yml` 已在 compose 中补挂 |
| 巡检 | `deploy/l3/scripts/observe_check.py` 16 项只读检查，逐日写入观察期台账 |

## 9. 架构级已知限制

1. 三端口仅回环绑定、**无 TLS 终止**；远程客户端需本机代理/隧道。
2. `web_fetch` / `web_search` 是 dsh 工具侧的直接出网通道，**绕过共享上游客户端与网关白名单**；`egress_policy_service.py` 的 `tool_denylist` 只是策略快照不是执行边界。Linux 实测联网容器访问 `https://example.com/` 返回 200。生产必须禁用这些工具或用容器/网络策略兜底。
3. DSH 原生审批无终端应答者：`approval/asked` 与 `approval/decided` 成对产生但 `outcome=unavailable`，依赖后端事件落库 + 超时拒绝的 fail-closed 路径。
4. 灰度只有部署级整机二元切换，无百分比/按租户切流。
5. 配额正确性（重复结算、`used` 多加、预占悬挂）与数据一致性仍按每日人工 G1 抽查，Prometheus 无法判定；离线结算 outbox 未做（P2 技术债）。
6. 对账触发仍在 L2（`reconcile_in_l3=false`），未迁移到 L3。

## 10. 与旧目标态架构图的差异对照

对照 `reports/architecture/agentpanel-architecture.mmd`（拆分前目标态）：

| 项 | 旧图 | 代码现状 | 影响 |
|---|---|---|---|
| 网关 chat 路径 | `POST /v1/gateway/chat/completions` | 独立网关 `POST /chat/completions`（`gateway/router.py:200`）；L2 仍保留 `/api/v1/gateway` 前缀隔离分支（`app_wrapper.py:58-64`），但那不是 L3 网关入口 | 按旧图调用会 404 |
| Redis | 「当前未启用」+ `:::planned` 虚线 | 三服务 `REDIS_ENABLED="true"`（compose `:40/:83/:123`）；配额、租约缓存、限流均依赖它 | 从「可选」变成硬依赖 |
| PostgreSQL | `5432` | `host.docker.internal:15432`（compose `:35-36` 等） | 连接串不同 |
| 编排入口 | dsh「⑥ HTTPS 9100 客户端凭据」直连 CAPI | `proxy_l3` 下客户端走 `9998 /api/v1/harness/*`，L2 只代理到 `http://l3-orchestration:9100`（compose `:47`）；编排直连主要用于本机验证/内部 | 调用拓扑变了 |
| 租约缓存 | 「Redis 可选」虚线 | `gw:lease:state:<id>` TTL 8s 为实际路径，T7.4 已有命中/未命中埋点 | 缓存行为已落地 |
| TLS | 标注 `HTTPS 9998/9999/9100` | `127.0.0.1` 回环 HTTP，无 TLS 终止 | 安全边界不同 |
| 可观测层 | 图中无 | Prometheus `:9090` 抓三服务 `/metrics`，2 组 14 条规则 | 新增旁路层 |
| 只读 DB / 对账未迁移 | `RDB 只读账号`、`RECON 未迁移 L3` | **仍成立** | 与目标态一致 |

另外 `spec.md` §11 的数据流 ASCII 图标注「L2 业务后端 :9998（宿主进程）」也是拆分前表述，现在 L2 同样是容器；以 §7 与 compose 为准。

## 11. 代码索引

| 关注点 | 文件 |
|---|---|
| L2 应用构建与前缀 | `base/start.py`、`base/app_wrapper.py:289`、`run.py` |
| 编排代理（只代理/503） | `base/plugins/harness/services/orchestration_proxy.py:56-102` |
| L2 内部额度路由 | `base/plugins/harness/api/l2_internal/quota_router.py:21` |
| 网关数据面路由 | `packages/agentpanel_common/gateway/router.py:190,200`、`lease_auth.py` |
| 编排 app 与路由 | `services/l3-orchestration/app/main.py:159-172`、`app/api/*.py` |
| 额度回呼客户端 | `services/l3-orchestration/app/l2_quota_client.py` |
| 配额服务与 key | `packages/agentpanel_common/quota/services/quota_service.py:30-32,127-140` |
| 监控中间件 | `packages/agentpanel_common/l3_metrics.py`、`prometheus.py` |
| 部署 | `deploy/l3/docker-compose.yml`、`deploy/l3/Dockerfile.l2`、`services/l3-*/Dockerfile` |
| 监控配置 | `monitoring/prometheus.yml`、`alert_rules.yml`、`monitoring-deployment.yml` |

## 12. 维护说明

- 本文记录 2026-11-09 的代码现状；观察期内（最早 2026-11-23 收口）**不修改现有架构图资产**。
- T7.5 执行时，应以本文 §2、§5、§10 为输入，把 `agentpanel-architecture.mmd`（及其 HTML 渲染）更新为最终态，并同步 `spec.md` §11；届时本文可作为「as-built 基线」保留归档。
- 所有判定以代码为准；若实现变更，先改代码再更新本文，不要反向以文档推定实现。
