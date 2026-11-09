# 目录整理后运行态验证报告

- 时间：2026-11-09 15:54–16:02 +0800
- 触发：三次目录整理（`7be9c13` 网关领域包迁入 → `2103fca` 常量下沉/编排解耦 → `84ae9b3` 改名 `common`）与运行容器切换（`c885f7d`，15:50:43）后的回归验证
- 判据：`reports/ops/l3-split-acceptance.md`（P6 T6.1–T6.7）、`reports/specs/l3-service-split/checklist.md`
- 性质：**只读、无写入验证**。未签发租约、未写计量数据、未停服务、未重跑 Linux 验证链
- 结论：所执行的判据全部通过，新目录布局未引入回归；发现 1 项需人工线下核对的安全差异（§7.1）

## 1. 验证环境

| 项 | 实测值 |
|---|---|
| compose | `deploy/l3/docker-compose.yml`（`name: agentpanel-l3`） |
| 容器 | `agentpanel-l3-l2-1` / `agentpanel-l3-l3-gateway-1` / `agentpanel-l3-l3-orchestration-1`，三者 `Up (healthy)` |
| 镜像 | `agentpanel-l2:local`、`agentpanel-l3-gateway:local`、`agentpanel-l3-orchestration:local` |
| 启动命令 | `python run.py`；`python services/gateway/run.py`；`sh -c 'export ORCHESTRATION_SERVICE_SECRET=$(cat /run/secrets/…); exec python services/orchestration/run.py'` |
| 端口 | `127.0.0.1:9998` / `9999` / `9100`，无 `0.0.0.0` |
| 运行用户 | 三容器 `uid=10001` |

## 2. 基础健康与容器安全（T6.1 / T6.5）

| 判据 | 实测 | 结论 |
|---|---|---|
| 三容器 healthy | compose `ps` 三者 `Up (healthy)` | 通过 |
| L2 `/health/health` | 200 `status=healthy`，`database/redis/qdrant` 均 healthy | 通过 |
| 网关 `/health` | 200 `status=ok`、`deployment=standalone`、`fail_closed=true` | 通过 |
| 网关 `/health/health`、`/health/live` | 200 `healthy` / 200 `alive` | 通过 |
| 编排 `/health/health` | 200 `status=healthy` | 通过 |
| 编排 `/health/orchestration` | 200 `mode=proxy_l3`、`write_enabled=true` | 通过 |
| 非 root | 三容器 `id -u` → `10001` | 通过 |
| 端口仅回环 | `docker port` 三条均 `127.0.0.1` | 通过 |
| 镜像层明文密钥 | `docker history --no-trunc` 扫 `requirepass\|SERVICE_SECRET=\|DB_PASSWORD=\|REDIS_PASSWORD=`，三镜像命中 0 | 通过 |
| 镜像内配置文件 | 网关/编排容器 0 命中；L2 容器命中 `/app/config.conf` → **见 §7.1** | 待人工核对 |

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
| L2 → L3 代理链路 | `9998/api/v1/harness/runs/nope` → **401**（编排侧返回，非 503），证明代理可达且不回落本进程 | 通过 |
| L2 内部额度接口拒绝匿名 | `/internal/v1/harness/quota/reserve`、`/settle`、`/clients/x/touch` 匿名 POST 均 401 | 通过 |
| L2 内部接口拒绝用户 JWT | 伪造 `Bearer eyJ…` POST reserve → 401 | 通过 |
| 网关匿名 / 错误租约 key | `POST /chat/completions` 匿名 401；`dgw.gl_invalid.secret` 401 | 通过 |
| 网关非法 JSON（无合法租约） | 401（鉴权先于解析，符合 fail-closed） | 通过 |
| 出网白名单 | `gateway_allowlist_check.py` 以 `services/gateway/common/service.py` 复跑，5 用例全部符合预期 | 通过 |
| 三入口 `/metrics` | 9998 / 9999 / 9100 均 200（7905 / 12199 / 11943 bytes） | 通过 |

> 「合法租约 + 非法 JSON → 400」需先由 L2 签发租约，属写入项，列入 §8 未执行。

## 5. 目录整理专项（三次提交后的回归）

| 判据 | 实测 | 结论 |
|---|---|---|
| 旧导入名 `services.gateway.gateway.*` | 活代码 0 处；仅 `common/constants.py:4`、`common/__init__.py:8` 两处 docstring 为历史时间线说明 | 通过 |
| `packages` 反向依赖 | `packages → services.* / base.*` 0 处 | 通过 |
| 编排依赖网关目录 | `services/orchestration → services.gateway` 0 处 | 通过 |
| 运行容器内布局 | L2、网关：`common/` 存在、`gateway/gateway/` 消失；编排：`/app/services/gateway` 整体不存在 | 通过 |
| manifest 三拆 | `base/plugins/harness/manifest.json` 含 `config.gateway_issuance`；`services/gateway/manifest.json` `name=l3-gateway`；`services/orchestration/manifest.json` `name=l3-orchestration`，后两者顶层键仅 `config/description/display_name/name/version`，无 `plugin_manager` | 通过 |
| 运行时标识连续性 | compose 服务名、容器/镜像名、manifest `name`、Prometheus job、指标 `service` 标签均未改 | 通过 |

