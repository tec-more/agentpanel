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
| 2026-11-09 | 13:37 | 脚本 | PASS (P16/F0/W0/S0) | — |
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
