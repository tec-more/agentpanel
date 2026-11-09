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
| 2026-11-09 | 17:20 | 脚本 | WARN (P15/F0/W1/S0) | WARN used 基线对比：quota:usr:990001:token:2026-11 12→无（需登记业务写入来源） |
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
| 第 1 周 | 2026-11-09 | WorkBuddy Agent 代执行（待 L3 拆分负责人签字复核） | **G1-A / G1-B / G1-C 均通过**：20 并发 reserve 仅 1 个唯一 hold；20 并发 settle 全部成功且重复批次零写入；20 并发 release 恰好 1 次 `released=true`。单条 settle 与重复 settle 幂等（`settled=1` → `settled=0/skipped=1`） | 待值班运维逐条人工复核（阈值解释需人工判断，脚本与代理不代劳） | 见 §8、§9.1；抽查前 `org:14` used=450、held 全 0；结算过程中 used 一度升至 530、held 归 0，验证后精确恢复 450，测试行 0 残留 |
| 第 2 周 | — | — | — | — | — |

## 5. 收口判定（T7.5 准入）

> 2026-11-09 16:32 收口准备：为五项准入补齐「当前状态 / 证据位置 / 责任人 / 到期动作」，
> **五项 checkbox 全部保持未勾选**——时间项与人工签字项不可由脚本或代理代劳。
> 到期当天的具体删除范围、命令与留痕见 `reports/ops/l3-split-t75-closeout-plan.md`；
> 本文只做准入登记，不构成 T7.5 的执行。

- [ ] 连续 14 天无 P1 故障（起算 2026-11-09 13:33:40 +0800 → 最早 2026-11-23 13:33:40 +0800）
      - 状态：计时中（11-09 为第 1 天）｜证据：§3 每日巡检行 + §7/§8/§9 事件登记
      - 责任人：值班运维｜到期动作：确认连续 14 个自然日无 P1 故障、无记录缺口
- [ ] 灰度方案 §4 全部阈值（R1–R7）未触发，且无回切/重置记录
      - 状态：截至 16:31 未触发（巡检 16/16 PASS）；期间三次容器切换/重启均已登记，均判定不重置计时
      - 证据：`l3-split-p7-grayscale.md` §4、本台账 §7 / §8 / §9.4
      - 责任人：L3 拆分负责人｜到期动作：逐条复核 R1–R7 并解释任何阈值边缘
- [ ] 每日巡检记录连续无缺口，WARN 均有业务写入说明
      - 状态：**未满足**——§3 目前仅 2026-11-09 一行（同日 15:51 / 16:12 / 16:31 覆盖写同一行）
      - 责任人：值班运维｜到期动作：自 11-10 起每日执行 `observe_check.py --append`，补齐 14 行
- [ ] 每周 G1 抽查通过，`used`/`held` 无异常
      - 状态：**部分完成**——第 1 周 G1-A/B/C 已实测通过（§4 周次表、§9.1）；第 2 周未开始；日志 5xx/503/401 抽样与 R1–R7 人工复核待做
      - 证据：§4 周次表、`l3-split-post-refactor-verification.md` §10.2 / §11
      - 责任人：数据/配额负责人｜到期动作：完成第 2 周抽查并核对 `used`/`held` 与对账
- [ ] L3 拆分负责人 + 值班运维 + 数据/配额负责人三方评审签字
      - 状态：未签｜责任人：三方本人｜到期动作：填写 §5.1 签字栏，任一未签不得收口

### 5.1 三方评审签字栏（到期填写，代理不可代签）

| 角色 | 姓名 | 结论（同意 / 不同意收口） | 日期 | 签字 |
|---|---|---|---|---|
| L3 拆分负责人 | | | | |
| 值班运维 | | | | |
| 数据/配额负责人 | | | | |

以上全部满足后，方可执行 T7.5（删除灰度开关与 L2 旧编排代码、更新架构图）。**在此之前保留旧代码与 `mode` 开关**；任一硬项未满足按灰度方案 §2 顺延，不以「时间到了」为由强行收口。

## 6. 巡检口径与已知缺口

1. **Alertmanager 已接入并自动落盘、外部通知渠道仍待定**（2026-11-09 17:18 更新，见 §11 与 `l3-split-p7-metrics.md` §9）：`prometheus.yml` 的 `alerting.alertmanagers` 指向 `alertmanager:9093`，webhook 指向常驻服务 `alert-webhook-logger`，告警自动写入 `monitoring/alert-sink/alert-events.jsonl`；**短信/邮件等外部值班通知渠道仍待运维提供或书面接受**。每日巡检仍会拉取 `/api/v1/alerts` 的 firing 列表写入结论；接入正式渠道列为 P1 待办。
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

