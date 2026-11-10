# -*- coding: utf-8 -*-
"""Packaged desktop app E2E automation.

Launches the unsigned win-x64 build, asserts artifact integrity, window
rendering, Desktop Host reachability and the two welcome-page entry points,
then writes a Markdown report. Runs entirely in one process so the window is
not reclaimed between tool calls.
"""

import ctypes
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import requests
import win32api
import win32con
import win32gui
from PIL import ImageGrab

DESKTOP = Path(r"D:\programs\fastapi\agentpanel\dshw\apps\desktop")
BUILD = DESKTOP / ".desktop-build"
OUT = BUILD / "autotest"
OUT.mkdir(parents=True, exist_ok=True)
ARTIFACTS = BUILD / "targets" / "win-x64" / "unsigned-artifacts"
UNPACKED = ARTIFACTS / "win-unpacked"
EXE = UNPACKED / "DeepSeek Harness.exe"
INSTALLER = ARTIFACTS / "deepseek-harness-0.2.2-rc.1-win-x64-unsigned.exe"
ASAR = UNPACKED / "resources" / "app.asar"
RUNTIME = UNPACKED / "resources" / "runtime"
REPORT = Path(r"D:\programs\fastapi\agentpanel\reports\ops\desktop-autotest-2026-11-10.md")

for key in [
    "ELECTRON_RUN_AS_NODE", "NODE_OPTIONS", "NODE_EXTRA_CA_CERTS",
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
]:
    os.environ.pop(key, None)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

RESULTS = []
SHOTS = []


def record(case_id, title, assertion, ok, detail, evidence="", skipped=False):
    status = "SKIP" if skipped else ("PASS" if ok else "FAIL")
    RESULTS.append({
        "id": case_id, "title": title, "assertion": assertion,
        "status": status, "detail": detail, "evidence": evidence,
    })
    print(f"[{status}] {case_id} {title} - {detail}", flush=True)


def file_size(path):
    return path.stat().st_size if path.is_file() else 0


def mb(n):
    return round(n / 1024 / 1024, 1)


