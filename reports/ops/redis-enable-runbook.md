# Redis 启用 Runbook（Windows PowerShell · 项目 `.venv` · 自建 `agentredis`）

> 适用：`d:\programs\fastapi\agentpanel` 宿主机三进程（L2 9998 / 网关 9999 / 编排 9100）。
> 本文给可直接复制执行的命令与说明。密码一律在运行时从 `config.conf` 读取，不写死、不回显明文。

---

## 已建成状态（本次执行事实）

| 项 | 实际值 |
|---|---|
| 容器名 | `agentredis` |
| 镜像 | `redis:7-alpine`（本地已有镜像，未拉取新版本） |
| 端口绑定 | `127.0.0.1:6379->6379/tcp`（仅回环，无 `0.0.0.0`） |
| 数据卷 | 命名卷 `agentredis_data` → `/data` |
| 持久化 | `--appendonly yes`（AOF） |
| 淘汰策略 | `--maxmemory-policy noeviction`（额度计数/预占 key 不可被淘汰） |
| 重启策略 | `--restart unless-stopped` |
| 密码 | 32 位强随机，`--requirepass` 注入；写入 `config.conf [redis] password`；报告仅给指纹与尾四位 |
| 与 `aipanel-redis` 关系 | 完全独立：未复用其容器、密码、端口、数据卷，未做任何改动 |
| 服务解释器 | `D:\programs\fastapi\agentpanel\.venv\Scripts\python.exe` |
| 配置开关 | `config.conf [redis] enabled=true, host=127.0.0.1, port=6379, db=0` |

> `config.conf` 已加入 `.gitignore` 并用 `git rm --cached` 解除跟踪（本地文件保留），避免密码入库。

---

## 执行前须知

**1）Python 环境统一用本项目 `.venv`**

- 解释器固定为 `D:\programs\fastapi\agentpanel\.venv\Scripts\python.exe`（下称 `$VENV`）。
- 不再用 pyenv 解释器启动任何服务。
- 依赖已核实（三入口可导入），**不需要** `pip install -r requirements.txt` 全量重装；只有单项缺失时才单独安装。

**2）Redis 用本仓库自建的 `agentredis`**

- 容器由本 runbook 第 2 节创建，属本项目专用，可停止/重建。
- **不动 `aipanel-redis`**（属 `D:\programs\fastapi\aipaneladmin` 部署，正在被其 `aipanel-app` 使用）。
- 不复用 `aipanel-redis` 的密码或数据卷。

**3）端口与密码不要猜**

- 固定 `host=127.0.0.1`、`port=6379`；**不要写 `host=redis`**（Docker 内网 DNS，宿主解析不到），**不要写容器 IP**（重建后会变）。
- 密码运行时从 `config.conf` 读取：
  ```powershell
  $REDIS_PASSWORD = (Select-String -Path $CFG -Pattern '^password\s*=' | Select-Object -First 1).Line.Split('=',2)[1].Trim()
  ```

**4）失败了该回看哪一节**

| 现象 | 回看 |
|---|---|
| `docker inspect agentredis` 报 No such object | §2 创建容器 |
| `docker port` 无输出、宿主连不上 | §2.2 端口绑定 |
| 探针报 `NOAUTH` / `WRONGPASS` | §2.1 密码生成与写入，§3 配置 |
| `/health/health` 仍是 `skipped` | §3 改配置、§4 重启 |
| 端口不监听、进程启动即退出 | §4 重启 |
| 监听进程 `ExecutablePath` 显示 pyenv | §5.0（venv redirector 属正常，按父子进程与 `sys.prefix` 判定） |
| `gw:lease:state:*` 抓不到 | §5.2（TTL 仅 8 秒，需请求后立即抓） |
| `counter_mode` 不是 `redis` | §5.3、§6 |
| G1 任一项不通过 | §6 结论与 §7 回滚 |
| 需要还原到 DB 降级 | §7 回滚 |

---

## 0. 前置：变量与只读检查

