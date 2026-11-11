# Windows 手动打包手册（agentpanel Harness 桌面客户端）

> 适用范围：在 Windows 本机把 `dshw/apps/desktop`（Electron 桌面壳 + 内嵌 Harness 运行时）打包成 win-x64 **unsigned 安装器**。
> 本手册基于 2026-11-10 实战打包记录整理，环境：Windows 11 + VS BuildTools 18 + Windows SDK 10.0.26100.0。
> 成功一次全流程约 **13–20 分钟**（压缩级别 0 时取下限）。

---

## 1. 产物与目录一览

| 项目 | 路径（相对 `dshw/apps/desktop`） |
|---|---|
| 安装器（最终产物） | `.desktop-build/targets/win-x64/unsigned-artifacts/deepseek-harness-<版本>-win-x64-unsigned.exe` |
| 免安装目录版 | `.desktop-build/targets/win-x64/unsigned-artifacts/win-unpacked/DeepSeek Harness.exe` |
| 打包过程日志 | `.desktop-build/packaging-runs/<run>/events.jsonl`、`result.json` |
| 下载缓存（Electron 等） | `DSH_DESKTOP_PACKAGE_CACHE_DIR` 指向的目录（本机 `dshw/.desktop-cache`） |
| 各阶段中间产物 | `.desktop-build/targets/win-x64/{runtime, package-set, dsh, electron, packed}` |

版本号来自 `apps/desktop/package.json` + 桌面构建版本发现逻辑（当前 0.2.x-rc 系列）。

---

## 2. 前置条件（一次性准备）

### 2.1 Node 与包管理器

- **Node ≥ 24.9.0**（monorepo engine 要求；本机装在 `D:/programs/fastapi/node24/node-v24.22.2-win-x64/`，系统默认 Node 22 只会得到 engine 警告但打包脚本可能用到新 API，务必显式用 24）
- pnpm 经 corepack：`corepack enable && corepack pnpm -v`（当前 11.28.5）
- 依赖已安装：仓库根 `pnpm install`

### 2.2 Visual Studio C++ 生成工具（编译安装器辅助 DLL）

`scripts/desktop-toolchain-preflight.ts` 会用 `vswhere` 检查：

- **Visual Studio Build Tools**（含 C++ 桌面开发工作负载 / MSVC v143+）
- **Windows SDK**（本机 10.0.26100.0）

首次打包时 `prepare-windows-installer.ps1` 会用 vcvars32 + cl 编译 `window-frame.dll` 并用 System.Drawing 生成 BMP 资源；**之后有新鲜度缓存守卫，产物比源码新就跳过编译**，所以编译环境只在首次或改源码后需要可用。

### 2.3 `.env.windows`（git 忽略，从 `.env.windows.example` 复制）

本机当前生效内容（本地 unsigned 构建）：

```ini
DSH_DESKTOP_APP_ID=com.deepseek.dsh
DSH_DESKTOP_APP_ID 之外的自动更新测试项见下
DOWNLOAD_TEST_ORIGIN=https://update.example.invalid   # 占位，使 check:package 过自动更新校验
DOWNLOAD_TEST_RELEASE_ID=022abef413afbd8a38d3b6dc4875038b  # 32 位 hex，一次发布批次固定
DSH_DESKTOP_MANDATORY_UPDATE_TEST_ORIGIN=https://update.example.invalid
DSH_DESKTOP_MANDATORY_UPDATE_CONFIG={"allowedAuthOrigins":["https://login.example.invalid"]}
DSH_DESKTOP_WINDOWS_COMPRESSION_LEVEL=0   # 0=store 不压缩，本地提速；正式发布建议 3-9
DSH_DESKTOP_NPM_REGISTRY=https://registry.npmmirror.com  # 内嵌 dsh 运行时安装走国内镜像
```

注意事项：
- `DSH_DESKTOP_APP_ID`、`AGENTPANEL_*` 是**运行时变量**，不要写进 `.env.windows`（会被 `unsupported setting` 拒绝）。
- `DSH_DESKTOP_PACKAGE_CACHE_DIR` 同样在文件白名单之外，**必须走用户级环境变量**：
  `setx DSH_DESKTOP_PACKAGE_CACHE_DIR "D:\programs\fastapi\agentpanel\dshw\.desktop-cache"`（对新开的终端才生效）。
- 签名字段（`DSH_DESKTOP_WINDOWS_CER_FILE` 等）本地 unsigned 全部留空。

### 2.4 磁盘