## 6. 监控与观察期

| 项 | 实测 |
|---|---|
| Prometheus targets | 6 job：`aipaneladmin` / `l3-gateway` / `l3-orchestration` / `prometheus` **up**；`pushgateway` / `node_exporter` **down**（未起，白名单内） |
| 规则 | `aipaneladmin_alerts` 4 条 + `l3_split_alerts` 10 条 = **14 条** |
| firing 告警 | 2 条 `ServiceUnavailable`（`pushgateway` / `node_exporter`），巡检白名单内，无业务告警 |
| 观察期巡检 | `observe_check.py --json` @ `2026-11-09T16:01:26+08:00` → **16/16 PASS，verdict PASS**（容器健康、五端点、L2 代理、编排直连、配额 Redis 可读、held 无悬挂、used 基线一致、两 `/metrics`、Prometheus 抓取、规则加载、非预期告警） |
| 观察期状态 | 起算 `2026-11-09 13:33:40 +0800`，最早收口 `2026-11-23 13:33 +0800`，本次未重置计时 |

**指标命名备忘**（避免后续误用）：HTTP 计数器实际名为共享 registry 的 `http_requests_total`（非 `l3_http_requests_total`）；L3 业务指标为 `l3_lease_cache_lookups_total`、`l3_quota_operations_total`、`l3_health_check_status`、`l3_health_check_last_success_timestamp_seconds`、`l3_service_info`。零值序列已预注册。

## 7. 发现与差异

### 7.1 L2 容器内存在 `config.conf`（需人工线下核对）

- 实测：L2 运行容器 `/app/config.conf`，2394 字节，含 `db_password`、`password`、`api_key`、`sender_password`、`wechat_api_key` 等键名；另有两份 `.env.*.example` 示例文件。
- 与 P6 验收 §6「镜像无配置/密钥，find 仅命中 sysfs」的记录不一致。
- **未判定部分**：该文件是镜像自带还是运行时挂载、键值为真实凭据还是占位符。核查需读取敏感值，用户已明确选择**拒绝共享敏感内容**，因此本次未读取、未复述、未以任何方式推断或绕过该拒绝。
- 建议：由负责人在受控环境只读核对（只看键名/长度，不打印值）；若确为真实凭据，应从镜像构建中剔除并改用 env / secrets 注入，并复核 `.dockerignore`。
- 归属：本项**不是三次目录整理引入**（整理未改 L2 的配置复制规则），登记为安全项待办，不阻断本次验证结论。

### 7.2 其它

- 两处旧路径字面量仅存在于 docstring（`common/constants.py:4`、`common/__init__.py:8`），用于说明「先 `gateway/gateway/` 后改名 `common/`」的时间线，不影响导入。
- `pushgateway` / `node_exporter` 未起、Alertmanager 未配置（规则求值但不会外发通知）仍为 P7 已知限制，见验收报告 §8.4。
- 15:50 容器切换造成进程内 Counter 归零，Prometheus 按 counter reset 处理；`rate()` / `increase()` 在 15:50 前后窗口需人工注意，已在 `l3-split-p7-observation-log.md` §7 登记。

## 8. 未执行项（需授权后另行安排）

| 项 | 判据来源 | 未执行原因 / 影响 |
|---|---|---|
| 租约签发 → 网关 `/chat/completions` 200、SSE 透传、`usage_record` 记账、租约吊销 | P6 §4 | 需 L2 签发租约并写 `usage_record`，**动计量数据** |
| 合法租约 + 非法 JSON → 400 | P1 清单 | 同上，需真实租约 |
| 预占 / 结算 / 释放、幂等、G1-A/B/C 20 并发 | P6 §5 | 改 `used` / `held`，巡检 `used 基线对比` 会 WARN，观察期需单独登记 |
| 停编排容器 → L2 代理 503；Redis / L2 down 故障注入 | P6 §7 | 中断服务或依赖，观察期内不擅自破坏 |
| Linux 验证链 `deploy/harness-linux-verify/run.ps1` 重跑 | `VERIFICATION.md` §复现 | `-v out:/out` 会**覆盖 `out/` 14 个原始证据孤本**，需先备份到新目录再跑 |
| T7.5 收口（删灰度开关 / 旧编排代码 / 更新架构图） | `checklist.md` | 14 天观察期最早 2026-11-23 13:33 结束，未到期 |

## 9. 结论

三次目录整理与容器切换后的**只读回归验证全部通过**：健康端点、依赖只读、配置契约 fail-closed、代理链路、内部接口鉴权、出网白名单、镜像布局、依赖方向、监控抓取与 16 项观察期巡检均无回归。运行态与新代码布局一致（网关 CMD 已是 `services/gateway/run.py`，编排镜像内无网关目录）。

观察期继续有效，起算与最早收口时间不变。§7.1 的安全差异需人工线下核对；§8 的写入与破坏性验证待授权后安排，其中 Linux 验证链重跑必须先备份 `out*/` 原始证据。