```powershell
# 作用：本次会话内复用的路径常量
$ROOT = 'd:\programs\fastapi\agentpanel'
$VENV = Join-Path $ROOT '.venv\Scripts\python.exe'
$CFG  = Join-Path $ROOT 'config.conf'
```

```powershell
# 作用：确认 .venv 解释器与版本
& $VENV -c "import sys;print(sys.executable);print(sys.version.split()[0])"
# 预期：D:\programs\fastapi\agentpanel\.venv\Scripts\python.exe
#       3.12.10
```

```powershell
# 作用：确认 6379 是否已被占用（占用则先查清属主，不要顶掉别人的监听）
Get-NetTCPConnection -State Listen -LocalPort 6379 -ErrorAction SilentlyContinue
# 预期：无输出（本次执行时为空闲）
```

```powershell
# 作用：确认 aipanel-redis 存在但不碰它（仅展示）
docker ps -a --filter "name=aipanel-redis" --format "{{.Names}}|{{.Image}}|{{.Status}}"
```

---

## 1. 依赖核实（不重装，只补缺）

```powershell
# 作用：确认 redis 包来自 .venv
& $VENV -c "import importlib.util;print(importlib.util.find_spec('redis'))"
# 预期：ModuleSpec(name='redis', ... origin='...\.venv\Lib\site-packages\redis\__init__.py')
```

```powershell
# 作用：两个入口的导入检查（只导入，不启动服务、不占端口）
$env:PYTHONPATH = $ROOT
foreach ($m in 'run','base.app_wrapper') {
  & $VENV -c "import $m; print('IMPORT_OK: $m')"
}
# 预期：两行 IMPORT_OK，退出码 0
```

```powershell
# 作用：仅当上面 find_spec 返回 None 时才执行
& $VENV -m pip install --upgrade "redis>=5"
```

---

## 2. 创建 `agentredis` 容器（仅本项目，不碰其它容器）

### 2.1 生成强随机密码并写入配置（先备份、先解跟踪）

```powershell
# 作用：备份 config.conf（备份文件已在 .gitignore 覆盖）
Copy-Item $CFG "$CFG.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"

# 作用：生成 32 位随机密码（字母+数字，避免 shell/ini 特殊字符）
$REDIS_PASSWORD = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
"password 长度=$($REDIS_PASSWORD.Length) 尾四位=$($REDIS_PASSWORD.Substring($REDIS_PASSWORD.Length-4))"
$fp = (Get-FileHash -InputStream ([IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($REDIS_PASSWORD))) -Algorithm SHA256).Hash.Substring(0,8)
"password 指纹=$fp"
# 报告只记录“指纹 + 尾四位”，不要把明文写进日志/文档
```

```powershell
# 作用：确认配置不会被 git 跟踪（若尚未处理，先执行下面两行）
git -C $ROOT check-ignore -v config.conf
# 预期：.gitignore:<行号>:/config.conf
git -C $ROOT rm --cached config.conf
# 预期：rm 'config.conf'（本地文件保留；这是 staged 的删除，需由项目负责人决定何时提交）
```

### 2.2 创建容器

```powershell
# 作用：创建并启动 agentredis（只绑回环、AOF、命名卷、noeviction、unless-stopped）
docker run -d --name agentredis --restart unless-stopped `
  -p 127.0.0.1:6379:6379 `
  -v agentredis_data:/data `
  redis:7-alpine redis-server `
  --appendonly yes `
  --requirepass $REDIS_PASSWORD `
  --maxmemory-policy noeviction

# 若同名容器已存在（重建场景），先执行：
# docker rm -f agentredis   # 仅删除容器，命名卷 agentredis_data 保留数据
```

### 2.3 验证容器事实

