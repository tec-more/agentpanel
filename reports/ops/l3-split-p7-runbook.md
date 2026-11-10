# 运维 Runbook：独立服务拆分（三容器）

- 日期：2026-11-09（2026-11-10 三轮命名统一：① `deploy/l3`→`deploy/gateway`、`Dockerfile.l2`→`Dockerfile.app`、`requirements-l3.txt`→`requirements-services.txt`、secrets `l2_config.conf`→`app_config.conf`；② compose 项目名 `agentpanel-l3`→`agentpanel`、服务名 `l2`/`l3-gateway`/`l3-orchestration`→`app`/`gateway`/`orchestration`、镜像名 `agentpanel-l2`/`agentpanel-l3-gateway`/`agentpanel-l3-orchestration`→`agentpanel-app`/`agentpanel-gateway`/`agentpanel-orchestration`、容器名同名固定、卷 `l2_storage`→`app_storage`；③ 服务凭据 `svc_l3_orchestration`→`svc_orchestration`、8080 upstream 改用容器名 `agentpanel-app`（别名 `agentpanel-l2` 退役）、Prometheus job `l3-gateway`/`l3-orchestration`→`gateway`/`orchestration`、规则组 `l3_split_alerts`→`agentpanel_alerts`、指标名去 `l3_` 前缀、`l3_metrics.py`→`service_metrics.py`、配置键 `l2_service_id`→`app_service_id` 等、mode 值 `proxy_l3`→`proxy`。历史报告中出现的旧名均按本行对照表理解）
- 适用：`deploy/gateway/docker-compose.yml`（`name: agentpanel`）
- 回滚手册：`reports/ops/port-switch-9998-9999-9100.md`
- 演练记录：`reports/ops/l3-split-p7-report.md`

## 1. 前置条件

| 依赖 | 要求 |
|---|---|
| Docker | Docker Desktop 可用；`com.docker.backend` 负责宿主端口代理 |
| 网络 | `agentpanel-net`（`172.28.0.0/16`，external） |
| Redis | `agentredis` 已 `docker network connect agentpanel-net`（热操作，不重启） |
| PG | `127.0.0.1:15432`（容器内走 `host.docker.internal:15432`） |
| secrets | `deploy/gateway/secrets/{db_password,redis_password,orchestration_service_secret,app_config.conf}` |
| 环境变量 | User 级 `ORCHESTRATION_SERVICE_SECRET`（长度 52，必须与 app `service_credential.svc_orchestration` 一致） |

首次或重建环境：

```powershell
# 1) 网络（已存在则跳过）
docker network create --subnet 172.28.0.0/16 agentpanel-net

# 2) Redis 热接入（可在容器运行时执行）
docker network connect agentpanel-net agentredis

# 3) 生成 secrets 与 .env
powershell -ExecutionPolicy Bypass -File deploy/gateway/scripts/prepare-secrets.ps1
```

> **已修复（2026-11-09 16:44）**：`prepare-secrets.ps1` 生成的 `deploy/gateway/.env` 曾写 `GW_PUBLIC_BASE_URL=http://127.0.0.1:19999`、`ORCH_PUBLIC_BASE_URL=http://127.0.0.1:19100`，需手动改为 `9999/9100`；脚本现已直接生成现行端口，与 `deploy/gateway/docker-compose.yml` 头部约定一致，重新生成 secrets 不再需要手改。若按 `port-switch-9998-9999-9100.md` 回滚到旧端口，仍需按该文档临时调整这两个值。

## 2. 启停与健康

```powershell
$ROOT = 'd:\programs\fastapi\agentpanel'
$COMPOSE = "$ROOT\deploy\gateway\docker-compose.yml"
$ENV = "$ROOT\deploy\gateway\.env"
Set-Location $ROOT

# 启动/更新（仅变更的服务会被重建）
docker compose -f $COMPOSE --env-file $ENV up -d

# 状态
docker compose -f $COMPOSE --env-file $ENV ps

# 停止并移除容器（保留镜像、secrets、agentpanel-net）
docker compose -f $COMPOSE --env-file $ENV down

# 单服务重启 / 强制重建（改了 env 或 secret 后）
docker compose -f $COMPOSE --env-file $ENV restart gateway
docker compose -f $COMPOSE --env-file $ENV up -d --force-recreate orchestration
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
| `9100/health/orchestration` | 200，`mode=proxy`、`write_enabled=true`、只读库写探测被拒 |
| `9998/api/v1/harness/runs/nope` | 401（代理到编排），503 表示编排不可达 |

启动耗时参考（实测）：干净 `up -d` 到三容器 healthy 约 13–18 秒；宿主三进程回滚约 33 秒。

## 3. 日志

```powershell
# 全部服务
docker compose -f $COMPOSE --env-file $ENV logs --tail=200 -f

