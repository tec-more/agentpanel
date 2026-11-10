# T7.4 监控/告警补齐：指标、告警与实测

- 日期：2026-11-09
- 范围：`reports/specs/l3-service-split/tasks.md` T7.4
- 前提：P6 验收通过、P7 T7.1–T7.3 完成；三容器 `9998/9999/9100` healthy
- 原则：**只加观测旁路，不改业务分支与返回码**；演练/验证前后 `org:14` / `usr:4` 的 `used` 不变
- 状态：**已实现并实测**；T7.5（删除灰度开关/旧代码、更新架构图）仍受 14 天观察期约束，未执行

---

## 1. 补齐前的问题

P7 报告 §1 与验收报告 §8.4 记录的缺口：网关/编排镜像无 `/metrics`，仅有 Docker HEALTHCHECK 与 `/health*`；5xx、预占失败、租约缓存命中未暴露，无告警规则。灰度方案 §4 因此只能靠日志人工统计 R2/R4。

仓库其实已有共享 Prometheus 基础设施（`packages/common/prometheus.py` 的 registry、HTTP 指标、`metrics_endpoint`），app 在 `base/start.py:729-734` 挂载；独立服务 两个 `build_app()` 从未挂载，也未接入业务埋点。本阶段复用该 registry，不新建第二套指标系统。

## 2. 实现

| 文件 | 变更 |
|---|---|
| `packages/common/service_metrics.py` | **新增**。共享 registry 上的 独立服务 业务指标、纯 ASGI HTTP 中间件、`/metrics` 端点工厂 |
| `services/gateway/app/main.py` | 挂载中间件 + `/metrics`，注入 DB/Redis 健康探针 |
| `services/orchestration/app/main.py` | 同上 |
| `services/gateway/common/lease_auth.py` | `_get_cached_lease()` 记录 hit/miss/unavailable/error |
| `services/orchestration/app/app_quota_client.py` | `_post()` 观测包装，记录 reserve/settle/release 成败与异常类型 |
| `monitoring/prometheus.yml` | 新增 `gateway` / `orchestration` 两个抓取 job |
| `monitoring/alert_rules.yml` | 新增 `agentpanel_alerts` 组 10 条规则，对齐灰度方案 R1–R6 |
| `monitoring/monitoring-deployment.yml` | 挂载 `alert_rules.yml`（此前未挂载，规则实际未加载）；prometheus 加 `host.docker.internal:host-gateway`；node_exporter 宿主端口 `9100→9101` |

关键设计：

1. **纯 ASGI 中间件**，不用 `PrometheusMiddleware`（`BaseHTTPMiddleware`）。后者会包装 `StreamingResponse`，可能破坏网关 `/chat/completions` 的 SSE 原样透传。新中间件只拦截 `http.response.start/body` 消息，不消费、不缓冲响应体。
2. **标签基数控制**：`endpoint` 优先用路由匹配后 `scope["path_params"]` 的值按段精确折叠成 `:id`，再用正则兜底处理 404/未匹配路径。避免了 `run_no`（含 `nope` 这类短值）产生高基数序列。
3. **`/metrics` 自身不计入指标**，避免抓取动作自我放大；健康 Gauge 随抓取刷新，带 10s 缓存，避免每次 scrape 都打 DB/Redis。
4. **观测旁路全部 try/except 吞异常**，埋点失败不影响租约鉴权与额度调用；`_post_impl` 拆出后由 `_post` 包装，异常类型与传播语义不变。

## 3. 指标清单

两进程共享同一套指标定义，未使用的业务计数器恒 0，按 `job` 取用即可。

| 指标 | 类型 | 标签 | 口径 / 来源 |
|---|---|---|---|
| `http_requests_total` | Counter | method, endpoint, status_code | 复用共享指标；覆盖 5xx（R2/R4）、401（R6） |
| `http_request_duration_seconds` | Histogram | method, endpoint | 复用共享指标；P95（R3） |
| `http_active_requests` | Gauge | — | 复用共享指标 |
| `http_response_size_bytes` | Histogram | method, endpoint | 复用共享指标 |
| `lease_cache_lookups_total` | Counter | result=`hit\|miss\|unavailable\|error` | `_get_cached_lease()`；`gw:lease:state:*` 命中情况 |
| `quota_operations_total` | Counter | action=`reserve\|settle\|release`, result=`ok\|failed`, reason | `app_quota_client._post()`；reason 为异常类名（`QuotaError`/`QuotaReservationConflict`/`QuotaUnavailable`）或 `none` |
| `health_check_status` | Gauge | service, check=`database\|redis` | 1=healthy/skipped，0=unhealthy；随 `/metrics` 抓取刷新 |
| `health_check_last_success_timestamp_seconds` | Gauge | service | 最近一次全绿探测时间 |
| `service_info` | Gauge | service, version | 进程存活即 1，便于 join |