```powershell
# 作用：核对镜像、状态、端口绑定、卷、重启策略、启动参数
docker inspect agentredis --format 'Image={{.Config.Image}} Status={{.State.Status}} Restart={{.HostConfig.RestartPolicy.Name}}'
# 预期：Image=redis:7-alpine Status=running Restart=unless-stopped

docker port agentredis 6379/tcp
# 预期：127.0.0.1:6379（不得出现 0.0.0.0:6379）

docker inspect agentredis --format '{{range .Mounts}}{{.Type}}={{.Name}}->{{.Destination}}{{println}}{{end}}'
# 预期：volume=agentredis_data->/data

docker inspect agentredis --format '{{range .Config.Cmd}}{{println .}}{{end}}'
# 预期：可看到 --appendonly yes / --requirepass <略> / --maxmemory-policy noeviction
```

```powershell
# 作用：容器内自检（持久化、淘汰策略、鉴权）
docker exec agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD CONFIG GET appendonly maxmemory-policy
# 预期：appendonly=yes / maxmemory-policy=noeviction
docker exec agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD PING
# 预期：PONG
```

```powershell
# 作用：宿主连通性（必须只监听回环）
Test-NetConnection 127.0.0.1 -Port 6379
# 预期：TcpTestSucceeded : True
Get-NetTCPConnection -State Listen -LocalPort 6379 | Select-Object LocalAddress,LocalPort,OwningProcess
# 预期：LocalAddress=127.0.0.1
```

### 2.4 项目探针验证

```powershell
# 作用：用 base.common.health.check_redis（项目探针）判断，而不是只 ping 端口
$env:PYTHONPATH = $ROOT
$env:REDIS_ENABLED = 'true'
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = '6379'
$env:REDIS_PASSWORD = "$REDIS_PASSWORD"
$env:REDIS_DB = '0'
& $VENV -c "import asyncio;from base.common.health import check_redis;print(asyncio.run(check_redis()))"
# 预期：{'status': 'healthy', 'message': 'Redis connection OK'}
Remove-Item Env:REDIS_ENABLED,Env:REDIS_HOST,Env:REDIS_PORT,Env:REDIS_PASSWORD,Env:REDIS_DB -ErrorAction SilentlyContinue
```

---

## 3. 改配置（`config.conf` 的 `[redis]`）

本次已写入以下值（密码为 2.1 生成值，未外显）：

```ini
[redis]
enabled = true
host = 127.0.0.1
port = 6379
password = <2.1 生成的 32 位密码>
db = 0
```

```powershell
# 作用：核对写入结果（password 行请不要回显到报告）
Select-String -Path $CFG -Pattern '^\[redis\]$' -Context 0,4
```

> 重新写回时的注意点：用无 BOM UTF-8，避免 configparser 读首行失败。
> ```powershell
> [System.IO.File]::WriteAllText($CFG, $text, (New-Object System.Text.UTF8Encoding($false)))
> ```

---

## 4. 重启三个进程（全部改用 `.venv`）

停止：按端口定位 PID（比记死 PID 稳）。

```powershell
# 作用：停止旧进程（连父进程一起停，避免 venv 启动器残留）
foreach ($p in 9998,9999,9100) {
  $pids = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue |
          Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($id in $pids) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$id"
    if ($proc) { Stop-Process -Id $proc.ParentProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    "stopped PID $id (port $p)"
  }
}
Start-Sleep -Seconds 3
```

```powershell
# 作用：确认三个端口已释放
foreach ($p in 9998,9999,9100) {
  $c = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue
  "{0} => {1}" -f $p, $(if ($c) { 'STILL LISTENING' } else { 'free' })
}
# 预期：9998 => free / 9999 => free / 9100 => free
```

```powershell
# 作用：确认 L3 需要的服务密钥可见（值不回显、不要重置）
$env:ORCHESTRATION_SERVICE_SECRET = [Environment]::GetEnvironmentVariable('ORCHESTRATION_SERVICE_SECRET','User')
if (-not $env:ORCHESTRATION_SERVICE_SECRET) { throw '缺少 ORCHESTRATION_SERVICE_SECRET，禁止启动 L3' }
```

