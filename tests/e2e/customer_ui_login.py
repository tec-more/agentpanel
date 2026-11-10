# -*- coding: utf-8 -*-
"""在真实 Windows 打包应用里用 customer 测试账号登录，验证进入工作区。

依赖：win32gui / win32api / win32clipboard / Pillow。
所有 GUI 操作在单个进程内完成（沙箱会回收跨命令存活的窗口进程）。
用法： <项目>.venv/Scripts/python.exe customer_ui_login.py
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import win32api  # noqa: E402
import win32clipboard  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402
import argparse  # noqa: E402

# --keep-open：测试结束后保留应用窗口，便于人工观察
# --slow：放慢每一步节奏，便于跟随流程
_args = argparse.ArgumentParser()
_args.add_argument("--keep-open", action="store_true",
                   help="测试结束后不关闭应用，便于人工观察界面")
_args.add_argument("--slow", action="store_true",
                   help="放慢每一步节奏，便于跟随流程")
_ARGS, _ = _args.parse_known_args()
KEEP_OPEN = _ARGS.keep_open
SLOW = _ARGS.slow

BUILD = Path(r"D:\programs\fastapi\agentpanel\dshw\apps\desktop\.desktop-build")
UNPACKED = BUILD / "targets/win-x64/unsigned-artifacts/win-unpacked"
EXE = UNPACKED / "DeepSeek Harness.exe"
USER_DATA = BUILD / "test-user-data-e2e-login"
STORE = USER_DATA / "account-store"
RESULTS_JSON = BUILD / "autotest/customer_e2e_results.json"

meta = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
EMAIL = meta["context"]["test_email"]
PASSWORD = "E2eTest@123456"

for _k in ("ELECTRON_RUN_AS_NODE", "NODE_OPTIONS", "NODE_EXTRA_CA_CERTS",
           "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
    os.environ.pop(_k, None)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

USER_DATA.mkdir(parents=True, exist_ok=True)
STORE.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env["ELECTRON_ENABLE_LOGGING"] = "1"
env["AGENTPANEL_CUSTOMER_URL"] = "http://127.0.0.1:9998/v1/customer"
env["AGENTPANEL_GATEWAY_URL"] = "http://127.0.0.1:9999"
env["AGENTPANEL_ACCOUNT_STORE_DIR"] = str(STORE)
# 关键：Electron 主进程的全局 fetch 走 Chromium 网络栈，会读系统代理；
# 沙箱给系统设了 127.0.0.1 代理，可能把 localhost Host 连接重置（ECONNRESET）。
# 显式让本次会话直连，并把回环地址加入 NO_PROXY 兜底。
env["NO_PROXY"] = "127.0.0.1,localhost,::1"
env["no_proxy"] = "127.0.0.1,localhost,::1"

log_path = BUILD / "customer-ui-login.log"
log = open(log_path, "w", encoding="utf-8", errors="replace")
proc = subprocess.Popen([str(EXE), f"--user-data-dir={USER_DATA}"],
                        cwd=str(UNPACKED), env=env, stdout=log, stderr=subprocess.STDOUT)


def app_windows():
    out = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            title = win32gui.GetWindowText(h)
            if "harness" in title.lower() or "deepseek" in title.lower():
                out.append((h, title, win32gui.GetWindowRect(h)))
    win32gui.EnumWindows(cb, None)
    return out


def wait_window(timeout=55):
    end = time.time() + timeout
    while time.time() < end:
        w = app_windows()
        if w:
            return w[0][0]
        if proc.poll() is not None:
            return None
        time.sleep(0.6)
    return None


def focus(hwnd):
    SWP = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, SWP)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.6)


def click(hwnd, fx, fy):
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    x, y = int(l + fx * (r - l)), int(t + fy * (b - t))
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    print(f"CLICK ratio=({fx},{fy}) -> ({x},{y})", flush=True)
    time.sleep(3.0 if SLOW else 1.0)


def set_clipboard(text):
    for _ in range(5):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            win32clipboard.CloseClipboard()
            return
        except Exception:
            time.sleep(0.2)


def key_down(vk):
    win32api.keybd_event(vk, 0, 0, 0)


def key_up(vk):
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


def paste(text):
    set_clipboard(text)
    key_down(win32con.VK_CONTROL)
    key_down(ord("V"))
    key_up(ord("V"))
    key_up(win32con.VK_CONTROL)
    time.sleep(0.5)


def tab():
    key_down(win32con.VK_TAB)
    key_up(win32con.VK_TAB)
    time.sleep(0.4)


def shot(name, hwnd=None, full=False):
    bbox = None if full else win32gui.GetWindowRect(hwnd)
    img = ImageGrab.grab(bbox=bbox, all_screens=True).convert("RGB")
    p = BUILD / name
    img.save(p)
    print("SHOT", p.name, img.size, flush=True)


hwnd = wait_window()
if hwnd is None:
    print("NO_WINDOW proc_exit=", proc.poll())
    print(log_path.read_text(encoding="utf-8", errors="replace")[-1200:])
    sys.exit(1)

focus(hwnd)
before = app_windows()
print("WINDOWS_BEFORE", [(t, r) for _, t, r in before], flush=True)
shot("ui-login-01-entry.png", hwnd)

click(hwnd, 0.528, 0.757)       # 欢迎页「登录」
focus(hwnd)
shot("ui-login-02-form.png", hwnd)

click(hwnd, 0.50, 0.412)        # 邮箱输入框（进入页面时已自动聚焦，点击确保）
paste(EMAIL)
tab()
paste(PASSWORD)
shot("ui-login-03-filled.png", hwnd)

click(hwnd, 0.50, 0.762)        # 「登录」提交
print("SUBMITTED, waiting for workspace...", flush=True)
time.sleep(20 if SLOW else 10)

after = app_windows()
print("WINDOWS_AFTER", [(t, r) for _, t, r in after], flush=True)
shot("ui-login-04-after.png", full=True)

# 打开左下角账号菜单，验证登录状态是否显示（登录成功应显示已登录身份而非「登录」项）
try:
    click(hwnd, 0.033, 0.955)   # 工作区侧边栏底部「更多」（账号菜单）
    time.sleep(2 if SLOW else 1)
    shot("ui-login-05-account-menu.png", full=True)
    click(hwnd, 0.5, 0.5)       # 点空白处收起菜单
    time.sleep(1)
except Exception as e:
    print("MENU_STEP_SKIPPED", type(e).__name__, str(e)[:120], flush=True)

account_file = STORE / "account.json"
account_info = "NOT_CREATED"
if account_file.exists():
    try:
        data = json.loads(account_file.read_text(encoding="utf-8"))
        keys = sorted(data.keys()) if isinstance(data, dict) else []
        vkey = str(data.get("virtualKey") or data.get("virtual_key") or "")
        account_info = f"keys={keys}, virtual_key_prefix={vkey[:4]}, bytes={account_file.stat().st_size}"
    except Exception as e:
        account_info = f"UNREADABLE {type(e).__name__}"
print("ACCOUNT_STORE", account_info, flush=True)

log.flush()
text = log_path.read_text(encoding="utf-8", errors="replace")
fatal = [l for l in text.splitlines()
         if any(k in l.lower() for k in ("fatal", "uncaught", "unhandled", "crash"))]
print("LOG_LINES", len(text.splitlines()), "FATAL", len(fatal), flush=True)
print("LOG_TAIL", text[-600:].replace("\n", " | "), flush=True)

(BUILD / "autotest/customer_ui_login_result.json").write_text(json.dumps({
    "email": EMAIL,
    "windows_before": [{"title": t, "rect": list(r)} for _, t, r in before],
    "windows_after": [{"title": t, "rect": list(r)} for _, t, r in after],
    "account_store": account_info,
    "fatal_log_lines": len(fatal),
}, ensure_ascii=False, indent=2), encoding="utf-8")

if KEEP_OPEN:
    print("KEEP_OPEN: 应用保持打开。你可自由观察登录后的主工作区；"
          "关闭窗口后脚本自动结束。", flush=True)
    try:
        proc.wait()
    except Exception:
        pass
    print("APP_CLOSED_BY_USER", flush=True)
else:
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=15)
        print("STOPPED", flush=True)
    except Exception as e:
        print("STOP_WARN", e, flush=True)
