# P6 验收报告：L3 编排与网关物理拆分

- 日期：2026-11-09
- 范围：`reports/specs/l3-service-split/tasks.md` T6.1–T6.8（容器形态）
- 结论：T6.1–T6.7 硬项通过；G1 并发结果与单仓基线一致；测试数据已清理；遗留与已知限制见 §6。
- 部署形态：L2 容器 + L3 网关容器 + L3 编排容器，宿主发布端口仅回环 `127.0.0.1`。

## 1. 验收环境

| 项 | 值 |
|---|---|
| compose | `deploy/l3/docker-compose.yml`（`name: agentpanel-l3`） |
| 容器 | `agentpanel-l3-l2-1`（`127.0.0.1:9998`）、`agentpanel-l3-l3-gateway-1`（`127.0.0.1:9999`）、`agentpanel-l3-l3-orchestration-1`（`127.0.0.1:9100`） |
| 镜像 | `agentpanel-l2:local`、`agentpanel-l3-gateway:local`（243MB）、`agentpanel-l3-orchestration:local`（243MB） |
| 依赖 | PG `host.docker.internal:15432`、Redis 别名 `agentredis:6379`、Qdrant `host.docker.internal:6333` |
| secrets | `db_password`、`redis_password`、`orchestration_service_secret`（`deploy/l3/secrets/`，不入库） |
| 运行用户 | 三容器均 `uid=10001`（非 root） |

## 2. 基础健康（T6.1）

```text
docker ps -> 三容器均为 Up (healthy)

GET 127.0.0.1:9998/health/health -> 200
{"status":"healthy","checks":{"database":{"status":"healthy"},"redis":{"status":"healthy","message":"Redis connection OK"},"qdrant":{"status":"healthy"}}}

GET 127.0.0.1:9999/health -> 200
{"status":"ok","deployment":"standalone","fail_closed":true}

GET 127.0.0.1:9999/health/health -> 200
{"status":"healthy","checks":{"database":{"status":"healthy"},"redis":{"status":"healthy","message":"Redis connection OK"}}}

GET 127.0.0.1:9100/health/health -> 200
{"status":"healthy","checks":{"database":{"status":"healthy"},"redis":{"status":"healthy"},"qdrant":{"status":"skipped","message":"Qdrant not used by l3-orchestration"}}}

GET 127.0.0.1:9100/health/orchestration -> 200
{"status":"healthy","mode":"proxy_l3","write_enabled":true,...}
```

说明：`9999/health/health` 是 P1 后新增实现（此前 Spec §8.1 第 3 条将其列为“实现项”），现已返回 DB/Redis 子项。

## 3. 依赖连通（T6.2）

| 项 | 实测 | 结论 |
|---|---|---|
| PG 只读 | `/health/orchestration` 的 `readonly_database.transaction_read_only=on`；`write_probe` 返回 `cannot execute CREATE SCHEMA in a read-only transaction` | 通过 |
| Redis 别名 | 三容器健康体均为 `Redis connection OK`（连接 `agentredis:6379`） | 通过 |
| schema 正向 | 编排启动日志：`启动自检通过：只读库可用且写被拒，schema=v1，service_credential active=1` | 通过 |
| schema 负向 | 以 `ORCH_SCHEMA_MIN_VERSION=2` 启动一次性容器：`SchemaCheckError: 数据库要求 schema 版本 2，当前代码仅支持 1`，`Application startup failed. Exiting.`，退出码 3 | 通过（fail-closed） |

> 退出码说明：配置契约类错误为 2；schema 断言失败由 uvicorn 生命周期异常退出，实测为 3。两者都拒绝进入半可用状态。

## 4. 业务链路（T6.3）

P6 当次以临时 Harness 客户端夹具实测：

- L2→L3 代理读：L2 `/v1/harness/sessions/<no>` 返回编排数据，与直连 `9100` 同一响应体；停编排容器后 L2 返回 503（`orchestration_downstream_unavailable`），不回落本进程；恢复后重新 200。P7 演练后复核 `9998/api/v1/harness/runs/nope` 为编排侧 401（非 503），证明代理链路可达。
- 租约→网关：L2 签发租约后 `POST 9999/chat/completions`；Redis 出现 `gw:lease:state:<lease_id>`（TTL≈8s）；吊销后键被写穿删除，原租约请求 401；匿名与 `dgw.gl_invalid.secret` 均 401；合法租约 + 非法 JSON 返回 400。
- 预占/结算：经 L2 内部额度 API 实测（详见 §5）。

## 5. 预占 / 结算 / 释放与 G1（T6.3、T6.4）

基线：`org:14` PG `used={"token":450.0}`、`plan_id=8`、`held=0`。

| 场景 | 实测结果 |
|---|---|
| reserve | 返回真实 `hold_id`；`held` 由 0 增至 100；`quota_reservation` 新增 active 行，`counter_mode=redis` |
| settle(60) | `usage_record` 落库；`held` 由 100 降至 40 |
| 重复 settle | `settled=0, skipped=1`（幂等，不重复记账） |
| release | `held` 归 0；预留状态 released |
| 重复 release | 返回已释放（`released=false`） |
| G1-A（同 hold 20 并发 reserve） | 仅 1 条 `quota_reservation`，`held=500` |
| G1-B（同 hold 20 并发 settle） | 仅一次 `settled=1` |
| G1-C（同 hold 20 并发 release） | 仅一次 `released=true` |