```powershell
# 作用：用 .venv 依次启动 L2 → 网关 → 编排（每个等端口监听后再起下一个）
New-Item -ItemType Directory -Force -Path (Join-Path $ROOT 'logs') | Out-Null

Start-Process $VENV -ArgumentList 'run.py' -WorkingDirectory $ROOT -WindowStyle Hidden `
  -RedirectStandardOutput "$ROOT\logs\l2.out.log" -RedirectStandardError "$ROOT\logs\l2.err.log"
do { Start-Sleep -Milliseconds 500 } until (Get-NetTCPConnection -State Listen -LocalPort 9998 -ErrorAction SilentlyContinue)

Start-Process $VENV -ArgumentList 'services\gateway\run.py' -WorkingDirectory $ROOT -WindowStyle Hidden `
  -RedirectStandardOutput "$ROOT\logs\gw.out.log" -RedirectStandardError "$ROOT\logs\gw.err.log"
do { Start-Sleep -Milliseconds 500 } until (Get-NetTCPConnection -State Listen -LocalPort 9999 -ErrorAction SilentlyContinue)

Start-Process $VENV -ArgumentList 'services\orchestration\run.py' -WorkingDirectory $ROOT -WindowStyle Hidden `
  -RedirectStandardOutput "$ROOT\logs\l3.out.log" -RedirectStandardError "$ROOT\logs\l3.err.log"
do { Start-Sleep -Milliseconds 500 } until (Get-NetTCPConnection -State Listen -LocalPort 9100 -ErrorAction SilentlyContinue)
```

```powershell
# 作用：确认端口监听与 Redis 连接日志
Get-NetTCPConnection -State Listen -LocalPort 9998,9999,9100 | Select-Object LocalAddress,LocalPort,OwningProcess
Select-String -Path "$ROOT\logs\l2.out.log" -Pattern 'Redis连接成功|Redis连接失败|Redis模块未安装'
# 预期：三个端口都有监听；日志出现 "Redis连接成功"
```

> 后台运行注意：`Start-Process` 在部分终端会话结束时可能被回收。若端口随后消失，改用持久化方式（计划任务/服务）或单独的常驻终端运行同样三条命令。

---

## 5. 校验

### 5.0 确认进程由 `.venv` 启动（含 venv redirector 说明）

`D:\programs\fastapi\agentpanel\.venv\Scripts\python.exe` 是 venv 启动器（约 274KB），它会 spawn 一个
pyenv 基础解释器子进程（命令行完全相同）。**监听端口由子进程持有**，因此：

- 子进程 `ExecutablePath` 显示 `C:\Users\admin\.pyenv\...\python.exe` 属正常；
- 判定依据是：父进程 `ExecutablePath` = `.venv\Scripts\python.exe`，且子进程内 `sys.prefix` 指向 `.venv`、
  `redis` 从 `.venv\Lib\site-packages` 导入。

```powershell
# 作用：按端口列出监听进程、其父进程与可执行路径
foreach ($port in 9998,9999,9100) {
  $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($c) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)"
    $pp = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)"
    "port=$port listen_pid=$($p.ProcessId) exe=$($p.ExecutablePath)"
    "        parent_pid=$($p.ParentProcessId) parent_exe=$($pp.ExecutablePath)"
  } else { "port=$port NOT LISTENING" }
}
# 预期：三个 parent_exe 均为 D:\programs\fastapi\agentpanel\.venv\Scripts\python.exe
```

```powershell
# 作用：解释器自证（sys.prefix / sys.executable / redis 来源）
& $VENV -c "import sys,redis;print(sys.executable);print(sys.prefix);print(redis.__file__)"
# 预期：.venv\Scripts\python.exe / .venv / .venv\Lib\site-packages\redis\__init__.py
```

### 5.1 L2 / L3：`/health/health` 中 redis 不再是 skipped

```powershell
# 作用：L2 与 L3 的 Redis 探针
(Invoke-RestMethod 'http://127.0.0.1:9998/health/health').checks.redis
(Invoke-RestMethod 'http://127.0.0.1:9100/health/health').checks.redis
# 预期：status=healthy, message='Redis connection OK'
# 若仍 skipped → 配置未生效（进程没重启或改错文件）；若 unhealthy → 看 message 里的 NOAUTH/refused
```

```powershell
# 作用：网关健康（网关只有 /health，没有 /health/health，也没有 redis 子项）
Invoke-RestMethod 'http://127.0.0.1:9999/health' | ConvertTo-Json -Compress
# 预期：{"status":"ok","deployment":"standalone","fail_closed":true}
# 网关的 Redis 连通性由 5.2 的租约缓存写入直接证明
```

### 5.2 网关：租约缓存真的落到 Redis

租约缓存 TTL 只有 8 秒。推荐用脚本“请求 + 立即抓 key”（见 §6 脚本中的 `gateway_lease` 段），或：

```powershell
# 作用：实时观察 Redis 命令；另开窗口发起一次带有效 dgw.* 租约的网关调用
docker exec -it agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD monitor
# 预期：出现 SET "gw:lease:state:<lease_id>" "<json>" EX "8"
#       以及额度相关命令：HGET/ZADD/SADD quota_* 等
# 退出：Ctrl+C
```

```powershell
# 作用：若刚好在 8 秒窗口内，可扫到残留 key（空结果不代表失败）
docker exec agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD --scan --pattern 'gw:lease:state:*'
```

### 5.3 额度预占：`counter_mode = redis` 且 `quota_hold:*` 存在

生产路径最可靠的做法是走 L2 内部额度 API（服务凭据 HMAC）。使用 §6 脚本即可同时完成该验证；
若只想手动看最近记录：

```powershell
# 作用：查最近 5 条预占记录的计数模式
$env:PYTHONPATH = $ROOT
& $VENV -c @'
import asyncio, configparser, asyncpg
c = configparser.ConfigParser(); c.read(r"d:\programs\fastapi\agentpanel\config.conf", encoding="utf-8")
d = c["db"]
async def main():
    conn = await asyncpg.connect(host=d["db_host"], port=int(d["db_port"]), user=d["db_user"],
                                 password=d["db_password"], database=d["db_name"])
    rows = await conn.fetch("select hold_id, counter_mode, status, created_at from quota_reservation order by id desc limit 5")
    for r in rows: print(dict(r))
    await conn.close()
