# P7 报告：文档收尾、灰度方案与回滚演练

- 日期：2026-11-09
- 范围：`reports/specs/l3-service-split/tasks.md` T7.1–T7.5
- 前提：P6 验收通过（`l3-split-acceptance.md`）；回滚手册 `port-switch-9998-9999-9100.md` §2
- 原则：不改业务逻辑代码；演练前后校验 `org:14` / `usr:4` 的 `used` 不变
- 后续补充：本报告落盘后同日补齐 T7.4（只加观测旁路、不改业务分支），详见 `reports/ops/l3-split-p7-metrics.md`；下表 T7.4 状态已同步

## 1. P7 条目状态

| ID | 状态 | 产出/说明 |
|---|---|---|
| T7.1 运维 runbook | 完成 | `reports/ops/l3-split-p7-runbook.md`（启停/secret 轮换/网络附加/日志/迁移/回滚） |
| T7.2 回滚演练 | 完成 | 本文件 §2、§3；两条路径均实测并恢复到三容器 healthy |
| T7.3 灰度方案 | 完成 | `reports/ops/l3-split-p7-grayscale.md`（保留期/二元切换/回切阈值/责任人） |
| T7.4 监控/告警 | 完成（同日补齐） | `reports/ops/l3-split-p7-metrics.md`：两容器 `/metrics` 200；5xx/401、预占与结算失败、租约缓存命中、健康 Gauge 均已暴露；`l3_split_alerts` 10 条规则经 promtool 与 Prometheus 实求值通过 |
| T7.5 收口 | **未开始** | 旧编排代码与 `mode` 开关仍在仓库；架构图未改；需完成 14 天观察期后执行 |

## 2. 演练 A：回滚到容器旧端口（19998/19999/19100）

方法：用 `git show e63b7a6:deploy/l3/docker-compose.yml` 生成临时 `deploy/l3/docker-compose.rollback-a.yml`（项目名同为 `agentpanel-l3`，相对路径不变），以进程环境覆盖 `GW_PUBLIC_BASE_URL=http://127.0.0.1:19999`、`ORCH_PUBLIC_BASE_URL=http://127.0.0.1:19100`。

实测：

```text
down 主 compose: 2.1s
up 回滚 compose -> 三容器 healthy: 18.0s
agentpanel-l3-l3-orchestration-1  Up (healthy)  127.0.0.1:19100->9100/tcp
agentpanel-l3-l2-1                Up (healthy)  127.0.0.1:19998->9998/tcp
agentpanel-l3-l3-gateway-1        Up (healthy)  127.0.0.1:19999->9999/tcp

GET 19998/health/health -> 200 healthy（db/redis/qdrant）
GET 19999/health -> 200 {"status":"ok","deployment":"standalone","fail_closed":true}
GET 19100/health/orchestration -> 200 healthy / mode=proxy_l3 / write_enabled=true
GET 19998/api/v1/harness/runs/nope -> 401 {"code":401,"msg":"无效的 Harness 客户端凭据"}
```

恢复：down 回滚 compose、删除临时 compose、主 compose `up -d` 到三容器 healthy **13.1s**；端口回到 `127.0.0.1:9998/9999/9100`，三 health 200。

## 3. 演练 B：回滚到宿主三进程（9998/9999/9100）

方法：主 compose `down` → 确认端口释放 → 用仓库 `.venv\Scripts\python.exe` 后台启动 L2 / 网关 / 编排（DB/Redis 从 `config.conf` 注入，编排另取 User 级 `ORCHESTRATION_SERVICE_SECRET`）。

实测：

```text
down 主 compose: 2.0s
9998 => free   9999 => free   9100 => free

进程启动时间: L2 12:25:30 / 网关 12:25:33 / 编排 12:25:35
三端点全部 200: 12:26:03（自 L2 启动约 33s；网关/编排约 28–30s）
9998 => listening pid=21224
9999 => listening pid=24292
9100 => listening pid=42852

GET 9998/health/health -> 200 healthy（db/redis/qdrant）
GET 9999/health -> 200 {"status":"ok","deployment":"standalone","fail_closed":true}
GET 9100/health/orchestration -> 200 healthy / mode=proxy_l3
GET 9998/api/v1/harness/runs/nope -> 401（编排侧鉴权，不是 503）
POST 9999/chat/completions 无凭据 -> 401 {"error":{"message":"缺少网关租约虚拟 key","type":"gateway_auth_error"}}

网关启动日志: public_base_url: http://127.0.0.1:9999
编排启动日志: 启动自检通过：只读库可用且写被拒，schema=v1，service_credential active=1
```

