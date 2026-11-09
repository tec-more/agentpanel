# 运维 Runbook：L3 拆分（三容器）

- 日期：2026-11-09
- 适用：`deploy/l3/docker-compose.yml`（`name: agentpanel-l3`）
- 回滚手册：`reports/ops/port-switch-9998-9999-9100.md`
- 演练记录：`reports/ops/l3-split-p7-report.md`

## 1. 前置条件

| 依赖 | 要求 |
|---|---|
| Docker | Docker Desktop 可用；`com.docker.backend` 负责宿主端口代理 |
| 网络 | `agentpanel-net`（`172.28.0.0/16`，external） |
| Redis | `agentredis` 已 `docker network connect agentpanel-net`（热操作，不重启） |
| PG | `127.0.0.1:15432`（容器内走 `host.docker.internal:15432`） |
| secrets | `deploy/l3/secrets/{db_password,redis_password,orchestration_service_secret,l2_config.conf}` |
| 环境变量 | User 级 `ORCHESTRATION_SERVICE_SECRET`（长度 52，必须与 L2 `service_credential.svc_l3_orchestration` 一致） |

首次或重建环境：

```powershell
# 1) 网络（已存在则跳过）
docker network create --subnet 172.28.0.0/16 agentpanel-net

# 2) Redis 热接入（可在容器运行时执行）
docker network connect agentpanel-net agentredis

# 3) 生成 secrets 与 .env
powershell -ExecutionPolicy Bypass -File deploy/l3/scripts/prepare-secrets.ps1
```

> **已修复（2026-11-09 16:44）**：`prepare-secrets.ps1` 生成的 `deploy/l3/.env` 曾写 `GW_PUBLIC_BASE_URL=http://127.0.0.1:19999`、`ORCH_PUBLIC_BASE_URL=http://127.0.0.1:19100`，需手动改为 `9999/9100`；脚本现已直接生成现行端口，与 `deploy/l3/docker-compose.yml` 头部约定一致，重新生成 secrets 不再需要手改。若按 `port-switch-9998-9999-9100.md` 回滚到旧端口，仍需按该文档临时调整这两个值。

## 2. 启停与健康

```powershell
$ROOT = 'd:\programs\fastapi\agentpanel'
$COMPOSE = "$ROOT\deploy\l3\docker-compose.yml"
$ENV = "$ROOT\deploy\l3\.env"
Set-Location $ROOT

# 启动/更新（仅变更的服务会被重建）
docker compose -f $COMPOSE --env-file $ENV up -d

# 状态
docker compose -f $COMPOSE --env-file $ENV ps

# 停止并移除容器（保留镜像、secrets、agentpanel-net）
docker compose -f $COMPOSE --env-file $ENV down

# 单服务重启 / 强制重建（改了 env 或 secret 后）
docker compose -f $COMPOSE --env-file $ENV restart l3-gateway
docker compose -f $COMPOSE --env-file $ENV up -d --force-recreate l3-orchestration
```

健康基线（容器已 healthy 后）：

```powershell
curl.exe -s -w "`nHTTP=%{http_code}`n" http://127.0.0.1:9998/health/health
curl.exe -s -w "`nHTTP=%{http_code}`n" http://127.0.0.1:9999/health
curl.exe -s -w "`nHTTP=%{http_code}`n" http://127.0.0.1:9999/health/health
curl.exe -s -w "`nHTTP=%{http_code}`n" http://127.0.0.1:9100/health/health
curl.exe -s -w "`nHTTP=%{http_code}`n" http://127.0.0.1:9100/health/orchestration
curl.exe -s -w "`nHTTP=%{http_code}`n" http://127.0.0.1:9998/api/v1/harness/runs/nope   # 期望 401，不是 503
```

| 端点 | 期望 |
|---|---|
| `9998/health/health` | 200，db/redis/qdrant 全 healthy |
| `9999/health` | 200，`status=ok`、`deployment=standalone`、`fail_closed=true` |
| `9999/health/health` | 200，database/redis healthy |
| `9100/health/health` | 200，database/redis healthy，qdrant skipped |
| `9100/health/orchestration` | 200，`mode=proxy_l3`、`write_enabled=true`、只读库写探测被拒 |
| `9998/api/v1/harness/runs/nope` | 401（代理到编排），503 表示编排不可达 |

启动耗时参考（实测）：干净 `up -d` 到三容器 healthy 约 13–18 秒；宿主三进程回滚约 33 秒。

## 3. 日志

```powershell
# 全部服务
docker compose -f $COMPOSE --env-file $ENV logs --tail=200 -f

# 单服务
docker compose -f $COMPOSE --env-file $ENV logs --tail=200 -f l3-orchestration
```

- 日志驱动：`json-file`，`max-size=10m`、`max-file=3`（compose 已配置）。
- 网关/编排容器 `read_only: true`，仅 `/tmp` 为 tmpfs，日志只走 stdout，不写宿主卷。
- L2 日志路径在容器内 `/app/logs`（由 secrets 中的 `l2_config.conf` 指定）。

## 4. 网络附加

