# 灰度观察期台账：L3 编排 / 网关物理拆分

- 状态：**观察期已启动，计时中**
- 起算时刻：**2026-11-09 13:33:40 +0800**
- 最早可收口时刻：**2026-11-23 13:33 +0800**（连续 14 天且 §5 全项通过；任一回切条件触发则重置）
- 依据：`reports/ops/l3-split-p7-grayscale.md` §2（保留期与进入/退出条件）、§3（切流留痕）、§4（回切阈值）、§6（检查清单）
- 配套：`deploy/l3/scripts/observe_check.py`（只读巡检）、`deploy/l3/observation-baseline.json`（起算基线快照）、`reports/ops/l3-split-p7-metrics.md`（T7.4 指标清单）

> 起算口径说明：实际切流（`orchestration.mode=proxy_l3`）发生于同日的 P6 验收 / 容器接管阶段，但当时未按 §3 记录切换时刻与验证输出，也未建立巡检台账。本次取「证据完备时刻」13:33:40 作为起算点，**比实际切流更晚、对收口更保守**，不存在倒填日期提前收口的问题。操作人栏需由 L3 拆分负责人复核确认。

## 1. 切换证据（起算基线实测，2026-11-09 13:33 +0800）

执行环境：本机 Windows，`mode=proxy_l3`，三容器由 `deploy/l3/docker-compose.yml` 管理。

```
docker ps --filter name=agentpanel-l3 --format '{{.Names}}|{{.Status}}|{{.Ports}}'
  agentpanel-l3-l2-1                Up About an hour (healthy)  127.0.0.1:9998->9998/tcp
  agentpanel-l3-l3-gateway-1        Up 8 minutes (healthy)      127.0.0.1:9999->9999/tcp
  agentpanel-l3-l3-orchestration-1  Up 8 minutes (healthy)      127.0.0.1:9100->9100/tcp
```

| 验证项 | 命令 / 端点 | 实测 |
|---|---|---|
| L2 健康 | `GET 9998/health/health` | 200 |
| 网关健康 | `GET 9999/health` | 200 |
| 编排健康 | `GET 9100/health/health` | 200 |
| 编排模式 | `GET 9100/health/orchestration` | 200，`mode=proxy_l3`，`write_enabled=True` |
| 代理可达（§3 第 4 步） | `GET 9998/api/v1/harness/runs/nope` | **401**（非 503，L3 链路正常） |
| 编排直连 | `GET 9100/v1/harness/runs/nope` | 401 |
| 网关指标 | `GET 9999/metrics` | 200，DB/Redis 健康 Gauge 均 1.0 |
| 编排指标 | `GET 9100/metrics` | 200，DB/Redis 健康 Gauge 均 1.0 |
| 抓取目标 | `9090/api/v1/targets` | `aipaneladmin` / `l3-gateway` / `l3-orchestration` 均 `up` |
| 告警规则 | `9090/api/v1/rules` | `aipaneladmin_alerts` 4 条 + `l3_split_alerts` 10 条 |
| 首次巡检 | `observe_check.py` | 16 项全 PASS，退出码 0（2026-11-09 13:35 复跑确认） |

操作人：WorkBuddy Agent 代执行（待 L3 拆分负责人签字复核）；命令原文：`docker compose -f deploy/l3/docker-compose.yml --env-file deploy/l3/.env up -d --force-recreate l3-gateway l3-orchestration`（T7.4 镜像重建），切流配置见 `deploy/l3/secrets/l2_config.conf`。

## 2. 起算基线快照

来自 `deploy/l3/observation-baseline.json`（由 `--init-baseline` 从 Redis 只读采集生成）：

| 键 | 值 |
|---|---|
| `quota:org:14:token:2026-11` | 450 |
| `quota:usr:4:token:2026-11` | 93294 |
| `quota:usr:990001:token:2026-11` | 12 |
| `quota_held:usr:4:token:2026-11` | 0 |
| `quota_held:usr:990001:token:2026-11` | 0 |
| `quota_holds_index` | 空 |

> `used` 会随正常业务请求增长，**不等于基线本身不是违规**。巡检把 `used` 变化记为 WARN，需值班判断是否为业务写入并在本台账登记；只有 `held != 0` 或 `quota_holds_index` 非空（R5 预占悬挂）才判 FAIL。若确认是正常业务写入，更新 `observation-baseline.json` 的 `quota_used` 并在备注注明来源与时间。

## 3. 每日巡检记录

执行：`cd D:/programs/fastapi/agentpanel && .venv/Scripts/python.exe deploy/l3/scripts/observe_check.py --append`
（只追加当日一行、同日重跑覆盖；退出码 1 表示有硬项失败，需按 §4 判定是否回切）

| 日期 | 时间 | 执行方式 | 结论 | 异常/备注 |
|---|---|---|---|---|
<!-- DAILY_ROWS_START -->
| 2026-11-09 | 15:51 | 脚本 | PASS (P16/F0/W0/S0) | — |
<!-- DAILY_ROWS_END -->