零值序列已预注册，无业务流量时 `/metrics` 也能看到完整口径。

## 4. 告警规则与灰度方案映射

| 告警 | 对应 | 阈值 / 表达式要点 |
|---|---|---|
| `ServiceDown` | R1 | `up{job=~"l3-(gateway\|orchestration)"} == 0`，for 2m |
| `HealthCheckFailing` | R1 | `health_check_status == 0`，for 5m |
| `Proxy5xxRateHigh` | R2 | app job 上 `/ (api/)?v1/harness/.*` 的 5xx 比例 > 1%，for 5m |
| `GatewayP95LatencyDoubled` | R3 | P95 相对 1 小时前 > 2 倍，且有流量，for 10m |
| `Gateway5xxRateHigh` | R4 | 网关 5xx 比例 > 1%，for 5m |
| `Orchestration5xxRateHigh` | 补充 | 编排 5xx 比例 > 1%，for 5m |
| `QuotaReserveFailed` / `QuotaSettleFailed` | R5 | 5m 内出现预占/结算失败即告警，for 1m |
| `InternalAuth401RateHigh` | R6 | 编排 401 比例 > 5% **且** 401 速率 > 0.05/s，for 5m（低流量保护，§9.6） |
| `LeaseCacheHitRateLow` | 观察项 | 30m 命中率 < 50%（非回切条件） |

所有比例表达式的分母用 `clamp_min(..., 0.001)` 保护，低流量/零流量不误报。带 `rollback: "true"` 标签的规则即灰度方案中的回切条件。

**未覆盖**：R5 的「重复结算、`used` 多加、预占悬挂」与 R7 的 `used/held` 数据一致性无法由 Prometheus 判定，仍按灰度方案每日人工 G1 抽查；本阶段不宣称自动告警已覆盖这两项。

## 5. 部署拓扑变更说明

- `monitoring/monitoring-deployment.yml` 此前**只挂载了 `prometheus.yml`，没有挂载 `alert_rules.yml`**，而 `prometheus.yml` 的 `rule_files: ["alert_rules.yml"]` 指向容器内路径——即规则此前实际未被加载。本次补上挂载。
- `deploy/gateway/docker-compose.yml` 已把宿主 `9100` 分配给 编排容器，而 `monitoring-deployment.yml` 的 node_exporter 原本也映射宿主 `9100`，两栈无法并存。改为宿主 `9101`（容器内仍 9100，`prometheus.yml` 的 `node_exporter:9100` 不变）。
- Prometheus 容器加 `extra_hosts: host.docker.internal:host-gateway`，保证 `host.docker.internal:9998/9999/9100` 可解析。
- 目标地址实测可用：三个 job（`aipaneladmin`、`gateway`、`orchestration`）在 Prometheus 中均为 `up`。

## 6. 验证证据（2026-11-09 实测）

| 项 | 结果 |
|---|---|
| `promtool check rules` | `SUCCESS: 14 rules found`（4 条原有 + 10 条新增） |
| `promtool check config` | `SUCCESS`，1 个 rule file |
| 本地 FastAPI/ASGI 中间件测试 | 200/401/500 计数、SSE 三帧完整不缓冲、`/metrics` 自排除、短 `run_no` 折叠为 `:id`、静态路径不误伤 —— 全通过 |
| 镜像重建 / 容器恢复 | `build` 成功；`up -d --force-recreate` 后三容器 healthy，`9998/health/health`、`9999/health`、`9100/health/health`、`9100/health/orchestration` 全 200；编排 `mode=proxy`、`write_enabled=true` |
| `/metrics` | `9999` → 200（5781 B）、`9100` → 200（7905 B） |
| 指标增量（生产） | 网关 `http_requests_total{endpoint="/chat/completions",status_code="401"}` +2；`lease_cache_lookups_total{result="miss"}` +1；编排 `http_requests_total{endpoint="/v1/harness/runs/:id",status_code="401"}` +3（两个不同短 run_no 合并到同一序列） |
| 健康 Gauge | 两容器 `database` / `redis` 均为 1 |
| Prometheus 端到端 | `/api/v1/targets`：两个 独立服务 job 均 `up`；`/api/v1/rules`：`agentpanel_alerts` 10 条已加载；`health_check_status` 等查询有数据 |
| 告警表达式求值 | 14 条全部 `status=success`、无异常；当前无 独立服务 告警触发（`ServiceUnavailable` 命中 2 个未启动的辅助组件，属预期） |
| 数据不变性 | Redis `quota:org:14:token:2026-11 = 450`、`quota:usr:4:token:2026-11 = 93294`，与 P7 报告 §4 基线一致 |