缓存目录 ~400MB（downloads + pnpm-store）、中间产物 + 产物 ~1GB、NSIS 打包临时空间，建议预留 **≥5GB**。

---

## 3. 每次打包前的环境设置（Git Bash）

```bash
# 1) PATH：System32 提前（用 bsdtar，GNU tar 会把 D: 当远程主机）+ Node 24
export PATH="/c/WINDOWS/system32:/d/programs/fastapi/node24/node-v24.22.2-win-x64:$PATH"
hash -r   # 清掉 bash 缓存的旧命令路径

# 2) 清代理（WorkBuddy 本地代理会 hang 掉 pnpm 网络库）
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

# 3) 镜像与沙箱开关
export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"   # Electron 直连 github 会超时
export CODEBUDDY_SAFE_DELETE_ENABLED=0   # 仅 AI/沙箱环境需要：打包要删大量文件，防 safe-delete 拦截

node -v   # 确认 v24.x
```

> 普通用户终端（非 AI 沙箱）可以省略 `CODEBUDDY_SAFE_DELETE_ENABLED`；若代理本就未设置则无需 unset。

### 补充：vcvars32 编译环境（仅首次或改 window-frame 源码时需要）

本环境 `reg.exe` 被沙箱黑名单拦截导致 vcvars32 探测失败，替代方案是**预置 SDK 环境变量**（VS18 BuildTools + SDK 10.0.26100.0）：

```bash
export WindowsSdkDir="C:\\Program Files (x86)\\Windows Kits\\10\\"
export WindowsSDKVersion="10.0.26100.0\\"
export INCLUDE="C:\\Program Files\\Microsoft Visual Studio\\...\\VC\\Tools\\MSVC\\14.51.36231\\include;..."
export LIB="...\\MSVC\\14.51.36231\\lib\\x64;...\\Windows Kits\\10\\Lib\\10.0.26100.0\\um\\x64;..."
```

缓存守卫生效后（`window-frame.dll` 已存在且新于源码）这步可完全跳过。

---

## 4. 一键打包（推荐路径）

在 `dshw/` 仓库根执行：

```bash
pnpm package:desktop:win:x64:unsigned
```

实际链路：`packages/desktop` 脚本 → `apps/desktop` 的 `tsx scripts/package-target.ts win-x64 --unsigned`。**必须经 pnpm 调起**（脚本读取 `npm_execpath`，直接 tsx 会报错）。

### 阶段流水（unsigned 路径）

| # | 阶段 | 内容 | 耗时参考 |
|---|------|------|---------|
| 1 | `configuration` | 校验 `.env.windows` 与目标组合 | 秒级 |
| 2 | `toolchain` | vswhere 检查 C++ 生成工具 | 秒级 |
| 3 | `build --profile local` | monorepo 编译：tsc + tsdown（host/client/desktop bundle 等 10 gate） | ~1.5min |
| 4 | `prepare:runtime` | 下载/准备 Node 运行时（走缓存）、生成 runtime manifests | 2.7–5min |
| 5 | `prepare:packages` | 组装安装器所需包集 | ~1min |
| 6 | `prepare:dsh` | 内嵌 pnpm 安装 dsh 运行时到目标目录（npm 镜像 + 过滤 `*_PROXY`） | 3.2–4.6min |
| 7 | `electron-builder`（NSIS） | 打 asar、7z 压缩（级别 0 时为 store）、生成安装器、编译 window-frame.dll（首次） | 5.3–7.3min（级别 0 时大幅缩短） |
| 8 | `smoke-packaged-runtime --unsigned` | 启动打包版运行时冒烟（DOCX/XLSX/PPTX→PDF、skill CLI 等） | ~1.5min |

任一阶段失败即中止，结果写入 `.desktop-build/packaging-runs/<run>/result.json`；实时进度看同目录 `events.jsonl`。

---

## 5. 产物验证

```bash
# 产物存在 + 体积（正常 300MB 上下，级别 0 会更大）
ls -lh apps/desktop/.desktop-build/targets/win-x64/unsigned-artifacts/

# 版本一致性：exe 元数据 / asar 内 app 版本 / 日志
node -e "console.log(require('./apps/desktop/package.json').version)"
```

**手动运行验证**（重要，自动化冒烟不覆盖 GUI）：

1. 双击（或在终端前台运行）`win-unpacked/DeepSeek Harness.exe`。
   - 若在 AI 沙箱里用命令行启动：`env -u ELECTRON_RUN_AS_NODE -u NODE_OPTIONS "...exe"`，否则 Electron 会变成 Node CLI。