巡检覆盖：三容器 healthy、4 个健康端点 200、`mode=proxy_l3`、代理 401、Redis 可读、`held` 无悬挂、`used` 基线对比、两个 `/metrics` 健康 Gauge、Prometheus 三个 L3 job、规则加载、非预期 firing 告警。

## 4. 每周人工抽查（脚本不代劳）

对应灰度方案 §6，以下项目**会写计量数据或需人工判断**，刻意不自动化：

- [ ] G1-A / G1-B / G1-C：同一 hold 的并发 reserve / settle / release 各一次，核对 `used` 与 `held` 及 `quota_reservation` 记录（参考 `l3-split-acceptance.md` §5）
- [ ] 抽查前后登记 `org:14` / `usr:4` 的 `used`，确认变化仅由本次抽查造成（R7）
- [ ] 容器日志中 5xx / 503 / 401 抽样，与 Prometheus 指标交叉校验
- [ ] 回切条件 §4 R1–R7 逐条复核，任一触发立即回切并**重置观察期**

| 周次 | 日期 | 执行人 | G1 结果 | R1–R7 复核 | 备注 |
|---|---|---|---|---|---|
| 第 1 周 | — | — | — | — | — |
| 第 2 周 | — | — | — | — | — |

## 5. 收口判定（T7.5 准入）

- [ ] 连续 14 天无 P1 故障（起算 2026-11-09 13:33 +0800 → 最早 2026-11-23 13:33 +0800）
- [ ] §4 全部阈值未触发，且无回切/重置记录
- [ ] 每日巡检记录连续无缺口，WARN 均有业务写入说明
- [ ] 每周 G1 抽查通过，`used`/`held` 无异常
- [ ] L3 拆分负责人 + 值班运维 + 数据/配额负责人三方评审签字

以上全部满足后，方可执行 T7.5（删除灰度开关与 L2 旧编排代码、更新架构图）。**在此之前保留旧代码与 `mode` 开关**。

## 6. 巡检口径与已知缺口

1. **Alertmanager 未配置**：`monitoring/monitoring-deployment.yml` 的 `alerting.alertmanagers` 为空，规则会求值但不会外发通知。每日巡检会拉取 `/api/v1/alerts` 的 firing 列表写入结论，但值班仍需主动查看 Prometheus 告警页；接入通知渠道列为 P1 待办。
2. **监控栈仅 prometheus 单服务常驻**：`pushgateway` / `node_exporter` 未启动，二者 `down` 及对应 `ServiceUnavailable` firing 已列入巡检白名单（`EXPECTED_FIRING_JOBS`），不计为非预期告警。若 9090 不可达，Prometheus 相关项记 WARN/SKIP 而非 FAIL，此时必须人工查看告警页并在备注登记。
3. **5xx / 预占失败未在生产真实触发**：会改动计量数据，T7.4 阶段只在本地 ASGI 测试与埋点注入层验证计数路径（见 `l3-split-p7-metrics.md` §7）。
4. **脚本只读**：不调用 reserve / settle / release，不写 Redis，不改配置；`--init-baseline` 只写本地 JSON 文件。
5. **观察期内边界**：不改业务分支、不删旧代码、不动计量数据；本台账与巡检脚本本身不违反该边界。

## 7. 运行态镜像切换记录（2026-11-09 15:50:43 +0800）

### 背景

同日完成三次目录整理后（`7be9c13` 整包迁入 → `2103fca` 常量下沉/编排解耦 → `84ae9b3` 领域包改名 `common`），运行中的三个容器仍是 12:26–13:24 用**旧镜像**启动的实例：网关 `CMD` 仍为 `python services/l3-gateway/run.py`。此前每次提交都只 `build` 未 `up`，运行态与代码布局脱节。本节记录把它们切到新镜像的整个过程与影响。

命令（沿用 §1 的 `--env-file` 口径）：

```
docker compose -f deploy/l3/docker-compose.yml --env-file deploy/l3/.env \
  up -d --force-recreate --wait --wait-timeout 180
```

| 服务 | 切换前镜像 | 切换后镜像 / `CMD` |
|---|---|---|
| l2 | `sha256:57e676a20176a` | `agentpanel-l2:local` / `python run.py` |
| l3-gateway | `sha256:d384224acff79` | `agentpanel-l3-gateway:local` / `python services/gateway/run.py` |
| l3-orchestration | `sha256:678d5312a944` | `agentpanel-l3-orchestration:local` / `/bin/sh -c '… exec python services/orchestration/run.py'` |

`--wait` 返回时三个容器均已 `healthy`（L2 → 网关 → 编排按 depends_on 依次就绪）。

### 容器内布局实测

| 容器 | `/app/services/gateway/common` | 旧 `gateway/gateway` | `/app/services/gateway` |
|---|---|---|---|
| l2 | 存在 | 不存在 | 存在 |
| l3-gateway | 存在 | 不存在 | 存在 |
| l3-orchestration | 不存在 | 不存在 | **整个目录不存在**（延续 `2103fca` 的解耦） |