复现命令（仓库根目录）：

```powershell
$ROOT = 'd:\programs\fastapi\agentpanel'
$COMPOSE = "$ROOT\deploy\l3\docker-compose.yml"; $ENV = "$ROOT\deploy\l3\.env"
docker compose -f $COMPOSE --env-file $ENV build gateway orchestration
docker compose -f $COMPOSE --env-file $ENV up -d --force-recreate gateway orchestration
docker compose -f "$ROOT\monitoring\monitoring-deployment.yml" up -d prometheus
curl.exe http://127.0.0.1:9999/metrics
curl.exe http://127.0.0.1:9100/metrics
curl.exe "http://127.0.0.1:9090/api/v1/targets?state=active"
```

## 7. 已知限制

1. **5xx 与预占/结算失败未在生产真实触发**：会改动计量数据，故只在本地 ASGI 测试与埋点函数注入层面验证计数路径；告警表达式通过 promtool 与 Prometheus 实求值验证。
2. **辅助组件未启动**：`pushgateway` / `node_exporter` 在 targets 中显示 `down`/`unknown`，不影响 独立服务 三个 job；其 `ServiceUnavailable` 持续 firing 属预期（巡检判 PASS）。Alertmanager 已于 2026-11-09 16:46 接入、17:18 起告警自动落盘留痕（见 §9），但**短信/邮件等外部值班通知渠道仍待运维配置或书面接受**，见 §8.3 / §9.4。
3. **标签冲突**：`prometheus.yml` 给两个 job 加了外部 `service` 标签，而 `health_check_status` / `service_info` 自带同名标签，Prometheus 按标准行为把后者重命名为 `exported_service`；告警规则统一使用 `job` 标签，不受影响。
4. **两个 独立进程共享指标定义**：编排也暴露恒 0 的租约缓存计数器、网关也暴露恒 0 的额度计数器；按 `job` 过滤即可。
5. **R5/R7 仍靠人工**：见 §4 末。
6. **保留期未开始计时**：T7.5 需 T7.4 补齐（已完成）且连续 14 天无 P1 故障、阈值未触发、G1 抽查通过后才能执行；本次未删除任何旧代码或灰度开关。

---

## 8. Alertmanager 接入（2026-11-09 16:46–16:49 +0800，观察期内补齐）

T7.4 遗留项「告警只求值、不外发」的链路已补齐。变更全部在监控旁路，未改三个 独立服务 业务进程、
未改 `mode`、未改业务分支、未删旧代码。操作人：WorkBuddy Agent 代执行（待运维复核）。

### 8.1 变更清单

| 文件 | 内容 |
|---|---|
| `monitoring/alertmanager.yml`（新增） | route 按 `alertname`/`job` 分组（`group_wait=10s`、`group_interval=30s`、`repeat_interval=4h`）；receiver `default-webhook`；`send_resolved: true`；critical 抑制同组 warning |
| `monitoring/monitoring-deployment.yml` | 新增 `alertmanager` 服务（9093:9093、`alertmanager_data` volume、`host.docker.internal:host-gateway`） |
| `monitoring/prometheus.yml` | `alerting.alertmanagers` 由空 targets 改为 `alertmanager:9093` |
| `deploy/gateway/scripts/prepare-secrets.ps1` | 顺带修复 `.env` 端口遗留：`19999/19100` → `9999/9100`（与 compose 头部、运行 `.env` 一致） |

镜像 `prom/alertmanager:latest`（0.34.2）直连 docker.io 超时，经 daocloud / quay 加速源拉取
后本地 tag 复用；该版本**不支持 `--config.expand-env`**（`amtool check-config` 会把 `${VAR}`
判为非法 URL），因此 webhook URL 写成固定值，正式渠道需编辑 `monitoring/alertmanager.yml`
后重启服务，不使用环境变量插值。

