@echo off
setlocal
rem Start DeepSeek Harness Web UI with AgentPanel wiring.
rem Double-click to launch; the browser opens automatically with a one-time token.
rem Pass extra flags after the script name, e.g.: start-web.cmd --no-open --port 3081

set DSH_AGENTPANEL_CUSTOMER_URL=http://127.0.0.1:9080/v1/customer
rem 发现应用目录已迁入 harness 插件，单独覆盖，customerUrl 仍用于登录/票据
set DSH_AGENTPANEL_APPS_ENDPOINT=http://127.0.0.1:9080/v1/harness/discover-apps
set DSH_AGENTPANEL_PANEL_URL=http://127.0.0.1:9080
set DSH_AGENTPANEL_GATEWAY_URL=http://127.0.0.1:9999

cd /d "%~dp0.."
echo Starting dsh web from %CD% ...
node --import tsx/esm apps/cli/src/bin.ts web %*

echo.
echo dsh web exited. Press any key to close this window.
pause >nul