恢复：停止三个后台进程 → 端口全部 free → 主 compose `up -d` 到三容器 healthy **13.0s**；`9998/9999/9100` 重新绑定，三 health 200。

## 4. 数据不变性（演练前后）

`p7_baseline.py` 在四个时点采样：`pre_drill` → `after_drill_a` → `during_drill_b` → `post_drill`。

| 对象 | pre | after A | during B | post |
|---|---|---|---|---|
| PG `org:14` used | `{"token":450.0}` | 同左 | 同左 | 同左 |
| PG `usr:4` used | `{"token":93294.0}` | 同左 | 同左 | 同左 |
| `org:14` plan_id | 8 | 8 | 8 | 8 |
| `usr:4` plan_id | 8 | 8 | 8 | 8 |
| Redis `quota:org:14:token:2026-11` | 450 | 450 | 450 | 450 |
| Redis `quota:usr:4:token:2026-11` | 93294 | 93294 | 93294 | 93294 |
| Redis held `org:14` | 无键 | 无键 | 无键 | 无键 |
| Redis held `usr:4` | 0 | 0 | 0 | 0 |

结论：两条回滚路径与恢复过程均未改变计量数据。

## 5. 恢复确认

```text
docker ps -> agentpanel-l3-l2-1 / l3-gateway-1 / l3-orchestration-1 全部 Up (healthy)
docker port -> 127.0.0.1:9998 / 127.0.0.1:9999 / 127.0.0.1:9100
Get-NetTCPConnection -> 9998/9999/9100 均 listening 127.0.0.1（pid 为 com.docker.backend 端口代理）
GET 9998/health/health -> 200；9999/health -> 200；9100/health/orchestration -> 200
GET 9998/api/v1/harness/runs/nope -> 401
临时文件 deploy/l3/docker-compose.rollback-a.yml 已删除；演练未改动 compose、.env、secrets 或业务数据；工作区改动仅为本阶段文档（见 §7）
```

## 6. 演练中的非预期错误（如实记录）

两次与演练路径无关的补充验证遇到环境性问题，均已绕开并完成，不影响 A/B 两条路径的结论：

1. 用 `docker compose run` 做 schema 负向验证时失败：
   `Error response from daemon: failed to set up container networking: Address already in use`
   原因：编排服务在 compose 中固定 `172.28.0.10`，`run` 的临时容器与在运行的编排容器抢同一静态 IP。
   处理：改用 `docker run --network agentpanel-net`（不指定静态 IP）执行同一镜像，负向验证成功：`SchemaCheckError: 数据库要求 schema 版本 2，当前代码仅支持 1`，启动失败，退出码 3。
2. 首次 `docker run` 使用了错误镜像名（`agentpanel-l3-l3-gateway:local`），实际镜像为 `agentpanel-l3-gateway:local`；改用正确名字后完成非 root 与镜像扫描验证。

两起均未改动任何运行中的数据或配置，三容器在演练期间保持最终 healthy 状态。

## 7. 文档清单

新增：

- `reports/ops/l3-split-acceptance.md`（T6.8：P6 逐项结果、G1 数值、已知限制）
- `reports/ops/l3-split-p7-runbook.md`（T7.1）
- `reports/ops/l3-split-p7-grayscale.md`（T7.3）
- `reports/ops/l3-split-p7-report.md`（本文件，T7.2 演练记录 + T7.4/T7.5 状态）
- `reports/ops/l3-split-p7-metrics.md`（T7.4 补齐：指标清单、告警映射、部署变更、验证证据）

更新：

- `reports/specs/l3-service-split/tasks.md`（P6 勾选、P7 状态与产出）
- `reports/specs/l3-service-split/spec.md`（新增实施状态与 P6 两处实测差异；§8.1/§8.4 对齐现状）
- `reports/specs/l3-service-split/checklist.md`（追加 P6 验收清单与 P7 状态）

未改（T7.1–T7.3 与演练阶段）：业务逻辑代码、`deploy/l3/docker-compose.yml`、`deploy/l3/.env`、secrets。
T7.4 另行新增 `packages/agentpanel_common/l3_metrics.py`，并在两服务入口、租约缓存、额度客户端与 `monitoring/` 中加入观测旁路（未改业务分支），见 `l3-split-p7-metrics.md` §2。
