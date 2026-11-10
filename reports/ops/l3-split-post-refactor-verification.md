# 目录整理后运行态验证报告

- 时间：2026-11-09 15:54–16:02 +0800
- 触发：三次目录整理（`7be9c13` 网关领域包迁入 → `2103fca` 常量下沉/编排解耦 → `84ae9b3` 改名 `common`）与运行容器切换（`c885f7d`，15:50:43）后的回归验证
- 判据：`reports/ops/l3-split-acceptance.md`（P6 T6.1–T6.7）、`reports/specs/l3-service-split/checklist.md`
- 性质：**只读、无写入验证**。未签发租约、未写计量数据、未停服务、未重跑 Linux 验证链
- 结论：只读判据与授权后的写入/破坏性判据全部通过，新目录布局未引入回归；发现 1 项需人工线下核对的安全差异（§7.1）

## 1. 验证环境

| 项 | 实测值 |
|---|---|
| compose | `deploy/gateway/docker-compose.yml`（`name: agentpanel`） |
| 容器 | `agentpanel-app` / `agentpanel-gateway` / `agentpanel-orchestration`，三者 `Up (healthy)` |
| 镜像 | `agentpanel-app:local`、`agentpanel-gateway:local`、`agentpanel-orchestration:local` |
| 启动命令 | `python run.py`；`python services/gateway/run.py`；`sh -c 'export ORCHESTRATION_SERVICE_SECRET=$(cat /run/secrets/…); exec python services/orchestration/run.py'` |
| 端口 | `127.0.0.1:9998` / `9999` / `9100`，无 `0.0.0.0` |
| 运行用户 | 三容器 `uid=10001` |

## 2. 基础健康与容器安全（T6.1 / T6.5）

| 判据 | 实测 | 结论 |
|---|---|---|
| 三容器 healthy | compose `ps` 三者 `Up (healthy)` | 通过 |
| app `/health/health` | 200 `status=healthy`，`database/redis/qdrant` 均 healthy | 通过 |
| 网关 `/health` | 200 `status=ok`、`deployment=standalone`、`fail_closed=true` | 通过 |
| 网关 `/health/health`、`/health/live` | 200 `healthy` / 200 `alive` | 通过 |
| 编排 `/health/health` | 200 `status=healthy` | 通过 |
| 编排 `/health/orchestration` | 200 `mode=proxy`、`write_enabled=true` | 通过 |
| 非 root | 三容器 `id -u` → `10001` | 通过 |
| 端口仅回环 | `docker port` 三条均 `127.0.0.1` | 通过 |
| 镜像层明文密钥 | `docker history --no-trunc` 扫 `requirepass\|SERVICE_SECRET=\|DB_PASSWORD=\|REDIS_PASSWORD=`，三镜像命中 0 | 通过 |
| 镜像内配置文件 | 网关/编排容器 0 命中；app 容器命中 `/app/config.conf` → **见 §7.1** | 待人工核对 |

## 3. 依赖连通、配置契约与 fail-closed（T6.2 / P1）

| 判据 | 实测 | 结论 |
|---|---|---|
| PG 只读 | `/health/orchestration` → `checks.readonly_database.checks.transaction_read_only="on"`；`write_probe.message="cannot execute CREATE SCHEMA in a read-only transaction"` | 通过 |
| Redis 别名 | 健康体 `Redis connection OK`（`agentredis:6379`） | 通过 |
| schema 正向 | `/health/orchestration` → `service_credential=healthy`（只读连接可用且写被拒） | 通过 |
| schema 负向 | 一次性容器 `ORCH_SCHEMA_MIN_VERSION=2`，`SUPPORTED_SCHEMA_VERSION=1` → `SchemaCheckError: 数据库要求 schema 版本 2，当前代码仅支持 1`，检查在 DB fetch 之前即拒绝 | 通过 |
| 配置契约必填缺失 | 一次性容器不带环境变量执行 `services/gateway/run.py` → **退出码 2**，提示缺少 `[DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, REDIS_PASSWORD]` | 通过 |
| `coerce()` 类型覆盖 | `str / int / float / bool / list / int_list / json` 七类实测值与期望一致 | 通过 |
| 三入口互不 import | `run.py` 仅 sys/os/configparser 等；两个服务 `run.py` 仅 `pathlib / sys / app.main` | 通过 |
| 全仓语法 | 847 个 `.py`，`compile()` 失败 0 | 通过 |