asyncio.run(main())
'@
# 预期：新产生的行 counter_mode='redis'（历史行为 'db' 属正常，不是失败）
```

```powershell
# 作用：交叉确认 Redis 里确有该预占的键
docker exec agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD --scan --pattern 'quota_hold:*'
docker exec agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD HGETALL 'quota_hold:<上面查到的 hold_id>'
# 预期：key 存在，值为 owner_type/owner_id/items/expire_at
```

---

## 6. G1 并发幂等复跑（Redis 计数路径）

同一批用例在 `counter_mode=redis` 下复跑，验证：

1. 20 并发预占同一 `hold_id`：只产生 1 条 `quota_reservation`，`quota_held` 只加一次；
2. 20 并发结算同一 `idem_key`：只产生 1 条 `usage_record`，`quota used` 只加一次；
3. `release` 幂等：并发与重复释放只有一次生效。

脚本使用临时主体 `org/990001` + 现有 `harness_demo_plan`（id=8），结束后自动清理预占/流水/账户/绑定与 Redis 键。

```powershell
# 作用：把 G1 脚本落到临时目录（不进入仓库）
$G1DIR = Join-Path $env:TEMP 'agentpanel_redis_g1'
New-Item -ItemType Directory -Force -Path $G1DIR | Out-Null
$G1PY = Join-Path $G1DIR 'g1_redis.py'
```

```python
# 文件内容：$G1PY
# G1 并发幂等复跑（Redis 计数路径）
import asyncio, json, sys, time
sys.path.insert(0, r"D:\programs\fastapi\agentpanel")