## 9. 收口准备与剩余补验（2026-11-09 16:23–16:32 +0800）

用户要求补完此前「仍未做的三项」，并明确选择 **「保留观察期，先做收口准备」**：
本节三项均**不删代码、不改 `mode`、不改架构图、不重置计时**。操作人：WorkBuddy Agent
代执行（待 L3 拆分负责人签字复核）。

### 9.1 额度 settle / G1-B（容器内，基线精确恢复）

宿主侧「读取本地 secrets 文件做基线采集」的一次尝试被敏感内容保护拦截（审批超时），
**未重试、未推断、未绕过**该路径；改回 §8 已采用的既定合规方式：基线采集、验证、清理
全部在编排容器内一次完成，凭据由容器内 `/run/secrets/` 读取且不进入任何输出。

验证前基线：Redis `quota*` 6 键、`usage_record` 21 行、`quota_reservation` 12 行、
`quota_account` 5 行、`org:14` used=450；测试 tag `p7s_adb4b703`。

| 场景 | 结果 |
|---|---|
| reserve(100) | 返回 `orch:p7s_adb4b703_a` |
| 单条 settle(60) | `settled=1` |
| 重复 settle 同 idem_key | `settled=0 / skipped=1`（幂等） |
| **G1-B：20 并发 settle（20 个不同 idem_key）** | 20/20 成功、`settled_sum=20`、`skipped_sum=0` |
| 同批 20 并发重复 settle | 20/20 成功、`settled_sum=0`、`skipped_sum=20`（零重复写入） |
| release / 重复 release | `true` / `false` |
| 结算过程中 | `usage_record` +21 行、`quota_reservation` +1 行、used 450→530、held 全 0 |

`finally` 清理：删除本次 `orch:p7s_*` 流水与预占行、恢复 `quota_account.used`、
按快照逐键恢复 Redis（含类型与 TTL）。**`redis_exact=true`、`db_exact=true`，10/10 判据通过**：
used 回到 450、DB 回到 21/12/5、测试行 0 残留。至此 §4 的 G1-A / G1-B / G1-C 全部实测通过。

### 9.2 Redis / L2 down 故障注入（P6 §7 同类口径）

| 端点 | 正常 | Redis down | L2 down | 恢复后 |
|---|---|---|---|---|
| L2 `/health/health` | 200 | -1（不可用） | 502（服务不可用） | 200 |
| 网关 `/health` | 200 | 200 | 200 | 200 |
| 编排 `/health/health` | 200 | -1（不可用） | 200 | 200 |
| 编排 `/health/orchestration` | 200 | 200 | 200 | 200 |
| L2 代理 `runs/nope` | 401 | -1 | 502 | 401 |
| 编排直连 `runs/nope` | 401 | 401 | 401 | 401 |
| 网关 `/chat/completions` 无凭据 | 401 | **401（未 fail-open）** | 401 | 401 |

L2 down 期间在编排容器内探测额度写链路：抛 `QuotaUnavailable` / `ConnectTimeout`，
**未伪造成功、未回落本进程**，与「编排写接口 503」的 fail-closed 口径一致。
恢复：`docker start agentredis` + `docker compose up -d --wait`，三容器 healthy、四端点 200。
L2 停机时宿主机 9998 返回 502 而非连接拒绝，属 Docker 端口转发层行为，服务本身不可用。

> 首次探测脚本自报 3 项 FAIL，均为**判据口径问题**，非系统异常：① `/health/orchestration`
> 响应体被截到 120 字符导致 `mode` 解析为 null；②「L2 不可达」硬编码期望 -1，未把 502
> 计入不可用；③ 由 ① 连带影响的 `mode unchanged`。补验完整读取响应体确认
> `mode=proxy_l3 / write_enabled=True`，判据改为 `!=200` 后 **10/10 PASS**。此处如实登记，
> 不把口径修正伪装成首次全绿。

### 9.3 T7.5 收口准备（仅留痕与预案）

1. §5 五项准入补齐「当前状态 / 证据位置 / 责任人 / 到期动作」，**checkbox 全部保持未勾**，
   并新增 §5.1 三方签字栏（代理不可代签）；
2. §4 周次表登记第 1 周 G1-A/B/C 结果与抽查前后 `used`/`held` 对照，第 2 周仍为空；
3. 新建 `reports/ops/l3-split-t75-closeout-plan.md`：到期当天的删除范围（P4 T4.1–T4.12）、
   开关读取点清单、架构图资产、验证命令、留痕与回退路径。

`tasks.md` / `checklist.md` / `spec.md` / `agentpanel-architecture.mmd` 中的 T7.5 状态与架构图
**均未改动、未提前打勾**，仅在预案中列为到期同步项。