> 退出码说明沿用 P6 §3：配置契约类为 2；schema 断言失败经 uvicorn 生命周期异常退出为 3。本次以代码级断言验证拒绝逻辑，未重复制造一次真实启动失败（避免起半可用进程）。

## 4. 业务边界（无写入路径）

| 判据 | 实测 | 结论 |
|---|---|---|
| app → 独立服务 代理链路 | `9998/api/v1/harness/runs/nope` → **401**（编排侧返回，非 503），证明代理可达且不回落本进程 | 通过 |
| app 内部额度接口拒绝匿名 | `/internal/v1/harness/quota/reserve`、`/settle`、`/clients/x/touch` 匿名 POST 均 401 | 通过 |
| app 内部接口拒绝用户 JWT | 伪造 `Bearer eyJ…` POST reserve → 401 | 通过 |
| 网关匿名 / 错误租约 key | `POST /chat/completions` 匿名 401；`dgw.gl_invalid.secret` 401 | 通过 |
| 网关非法 JSON（无合法租约） | 401（鉴权先于解析，符合 fail-closed） | 通过 |
| 出网白名单 | `gateway_allowlist_check.py` 以 `services/gateway/common/service.py` 复跑，5 用例全部符合预期 | 通过 |
| 三入口 `/metrics` | 9998 / 9999 / 9100 均 200（7905 / 12199 / 11943 bytes） | 通过 |

> 「合法租约 + 非法 JSON → 400」需先由 app 签发租约，属写入项，列入 §8 未执行。

## 5. 目录整理专项（三次提交后的回归）

| 判据 | 实测 | 结论 |
|---|---|---|
| 旧导入名 `services.gateway.gateway.*` | 活代码 0 处；仅 `common/constants.py:4`、`common/__init__.py:8` 两处 docstring 为历史时间线说明 | 通过 |
| `packages` 反向依赖 | `packages → services.* / base.*` 0 处 | 通过 |
| 编排依赖网关目录 | `services/orchestration → services.gateway` 0 处 | 通过 |
| 运行容器内布局 | app、网关：`common/` 存在、`gateway/gateway/` 消失；编排：`/app/services/gateway` 整体不存在 | 通过 |
| manifest 三拆 | `base/plugins/harness/manifest.json` 含 `config.gateway_issuance`；`services/gateway/manifest.json` `name=gateway`；`services/orchestration/manifest.json` `name=orchestration`，后两者顶层键仅 `config/description/display_name/name/version`，无 `plugin_manager` | 通过 |
| 运行时标识连续性 | compose 服务名、容器/镜像名、manifest `name`、Prometheus job、指标 `service` 标签均未改 | 通过 |

## 6. 监控与观察期

| 项 | 实测 |
|---|---|
| Prometheus targets | 6 job：`aipaneladmin` / `gateway` / `orchestration` / `prometheus` **up**；`pushgateway` / `node_exporter` **down**（未起，白名单内） |
| 规则 | `aipaneladmin_alerts` 4 条 + `agentpanel_alerts` 10 条 = **14 条** |
| firing 告警 | 2 条 `ServiceUnavailable`（`pushgateway` / `node_exporter`），巡检白名单内，无业务告警 |
| 观察期巡检 | `observe_check.py --json` @ `2026-11-09T16:01:26+08:00` → **16/16 PASS，verdict PASS**（容器健康、五端点、app 代理、编排直连、配额 Redis 可读、held 无悬挂、used 基线一致、两 `/metrics`、Prometheus 抓取、规则加载、非预期告警） |
| 观察期状态 | 起算 `2026-11-09 13:33:40 +0800`，最早收口 `2026-11-23 13:33 +0800`，本次未重置计时 |