### 8.2 验证（6/6 判据通过）

| 判据 | 证据 |
|---|---|
| 配置静态校验 | `promtool check config`（14 条规则）、`amtool check-config` 均 SUCCESS；`docker compose config --quiet` OK |
| Prometheus → Alertmanager | `/api/v1/alertmanagers`：`activeAlertmanagers=[http://alertmanager:9093/api/v2/alerts]`、`droppedAlertmanagers=[]`；SIGHUP 热重载，Prometheus 容器未重启（`Up 3 hours`） |
| 真实规则告警送达 AM | `/api/v2/alerts`：2 条 `ServiceUnavailable`（`job=node_exporter` / `pushgateway`，state=active，`generatorURL` 指向 Prometheus） |
| AM → receiver（真实告警） | AM 日志 16:47:23 `Notify success ... aggrGroup={alertname="ServiceUnavailable", job="node_exporter"} attempts=8 numAlerts=1` |
| AM → receiver（探针） | 临时本地 webhook（9094）收到 `firing` + `resolved` 两个 POST，`receiver=default-webhook`，payload 含 `groupLabels`/`alerts` |
| 恢复核验 | 巡检 **16/16 PASS @16:49:40**；3 个 独立服务 job up、14 条规则加载、三业务容器 healthy、`mode=proxy` |

首次端到端脚本把 webhook payload 当作数组解析（实际是含 `alerts` 字段的对象）而报错，
未产生结论；重跑改用「AM 内真实告警 + 探针投递」两段判据，如实登记，不把重跑伪装成首次全绿。
另：`job=pushgateway` 组因验证接收器关闭过早，首次投递重试 9 次后被取消，属验证脚本时序问题，
非系统缺陷；`repeat_interval=4h`，该组下次通知在 4h 后或状态变化时。

### 8.3 仍存在边界（需运维决策，收口前需补齐或书面接受）

- 默认 webhook 已于 17:18 改为常驻本地落盘服务（见 §9.1），告警自动留痕、不再有占位投递失败；
  但**短信/邮件等外部值班通知渠道仍未接入**，收口前需运维提供正式 URL 或书面接受该边界。
- `pushgateway` / `node_exporter` 未启动，`ServiceUnavailable` 持续 firing 属预期。
- R5（重复结算 / `used` 多加 / 预占悬挂）与 R7（`used`/`held` 一致性）仍靠人工 G1 抽查。
- Prometheus 为 SIGHUP 热重载，未重启容器、未清 TSDB；规则求值与抓取可能出现 <15s 的窗口
  间隙，不影响 14 天观察期计时（计时基于灰度切换与业务进程，非监控组件）。

---

## 9. 常驻告警落盘与端口契约核对（2026-11-09 17:06–17:22 +0800）

用户选择「补完 1、2 两项尾巴」。本轮全部在监控旁路与非敏感运行态核对，
**未读取、未执行 `prepare-secrets.ps1`**（该文件含敏感内容，用户已明确拒绝共享，
故第 2 项改用不接触脚本内容的等效契约核对）；未写 Redis、未改基线、未改巡检口径。

### 9.1 常驻告警接收器（消除占位 URL）

| 文件 | 变更 |
|---|---|
| `monitoring/alert_sink.py`（新增） | 仅监听 monitoring 网络 9094，接收 `/alerts` 并把通知摘要追加为 JSONL；不记录请求头/凭据、不发布宿主端口 |
| `monitoring/monitoring-deployment.yml` | 新增 `alert-webhook-logger` 服务（python:3.12-slim、healthcheck、`./alert-sink` bind mount、`restart: unless-stopped`）；AM 加 `depends_on`、去掉不再需要的 `extra_hosts` |
| `monitoring/alertmanager.yml` | webhook URL 由宿主占位 `host.docker.internal:9094` 改为同网络服务名 `alert-webhook-logger:9094`；`repeat_interval` 保持 4h |
| `.gitignore` | 忽略 `monitoring/alert-sink/`（运行态事件流不入库） |

配置通过 `/-/reload` 热加载（AM 日志 09:18:28 `Loading`/`Completed`）。
注意：AM 0.34.2 的 `/api/v2/status` 会把 webhook URL 脱敏为 `<secret>`，
**不能用该接口判断 URL 是否更新**；以容器内挂载文件与 AM 加载日志为准。
首次据状态接口得到的 `False` 属判据口径问题，如实登记。