### 9.4 恢复核验与观察期影响

巡检 **16/16 PASS、verdict PASS @ 2026-11-09 16:31:51 +0800**；`mode=proxy_l3`、
`write_enabled=true`；used 3 键 `450 / 93294 / 12` 与起算基线一致、held 全 0、
`quota_holds_index` 空；DB 21 / 12 / 5 行、测试行 0；三容器 healthy、Redis 已恢复。

- Redis 重启后 `quota_held:org:14:token:2026-11`（值为 0 的空壳键，**非起算基线键**，
  系 §8 补验残留）TTL 自然到期消失，held 键集合回到起算基线的
  `usr:4` / `usr:990001` 两个全 0 键；**业务计量数据无变化**，巡检判 PASS。
- 唯一实质影响：16:30–16:31 的 Redis 与 L2 容器重启使**进程内指标 Counter 归零**，
  `rate()` / `increase()` 在 16:31 前后窗口的负增量不代表业务下跌（继 15:50、16:08 之后第三次）。
- 未改业务分支、未删旧代码、未改 `mode`、未动起算基线。**不重置 14 天计时**：
  起算仍为 13:33:40 +0800，最早收口 **2026-11-23 13:33 +0800**；不触发灰度方案 §4 回切条件。

---

## 10. 监控告警链路补齐与端口遗留修复（2026-11-09 16:44–16:49 +0800）

用户「继续」后盘点剩余项：11-23 收口 / 第 2 周 G1 / 三方签字属时间或人工锁，
`config.conf` 属线下受控核对项（不读取、不推断）；本轮只推进两项可执行遗留，
完整证据见 `l3-split-p7-metrics.md` §8。操作人：WorkBuddy Agent 代执行（待运维复核）。

- 新增 `monitoring/alertmanager.yml` 与 compose `alertmanager` 服务（0.34.2，9093），
  `prometheus.yml` 的 `alerting.alertmanagers` 指向 `alertmanager:9093`，SIGHUP 热重载。
- 链路实测 6/6：Prometheus active alertmanager 1 个 / dropped 0；AM 内 2 条真实
  `ServiceUnavailable`（node_exporter / pushgateway）；AM 日志 16:47:23 `Notify success`；
  临时 webhook 收到探针 `firing` + `resolved`；`promtool` / `amtool` / compose 静态校验全绿。
- `prepare-secrets.ps1` 生成 `.env` 的两个 public base URL 由 `19999/19100` 改为
  `9999/9100`，与现行 compose 及运行态一致；脚本语法静态解析 0 错误。

**边界（该时点状态；17:18 已替换为常驻落盘服务，见 §11）**：默认 webhook URL 为本地验证占位 `http://host.docker.internal:9094/alerts`，
正式通知渠道待运维提供（改一行 URL 后重启 AM）；AM 0.34.2 不支持 `--config.expand-env`。
首次端到端脚本因 payload 解析类型错误未产生结论，重跑改用两段判据，`pushgateway` 组
首次投递因接收器关闭过早被取消，均已如实登记在 metrics §8.2。

**观察期影响**：监控栈变更不涉及业务进程；Prometheus 未重启（SIGHUP）、TSDB 未清。
巡检 **16/16 PASS @16:49:40**（3 个 L3 job up、14 条规则加载、firing 均为已知辅助组件 down）；
`mode=proxy_l3`、used/held 基线不变、三业务容器 healthy。**不重置计时**：起算
13:33:40 +0800，最早收口 **2026-11-23 13:33 +0800**，不触发灰度方案 §4 回切条件。
剩余开放项：正式通知渠道 URL、`config.conf` 线下核对、第 2 周 G1、三方签字、T7.5 到期收口。

---

## 11. 告警落盘、端口契约核对与 17:20 WARN 登记（2026-11-09 17:06–17:22 +0800）

用户选择「补完 1、2 两项尾巴」。本轮只动监控旁路与非敏感运行态核对：
**未读取、未执行 `prepare-secrets.ps1`**（该文件含敏感内容，用户明确拒绝共享，
故第 2 项改用不接触脚本内容的等效契约核对）；未写 Redis、未改基线、未改巡检口径。
完整证据见 `l3-split-p7-metrics.md` §9。

### 11.1 常驻告警落盘（8/8 判据通过）

新增 `monitoring/alert_sink.py` 与 compose `alert-webhook-logger` 服务，
AM webhook URL 由宿主占位改为同网络服务名，`repeat_interval` 仍 4h；
落盘文件 `monitoring/alert-sink/alert-events.jsonl` 已加入 `.gitignore`。
实测 3 行：真实规则告警 `ServiceUnavailable / node_exporter`、探针 firing + resolved；
receiver 均为 `default-webhook`，AM 最近 4 分钟无投递失败。
为使真实告警在新 URL 上重投，验证窗口内临时把 `repeat_interval` 改为 `1m`，
验证后已恢复 `4h` 并 reload 确认。`pushgateway` 组本轮未落盘（16:47 首次投递被取消、
4h 重投窗口未到），不伪造结果。