CONCURRENCY, ORG_ID, PLAN_ID = 20, 990001, 8
HOLD_ID = f"g1redis_hold_{int(time.time())}"
IDEM_KEY = f"g1redis:idem:{int(time.time())}"
RESERVE_TOKEN, SETTLE_TOKEN = 500.0, 200.0

def _period():
    n = time.localtime(); return f"{n.tm_year:04d}-{n.tm_mon:02d}"

async def main() -> int:
    from tortoise import Tortoise
    from base.common.setting import TORTOISE_ORM
    await Tortoise.init(config=TORTOISE_ORM)
    from base.common.cache import RedisCache
    from base.common.quota.models.binding import QuotaPlanBinding
    from base.common.quota.models.quota import QuotaAccount, UsageRecord
    from base.common.quota.models.reservation import QuotaReservation
    from base.common.quota.services.quota_service import ACTIVE_OWNERS_KEY, HOLD_INDEX_KEY, QuotaService

    owner, period = ("org", ORG_ID), _period()
    used_key = f"quota:org:{ORG_ID}:token:{period}"
    held_key = f"quota_held:org:{ORG_ID}:token:{period}"
    hold_key = f"quota_hold:{HOLD_ID}"
    out, failures = {"hold_id": HOLD_ID, "idem_key": IDEM_KEY}, []
    cache = await RedisCache.get_instance()
    redis = cache._client if cache.is_enabled() else None
    if redis is None:
        print(json.dumps({"ok": False, "reason": "Redis 未启用"})); return 2

    async def cleanup():
        await UsageRecord.filter(idem_key=IDEM_KEY).delete()
        await QuotaReservation.filter(hold_id=HOLD_ID).delete()
        await QuotaAccount.filter(owner_type="org", owner_id=ORG_ID).delete()
        await QuotaPlanBinding.filter(bind_type="organization", bind_key=str(ORG_ID)).delete()
        for k in (used_key, held_key, hold_key): await redis.delete(k)
        await redis.zrem(HOLD_INDEX_KEY, HOLD_ID)
        await redis.srem(ACTIVE_OWNERS_KEY, f"org:{ORG_ID}")

    await cleanup()
    await QuotaPlanBinding.create(bind_type="organization", bind_key=str(ORG_ID), plan_id=PLAN_ID, priority=0)
    await QuotaService.ensure_account("org", ORG_ID)
    try:
        async def reserve():
            try: return {"ok": True, "v": await QuotaService.quota_estimate(owner=owner, items={"token": RESERVE_TOKEN}, hold_id=HOLD_ID, source="g1redis")}
            except Exception as e: return {"ok": False, "e": f"{type(e).__name__}: {e}"}
        rs = await asyncio.gather(*[reserve() for _ in range(CONCURRENCY)])
        rows = await QuotaReservation.filter(hold_id=HOLD_ID).all()
        held, used = float(await redis.get(held_key) or 0), float(await redis.get(used_key) or 0)
        out["A_reserve"] = {"same_hold_returns": sum(1 for r in rs if r["ok"] and r["v"] == HOLD_ID),
                            "errors": [r["e"] for r in rs if not r["ok"]],
                            "db_rows": len(rows), "counter_mode": [r.counter_mode for r in rows],
                            "redis_held": held, "redis_used": used,
                            "hold_key_exists": int(await redis.exists(hold_key))}
        if len(rows) != 1 or rows[0].counter_mode != "redis": failures.append("A: 行数/计数模式不符")
        if abs(held - RESERVE_TOKEN) > 1e-6: failures.append(f"A: held={held} 应只加一次 {RESERVE_TOKEN}")

        async def settle():
            try: return {"ok": True, "v": await QuotaService.quota_settle(HOLD_ID, [{"idem_key": IDEM_KEY, "resource_type": "token", "amount": SETTLE_TOKEN, "node_id": "g1-node", "seq": 1, "source": "g1redis"}])}
            except Exception as e: return {"ok": False, "e": f"{type(e).__name__}: {e}"}
        ss = await asyncio.gather(*[settle() for _ in range(CONCURRENCY)])
        usage = await UsageRecord.filter(idem_key=IDEM_KEY).all()
        used2, held2 = float(await redis.get(used_key) or 0), float(await redis.get(held_key) or 0)
        out["B_settle"] = {"usage_rows": len(usage), "settled_sum": sum(int(r["v"].get("settled") or 0) for r in ss if r["ok"]),
                           "errors": [r["e"] for r in ss if not r["ok"]],
                           "redis_used": used2, "redis_held": held2}
        if len(usage) != 1: failures.append(f"B: usage_record={len(usage)} 应为 1")
        if abs(used2 - SETTLE_TOKEN) > 1e-6: failures.append(f"B: used={used2} 应只加一次 {SETTLE_TOKEN}")

        async def release():
            try: return {"ok": True, "v": await QuotaService.quota_release(HOLD_ID)}
            except Exception as e: return {"ok": False, "e": f"{type(e).__name__}: {e}"}
        rr = await asyncio.gather(*[release() for _ in range(10)])
        again = await QuotaService.quota_release(HOLD_ID)
        row = await QuotaReservation.get_or_none(hold_id=HOLD_ID)
        out["C_release"] = {"true_count": sum(1 for r in rr if r["ok"] and r["v"]), "repeat": bool(again),
                            "errors": [r["e"] for r in rr if not r["ok"]],
                            "status": row.status if row else None, "redis_held": float(await redis.get(held_key) or 0),
                            "hold_key_exists": int(await redis.exists(hold_key))}
        if out["C_release"]["true_count"] != 1: failures.append("C: 并发释放应只有一次 true")
        if out["C_release"]["repeat"]: failures.append("C: 重复释放应返回 False")
        if out["C_release"]["status"] != "released": failures.append(f"C: 状态={out['C_release']['status']} 应为 released")

        out["failures"], out["ok"] = failures, not failures
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0 if not failures else 1
    finally:
        await cleanup()
        await Tortoise.close_connections()

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