**落盘验证 8/8 PASS**（`monitoring/alert-sink/alert-events.jsonl`，3 行）：
真实规则告警 `ServiceUnavailable / node_exporter` 1 行、探针 `AlertmanagerPipelineProbe`
的 firing + resolved 各 1 行，receiver 均为 `default-webhook`；AM 最近 4 分钟
`Notify attempt failed` 0 次。为让真实告警在新 URL 上重投，验证窗口内临时把
`repeat_interval` 改为 `1m`，验证后已恢复 `4h` 并 reload 确认；窗口内重复通知属预期。
`pushgateway` 组因 16:47 首次投递重试被取消、4h 重投窗口未到，本轮未落盘，不伪造结果。

查看命令：
`docker compose -f monitoring/monitoring-deployment.yml exec alert-webhook-logger sh -c 'tail -n 20 /data/alert-events.jsonl'`

### 9.2 端口契约核对（不接触脚本内容）

| 来源 | 网关 | 编排 |
|---|---|---|
| `deploy/gateway/.env` | `9999` | `9100` |
| 容器内环境变量 | `GW_PUBLIC_BASE_URL=...9999` | `ORCH_PUBLIC_BASE_URL=...9100` |
| 宿主端口映射 | `127.0.0.1:9999->9999` | `127.0.0.1:9100->9100` |

6/6 判据通过，与 compose 头部约定一致。此前已完成的脚本语法解析（0 错误）与
`.env` 端口核对结果沿用，不重跑、不重新读取脚本文件。

### 9.3 观察期事件：17:20 巡检 WARN（非业务写入）

`observe_check.py --append @17:20` 结论 **WARN（P15 / F0 / W1 / S0）**：
`quota:usr:990001:token:2026-11` 的 Redis used 缓存键由基线 12 变为「无」。

只读核查：DB 真账 `quota_account.used` 仍为 `{"token": 12.0}`；
`usage_record` 21 / `quota_reservation` 12 / `quota_account` 5 行、测试行 0，与起算基线一致；
Redis `expired_keys=2 / evicted_keys=0 / maxmemory-policy=noeviction`；
`quota_service.py` 无删除 `_used_key` 的路径（只删 hold 键）；本轮亦未写 Redis。
故判定为 **Redis used 缓存键缺失，DB 真账正确，非业务写入、非计量丢失、
非本轮监控变更所致**。17:29 复核更正：「TTL 到期」仅为推断，**消失原因未确定**——
`_period_ttl`（:164）把月度键 TTL 设到月末，实测 `usr:4` 键 TTL ≈21.6 天指向 12-01，
同月同类型键不该在 11-09 到期。

未擅自处置：不改起算基线 `observation-baseline.json`、不改巡检脚本 R7 口径、
不手工重建 Redis 缓存键。补查重建机制（修正此前「业务读取以 DB 值为底重建」）：
`quota_service.py:1126` 只是展示回退、**不写回 Redis**；`reconcile_active_accounts`（:1160）
方向为 Redis → PG，**不会重建该键**；只有写操作重建，`reserve`（:333）用 DB 值播种，
`_settle_redis_counters`（:791）用 `0` 播种后累加——故缺失窗口内若发生无预占直接 settle，
Redis 实时 used 会从 0 起算、低估历史 12，使配额判断偏松；DB 真账不受影响，
下一次 reserve 可纠正。属既有设计弱点、非本轮引入，登记为收口后改进项。

巡检侧 WARN 非 FAIL、退出码 0，§5 准入的「WARN 均有说明」已由本节满足；
当时的代价是键不恢复则 14 天内每日均为 P15/F0/W1/S0、16/16 信号消失。
**17:34 用户授权后已按 DB 真账重建该键**（值 `12`、TTL 对齐 `usr:4` 的 1866359s、
指向 2026-12-01），一次 `SET NX EX`，8/8 判据通过；复跑巡检
**16/16 PASS @17:34:16**，WARN 消除。未改起算基线、未改巡检脚本口径、未改业务代码、
DB 真账零变化；**不建议**改基线或改脚本口径。执行细节见
`l3-split-p7-observation-log.md` §11.5，完整论证见 §11.3。

### 9.4 观察期影响

