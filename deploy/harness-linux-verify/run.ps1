# 在 Windows 上构建并运行 Linux 验证容器（Docker Desktop）。
# 不占用 9998/9999，不依赖正在运行的开发服务。
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$projectRoot = Resolve-Path (Join-Path $here "..\..")
$outDir = Join-Path $here "out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

docker build -t agentpanel-dsh-verify:0.1.5rc1 -f (Join-Path $here "Dockerfile") $here
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

docker run --rm --name agentpanel-dsh-verify `
  --network none `
  --security-opt seccomp=unconfined `
  --add-host api.deepseek.com:127.0.0.1 `
  -v "${outDir}:/out" `
  -v "$projectRoot\services\gateway\common\service.py:/opt/project_gateway_service.py:ro" `
  -v "$projectRoot\packages\agentpanel_common\upstream\egress.py:/opt/project_gateway_egress.py:ro" `
  agentpanel-dsh-verify:0.1.5rc1

Write-Host "结果目录: $outDir"
