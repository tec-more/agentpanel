# T7.4 监控/告警补齐：指标、告警与实测

- 日期：2026-11-09
- 范围：`reports/specs/l3-service-split/tasks.md` T7.4
- 前提：P6 验收通过、P7 T7.1–T7.3 完成；三容器 `9998/9999/9100` healthy
- 原则：**只加观测旁路，不改业务分支与返回码**；演练/验证前后 `org:14` / `usr:4` 的 `used` 不变
- 状态：**已实现并实测**；T7.5（删除灰度开关/旧代码、更新架构图）仍受 14 天观察期约束，未执行

---

## 1. 补齐前的问题

P7 报告 §1 与验收报告 §8.4 记录的缺口：L3 网关/编排镜像无 `/metrics`，仅有 Docker HEALTHCHECK 与 `/health*`；5xx、预占失败、租约缓存命中未暴露，无告警规则。灰度方案 §4 因此只能靠日志人工统计 R2/R4。

仓库其实已有共享 Prometheus 基础设施（`packages/agentpanel_common/prometheus.py` 的 registry、HTTP 指标、`metrics_endpoint`），L2 在 `base/start.py:729-734` 挂载；L3 两个 `build_app()` 从未挂载，也未接入业务埋点。本阶段复用该 registry，不新建第二套指标系统。

## 2. 实现

| 文件 | 变更 |
|---|---|
| `packages/agentpanel_common/l3_metrics.py` | **新增**。共享 registry 上的 L3 业务指标、纯 ASGI HTTP 中间件、`/metrics` 端点工厂 |
| `services/gateway/app/main.py` | 挂载中间件 + `/metrics`，注入 DB/Redis 健康探针 |
| `services/orchestration/app/main.py` | 同上 |
| `services/gateway/common/lease_auth.py` | `_get_cached_lease()` 记录 hit/miss/unavailable/error |
| `services/orchestration/app/l2_quota_client.py` | `_post()` 观测包装，记录 reserve/settle/release 成败与异常类型 |
| `monitoring/prometheus.yml` | 新增 `l3-gateway` / `l3-orchestration` 两个抓取 job |
| `monitoring/alert_rules.yml` | 新增 `l3_split_alerts` 组 10 条规则，对齐灰度方案 R1–R6 |
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
| `l3_lease_cache_lookups_total` | Counter | result=`hit\|miss\|unavailable\|error` | `_get_cached_lease()`；`gw:lease:state:*` 命中情况 |
| `l3_quota_operations_total` | Counter | action=`reserve\|settle\|release`, result=`ok\|failed`, reason | `l2_quota_client._post()`；reason 为异常类名（`QuotaError`/`QuotaReservationConflict`/`QuotaUnavailable`）或 `none` |
| `l3_health_check_status` | Gauge | service, check=`database\|redis` | 1=healthy/skipped，0=unhealthy；随 `/metrics` 抓取刷新 |
| `l3_health_check_last_success_timestamp_seconds` | Gauge | service | 最近一次全绿探测时间 |
| `l3_service_info` | Gauge | service, version | 进程存活即 1，便于 join |

零值序列已预注册，无业务流量时 `/metrics` 也能看到完整口径。

## 4. 告警规则与灰度方案映射

| 告警 | 对应 | 阈值 / 表达式要点 |
|---|---|---|
| `L3ServiceDown` | R1 | `up{job=~"l3-(gateway\|orchestration)"} == 0`，for 2m |
| `L3HealthCheckFailing` | R1 | `l3_health_check_status == 0`，for 5m |
| `L3Proxy5xxRateHigh` | R2 | L2 job 上 `/ (api/)?v1/harness/.*` 的 5xx 比例 > 1%，for 5m |
| `L3GatewayP95LatencyDoubled` | R3 | P95 相对 1 小时前 > 2 倍，且有流量，for 10m |
| `L3Gateway5xxRateHigh` | R4 | 网关 5xx 比例 > 1%，for 5m |
| `L3Orchestration5xxRateHigh` | 补充 | 编排 5xx 比例 > 1%，for 5m |
| `L3QuotaReserveFailed` / `L3QuotaSettleFailed` | R5 | 5m 内出现预占/结算失败即告警，for 1m |
| `L3InternalAuth401RateHigh` | R6 | 编排 401 比例 > 5%，for 5m |
| `L3LeaseCacheHitRateLow` | 观察项 | 30m 命中率 < 50%（非回切条件） |

所有比例表达式的分母用 `clamp_min(..., 0.001)` 保护，低流量/零流量不误报。带 `rollback: "true"` 标签的规则即灰度方案中的回切条件。

**未覆盖**：R5 的「重复结算、`used` 多加、预占悬挂」与 R7 的 `used/held` 数据一致性无法由 Prometheus 判定，仍按灰度方案每日人工 G1 抽查；本阶段不宣称自动告警已覆盖这两项。

## 5. 部署拓扑变更说明