监控栈变更不涉及三个 独立服务 业务进程；Prometheus 未重启、AM 仅 reload、接收器为新增容器。
恢复后 `repeat_interval=4h`、`mode=proxy`、used/held 真账未变、三业务容器 healthy。
**不重置计时**：起算 13:33:40 +0800，最早收口 2026-11-23 13:33 +0800。
边界收敛：告警已能自动本地留痕，但**短信/邮件等外部值班通知渠道仍待运维提供或书面接受**；
`config.conf` 线下核对、第 2 周 G1、三方签字、T7.5 到期收口仍待。

### 9.5 R6 自激误报分析（17:35 发现，17:43 已修复）

`agentpanel_alerts` 的 R6 规则（401 比例 > 5%、`for: 5m`、`rollback: "true"`）在低流量环境下
被**巡检自身的预期 401 探测**触发：17:36 实测编排侧 5 分钟窗口只有两个健康 200 与
`/v1/harness/runs/:id` 401，`401_rate=0.0140/s` / `total_rate=0.1053/s` → 比例 13.3%，
分母过小。时间线 17:30:11 pending → 17:35:11 firing，恰好使 17:34 巡检 PASS 16/16、
17:36 巡检 FAIL 15/16；与 17:34 的缓存重建无因果关系（重建脚本不发 HTTP）。

该告警带 `rollback: "true"`，按灰度方案 §4 若机械执行有误回切风险。
发现当时未改规则（超出「授权重建」范围）；**17:43 用户「授权调整 R6 规则」后已修复，见 §9.6**。
完整证据、处置选项与观察期影响见 `l3-split-p7-observation-log.md` §11.6 / §11.7。

### 9.6 R6 低流量保护（2026-11-09 17:41–17:43 +0800，用户授权）

| 文件 | 变更 |
|---|---|
| `monitoring/alert_rules.yml` | R6 表达式在「401 比例 > 5%」基础上追加 `and sum(rate(...401...[5m])) > 0.05`（≈ 5 分钟内 15 次 401）；比例阈值、`for: 5m`、`rollback: "true"` 均不变；summary/description 同步，注释写明误报背景 |
| `monitoring/r6_rules_test.yml`（新增） | `promtool test rules` 单元测试两场景，随规则一起回归 |

**更正上一轮的建议**：当时推荐「总流量门槛 `total_rate > 0.05`」其实挡不住这次误报——
实测误报时 `total_rate=0.1053/s` 已超过 0.05；真正的特征是 **401 绝对量极小**
（`401_rate=0.0140/s`）。因此改用 401 绝对速率门槛，只挡零星探测，
真实服务凭据故障时 401 成批出现仍能触发。

验证（全部通过）：

| 判据 | 结果 |
|---|---|
| 静态校验 | `promtool check rules` 14 条 SUCCESS；`promtool check config` SUCCESS |
| **规则单元测试** | `promtool test rules` **SUCCESS**：场景 A 低流量探测（200 0.167/s + 401 0.0167/s，比例 ≈9%）**不触发**；场景 B 真实凭据故障（401 0.5/s，比例 93.75%）**触发**，labels/annotations 精确匹配 |
| 热重载 | SIGHUP 重载，Prometheus 容器未重启（`Up 4 hours`）；规则 `health=ok / state=inactive`、`for=300s`、labels 保留 |
| 运行态 | 新表达式在真实数据上返回空；`InternalAuth401RateHigh` 从 firing 列表消失，仅剩 2 条已知 `ServiceUnavailable`；巡检产生的 401 未使表达式为真 |
| 巡检 | `observe_check.py --append @17:43` → **PASS 16/16（P16/F0/W0/S0）** |
| 告警链路 | `activeAlertmanagers=1 / dropped=0`，未受影响 |

运行命令（宿主仓库根目录）：
```
MSYS2_ARG_CONV_EXCL='*' docker run --rm -v "<repo>/monitoring:/rules:ro" \
  --entrypoint promtool prom/prometheus:latest test rules /rules/r6_rules_test.yml
```
Git Bash 下必须禁用 POSIX 路径转换，否则 `/rules/...` 会被改写成本机 Git 安装路径。

**边界**：`0.05/s` 是按当前低流量设定的保守值，运维可按真实流量再调；规则仍保留
比例 5% 与 `for 5m`，不是把 R6 关掉。本变更只在监控旁路，不改业务代码、不改 `mode`、
不重启业务容器、不动计量数据、**不重置计时**（起算 13:33:40 / 最早收口 2026-11-23 13:33）。