**指标命名备忘**（避免后续误用）：HTTP 计数器实际名为共享 registry 的 `http_requests_total`（非 `l3_http_requests_total`）；独立服务 业务指标为 `lease_cache_lookups_total`、`quota_operations_total`、`health_check_status`、`health_check_last_success_timestamp_seconds`、`service_info`。零值序列已预注册。

## 7. 发现与差异

### 7.1 app 容器内存在 `config.conf`（需人工线下核对）

- 实测：app 运行容器 `/app/config.conf`，2394 字节，含 `db_password`、`password`、`api_key`、`sender_password`、`wechat_api_key` 等键名；另有两份 `.env.*.example` 示例文件。
- 与 P6 验收 §6「镜像无配置/密钥，find 仅命中 sysfs」的记录不一致。
- **未判定部分**：该文件是镜像自带还是运行时挂载、键值为真实凭据还是占位符。核查需读取敏感值，用户已明确选择**拒绝共享敏感内容**，因此本次未读取、未复述、未以任何方式推断或绕过该拒绝。
- 建议：由负责人在受控环境只读核对（只看键名/长度，不打印值）；若确为真实凭据，应从镜像构建中剔除并改用 env / secrets 注入，并复核 `.dockerignore`。
- 归属：本项**不是三次目录整理引入**（整理未改 app 的配置复制规则），登记为安全项待办，不阻断本次验证结论。

### 7.2 其它

- 两处旧路径字面量仅存在于 docstring（`common/constants.py:4`、`common/__init__.py:8`），用于说明「先 `gateway/gateway/` 后改名 `common/`」的时间线，不影响导入。
- `pushgateway` / `node_exporter` 未起仍为 P7 已知限制，见验收报告 §8.4；Alertmanager 已于 16:46 接入（规则可送达并经 webhook 投递，正式通知渠道待运维配置），见 `l3-split-p7-metrics.md` §8。
- 15:50 容器切换造成进程内 Counter 归零，Prometheus 按 counter reset 处理；`rate()` / `increase()` 在 15:50 前后窗口需人工注意，已在 `l3-split-p7-observation-log.md` §7 登记。

## 8. 首次验证时未执行的项（16:04 已授权补验，结果见 §10）

> 下表是 16:02 首次只读验证时的状态；用户于 16:04 授权后已执行除 T7.5 外的全部项；
> 16:23 后又补完 settle、Redis / app down 注入与收口准备，见 §11。表格保留历史状态不改。

| 项 | 判据来源 | 未执行原因 / 影响 |
|---|---|---|
| 租约签发 → 网关 `/chat/completions` 200、SSE 透传、`usage_record` 记账、租约吊销 | P6 §4 | 需 app 签发租约并写 `usage_record`，**动计量数据** |
| 合法租约 + 非法 JSON → 400 | P1 清单 | 同上，需真实租约 |
| 预占 / 结算 / 释放、幂等、G1-A/B/C 20 并发 | P6 §5 | 改 `used` / `held`，巡检 `used 基线对比` 会 WARN，观察期需单独登记 |
| 停编排容器 → app 代理 503；Redis / app down 故障注入 | P6 §7 | 中断服务或依赖，观察期内不擅自破坏 |
| Linux 验证链 `deploy/harness-linux-verify/run.ps1` 重跑 | `VERIFICATION.md` §复现 | `-v out:/out` 会**覆盖 `out/` 14 个原始证据孤本**，需先备份到新目录再跑 |
| T7.5 收口（删灰度开关 / 旧编排代码 / 更新架构图） | `checklist.md` | 14 天观察期最早 2026-11-23 13:33 结束，未到期；16:32 仅完成收口准备（§11.3） |

## 9. 结论

