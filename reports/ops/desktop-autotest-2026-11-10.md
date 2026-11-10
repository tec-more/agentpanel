# 桌面版自动化测试报告

- 生成时间：2026-11-10 17:04:46
- 被测对象：DeepSeek Harness 桌面版 `0.2.2-rc.1` / `win-x64` / unsigned 打包产物
- 被测程序：`D:\programs\fastapi\agentpanel\dshw\apps\desktop\.desktop-build\targets\win-x64\unsigned-artifacts\win-unpacked\DeepSeek Harness.exe`
- 测试方式：自动化脚本自启动实例 → 产物断言 → 窗口渲染 → Host 可达性 → UI 点击交互 → 日志扫描
- 配置隔离：每个用例使用独立 `test-user-data-autotest-*` 目录，保证落在首次启动欢迎页

## 结果摘要

| 总计 | PASS | FAIL | SKIP |
| --- | --- | --- | --- |
| 20 | 20 | 0 | 0 |

## 用例明细

| ID | 用例 | 断言 | 结果 | 实测 | 证据 |
| --- | --- | --- | --- | --- | --- |
| A01 | 主可执行文件 | win-unpacked/DeepSeek Harness.exe 存在且 > 200 MB | PASS | 234.9 MB | DeepSeek Harness.exe |
| A02 | NSIS 未签名安装器 | unsigned exe 存在且 > 300 MB | PASS | 303.4 MB | deepseek-harness-0.2.2-rc.1-win-x64-unsigned.exe |
| A03 | 应用包 app.asar | app.asar 存在且 > 200 MB | PASS | 215.8 MB | app.asar |
| A04 | 随包运行时目录 | runtime/bin、cli、primary-runtime 与 versions.json 齐备 | PASS | {"schemaVersion": 1, "node": "24.21.0", "pnpm": "11.28.5"} | resources/runtime/versions.json |
| A05 | 版本一致性 | package.json 版本与安装器文件名一致 | PASS | package.json=0.2.2-rc.1, installer=0.2.2-rc.1 |  |
| A06 | 网关可达性 | 127.0.0.1:9999 有 HTTP 响应 | PASS | HTTP 404, 22 bytes |  |
| A07 | 控制面可达性 | 127.0.0.1:9998 有 HTTP 响应 | PASS | HTTP 200, 476 bytes |  |
| S01 | 打包运行时 smoke | 仓库自带 smoke 脚本退出码为 0 | PASS | exit=0, 79s | smoke-autotest.log |
| C01-start | 登录入口 · 窗口启动 | 进程创建且可见窗口出现 | PASS | pid=41516, 窗口=DeepSeek Harness, rect=(988, 250, 2212, 1667) |  |
| C01-render | 登录入口 · 欢迎页渲染 | 窗口截图尺寸合理且非空白 | PASS | 1224x1417, 均值=220 | login-01-welcome.png |
| C01-host | 登录入口 · Desktop Host | Host 地址可从日志解析且 HTTP 可达 | PASS | port=57748, HTTP 200, 41405 bytes | app-launch-login.log |
| C01-ui | 登录入口 · 交互响应 | 点击「登录」后界面发生变化 | PASS | 点击=(1600,1326), 像素均差=4.96, 窗口标题=['DeepSeek Harness'] | login-02-after-login.png |
| C01 | 登录入口 | 点击后业务流程无 IPC handler 错误 | PASS | 无 IPC handler 错误 | app-launch-login.log |
| C01-log | 登录入口 · 启动日志 | 无致命崩溃且进程存活 | PASS | IPC 错误行=0, 崩溃=False, 日志行数=2 | app-launch-login.log |
| C02-start | 连接账号（注册）入口 · 窗口启动 | 进程创建且可见窗口出现 | PASS | pid=22116, 窗口=DeepSeek Harness, rect=(988, 250, 2212, 1667) |  |
| C02-render | 连接账号（注册）入口 · 欢迎页渲染 | 窗口截图尺寸合理且非空白 | PASS | 1224x1417, 均值=220 | connect-01-welcome.png |
| C02-host | 连接账号（注册）入口 · Desktop Host | Host 地址可从日志解析且 HTTP 可达 | PASS | port=56583, HTTP 200, 41405 bytes | app-launch-connect.log |
| C02-ui | 连接账号（注册）入口 · 交互响应 | 点击「连接账号」后界面发生变化 | PASS | 点击=(1600,1496), 像素均差=4.42, 窗口标题=['DeepSeek Harness'] | connect-02-after-connect.png |
| C02 | 连接账号（注册）入口 | 点击后业务流程无 IPC handler 错误 | PASS | 无 IPC handler 错误 | app-launch-connect.log |
| C02-log | 连接账号（注册）入口 · 启动日志 | 无致命崩溃且进程存活 | PASS | IPC 错误行=0, 崩溃=False, 日志行数=2 | app-launch-connect.log |

## 截图证据

- `D:\programs\fastapi\agentpanel\dshw\apps\desktop\.desktop-build\autotest\login-01-welcome.png`（1224x1417）
- `D:\programs\fastapi\agentpanel\dshw\apps\desktop\.desktop-build\autotest\login-02-after-login.png`（1224x1417）
- `D:\programs\fastapi\agentpanel\dshw\apps\desktop\.desktop-build\autotest\connect-01-welcome.png`（1224x1417）
- `D:\programs\fastapi\agentpanel\dshw\apps\desktop\.desktop-build\autotest\connect-02-after-connect.png`（1224x1417）

## 仓库自带测试

- 命令：`node ../../node_modules/tsx/dist/cli.mjs scripts/smoke-packaged-runtime.ts --unsigned`
- 退出码：`0`，耗时 79s，日志 `D:/programs/fastapi/agentpanel/dshw/apps/desktop/.desktop-build/smoke-autotest.log`
- 覆盖范围：随包运行时树、原生 Office 转换（ASAR 外）、运行时签名校验（unsigned 跳过签名）


## 环境与已知限制

- 沙箱全局注入 `ELECTRON_RUN_AS_NODE=1`，会让 Electron 退化为 Node CLI（无窗口）；脚本启动实例时已剔除该变量及大小写重复的代理变量。
- 沙箱安全策略拦截 `reg.exe`（应用内部调用），该拦截属于环境限制，不是应用缺陷；已验证它不影响欢迎页渲染与 Host 启动。
- 由工具启动的 GUI 进程会在命令会话结束时被回收，因此本报告的实例由脚本在同一进程内启动、断言、关闭；长时间人工验收需手动双击 exe。
- 更新策略 origin 为 `https://update.example.invalid` 占位域名，强制更新/登录测试环境弹窗流程未纳入本次自动化。
- 真实账号登录已验证：由 `customer_ui_login.py` 在真实打包应用内用 customer 测试账号完成「登录 → 进入主工作区」全流程，
  `account-store/account.json` 落盘（含 `accessToken`/`customerId`/`lease`），主工作区正常渲染（见 `ui-login-04-after.png`）。
- 欢迎页「添加 API Key」可见入口已按产品决策隐藏，仅保留「登录」与「连接账号（注册）」；本脚本的 C01/C02 验证这两个入口的点击响应。

## 复现

```bash
D:\programs\fastapi\agentpanel\.venv\Scripts\python.exe D:\programs\fastapi\agentpanel\tests\e2e\desktop_e2e.py
```

结构化结果：`D:\programs\fastapi\agentpanel\dshw\apps\desktop\.desktop-build\autotest\results.json`