### 切换后验证

- 端点：L2 `/health/health`、网关 `/health`、编排 `/health/health`、编排 `/health/orchestration` 均 200；`mode=proxy_l3`、`write_enabled=true`；L2 代理 `/api/v1/harness/runs/nope` 返回 **401**（非 503，编排链路正常）。
- 监控：Prometheus `aipaneladmin` / `l3-gateway` / `l3-orchestration` / `prometheus` 四个 job 均 `up`；规则组仍为 `aipaneladmin_alerts` 4 条 + `l3_split_alerts` 10 条；firing 2 条 `ServiceUnavailable` 属 §6 已知白名单（pushgateway / node_exporter 未启动）。
- 巡检：`observe_check.py` **16/16 PASS、verdict PASS**（15:51），§3 当日行已用切换后数据追加；`used` 3 个键与起算基线一致、`held` 全 0、`quota_holds_index` 空，基线 JSON 无需更新。
- 三镜像 `docker compose build` 在此之前的提交中均已通过，容器内新路径导入冒烟通过。

### 对观察期的影响评估

1. **进程内指标计数器归零**（唯一实质影响）：切换前 L2 `/health/health` 825、网关 `/health` 594、编排 `/health/health` 592；切换后为 4 / 4 / 3（巡检自身请求产生）。这是重建容器导致 `http_requests_total` 等进程内 Counter 重置，Prometheus 会按 counter reset 处理；判读 `rate()` / `increase()` 时注意 15:50 前后窗口的负增量不代表业务下跌。业务计数器 `l3_quota_operations_total` 本就为 0，无数据丢失。
2. **不重置观察期计时**：起算时刻仍为 13:33:40 +0800，最早收口 2026-11-23 13:33 +0800。本次是镜像/目录布局切换，不是切流模式变更（`mode` 保持 `proxy_l3`），不触发 §3 重新留痕或 §4 回切条件。
3. **未触碰观察期边界**：未改业务分支、未删旧代码、未动计量数据（Redis `used`/`held` 与基线完全一致）。§5 收口检查清单状态不变。
4. 操作人：WorkBuddy Agent 代执行（待 L3 拆分负责人签字复核）。

## 8. 授权补验登记（2026-11-09 16:04–16:13 +0800）

用户对 `l3-split-post-refactor-verification.md` §8 的写入/破坏性项授权执行；**T7.5 收口因
14 天观察期时间约束仍不执行**（最早 2026-11-23 13:33）。操作人：WorkBuddy Agent 代执行
（待 L3 拆分负责人签字复核）。

| 时刻 | 动作 | 观察期影响 |
|---|---|---|
| 16:04 | 备份 `out/`、`out-network/`、基线到 `.workbuddy/evidence-backup-20261109-1604/`（15 文件 / 1,053,201 字节）；新建 `out-rerun-20261109/` | 无 |
| 16:07 | 重跑 Linux 隔离验证链，输出到新目录，退出码 0；原证据 mtime/大小未变 | 隔离容器，无 |
| 16:08 | `stop l3-orchestration` → L2 代理 503 `orchestration_downstream_unavailable`；`up -d --wait` 恢复 healthy → 401 | 编排容器重启，进程内 Counter 归零；Prometheus 短暂 down 后恢复 |
| 16:09 | 独立 9990 网关跑 `verify_gateway.py`，**66/66 PASS**；9990/9991/9992 全部终止 | `p3v_` fixture 写入后由脚本 `finally` 清理 |
| 16:11 | 编排容器经 L2 内部额度 API 验证 reserve/幂等/20 并发/释放（主体 `org:14`） | `held` 临时变化后归零，`used` 未变 |
| 16:12 | 清理测试行与 Redis 键、逐项恢复 `used`/`held` 快照；巡检 16/16 PASS | 基线完全一致 |

**恢复核验**：`quota:org:14:token:2026-11=450`、`quota:usr:4:...=93294`、`quota:usr:990001:...=12`
与基线一致；`quota_held:*` 全 0；`quota_holds_index` 空；`quota_reservation` 12 行、
`usage_record` 21 行与验证前相同，测试行 0 残留；三容器 healthy；五端点与 `/metrics` 正常；
Prometheus 抓取 / 规则加载 / 非预期告警三项巡检仍 PASS。

**影响评估与判定**：唯一实质影响是 16:08 编排容器重启导致进程内 Counter 再次归零，
判读 `rate()` / `increase()` 时 16:08 前后窗口的负增量不代表业务下跌。业务计量数据已完全恢复，
未改业务分支、未删旧代码、未改 `mode`（仍 `proxy_l3`），**不重置 14 天计时**、
不触发 §4 回切条件。起算仍为 13:33:40 +0800，最早收口 2026-11-23 13:33 +0800。
每日 `observe_check.py --append` 口径不变，本节作为当日补充留痕。