三次目录整理与容器切换后的**只读回归验证全部通过**：健康端点、依赖只读、配置契约 fail-closed、代理链路、内部接口鉴权、出网白名单、镜像布局、依赖方向、监控抓取与 16 项观察期巡检均无回归。运行态与新代码布局一致（网关 CMD 已是 `services/gateway/run.py`，编排镜像内无网关目录）。

观察期继续有效，起算与最早收口时间不变。§7.1 的安全差异仍需人工线下核对；§8 的写入与破坏性项已于 16:04 获授权并全部完成（T7.5 除外），见 §10，且 Linux 验证链重跑前已备份原始证据、实际输出到新目录未覆盖孤本。16:23–16:32 另补完 settle、Redis / app down 注入与 T7.5 收口准备，见 §11；三项均未改运行代码。

## 10. 授权后补验（2026-11-09 16:04–16:13 +0800）

用户于 16:04 对 §8 的写入/破坏性项授权（T7.5 收口因观察期时间约束仍不执行）。执行前先把
`out/`、`out-network/` 与基线备份到 `.workbuddy/evidence-backup-20261109-1604/`
（15 文件 / 1,053,201 字节），并把 Linux 验证输出改到新目录；**原 `out/` 与 `out-network/`
的 mtime / 大小全程未变**。

### 10.1 网关数据面完整链路（独立实例，fixture 自动清理）

以 `services/gateway/run.py` 起 9990 独立实例（`GW_ALLOW_LOOPBACK=true`、白名单含
`127.0.0.1`、`GW_MAX_CONCURRENT_REQUESTS_PER_OWNER=1`），执行
`services/gateway/tests/verify_gateway.py`：**66 通过 / 0 失败，退出码 0**，覆盖 V3–V11：

| 组 | 关键结果 |
|---|---|
| V3 鉴权 | 缺凭据 / JWT / 非 dgw / secret 不符 / 已吊销 / 已过期均 401；会话关闭与 run 终态 403；鉴权失败不触达上游；超 RPM 429 |
| V4 白名单 | 非白名单域名 403 且未触达上游；临时 9991 实例 `allow_loopback=false` 拒绝回环 |
| V5 / V6 转发与记账 | 合法租约非流式 200、`dsh_session_log` 已剥离；**SSE 逐字节透传 361/361 字节**；`usage_record` 2 行、`source=gateway`、`idem_key` 前缀 `gw:<lease_id>:` 且每次唯一；非流式与流式用量口径均 12/8/20 |
| V7 失败记账 | 403 请求恰好 1 行、`resource_type=gateway_error`、`amount=0` |
| V8 预算 / 并发 / 截断 | 预算耗尽 402 且自动吊销、并发上限 429、流式越界截断 `partial=true` 并单独记账 |
| V9 Redis 缓存 | `gw:lease:state:*` TTL=8s；吊销写穿删除 |
| V10 DB 兜底 | 临时 9992 实例 `REDIS_ENABLED=false`，请求仍 200、账户用量 +20、并发槽释放 |
| V11 审计 | 4 类事件齐全、`event_source=gateway`、不落虚拟 key 明文 |

脚本 `finally` 执行 `cleanup_db` + `cleanup_redis`；9990/9991/9992 端口实测均已关闭。
fixture 使用 `p3v_` 前缀与 `usr/999001`，与观察期基线键 `usr/990001`、`org/14` 不同。

### 10.2 app 内部额度链路（真实主体，基线精确恢复）

在编排容器内经 `app/app_quota_client._post` 调用 app 内部额度 API；服务凭据由容器内 shell
读取 `/run/secrets/` 后 export、脚本经 stdin 注入，**密钥未进入任何输出**。
先用独立 `usr/999002` 探测得到 `hold_id=""` —— 这是 `quota_estimate` 对未绑定套餐主体
「不计量」的设计行为（未写任何数据），不是回归；改用 P6 使用过的 `org:14`：