- `monitoring/monitoring-deployment.yml` 此前**只挂载了 `prometheus.yml`，没有挂载 `alert_rules.yml`**，而 `prometheus.yml` 的 `rule_files: ["alert_rules.yml"]` 指向容器内路径——即规则此前实际未被加载。本次补上挂载。
- `deploy/l3/docker-compose.yml` 已把宿主 `9100` 分配给 L3 编排容器，而 `monitoring-deployment.yml` 的 node_exporter 原本也映射宿主 `9100`，两栈无法并存。改为宿主 `9101`（容器内仍 9100，`prometheus.yml` 的 `node_exporter:9100` 不变）。
- Prometheus 容器加 `extra_hosts: host.docker.internal:host-gateway`，保证 `host.docker.internal:9998/9999/9100` 可解析。
- 目标地址实测可用：三个 job（`aipaneladmin`、`l3-gateway`、`l3-orchestration`）在 Prometheus 中均为 `up`。

## 6. 验证证据（2026-11-09 实测）

| 项 | 结果 |
|---|---|
| `promtool check rules` | `SUCCESS: 14 rules found`（4 条原有 + 10 条新增） |
| `promtool check config` | `SUCCESS`，1 个 rule file |
| 本地 FastAPI/ASGI 中间件测试 | 200/401/500 计数、SSE 三帧完整不缓冲、`/metrics` 自排除、短 `run_no` 折叠为 `:id`、静态路径不误伤 —— 全通过 |
| 镜像重建 / 容器恢复 | `build` 成功；`up -d --force-recreate` 后三容器 healthy，`9998/health/health`、`9999/health`、`9100/health/health`、`9100/health/orchestration` 全 200；编排 `mode=proxy_l3`、`write_enabled=true` |
| `/metrics` | `9999` → 200（5781 B）、`9100` → 200（7905 B） |
| 指标增量（生产） | 网关 `http_requests_total{endpoint="/chat/completions",status_code="401"}` +2；`l3_lease_cache_lookups_total{result="miss"}` +1；编排 `http_requests_total{endpoint="/v1/harness/runs/:id",status_code="401"}` +3（两个不同短 run_no 合并到同一序列） |
| 健康 Gauge | 两容器 `database` / `redis` 均为 1 |
| Prometheus 端到端 | `/api/v1/targets`：两个 L3 job 均 `up`；`/api/v1/rules`：`l3_split_alerts` 10 条已加载；`l3_health_check_status` 等查询有数据 |
| 告警表达式求值 | 14 条全部 `status=success`、无异常；当前无 L3 告警触发（`ServiceUnavailable` 命中 2 个未启动的辅助组件，属预期） |
| 数据不变性 | Redis `quota:org:14:token:2026-11 = 450`、`quota:usr:4:token:2026-11 = 93294`，与 P7 报告 §4 基线一致 |

复现命令（仓库根目录）：

```powershell
$ROOT = 'd:\programs\fastapi\agentpanel'
$COMPOSE = "$ROOT\deploy\l3\docker-compose.yml"; $ENV = "$ROOT\deploy\l3\.env"
docker compose -f $COMPOSE --env-file $ENV build l3-gateway l3-orchestration
docker compose -f $COMPOSE --env-file $ENV up -d --force-recreate l3-gateway l3-orchestration
docker compose -f "$ROOT\monitoring\monitoring-deployment.yml" up -d prometheus
curl.exe http://127.0.0.1:9999/metrics
curl.exe http://127.0.0.1:9100/metrics
curl.exe "http://127.0.0.1:9090/api/v1/targets?state=active"
```

## 7. 已知限制

1. **5xx 与预占/结算失败未在生产真实触发**：会改动计量数据，故只在本地 ASGI 测试与埋点函数注入层面验证计数路径；告警表达式通过 promtool 与 Prometheus 实求值验证。
2. **监控栈只启动了 `prometheus` 单服务**：`pushgateway` / `node_exporter` 等未启动，在 targets 中显示 `down`/`unknown`，不影响 L3 三个 job；本次也未配置 Alertmanager（`alerting.alertmanagers` 为空），**告警规则会被求值但不会向外发送通知**。接入 Alertmanager 与通知渠道属于后续运维事项。
3. **标签冲突**：`prometheus.yml` 给两个 job 加了外部 `service` 标签，而 `l3_health_check_status` / `l3_service_info` 自带同名标签，Prometheus 按标准行为把后者重命名为 `exported_service`；告警规则统一使用 `job` 标签，不受影响。
4. **两个 L3 进程共享指标定义**：编排也暴露恒 0 的租约缓存计数器、网关也暴露恒 0 的额度计数器；按 `job` 过滤即可。
5. **R5/R7 仍靠人工**：见 §4 末。
6. **保留期未开始计时**：T7.5 需 T7.4 补齐（已完成）且连续 14 天无 P1 故障、阈值未触发、G1 抽查通过后才能执行；本次未删除任何旧代码或灰度开关。