### 11.2 端口契约核对（6/6 通过）

`.env` 的 `GW_PUBLIC_BASE_URL` / `ORCH_PUBLIC_BASE_URL`、网关/编排容器内同名环境变量、
宿主端口映射三方均为 `9999` / `9100`，与 compose 头部约定一致。
此前已完成的脚本语法解析（0 错误）与 `.env` 端口核对结果沿用，不重跑、不重新读取脚本。

### 11.3 17:20 巡检 WARN 说明（**非业务写入**）

`observe_check.py --append @17:20` 结论 **WARN（P15 / F0 / W1 / S0）**：
`quota:usr:990001:token:2026-11` 的 Redis used 缓存键由基线 12 变为「无」。

只读核查：DB 真账 `quota_account.used` 仍为 `{"token": 12.0}`；
`usage_record` 21 / `quota_reservation` 12 / `quota_account` 5 行、测试行 0，与起算基线一致；
Redis `expired_keys=2 / evicted_keys=0 / maxmemory-policy=noeviction`；
`quota_service.py` 无删除 `_used_key` 的路径（只删 hold 键）；本轮未写 Redis。
判定：**Redis used 缓存键缺失，DB 真账正确，非业务写入、非计量丢失、非本轮监控变更所致**。

> 17:29 复核更正（仅更正结论措辞，不改运行态、不改基线、不改巡检口径）：
> 上文「TTL 到期」只是基于 `expired_keys=2` 的推断，**消失原因未确定**。
> `_period_ttl`（`quota_service.py:164`）把月度计数器 TTL 设到月末，实测
> `quota:usr:4:token:2026-11` TTL 1866610s（≈21.6 天，指向 2026-12-01），
> 同月同类型键不该在 11-09 到期；代码亦无删除 `_used_key` 的路径。
> 保留「无业务写入、非计量丢失」结论，但不把消失原因写成已证实的 TTL 到期。

缓存键重建机制（17:29 补查，修正此前「业务读取以 DB 值为底重建」的说法）：

- 读取端点 `quota_service.py:1126` 只是 `redis.get(...) or account.used` 的**展示回退，不写回 Redis**；
- `reconcile_active_accounts`（`quota_service.py:1160`，`base/start.py` 每分钟调度）方向为
  **Redis → PG**，以 `account.used` 为底叠加现存 Redis 键；`usr:990001` 在 `quota_active_owners`
  中，故 DB 真账保持 12，但**对账不会重建缺失的 Redis 键**；
- 只有写操作会重建：`reserve`（:333）用 DB 值播种（安全）；`_settle_redis_counters`（:791）
  用 `0` 播种后累加。因此**缺失窗口内若发生无预占直接 settle，Redis 实时 used 会从 0 起算，
  低估历史 12，使 `used + held > limit` 判断偏松**；DB 流水与真账不受影响，下一次 reserve
  会用 DB 值播种纠正。这是既有设计弱点、非本轮引入，观察期内不改业务代码，
  登记为 T7.5 收口后的改进项。

未擅自处置：不改起算基线 `observation-baseline.json`（保留 14 天对比口径）、
不改巡检脚本 R7 口径、不手工重建 Redis 缓存键。巡检侧 WARN 非 FAIL、退出码 0，
§5「WARN 均有说明」已由本节满足；但键不恢复则 14 天内每日均为 P15/F0/W1/S0、
需逐日登记，且 16/16 PASS 健康信号消失。若要立即恢复，需按 DB 真账重建该键
（值 12、TTL 到 2026-12-01，对齐 `usr:4`），属一次 `SET ... EX` 写入计量缓存，需单独授权；
**不建议**改基线或改脚本口径（会破坏 14 天对比、掩盖真实异常）。
此项按台账 §6「WARN 需登记写入来源」口径登记为「无业务写入」。

### 11.4 观察期影响

监控栈变更不涉及三个 L3 业务进程；Prometheus 未重启、AM 仅 reload、接收器为新增容器；
`mode=proxy_l3`、used/held 真账未变、三业务容器 healthy。**不重置计时**：
起算 13:33:40 +0800，最早收口 **2026-11-23 13:33 +0800**，不触发回切。
边界收敛：告警已能自动本地留痕；仍待的是外部值班通知渠道、`config.conf` 线下核对、
第 2 周 G1、三方签字与 T7.5 到期收口。