| 场景 | 结果 |
|---|---|
| reserve(100) | 返回真实 `orch:p7v_<tag>_a` |
| 重复 reserve 同 hold | 返回同一 hold_id，幂等 |
| G1-A：20 并发 reserve 同 hold | 20/20 成功，**仅 1 个唯一 hold** |
| G1-C：20 并发 release | 20/20 成功，**恰好 1 次 `released=true`** |
| release / 重复 release | `true` / `false` |

当时未执行 settle：`usage_record` 记账已由 §10.1 的 V6/V7/V8/V10 覆盖，避免重复写计量表
（该省略项已于 16:29 补验，见 §11.1）。
验证后清理并逐项核对：`quota:org:14:token:2026-11=450`、`quota_held:*` 全 0、
`quota_reservation` 12 行、`usage_record` 21 行、测试行 0 残留，**与验证前完全一致**。

### 10.3 故障注入

`docker compose stop orchestration` 后，app 代理 `/api/v1/harness/runs/nope` 返回
**503 `orchestration_downstream_unavailable`**（`ConnectError: Name or service not known`），
未回落本进程；`up -d --wait` 恢复后回到 401，三容器 healthy。
当时未做 Redis / app down 注入（会扩大中断面，且 P6 §7 已记录同类结果）；
这两项已于 16:30–16:31 补做，见 §11.2。

### 10.4 Linux 容器验证链重跑

用改名后的 `services/gateway/common/service.py` 挂载路径重跑（隔离网络 `--network none`），
退出码 0，9 个新证据文件落在 `deploy/harness-linux-verify/out-rerun-20261109/`：

- `1_pre_execute_hook` PASS、`2_workspace_escape` PASS、`3_egress` PASS；
- `4_native_approval` **FAIL**（`session/request_permission` 0 次、`no approval channel is available`）——
  与 2026-11-07 原始结论一致，是已登记的已知限制，不是本次目录改名的回归；
- `gateway_allowlist` **5 用例全部通过**，证明新挂载路径有效；
  `placeholder_key_used=true`、`real_provider_called=false`。

原始证据未被覆盖，另存本地备份 `.workbuddy/evidence-backup-20261109-1604/`（不入库）。

### 10.5 恢复核验与观察期影响

巡检 **16/16 PASS、verdict PASS @ 2026-11-09T16:12:28+08:00**；`used` 3 键与基线一致、
`held` 全 0、`quota_holds_index` 空；三容器 healthy；临时端口 9990/9991/9992 全关闭；
Prometheus 抓取与非预期告警仍 PASS。

唯一观察期影响是故障注入使编排容器重启，**进程内指标 Counter 再次归零**，
`rate()` / `increase()` 在 16:08 前后窗口需人工注意；业务计量数据最终完全恢复。
未改业务分支、未删旧代码、`mode` 仍 `proxy`，起算 13:33:40 与最早收口
2026-11-23 13:33 不变，不触发回切。完整登记见 `l3-split-p7-observation-log.md` §8。


## 11. 后续补验与收口准备（2026-11-09 16:23–16:32 +0800）

用户要求补完「仍未做的三项」，并明确选择 **「保留观察期，先做收口准备」**。本节三项均
**不删代码、不改 `mode`、不改架构图、不重置计时**；完整台账与逐项数据见
`l3-split-p7-observation-log.md` §9。操作人：WorkBuddy Agent 代执行（待签字复核）。

### 11.1 额度 settle / G1-B（补齐 §10.2 的省略项）

宿主侧读取本地 secrets 做基线采集的一次尝试被敏感内容保护拦截（审批超时），**未重试、
未推断、未绕过**；改回 §10 已采用的容器内合规路径，凭据只在容器内流转、不进入任何输出，
基线采集 → 验证 → 清理 → 核对一次完成（tag `p7s_adb4b703`）。