```powershell
# 作用：执行 G1（全部使用 .venv 解释器）
& $VENV $G1PY
# 预期：JSON 中 "ok": true，"failures": []
#       本次实测：A 20/20 返回同一 hold、DB 1 行 redis、held=500、used=0；
#                B usage_record=1、settled 合计=1、used=200、held=300；
#                C true_count=1、重复释放 false、status=released、held=0
```

**若 G1 不通过**

- 记录 `failures` 的实际数值与差异；
- 按 §7 回滚到 `enabled=false` 并重启，保持 DB 路径可用；
- 把不通过的项与数值写入验收记录，不要保留半开状态。

**清理检查**

```powershell
# 作用：确认测试数据已清理（预期全部为 0）
docker exec agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD DBSIZE
# 注意：DBSIZE 可能包含服务运行期产生的并发槽等键，不必强求为 0；重点是下面的测试键为空
docker exec agentredis redis-cli --no-auth-warning -a $REDIS_PASSWORD --scan --pattern 'quota_*:org:990001:*'
```
```powershell
# 作用：DB 侧清理确认（预期均为 0）
$env:PYTHONPATH = $ROOT
& $VENV -c @'
import asyncio, sys
sys.path.insert(0, r"d:\programs\fastapi\agentpanel")
async def m():
    from tortoise import Tortoise
    from base.common.setting import TORTOISE_ORM
    await Tortoise.init(config=TORTOISE_ORM)
    c = Tortoise.get_connection("postgres")
    for t, w in [("quota_reservation","hold_id LIKE 'g1redis_%'"),
                 ("quota_account","owner_type='org' AND owner_id=990001"),
                 ("quota_plan_binding","bind_type='organization' AND bind_key='990001'"),
                 ("usage_record","idem_key LIKE 'g1redis:%'")]:
        r = await c.execute_query_dict(f"SELECT COUNT(*) AS c FROM {t} WHERE {w}")
        print(t, r[0]["c"])
    await Tortoise.close_connections()
asyncio.run(m())
'@
```