2. 首启应显示欢迎页（登录 / 添加 API Key），日志无报错。
3. 打包版 DevTools 用 **F12**（`DSH_DESKTOP_OPEN_DEVTOOLS` 环境变量对 app.isPackaged 无效）。
4. 需要测「登录测试环境」弹窗时，在 `%APPDATA%` 对应 userData 的 `desktop/settings.json` 加 `updates.allowTestAuthPopupWindow=true`。

可选：`pnpm --filter @deepseek-ai/dsh-desktop run check:package`（`--check` 模式，做自动更新等发布前校验；本地无签名凭据时签名类报错属预期）。

---

## 6. 分阶段手动打包（调试用）

```bash
cd dshw/apps/desktop

# 只做准备工作（build + prepare:runtime/packages/dsh），不进 electron-builder
pnpm run package:win:x64:unsigned --dir      # 到 unpacked 目录为止，跳过 NSIS（提速验证界面用）
pnpm run prepare:package                      # prepare-only，之后可手动调 electron-builder 复试单阶段

# 手动重打（复用已准备好的运行时）
pnpm exec electron-builder --config electron-builder.config.mjs --win --x64 --publish never
```

`--dir` 版本适合「改了客户端代码 → 快速看界面」的迭代循环：免 NSIS 压缩，整体可压到 8 分钟以内。

---

## 7. 常见故障与对策（实战记录）

| 症状 | 原因 | 对策 |
|------|------|------|
| `safe-delete ... exceeds threshold` 中止 | 沙箱删除大量文件被拦 | `export CODEBUDDY_SAFE_DELETE_ENABLED=0` |
| `download:electron fetch failed` / github 超时 | Electron 二进制直连 github | `export ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/` |
| `tar: Cannot connect to D:` | GNU tar 把 `D:` 当远程主机 | PATH 前置 `/c/WINDOWS/system32` 用 bsdtar |
| vcvars32 / `windows.h` 缺失 | `reg.exe` 被沙箱拦截 → SDK 探测失败 | 预置 `WindowsSdkDir/WindowsSDKVersion/INCLUDE/LIB`；或依赖已缓存产物跳过编译 |
| `runtime:lockfile` 失败、pnpm 解析挂起 | pnpm 网络库读到本地代理 / 网络抖动 | unset `*_PROXY`（prepare-dsh 已过滤）；重试 |
| pnpm 并发 registerProject 活锁/EPERM | pnpm v11 Windows fresh store 竞态 | 已由 `patchBundledPnpmProjectRegistration` 补丁修复；若复现重跑一次 |
| smoke 阶段单项失败 | 多为瞬态 flaky | 单独重跑：`pnpm exec tsx scripts/smoke-packaged-runtime.ts --unsigned` |
| `pnpm package` 报 `invoke this script through a pnpm package command` | 直接 tsx 调 package-target.ts | 必须经 `pnpm run package:*` 链路 |

---

## 8. 提速技巧（本地迭代）

1. **压缩级别 0**：`.env.windows` 的 `DSH_DESKTOP_WINDOWS_COMPRESSION_LEVEL=0`（store 模式），NSIS 阶段从 ~6min 降到 ~2min，代价是安装器更大。
2. **`--dir` 免安装版**：跳过 NSIS，改 `win-unpacked` 目录直接运行。
3. **持久缓存目录**：`DSH_DESKTOP_PACKAGE_CACHE_DIR`（用户级 setx），Electron 下载与 pnpm store 跨次复用（首次后省 5–8min）。
4. **Defender 排除**：把 `dshw/.desktop-build`、`dshw/.desktop-cache`、`dshw/node_modules` 加入 Windows Defender 排除列表，编译/压缩阶段提速明显。
5. **新鲜度缓存**：window-frame.dll 等原生产物已有守卫，未改源码时不会重编。

---

## 9. 版本与发布说明

- 本手册仅覆盖 **unsigned 本地包**。正式签名发布需要：签名证书（`DSH_DESKTOP_WINDOWS_CER_FILE/SIGNTOOL/KEY_CONTAINER/TOKEN_PIN`）、`setup-windows-packaging.ps1` 初始化的受控打包目录、以及 `upload:win:x64` 上传链路——见 `dshw/docs` 与 `scripts/preflight-desktop-publish.mjs`。
- `pnpm package:desktop:win:x64`（不带 `:unsigned`）走签名 + 发布记录链路，本地无凭据会失败，属预期。
- 打包后建议跑 `tests/e2e/desktop_e2e.py`（桌面自动化 20 项）做端到端回归。