| 判据 | 结果 |
|---|---|
| reserve(100) | 返回 `orch:p7s_adb4b703_a` |
| 单条 settle(60) / 重复同 idem_key | `settled=1` → `settled=0 / skipped=1` |
| **G1-B：20 并发 settle（20 个不同 idem_key）** | 20/20 成功、`settled_sum=20`、`skipped_sum=0` |
| 同批 20 并发重复 settle | 20/20 成功、`settled_sum=0`、`skipped_sum=20`（零重复写入） |
| release / 重复 release | `true` / `false` |
| 结算过程中 | `usage_record` +21 行、`quota_reservation` +1 行、used 450→530、held 全 0 |
| 清理后 | `redis_exact=true`、`db_exact=true`；used 回 450、DB 回 21/12/5、测试行 0 |

**10/10 判据通过**，§4 的 G1-A / G1-B / G1-C 至此全部实测通过。

### 11.2 Redis / app down 故障注入（补齐 §10.3 的省略项）

| 判据 | 实测 |
|---|---|
| Redis down | app `/health/health` 与编排 `/health/health` 不可用；网关 `/health` 200；编排 `/health/orchestration` 200；编排直连读 401；**网关无凭据 `/chat/completions` 仍 401，未 fail-open** |
| app down | app 端口 502（服务不可用）；编排健康 200、编排直连读 401；网关 `/health` 200；**编排额度写链路抛 `QuotaUnavailable` / `ConnectTimeout`，未伪造成功、未回落本进程** |
| 恢复 | `docker start agentredis` + `compose up -d --wait` → 三容器 healthy、四健康端点 200、代理 401 |

首次探测脚本自报 3 项 FAIL 均为判据口径问题（响应体截断致 `mode` 解析 null、
「app 不可达」硬编码期望 -1 而实际 502、由此连带的 `mode unchanged`），**非系统异常**；
补验完整读取确认 `mode=proxy / write_enabled=True`，判据改为 `!=200` 后 **10/10 PASS**。
此处如实登记，不把口径修正伪装成首次全绿。

### 11.3 T7.5 收口准备（仅留痕与预案，不执行）

1. 台账 §5 五项准入补齐「当前状态 / 证据位置 / 责任人 / 到期动作」，**checkbox 全部保持未勾**；
   新增 §5.1 三方签字栏（代理不可代签）。
2. 台账 §4 周次表登记第 1 周 G1-A/B/C 结果与抽查前后 `used`/`held` 对照，第 2 周仍为空。
3. 新建 `reports/ops/l3-split-t75-closeout-plan.md`：到期删除范围（P4 T4.1–T4.12）、
   `mode` 开关 9 个读取点、架构图/规格文档资产、分提交顺序、验证命令、留痕签字与代码级回退路径。

`tasks.md` / `checklist.md` / `spec.md` / `agentpanel-architecture.mmd` 的 T7.5 状态与架构图
**均未改动、未提前打勾**，仅在预案中列为到期同步项。§7.1 的 `config.conf` 安全差异仍为
线下人工受控核对项，本轮未读取、未推断任何敏感值。

### 11.4 恢复核验与观察期影响

巡检 **16/16 PASS @ 2026-11-09 16:31:51 +0800**；`mode=proxy`、`write_enabled=true`；
used 3 键 `450 / 93294 / 12` 与起算基线一致、held 全 0、`quota_holds_index` 空；
DB 21 / 12 / 5 行、测试行 0；三容器 healthy、Redis 已恢复。Redis 重启后一个值为 0 的
`quota_held:org:14` 空壳键（非起算基线键，§10 补验残留）TTL 自然到期消失，held 键集合
回到起算基线，业务计量数据无变化。

唯一实质影响：16:30–16:31 的 Redis 与 app 容器重启使**进程内指标 Counter 归零**，
`rate()` / `increase()` 在 16:31 前后窗口的负增量不代表业务下跌（继 15:50、16:08 之后第三次）。
未改业务分支、未删旧代码、未改 `mode`、未动起算基线，**不重置 14 天计时**：
起算 13:33:40 +0800，最早收口 2026-11-23 13:33 +0800，不触发回切。
