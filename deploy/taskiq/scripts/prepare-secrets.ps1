# taskiq 栈 secrets 与 .env 生成（仅开发/验证；生产用外部密钥管理）
#
# 用法（仓库根或任意目录，PowerShell）：
#   powershell -ExecutionPolicy Bypass -File deploy/taskiq/scripts/prepare-secrets.ps1
#
# 输入：根目录 config.conf 的 [db] / [rabbitmq]；redis 密码取自 deploy/app/config.conf
#       （与 redis 容器启动密码一致），缺省回退根目录 config.conf
# 输出（均被 .gitignore 排除，禁止入库）：
#   deploy/taskiq/secrets/db_password
#   deploy/taskiq/secrets/redis_password
#   deploy/taskiq/secrets/taskiq_broker_url      # amqp 完整 URL（含专用 vhost，容器经 host.docker.internal 访问宿主 RabbitMQ）
#   deploy/taskiq/secrets/taskiq_db_url          # PG async URL（postgresql+asyncpg://）
#   deploy/taskiq/.env                           # compose 变量插值（不含密钥）
#
# 说明：
#   - taskiq 容器复用 app 镜像（agentpanel-app），config.conf 已烤进镜像；
#     DB_HOST / REDIS_HOST / TASKIQ_* 经 compose environment 与 *_FILE secret 覆盖，
#     不在此改写 config.conf。
#   - vhost / 账号优先级：config.conf [rabbitmq] taskiq_* 三键 -> 共用键 -> 缺省 agentpanel。
#   - 密码经 URI 编码，避免 @ / / 等特殊字符破坏 amqp / postgresql URL。

$ErrorActionPreference = 'Stop'

$scriptDir = $PSScriptRoot                                   # deploy/taskiq/scripts
$deployDir = Split-Path -Parent $scriptDir                    # deploy/taskiq
$repoRoot  = Split-Path -Parent (Split-Path -Parent $deployDir)  # 仓库根
$secretsDir = Join-Path $deployDir 'secrets'
$sourceConf = Join-Path $repoRoot 'config.conf'
$envFile    = Join-Path $deployDir '.env'

if (-not (Test-Path $sourceConf)) {
    throw "找不到根目录 config.conf：$sourceConf"
}
if (-not (Test-Path $secretsDir)) {
    New-Item -ItemType Directory -Path $secretsDir | Out-Null
}

function Read-IniValue {
    param([string[]]$Lines, [string]$Section, [string]$Key, [switch]$Required)
    $inSection = $false
    foreach ($line in $Lines) {
        if ($line -match '^\s*\[(.+)\]\s*$') {
            $inSection = ($Matches[1].Trim() -eq $Section)
            continue
        }
        if ($inSection -and $line -match ('^\s*' + [regex]::Escape($Key) + '\s*=\s*(.*)$')) {
            return $Matches[1].Trim()
        }
    }
    if ($Required) { throw "config.conf 缺少 [$Section] $Key" }
    return ''
}

function Write-SecretText {
    param([string]$Path, [string]$Value)
    [System.IO.File]::WriteAllText($Path, $Value, (New-Object System.Text.UTF8Encoding($false)))
}

$confLines = [System.IO.File]::ReadAllLines($sourceConf, [System.Text.Encoding]::UTF8)

$dbName = Read-IniValue $confLines 'db' 'db_name' -Required
$dbUser = Read-IniValue $confLines 'db' 'db_user' -Required
$dbPassword = Read-IniValue $confLines 'db' 'db_password' -Required
$dbPort = Read-IniValue $confLines 'db' 'db_port' -Required

# Redis 密码必须与 redis 容器实际启动密码一致：redis 容器由 deploy/app/.env 的
# REDIS_PASSWORD 启动，运行时 app 读 deploy/app/config.conf（同值）。优先取该文件，
# 缺省回退到仓库根 config.conf（仅本地开发/构建期模板）。
$deployAppConf = Join-Path (Split-Path -Parent $deployDir) 'app/config.conf'
if (Test-Path $deployAppConf) {
    $appConfLines = [System.IO.File]::ReadAllLines($deployAppConf, [System.Text.Encoding]::UTF8)
    $redisPassword = Read-IniValue $appConfLines 'redis' 'password'
}
if (-not $redisPassword) {
    $redisPassword = Read-IniValue $confLines 'redis' 'password' -Required
}

$rmqHost = Read-IniValue $confLines 'rabbitmq' 'host' -Required
$rmqPort = Read-IniValue $confLines 'rabbitmq' 'port' -Required
$rmqUser = Read-IniValue $confLines 'rabbitmq' 'taskiq_username'
if (-not $rmqUser) { $rmqUser = Read-IniValue $confLines 'rabbitmq' 'username' -Required }
$rmqPass = Read-IniValue $confLines 'rabbitmq' 'taskiq_password'
if (-not $rmqPass) { $rmqPass = Read-IniValue $confLines 'rabbitmq' 'password' -Required }
$taskiqVhost = Read-IniValue $confLines 'rabbitmq' 'taskiq_vhost'
if (-not $taskiqVhost) { $taskiqVhost = Read-IniValue $confLines 'rabbitmq' 'virtual_host' }
if (-not $taskiqVhost) { $taskiqVhost = 'agentpanel' }

# 容器内经 host.docker.internal 访问宿主 RabbitMQ / PG
$taskiqBrokerUrl = "amqp://$([System.Uri]::EscapeDataString($rmqUser)):$([System.Uri]::EscapeDataString($rmqPass))@host.docker.internal:$rmqPort/$([System.Uri]::EscapeDataString($taskiqVhost))"
$taskiqDbUrl = "postgresql+asyncpg://$([System.Uri]::EscapeDataString($dbUser)):$([System.Uri]::EscapeDataString($dbPassword))@host.docker.internal:$dbPort/$dbName"

# secrets（无行尾换行，避免被当成密码一部分）
Write-SecretText (Join-Path $secretsDir 'db_password') $dbPassword
Write-SecretText (Join-Path $secretsDir 'redis_password') $redisPassword
Write-SecretText (Join-Path $secretsDir 'taskiq_broker_url') $taskiqBrokerUrl
Write-SecretText (Join-Path $secretsDir 'taskiq_db_url') $taskiqDbUrl

# .env：compose 变量插值（不含密钥）
$envContent = @(
    "# 由 deploy/taskiq/scripts/prepare-secrets.ps1 生成；禁止入库",
    "DB_NAME=$dbName",
    "DB_USER=$dbUser",
    "TAG=latest",
    "TASKIQ_VHOST=$taskiqVhost"
) -join "`n"
[System.IO.File]::WriteAllText($envFile, $envContent + "`n", (New-Object System.Text.UTF8Encoding($false)))

Write-Host "secrets 已生成：$secretsDir"
Write-Host "  db_password / redis_password / taskiq_broker_url / taskiq_db_url"
Write-Host "env 已生成：$envFile"
Write-Host "注意：taskiq_broker_url 使用专用 vhost '$taskiqVhost'，须先在 RabbitMQ 创建并授权（deploy/rabbitmq/definitions.json）。"