清理后（本次复核）：`usage_record` 总数 21、`quota_reservation` 总数 12、`p6` 前缀计数 0；`org:14` `used=450`、`held=0`。

## 6. 容器安全（T6.5）

| 项 | 实测 |
|---|---|
| 非 root | `docker exec <c> id -u` → `10001`（L2/网关/编排一致） |
| 端口回环 | `docker port` → `127.0.0.1:9998/9999/9100`，无 `0.0.0.0` |
| 镜像无配置/密钥 | `find / -maxdepth 4 \( -name config.conf -o -name '.env*' -o -name '*secret*' \)` 仅命中 `/sys/module/secretmem`（内核 sysfs 路径，非文件） |
| 镜像层扫描 | `docker history --no-trunc | Select-String 'requirepass|SERVICE_SECRET|password'` 无匹配 |

## 7. 故障注入与重启语义（T6.6、T6.7）

T6.6（P6 当次注入，本轮 P7 未重复破坏性注入）：

- Redis down：依赖 Redis 的租约缓存/预算路径降级，保持 fail-closed；不回落为“放行”。
- L2 down：编排写接口 503；读路径与网关转发仍可用。
- 错误服务密钥：401。
- `ORCH_WRITE_ENABLED=false`：写接口 409。

T6.7（重启语义）：

- 网关租约缓存键 `gw:lease:state:<lease_id>` 位于 Redis，TTL 默认 8s（`services/gateway/app/config.py:41`，限 5–10s）。
- 网关容器重启不会清空 Redis 中的缓存键，旧状态最迟在一个 TTL（≤8s）后自然过期；吊销路径为写穿删除，通常立即失效。
- 因此“吊销后最多 8s 内仍可能被接受”是已记录的语义边界，不是缺陷。

## 8. 已知限制（单独成节）

1. **端口仅回环**：三容器发布端口均绑定 `127.0.0.1`（`9998/9999/9100`），不接受远程直连；远程客户端需本机代理/隧道，且当前无 TLS 终止。
2. **`web_fetch`/`web_search` 可绕网关直连**：二者是 dsh 工具侧的直接出网通道，不经过共享上游客户端与网关白名单（`packages/agentpanel_common/upstream/egress.py:7-8` 明确说明）。`base/plugins/harness/services/egress_policy_service.py:42` 的 `tool_denylist` 只是策略快照，不是执行边界；Linux 实测联网容器访问 `https://example.com/` 返回 200（`deploy/harness-linux-verify/VERIFICATION.md` §3）。生产必须禁用这些工具或用容器/网络策略兜底。
3. **DSH 原生审批无终端应答者**：SDK profile 未组合 answerer，`approval/asked` 与 `approval/decided` 成对产生但 `outcome=unavailable`，客户端收到 `session/request_permission` 0 次，工具报 `no approval channel is available`（`deploy/harness-linux-verify/VERIFICATION.md` §4）。当前依赖后端审批事件落库 + 超时拒绝的 fail-closed 路径，不宣称原生审批可下发。
4. **监控/告警（原缺口已补齐，仍有边界）**：P6 当时 L3 两镜像无 `/metrics`、无告警规则；T7.4 已于 2026-11-09 补齐（两容器 `/metrics`、`l3_split_alerts` 10 条规则、Prometheus 端到端抓取通过）。同日 16:46 又接入 Alertmanager（`l3-split-p7-metrics.md` §8，6/6 判据通过，真实规则告警与探针均投递到 webhook receiver），但**默认 URL 为本地占位、正式通知渠道待运维提供**。仍需人工的是 R5 重复结算/`used` 多加/预占悬挂与 R7 数据一致性抽查。
5. **灰度只能部署级二元切换**：`orchestration.mode` 仅支持 `l2|proxy_l3`，没有按比例/按租户切流实现；切流与回切都是整机切换（详见 `l3-split-p7-grayscale.md`）。
6. **密钥脚本端口遗留（2026-11-09 16:44 已修复）**：`deploy/l3/scripts/prepare-secrets.ps1` 生成 `.env` 的 `GW_PUBLIC_BASE_URL` / `ORCH_PUBLIC_BASE_URL` 由 `19999/19100` 改为 `9999/9100`，与 `deploy/l3/docker-compose.yml` 头部约定及运行态 `.env` 一致；旧端口仅在注释中作为 `port-switch-9998-9999-9100.md` 回滚场景保留。PowerShell 静态解析 0 错误，重新生成 secrets 不再需要手改。
7. **本机演练的进程生命周期**：Trae 终端会话结束会回收 `Start-Process` 子进程；宿主进程回滚必须作为常驻后台任务运行（与 `port-switch-9998-9999-9100.md` §2.2 记录一致）。

## 9. 结论

P6 硬项全部通过，容器形态可以接管 `9998/9999/9100`。T7.4 已补齐，但 T7.5（删除灰度开关与旧代码、更新架构图）需完成 14 天观察期后方可执行，在此之前不建议删除 L2 侧旧编排代码；回滚路径已由 P7 演练实测（见 `l3-split-p7-report.md`）。