```powershell
docker network inspect agentpanel-net --format '{{json .IPAM.Config}}'
docker network inspect agentpanel-net --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}'
```

- 编排容器固定 IP `172.28.0.10`；`ORCH_INTERNAL_ALLOWED_IPS=172.28.0.10,127.0.0.1,::1` 为精确匹配，不能写 CIDR。
- `agentredis` 必须在该网络内，网关/编排才能解析 `agentredis:6379`。
- 若 `agentpanel-net` 不存在或冲突，先停止容器，再重建网络；`agentredis` 可热接入。

### 4.1 对外 nginx 入口（F1，2026-11-09 18:07 修复）

运行中的 `aipanel-nginx`（宿主 8080）由**另一个目录**的 compose 管理，配置挂载自
`D:\programs\fastapi\aipaneladmin\deploy\nginx\conf.d\aipanel.conf`，其 upstream 曾指向
legacy `app:9998`（该容器 DB 未初始化、harness 路由 404）。已改为指向新 L2：

```powershell
# 1) 把新 L2 容器热接入 nginx 所在网络并设别名（不重启任何容器）
docker network connect --alias agentpanel-l2 app_default agentpanel-l3-l2-1
# 2) 已把 upstream 改为 server agentpanel-l2:9998; 并 nginx -t && nginx -s reload
docker exec aipanel-nginx nginx -t
docker exec aipanel-nginx nginx -s reload
```

验证基线：`8080/health/health` = 200 healthy、`8080/api/v1/harness/runs/nope` = **401**
（代理链路正常，不是 404/503）、`8080/panel` = 200。

> **重要**：`docker network connect` 的别名是容器级临时状态，**每次 `up -d --force-recreate l2`
> 或重建 L2 容器后都会丢失**，8080 会退回 502。重建后必须重新执行上面第 1 步
> （可用 `docker inspect agentpanel-l3-l2-1 --format '{{json .NetworkSettings.Networks}}'`
> 确认 `app_default` 下仍有 `agentpanel-l2` 别名）。该别名刻意不写进
> `deploy/l3/docker-compose.yml`，避免三容器部署硬依赖另一套 legacy compose 的网络。

## 5. 密钥轮换

### 5.1 编排服务密钥（`ORCHESTRATION_SERVICE_SECRET`）

该值同时用于：L3→L2 内部额度接口的 HMAC 签名，以及 L2 DB 中 `service_credential.svc_l3_orchestration` 的校验。当前只支持单 active 凭据，轮换存在短暂 401 窗口。

顺序：

1. 在维护窗口内，通过 L2 现有服务凭据流程更新 `svc_l3_orchestration` 的 `secret_hash`（或重建该凭据）；
2. 更新 `deploy/l3/secrets/orchestration_service_secret`（无行尾换行）；
3. `docker compose ... up -d --force-recreate l3-orchestration`；
4. 复核 `9100/health/orchestration` 的 `service_credential` healthy，并跑一次内部额度调用确认不再 401。

建议在 5 分钟内完成；期间编排写路径可能 401，L2 代理读仍可用。

### 5.2 数据库密码

1. 修改 PG 中 L2/ L3 所用账号密码；
2. 更新 `deploy/l3/secrets/db_password` 与 `deploy/l3/secrets/l2_config.conf` 的 `[db] db_password`；
3. `docker compose ... up -d --force-recreate`（三个服务都读该密码）。

### 5.3 Redis 密码

1. 修改 `agentredis` 的 `requirepass`（该容器不在本 compose 内，需单独操作）；
2. 更新 `deploy/l3/secrets/redis_password` 与 `l2_config.conf` 的 `[redis] password`；
3. 重建三个容器。

> Redis 密码轮换会影响所有使用 `agentredis` 的服务，必须先确认影响面再操作。

## 6. 数据库迁移

- 唯一迁移执行方是 L2（aerich + `migrations/*.sql` + `generate_schemas`）；L3 容器不执行任何 DDL/DML 迁移。
- compose 中 L2 固定 `RUN_DB_MIGRATIONS=false`，因此发布顺序是：先迁移，再起/更新 L3，最后验证。
- 迁移方式（维护窗口，二选一）：
  - 宿主 `.venv\Scripts\python.exe run.py` 启动 L2，等待日志出现“数据库初始化流程完成”，再停止；
  - 或临时将 compose 中 L2 的 `RUN_DB_MIGRATIONS` 改为 `"true"`，重建一次 L2，确认迁移完成后改回 `"false"` 并再次重建。
- L3 通过 `ORCH_SCHEMA_MIN_VERSION` 拒绝旧库：高于内置版本（当前 1）时启动失败，退出码 3。

## 7. 回滚

- 回滚到容器旧端口（`19998/19999/19100`）或宿主三进程（`9998/9999/9100`），按 `reports/ops/port-switch-9998-9999-9100.md` §2 执行。
- 两条路径的实测耗时与恢复确认见 `reports/ops/l3-split-p7-report.md`。
- 回滚不迁移数据、不删卷；容器停止即可，保留镜像用于复现。