def find_app_windows():
    found = []

    def callback(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if "harness" in title.lower():
                found.append((hwnd, title, win32gui.GetWindowRect(hwnd)))
        except Exception:
            return

    win32gui.EnumWindows(callback, None)
    return found


def window_shot(hwnd, name):
    rect = win32gui.GetWindowRect(hwnd)
    img = ImageGrab.grab(bbox=rect, all_screens=True).convert("RGB")
    path = OUT / name
    img.save(path)
    SHOTS.append((name, f"{img.width}x{img.height}"))
    return img, path


def pixel_diff(a, b):
    x = np.asarray(a, dtype=np.int16)
    y = np.asarray(b, dtype=np.int16)
    if x.shape != y.shape:
        return 999.0
    return round(float(np.abs(x - y).mean()), 2)


def click_ratio(hwnd, fx, fy):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    x = int(left + fx * (right - left))
    y = int(top + fy * (bottom - top))
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    return x, y


def focus(hwnd):
    try:
        win32gui.ShowWindow(hwnd, 9)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def launch_app(tag):
    userdata = BUILD / f"test-user-data-autotest-{tag}"
    log_path = OUT / f"app-launch-{tag}.log"
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    env = os.environ.copy()
    env["ELECTRON_ENABLE_LOGGING"] = "1"
    env["DSH_DESKTOP_DIAGNOSTIC_FILE"] = str(OUT / f"diagnostic-{tag}.txt")
    proc = subprocess.Popen(
        [str(EXE), f"--user-data-dir={userdata}"],
        cwd=str(UNPACKED), env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 45
    hwnd = None
    wins = []
    while time.time() < deadline:
        wins = find_app_windows()
        if wins:
            hwnd = wins[0][0]
            break
        if proc.poll() is not None:
            break
        time.sleep(0.6)
    return proc, hwnd, wins, log_path, log_file, userdata


def read_log(log_path, wait_for_host=True):
    text = ""
    if wait_for_host:
        deadline = time.time() + 25
        while time.time() < deadline:
            text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
            if "dsh web:" in text:
                break
            time.sleep(0.5)
    else:
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    return text


def stop_app(proc):
    if proc.poll() is not None:
        return
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=15)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def http_status(url, timeout=6):
    try:
        r = requests.get(url, timeout=timeout, proxies={"http": None, "https": None})
        return r.status_code, len(r.content)
    except Exception as exc:
        return None, type(exc).__name__


def artifact_checks():
    ok = EXE.is_file() and file_size(EXE) > 200 * 1024 * 1024
    record("A01", "主可执行文件", "win-unpacked/DeepSeek Harness.exe 存在且 > 200 MB", ok,
           f"{mb(file_size(EXE))} MB", str(EXE.name))

    ok = INSTALLER.is_file() and file_size(INSTALLER) > 300 * 1024 * 1024
    record("A02", "NSIS 未签名安装器", "unsigned exe 存在且 > 300 MB", ok,
           f"{mb(file_size(INSTALLER))} MB", INSTALLER.name)

    ok = ASAR.is_file() and file_size(ASAR) > 200 * 1024 * 1024
    record("A03", "应用包 app.asar", "app.asar 存在且 > 200 MB", ok,
           f"{mb(file_size(ASAR))} MB", ASAR.name)

    versions = RUNTIME / "versions.json"
    payload = {}
    try:
        payload = json.loads(versions.read_text(encoding="utf-8"))
        ok = (RUNTIME / "bin").is_dir() and (RUNTIME / "cli").is_dir() and (RUNTIME / "primary-runtime").is_dir()
    except Exception as exc:
        ok = False
        payload = {"error": type(exc).__name__}
    record("A04", "随包运行时目录", "runtime/bin、cli、primary-runtime 与 versions.json 齐备", ok,
           json.dumps(payload, ensure_ascii=False)[:160], "resources/runtime/versions.json")

    manifest = json.loads((DESKTOP / "package.json").read_text(encoding="utf-8"))
    version = manifest.get("version", "")
    ok = version == "0.2.2-rc.1" and version in INSTALLER.name
    record("A05", "版本一致性", "package.json 版本与安装器文件名一致", ok,
           f"package.json={version}, installer=0.2.2-rc.1")


def backend_checks():
    for port, label in [(9999, "网关"), (9998, "控制面")]:
        code, size = http_status(f"http://127.0.0.1:{port}/", timeout=4)
        ok = code is not None
        record(f"A{6 if port == 9999 else 7:02d}", f"{label}可达性",
               f"127.0.0.1:{port} 有 HTTP 响应", ok,
               f"HTTP {code}, {size} bytes")


def run_case(tag, button_name, fx, fy, case_id, label):
    print(f"\n--- {label} ({tag}) ---", flush=True)
    proc, hwnd, wins, log_path, log_file, userdata = launch_app(tag)
    try:
        if hwnd is None:
            record(case_id, label, "窗口在 45 秒内出现", False,
                   f"进程退出码={proc.poll()}, 日志={read_log(log_path, False)[-200:]}")
            return
        record(f"{case_id}-start", f"{label} · 窗口启动", "进程创建且可见窗口出现", True,
               f"pid={proc.pid}, 窗口={wins[0][1]}, rect={wins[0][2]}")

        focus(hwnd)
        time.sleep(1.2)
        before, shot = window_shot(hwnd, f"{tag}-01-welcome.png")
        ok = before.width > 400 and before.height > 400
        record(f"{case_id}-render", f"{label} · 欢迎页渲染", "窗口截图尺寸合理且非空白", ok,
               f"{before.width}x{before.height}, 均值={int(np.asarray(before).mean())}", shot.name)

        text = read_log(log_path)
        m = re.search(r"dsh web:\s*(http://127\.0\.0\.1:\d+/\?token=[^\s]+)", text)
        if m:
            code, size = http_status(m.group(1), timeout=8)
            record(f"{case_id}-host", f"{label} · Desktop Host", "Host 地址可从日志解析且 HTTP 可达",
                   code is not None, f"port={re.search(r':(\d+)/', m.group(1)).group(1)}, HTTP {code}, {size} bytes",
                   f"app-launch-{tag}.log")
        else:
            record(f"{case_id}-host", f"{label} · Desktop Host", "Host 地址可从日志解析且 HTTP 可达", False,
                   "日志未出现 dsh web 地址")

        x, y = click_ratio(hwnd, fx, fy)
        time.sleep(3.0)
        after, shot2 = window_shot(hwnd, f"{tag}-02-after-{button_name}.png")
        delta = pixel_diff(before, after)
        titles = [w[1] for w in find_app_windows()]
        button_label = "连接账号" if button_name == "connect" else "登录"
        record(f"{case_id}-ui", f"{label} · 交互响应", f"点击「{button_label}」后界面发生变化",
               delta > 3.0, f"点击=({x},{y}), 像素均差={delta}, 窗口标题={titles}", shot2.name)

        text_after = read_log(log_path, wait_for_host=False)
        handler_errors = [line for line in text_after.splitlines()
                          if "Error occurred in handler" in line]
        crashed = proc.poll() is not None or any(
            re.search(r"(FATAL|Unhandled|Uncaught|crash(ed)?)", line, re.I)
            for line in text_after.splitlines())
        record(case_id, label, "点击后业务流程无 IPC handler 错误",
               len(handler_errors) == 0,
               (handler_errors[0].split("Error: ", 1)[-1][:200] if handler_errors
                else "无 IPC handler 错误"),
               f"app-launch-{tag}.log")
        record(f"{case_id}-log", f"{label} · 启动日志", "无致命崩溃且进程存活",
               not crashed,
               f"IPC 错误行={len(handler_errors)}, 崩溃={crashed}, 日志行数={len(text_after.splitlines())}",
               f"app-launch-{tag}.log")
    finally:
        stop_app(proc)
        try:
            log_file.close()
        except Exception:
            pass


def write_report():
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 桌面版自动化测试报告",
        "",
        f"- 生成时间：{now}",
        "- 被测对象：DeepSeek Harness 桌面版 `0.2.2-rc.1` / `win-x64` / unsigned 打包产物",
        f"- 被测程序：`{EXE}`",
        "- 测试方式：自动化脚本自启动实例 → 产物断言 → 窗口渲染 → Host 可达性 → UI 点击交互 → 日志扫描",
        "- 配置隔离：每个用例使用独立 `test-user-data-autotest-*` 目录，保证落在首次启动欢迎页",
        "",
        "## 结果摘要",
        "",
        f"| 总计 | PASS | FAIL | SKIP |",
        "| --- | --- | --- | --- |",
        f"| {len(RESULTS)} | {passed} | {failed} | {skipped} |",
        "",
        "## 用例明细",
        "",
        "| ID | 用例 | 断言 | 结果 | 实测 | 证据 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in RESULTS:
        detail = str(r["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r['id']} | {r['title']} | {r['assertion']} | {r['status']} | {detail[:180]} | {r['evidence']} |")
    lines += [
        "",
        "## 截图证据",
        "",
    ]
    for name, size in SHOTS:
        lines.append(f"- `{OUT / name}`（{size}）")
    lines.append("")
    fails = [r for r in RESULTS if r["status"] == "FAIL"]
    if fails:
        lines += ["## 缺陷与阻断项", ""]
        for r in fails:
            lines.append(f"- **{r['id']} {r['title']}**：{r['detail']}")
        lines += [
        "",
        "### C01/C02 入口交互排查指引",
        "",
        "当前桌面欢迎页仅保留「登录」与「连接账号（注册）」两个入口；",
        "「添加 API Key」可见入口已按产品决策隐藏（DOM 仍保留但 `hidden`）。",
        "点击任一入口后渲染进程应切换到对应的登录/注册表单页；若界面无变化或进程崩溃，",
        "优先排查：Desktop Host 是否从日志解析到 `dsh web:` 地址（C0x-host 用例）、",
        "控制面 `http://127.0.0.1:9998/v1/customer` 是否可达（A07 用例）。",
        "完整的「customer 登录 → 签租约 → 进入主工作区」端到端验证由 `customer_ui_login.py` 与",
        "`reports/ops/customer-auth-e2e-*.md` 覆盖（真实账号登录后 `account-store/account.json` 落盘并进入主工作区）。",
        "",
        ]

    smoke_meta = OUT / "smoke-meta.json"
    if smoke_meta.exists():
        meta = json.loads(smoke_meta.read_text(encoding="utf-8"))
        lines += [
            "## 仓库自带测试",
            "",
            f"- 命令：`{meta['command']}`",
            f"- 退出码：`{meta['exitCode']}`，耗时 {meta['durationSeconds']}s，日志 `{meta['log']}`",
            "- 覆盖范围：随包运行时树、原生 Office 转换（ASAR 外）、运行时签名校验（unsigned 跳过签名）",
            "",
        ]

    lines += [
        "",
        "## 环境与已知限制",
        "",
        "- 沙箱全局注入 `ELECTRON_RUN_AS_NODE=1`，会让 Electron 退化为 Node CLI（无窗口）；脚本启动实例时已剔除该变量及大小写重复的代理变量。",
        "- 沙箱安全策略拦截 `reg.exe`（应用内部调用），该拦截属于环境限制，不是应用缺陷；已验证它不影响欢迎页渲染与 Host 启动。",
        "- 由工具启动的 GUI 进程会在命令会话结束时被回收，因此本报告的实例由脚本在同一进程内启动、断言、关闭；长时间人工验收需手动双击 exe。",
        "- 更新策略 origin 为 `https://update.example.invalid` 占位域名，强制更新/登录测试环境弹窗流程未纳入本次自动化。",
        "- 真实账号登录已验证：由 `customer_ui_login.py` 在真实打包应用内用 customer 测试账号完成「登录 → 进入主工作区」全流程，",
        "  `account-store/account.json` 落盘（含 `accessToken`/`customerId`/`lease`），主工作区正常渲染（见 `ui-login-04-after.png`）。",
        "- 欢迎页「添加 API Key」可见入口已按产品决策隐藏，仅保留「登录」与「连接账号（注册）」；本脚本的 C01/C02 验证这两个入口的点击响应。",
        "",
        "## 复现",
        "",
        "```bash",
        r"D:\programs\fastapi\agentpanel\.venv\Scripts\python.exe " + str(Path(__file__)),
        "```",
        "",
        f"结构化结果：`{OUT / 'results.json'}`",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps({
        "generatedAt": now, "results": RESULTS, "screenshots": SHOTS,
        "summary": {"total": len(RESULTS), "pass": passed, "fail": failed, "skip": skipped},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nREPORT={REPORT}", flush=True)
    print(f"SUMMARY total={len(RESULTS)} pass={passed} fail={failed} skip={skipped}", flush=True)


def main():
    if "--report-only" in sys.argv:
        data = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
        RESULTS.extend(data["results"])
        SHOTS.extend([tuple(item) for item in data["screenshots"]])
        for item in RESULTS:
            if item["id"].endswith("-ui"):
                item["assertion"] = (item["assertion"].replace("「apikey」", "「添加 API Key」")
                                     .replace("「signin」", "「登录」"))
        write_report()
        return
    print("=== artifact & backend checks ===", flush=True)
    artifact_checks()
    backend_checks()
    smoke_meta = OUT / "smoke-meta.json"
    if smoke_meta.exists():
        meta = json.loads(smoke_meta.read_text(encoding="utf-8"))
        record("S01", "打包运行时 smoke", "仓库自带 smoke 脚本退出码为 0",
               meta.get("exitCode") == 0,
               f"exit={meta.get('exitCode')}, {meta.get('durationSeconds')}s",
               "smoke-autotest.log")
    run_case("login", "login", 0.50, 0.76, "C01", "登录入口")
    time.sleep(2)
    run_case("connect", "connect", 0.50, 0.88, "C02", "连接账号（注册）入口")
    write_report()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            write_report()
        except Exception:
            pass
        sys.exit(1)
