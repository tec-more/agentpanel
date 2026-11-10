# P5 Docker 交付：生成本地 secrets 与 .env（仅开发/验证环境；生产用外部密钥管理）
#
# 用法（Windows PowerShell，仓库根目录或任意目录）：
#   powershell -ExecutionPolicy Bypass -File deploy/gateway/scripts/prepare-secrets.ps1
#
# 输入：
#   - 根目录 config.conf 的 [db] / [redis]（密码来源）
#   - 环境变量 ORCHESTRATION_SERVICE_SECRET（必须与 L2 DB 中
#     service_credential.svc_orchestration 的凭据一致，不能随机生成）
#
# 输出（均被 .gitignore 排除，禁止入库）：
#   deploy/gateway/secrets/db_password
#   deploy/gateway/secrets/redis_password
#   deploy/gateway/secrets/orchestration_service_secret
#   deploy/gateway/secrets/app_config.conf        # 容器内 /app/config.conf
#   deploy/gateway/.env
#
# 说明：app_config.conf 只调整容器内可达地址（DB/Qdrant/RabbitMQ 走
# host.docker.internal，Redis 走 agentredis 网络别名），密码与业务配置沿用
# 根目录 config.conf；新增 [deploy] 段用于容器 fail-closed 自检。

$ErrorActionPreference = 'Stop'

$scriptDir = $PSScriptRoot                                   # deploy/gateway/scripts
$deployDir = Split-Path -Parent $scriptDir                       # deploy/gateway
$repoRoot = Split-Path -Parent (Split-Path -Parent $deployDir)   # 仓库根
$secretsDir = Join-Path $deployDir 'secrets'
$sourceConf = Join-Path $repoRoot 'config.conf'
$envFile = Join-Path $deployDir '.env'

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

function Set-IniValue {
    param([string[]]$Lines, [string]$Section, [string]$Key, [string]$Value)
    $out = New-Object System.Collections.Generic.List[string]
    $inSection = $false
    $written = $false
    foreach ($line in $Lines) {
        if ($line -match '^\s*\[(.+)\]\s*$') {
            if ($inSection -and -not $written) {
                $out.Add("$Key = $Value"); $written = $true
            }
            $inSection = ($Matches[1].Trim() -eq $Section)
            $out.Add($line)
            continue
        }
        if ($inSection -and -not $written -and
            $line -match ('^\s*' + [regex]::Escape($Key) + '\s*=')) {
            $out.Add("$Key = $Value"); $written = $true
            continue
        }
        $out.Add($line)
    }
    if ($inSection -and -not $written) { $out.Add("$Key = $Value") }
    return $out.ToArray()
}

function Ensure-IniSection {
    param([string[]]$Lines, [string]$Section)
    $exists = $false
    foreach ($line in $Lines) {
        if ($line -match '^\s*\[(.+)\]\s*$' -and $Matches[1].Trim() -eq $Section) {
            $exists = $true; break
        }
    }
    if ($exists) { return $Lines }
    return @($Lines + @('', "[$Section]"))
}

function Write-SecretText {
    param([string]$Path, [string]$Value)
    [System.IO.File]::WriteAllText($Path, $Value, (New-Object System.Text.UTF8Encoding($false)))
}

$confLines = [System.IO.File]::ReadAllLines($sourceConf, [System.Text.Encoding]::UTF8)

$dbName = Read-IniValue $confLines 'db' 'db_name' -Required
$dbUser = Read-IniValue $confLines 'db' 'db_user' -Required
$dbPassword = Read-IniValue $confLines 'db' 'db_password' -Required
$redisPassword = Read-IniValue $confLines 'redis' 'password' -Required

$orchSecret = $env:ORCHESTRATION_SERVICE_SECRET
if ([string]::IsNullOrWhiteSpace($orchSecret)) {
    # 与 reports/ops/redis-enable-runbook.md 一致：优先复用 User 级环境变量
    $orchSecret = [Environment]::GetEnvironmentVariable('ORCHESTRATION_SERVICE_SECRET', 'User')
}
if ([string]::IsNullOrWhiteSpace($orchSecret)) {
    throw ("环境变量 ORCHESTRATION_SERVICE_SECRET 未设置（进程级或 User 级）。" +
           "该值必须与 L2 DB service_credential(svc_orchestration) 一致，请从现有部署环境读取后重试。")
}

# secrets：密码文件不带行尾换行，避免被当成密码的一部分
Write-SecretText (Join-Path $secretsDir 'db_password') $dbPassword
Write-SecretText (Join-Path $secretsDir 'redis_password') $redisPassword
Write-SecretText (Join-Path $secretsDir 'orchestration_service_secret') $orchSecret.Trim()

# app config.conf：容器内地址改写 + [deploy] 段
$appLines = $confLines
$appLines = Set-IniValue $appLines 'db' 'db_host' 'host.docker.internal'
$appLines = Set-IniValue $appLines 'storage' 'path' '/app/storage'
$appLines = Set-IniValue $appLines 'log' 'path' '/app/logs'
$appLines = Set-IniValue $appLines 'redis' 'host' 'agentredis'
$appLines = Set-IniValue $appLines 'qdrant' 'host' 'http://host.docker.internal:6333'
$appLines = Set-IniValue $appLines 'rabbitmq' 'host' 'host.docker.internal'
$appLines = Ensure-IniSection $appLines 'deploy'
$appLines = Set-IniValue $appLines 'deploy' 'env' 'docker'
$appLines = Set-IniValue $appLines 'deploy' 'strict_startup' 'true'

$appConfigPath = Join-Path $secretsDir 'app_config.conf'
[System.IO.File]::WriteAllLines($appConfigPath, $appLines, (New-Object System.Text.UTF8Encoding($false)))

# .env：compose 变量插值（不含密钥）
# 端口与 deploy/gateway/docker-compose.yml 头部约定保持一致：网关 9999 / 编排 9100。
# 旧端口 19999 / 19100 仅用于 port-switch-9998-9999-9100.md 记载的回滚场景。
$envContent = @(
    "# 由 deploy/gateway/scripts/prepare-secrets.ps1 生成；禁止入库",
    "DB_NAME=$dbName",
    "DB_USER=$dbUser",
    "TAG=local",
    "GW_PROVIDER_DOMAIN_ALLOWLIST=api.deepseek.com",
    "GW_PUBLIC_BASE_URL=http://127.0.0.1:9999",
    "ORCH_PUBLIC_BASE_URL=http://127.0.0.1:9100"
) -join "`n"
[System.IO.File]::WriteAllText($envFile, $envContent + "`n", (New-Object System.Text.UTF8Encoding($false)))

Write-Host "secrets 已生成：$secretsDir"
Write-Host "  db_password / redis_password / orchestration_service_secret / app_config.conf"
Write-Host "env 已生成：$envFile"