# 单服务
docker compose -f $COMPOSE --env-file $ENV logs --tail=200 -f orchestration
```

- 日志驱动：`json-file`，`max-size=10m`、`max-file=3`（compose 已配置）。
- 网关/编排容器 `read_only: true`，仅 `/tmp` 为 tmpfs，日志只走 stdout，不写宿主卷。
- app 日志路径在容器内 `/app/logs`（由 secrets 中的 `app_config.conf` 指定）。

## 4. 网络附加

```powershell
docker network inspect agentpanel-net --format '{{json .IPAM.Config}}'
docker network inspect agentpanel-net --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}'
```

- 编排容器固定 IP `172.28.0.10`；`ORCH_INTERNAL_ALLOWED_IPS=172.28.0.10,127.0.0.1,::1` 为精确匹配，不能写 CIDR。
- `agentredis` 必须在该网络内，网关/编排才能解析 `agentredis:6379`。
- 若 `agentpanel-net` 不存在或冲突，先停止容器，再重建网络；`agentredis` 可热接入。

### 4.1 对外 nginx 入口（F1 18:07 修复；别名 18:44 持久化）

运行中的 `aipanel-nginx`（宿主 8080）由**另一个目录**的 compose 项目 `app` 管理，配置挂载自
`D:\programs\fastapi\aipaneladmin\deploy\nginx\conf.d\aipanel.conf`，其 upstream 曾指向
legacy `app:9998`（该容器 DB 未初始化、harness 路由 404）。已改为 `server agentpanel-app:9998;`
并 `nginx -t && nginx -s reload` 生效；外部配置备份为 `aipanel.conf.bak-20261109-1807`。

**别名已持久化**：`agentpanel-app` 不再是手工 `docker network connect` 的容器级临时状态，
而是写进 `deploy/gateway/docker-compose.yml` 的 compose 声明：

```yaml
services:
  l2:
    networks:
      agentpanel-net: {}
      app_default:
        aliases: [agentpanel-app]
networks:
  agentpanel-net:
    external: true
  app_default:            # 由 legacy 项目 app 创建
    external: true
```

因此 `up -d --force-recreate app` 会自动把新容器接入 `app_default` 并带上别名。
18:44 验收：先 `docker network disconnect app_default agentpanel-app` 复现 8080 超时，
再 `up -d --no-deps --force-recreate --wait app`，`docker inspect` 显示 `app_default.aliases`
自动含 `agentpanel-app`，8080 立即恢复 200 healthy / harness 401 / `/panel` 200，巡检 PASS 16/16。
**重建后不再需要任何手工网络命令。**

验证基线：

```powershell
docker inspect agentpanel-app --format '{{json .NetworkSettings.Networks}}'
# app_default.aliases 必须含 agentpanel-app
# 8080/health/health 200 healthy；8080/api/v1/harness/runs/nope 401；8080/panel 200
```

**无 legacy 栈时**：默认 compose 把 `app_default` 声明为 external，网络不存在会导致 `up -d` 失败。
干净机器上先手动建一个空网络即可满足 external 声明（2026-11-10 起 `docker-compose.standalone.yml`
叠加文件已删除，需要时从 git 历史找回）：

```powershell
docker network create app_default
docker compose -f deploy/gateway/docker-compose.yml --env-file deploy/gateway/.env up -d
```

之后三容器只在 `agentpanel-net` 内互通，直接访问 `9998/9999/9100`；l2 会挂到一个无 nginx 的
空 `app_default` 网络上，`agentpanel-app` 别名无实际消费方，不影响功能。

## 5. 密钥轮换

### 5.1 编排服务密钥（`ORCHESTRATION_SERVICE_SECRET`）

该值同时用于：独立服务→app 内部额度接口的 HMAC 签名，以及 app DB 中 `service_credential.svc_orchestration` 的校验。当前只支持单 active 凭据，轮换存在短暂 401 窗口。

顺序：

1. 在维护窗口内，通过 app 现有服务凭据流程更新 `svc_orchestration` 的 `secret_hash`（或重建该凭据）；
2. 更新 `deploy/gateway/secrets/orchestration_service_secret`（无行尾换行）；
3. `docker compose ... up -d --force-recreate orchestration`；
4. 复核 `9100/health/orchestration` 的 `service_credential` healthy，并跑一次内部额度调用确认不再 401。

建议在 5 分钟内完成；期间编排写路径可能 401，app 代理读仍可用。

### 5.2 数据库密码

1. 修改 PG 中 app/ 独立服务 所用账号密码；
2. 更新 `deploy/gateway/secrets/db_password` 与 `deploy/gateway/secrets/app_config.conf` 的 `[db] db_password`；
3. `docker compose ... up -d --force-recreate`（三个服务都读该密码）。

### 5.3 Redis 密码

1. 修改 `agentredis` 的 `requirepass`（该容器不在本 compose 内，需单独操作）；
2. 更新 `deploy/gateway/secrets/redis_password` 与 `app_config.conf` 的 `[redis] password`；
3. 重建三个容器。

> Redis 密码轮换会影响所有使用 `agentredis` 的服务，必须先确认影响面再操作。

## 6. 数据库迁移

- 唯一迁移执行方是 app（aerich + `migrations/*.sql` + `generate_schemas`）；独立服务容器不执行任何 DDL/DML 迁移。
- compose 中 app 固定 `RUN_DB_MIGRATIONS=false`，因此发布顺序是：先迁移，再起/更新 独立服务，最后验证。
- 迁移方式（维护窗口，二选一）：
  - 宿主 `.venv\Scripts\python.exe run.py` 启动 app，等待日志出现“数据库初始化流程完成”，再停止；
  - 或临时将 compose 中 app 的 `RUN_DB_MIGRATIONS` 改为 `"true"`，重建一次 app，确认迁移完成后改回 `"false"` 并再次重建。
- 独立服务 通过 `ORCH_SCHEMA_MIN_VERSION` 拒绝旧库：高于内置版本（当前 1）时启动失败，退出码 3。

## 7. 回滚

- 回滚到容器旧端口（`19998/19999/19100`）或宿主三进程（`9998/9999/9100`），按 `reports/ops/port-switch-9998-9999-9100.md` §2 执行。
- 两条路径的实测耗时与恢复确认见 `reports/ops/l3-split-p7-report.md`。
- 回滚不迁移数据、不删卷；容器停止即可，保留镜像用于复现。