---

## 7. 回滚

回滚只回滚“本服务配置 + 本服务进程”。容器可停，但**不要删除命名卷**（避免数据丢失）。

```powershell
# 作用：停止三个进程（按端口定位 PID，含父进程）
foreach ($p in 9998,9999,9100) {
  $pids = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue |
          Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($id in $pids) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$id"
    if ($proc) { Stop-Process -Id $proc.ParentProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
  }
}
Start-Sleep -Seconds 3
```

```powershell
# 作用：把 [redis] 改回 enabled=false（host/port/db 保留，password 留空）
Copy-Item $CFG "$CFG.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
$off = @'
[redis]
enabled = false
host = 127.0.0.1
port = 6379
password = 
db = 0

'@
$text = Get-Content $CFG -Raw -Encoding UTF8
$text = [regex]::Replace($text, '(?m)^\[redis\]\r?\n(?:[^\[\r\n].*\r?\n)*', { param($m) $off })
[System.IO.File]::WriteAllText($CFG, $text, (New-Object System.Text.UTF8Encoding($false)))
```

```powershell
# 作用：按第 4 节用 .venv 重新启动，然后确认已回到 DB 降级
Start-Sleep -Seconds 5
(Invoke-RestMethod 'http://127.0.0.1:9998/health/health').checks.redis
# 预期：status=skipped, message='Redis not enabled'
```

```powershell
# 作用：可选——停容器但保留数据卷（下次启用直接 docker start agentredis）
docker stop agentredis
# 不要执行 docker rm -v / docker volume rm agentredis_data
```

---

## 本次验收记录（实测值）

| 项 | 实测 |
|---|---|
| `agentredis` 状态 | `Up`，`127.0.0.1:6379->6379/tcp`，`restart=unless-stopped` |
| 容器内配置 | `appendonly=yes`、`maxmemory-policy=noeviction`、`PING=PONG` |
| 项目探针 | `{'status': 'healthy', 'message': 'Redis connection OK'}` |
| L2 `/health/health` | `redis: healthy` |
| L3 `/health/health` | `redis: healthy` |
| 网关 `/health` | `{"status":"ok","deployment":"standalone","fail_closed":true}`（无 redis 子项） |
| 网关租约缓存 | `gw:lease:state:gl_g1verify_*` 存在，TTL=8s |
| 预占 | L2 内部 API 返回 200；`quota_reservation` 1 行 `counter_mode=redis`；`quota_hold:*` 存在 |
| G1-A 预占 | 20 并发返回同一 hold；DB 1 行；`held=500`、`used=0` |
| G1-B 结算 | 20 并发同一 idem_key；`usage_record=1`；`settled=1`；`used=200`、`held=300` |
| G1-C 释放 | 10 并发只有 1 次 `true`；重复释放 `false`；状态 `released`；`held=0`、hold key 删除 |

---

## 安全性与影响

- **DB 仍是权威账本**：`quota_reservation`（`hold_id` 唯一）与 `usage_record`（`idem_key` 唯一）始终先落库；Redis 只承担原子计数与缓存。
- **Redis 模式的历史行不会“卡死”**：结算按行内 `counter_mode` 分支；`redis` 行在 Redis 关闭后仍可结算，Redis 计数更新失败只告警。
- **可观测差异**：网关租约吊销最多延迟 `lease_cache_ttl_seconds=8s`；`authz`/`permissions` 缓存从 DB 直查切到 Redis。
- **不要动的东西**：`ORCHESTRATION_SERVICE_SECRET`（改掉会让 L3→L2 内部额度调用 503 fail-closed）；`aipanel-redis`；`agentredis_data` 卷。
- **密码**：只在 `config.conf` 本地保存（已解跟踪并 ignore）；文档与日志仅记录指纹/尾四位。
