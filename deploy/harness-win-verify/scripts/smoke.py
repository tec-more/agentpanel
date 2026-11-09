"""Windows 侧 DeepSeek Harness 下载产物验证（离线 / 假 provider / 占位 key）。

边界：
- 不读取项目 config.conf、secrets、.env，不使用任何真实凭据；
- 假 provider 只监听 127.0.0.1 高位端口，模型请求不会发往真实 provider；
- 不执行 bash / 文件越界 / 公网抓取 / 原生审批等危险用例（Windows 无 --network none 等价隔离）；
- 会话只要求模型返回固定文本，不触发任何工具调用。
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ROOT / "wheels"
PKG = ROOT / "pkg"
STATE = ROOT / "state"
OUT = ROOT / "out"
DSH_HOME = STATE / "dsh_home"
WORKSPACE = STATE / "workspace"

SDK_WHEEL = WHEELS / "deepseek_harness_sdk-0.1.5rc1-py3-none-any.whl"
RT_WHEEL = WHEELS / "deepseek_harness_runtime_bin-0.1.5rc1-py3-none-win_amd64.whl"
EXPECTED_HASHES = {
    SDK_WHEEL.name: "8d9897e97e8a95fd738cb2c3e2c563951d824e43847ec6f3b0fb172c0729b4d8",
    RT_WHEEL.name: "d031a5ab4919c572fd7e48c7ef19ec8b1896e93d93c44b0937bb958c528f8acf",
}
EXE_REL = "deepseek_harness_runtime/runtime/deepseek-harness-sdk-runtime-win-x64.exe"
RG_REL = "deepseek_harness_runtime/runtime/deepseek-harness-sdk-runtime-win-x64-rg.exe"

PORT = int(os.environ.get("WIN_VERIFY_PORT", "18081"))
PLACEHOLDER_KEY = "sk-agentpanel-verify-placeholder"
EXPECTED_TEXT = "WIN_SMOKE_OK"
PROVIDER_REQUESTS: list[dict] = []
REQUEST_LOCK = threading.Lock()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe(value, limit: int = 2000):
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "...(truncated)"


def prepare() -> dict:
    for path in (DSH_HOME, WORKSPACE, OUT):
        path.mkdir(parents=True, exist_ok=True)
    checks = []
    for wheel in (SDK_WHEEL, RT_WHEEL):
        digest = sha256(wheel) if wheel.exists() else ""
        checks.append({
            "file": wheel.name,
            "exists": wheel.exists(),
            "size": wheel.stat().st_size if wheel.exists() else 0,
            "sha256": digest,
            "sha256_expected": EXPECTED_HASHES[wheel.name],
            "match": digest == EXPECTED_HASHES[wheel.name],
        })
    if not all(c["match"] for c in checks):
        return {"checks": checks, "ok": False, "reason": "wheel missing or checksum mismatch"}

    marker = PKG / ".extracted"
    if not marker.exists():
        with zipfile.ZipFile(RT_WHEEL) as zf:
            zf.extractall(PKG)
        with zipfile.ZipFile(SDK_WHEEL) as zf:
            zf.extractall(PKG)
        marker.write_text("extracted from pinned wheels\n", encoding="utf-8")

    exe = PKG / EXE_REL
    rg = PKG / RG_REL
    with zipfile.ZipFile(RT_WHEEL) as zf:
        inner_hashes = {
            name: hashlib.sha256(zf.read(name)).hexdigest()
            for name in (EXE_REL, RG_REL)
        }
    local_hashes = {"exe": sha256(exe), "rg": sha256(rg)}
    return {
        "checks": checks,
        "ok": exe.exists() and rg.exists() and local_hashes["exe"] == inner_hashes[EXE_REL],
        "exe": str(exe),
        "exe_size": exe.stat().st_size if exe.exists() else 0,
        "exe_sha256": local_hashes["exe"],
        "rg_sha256": local_hashes["rg"],
        "runtime_from": "downloaded wheel (not the preinstalled .venv copy)",
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def handle(self):
        # dsh 在收完响应后可能直接关闭 keep-alive 连接；服务端读下一个请求时会收到 RST。
        # 这是 HTTP 长连接的正常收尾噪音，不应污染验证输出。
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._send(200, b'{"ok":true}', "application/json")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}
        # 不记录 Authorization 或任何请求头凭据
        with REQUEST_LOCK:
            PROVIDER_REQUESTS.append({
                "path": self.path,
                "stream": bool(body.get("stream")),
                "model": body.get("model"),
                "message_count": len(body.get("messages") or []),
                "tool_count": len(body.get("tools") or []),
            })
        created = int(time.time())
        base = {"id": "chatcmpl-agentpanel-win-verify", "model": "deepseek-v4-flash", "created": created}
        if body.get("stream"):
            chunks = [
                {**base, "object": "chat.completion.chunk", "choices": [
                    {"index": 0, "delta": {"role": "assistant", "content": EXPECTED_TEXT}, "finish_reason": None}]},
                {**base, "object": "chat.completion.chunk", "choices": [
                    {"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ]
            payload = b"".join(
                f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode("utf-8") for c in chunks
            ) + b"data: [DONE]\n\n"
            self._send(200, payload, "text/event-stream")
        else:
            payload = {**base, "object": "chat.completion", "choices": [
                {"index": 0, "message": {"role": "assistant", "content": EXPECTED_TEXT},
                 "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")


def cli_checks(exe: Path) -> list[dict]:
    env = os.environ.copy()
    env["DSH_HOME"] = str(DSH_HOME.resolve())
    env["DSH_TELEMETRY_MODE"] = "DISABLED"
    results = []
    commands = [
        ("installed_dsh_cli", [str(Path(sys.executable).parent / "dsh.exe"), "--version"]),
        ("downloaded_standalone_exe", [str(exe), "--version"]),
    ]
    for label, cmd in commands:
        entry = {"name": label, "cmd": cmd[0], "args": cmd[1:]}
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                                  timeout=90, encoding="utf-8", errors="replace")
            entry.update({
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "").strip()[:800],
                "stderr": (proc.stderr or "").strip()[:800],
                "launched": True,
            })
        except subprocess.TimeoutExpired:
            entry.update({"launched": True, "returncode": None, "timeout": True,
                          "stdout": "", "stderr": "timed out after 90s"})
        except Exception as exc:
            entry.update({"launched": False, "error": f"{type(exc).__name__}: {exc}"})
        results.append(entry)
    return results


def session_check(exe: Path) -> dict:
    from deepseek_harness.api import final_response, finish_reason
    from deepseek_harness.client import HarnessClient, HarnessConfig

    result: dict = {"scenario": "text_only_smoke", "dangerous_scenarios_executed": []}
    session_id = f"win-smoke-{uuid.uuid4().hex[:8]}"
    cfg = HarnessConfig(
        dsh_bin=str(exe),
        profile="sdk",
        dsh_home=str(DSH_HOME.resolve()),
        cwd=str(WORKSPACE.resolve()),
        env={
            "DEEPSEEK_API_KEY": PLACEHOLDER_KEY,
            "DEEPSEEK_BASE_URL": f"http://127.0.0.1:{PORT}/v1",
            "DSH_TELEMETRY_MODE": "DISABLED",
        },
        initialize_timeout_seconds=60.0,
        request_timeout_seconds=90.0,
    )
    client = HarnessClient(cfg)
    notes, events, errors = [], [], []
    stop = threading.Event()

    try:
        client.start()
        init = client.initialize(cwd=str(WORKSPACE.resolve()),
                                 provider="deepseek-official", model="deepseek-v4-flash")
        result["initialized"] = True
        result["initialize"] = safe(init)

        with client.subscribe_session_notifications(session_id) as sub:
            out_queue: queue.Queue = queue.Queue()

            def reader():
                while not stop.is_set():
                    try:
                        out_queue.put(("notification", sub.next()))
                    except BaseException as exc:
                        out_queue.put(("error", str(exc)))
                        return

            threading.Thread(target=reader, daemon=True).start()
            message_id = client.session_prompt(
                session_id,
                [{"type": "text", "text":
                  "SMOKE: reply with the exact token WIN_SMOKE_OK and do not call any tool."}],
                notification_subscription=sub,
            )
            result["message_id"] = message_id
            deadline = time.time() + 90.0
            while time.time() < deadline:
                try:
                    kind, item = out_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                if kind == "error":
                    errors.append(item)
                    break
                note = {"method": item.method, "payload": safe(item.payload)}
                notes.append(note)
                if item.method == "session.event":
                    payload = item.payload if isinstance(item.payload, dict) else {}
                    event = payload.get("event")
                    if isinstance(event, dict):
                        events.append(event)
                if (item.method == "session.status"
                        and isinstance(item.payload, dict)
                        and item.payload.get("sessionId") == session_id
                        and item.payload.get("status") == "idle"):
                    result["reached_idle"] = True
                    break
            else:
                errors.append("session did not reach idle within 90s")
        stop.set()
        result["final_response"] = final_response(events)
        result["finish_reason"] = finish_reason(events)
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        result["initialized"] = False
    finally:
        stop.set()
        try:
            client.close()
        except Exception as exc:
            errors.append(f"close failed: {type(exc).__name__}: {exc}")

    result.update({
        "session_id": session_id,
        "event_count": len(events),
        "notification_count": len(notes),
        "notes": notes,
        "errors": errors,
        "text_matches": EXPECTED_TEXT in str(result.get("final_response") or ""),
    })
    result["pass"] = bool(
        result.get("initialized") and result.get("reached_idle")
        and result["text_matches"] and not errors
    )
    return result


def main() -> int:
    for path in (DSH_HOME, WORKSPACE, OUT):
        path.mkdir(parents=True, exist_ok=True)

    download = prepare()
    report: dict = {
        "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "download": download,
        "safety": {
            "placeholder_key_used": True,
            "real_provider_called": False,
            "provider_base_url": f"http://127.0.0.1:{PORT}/v1",
            "network_isolation": "none (Windows host has no --network none equivalent)",
            "dangerous_scenarios_executed": [],
        },
    }
    if not download.get("ok"):
        report["verdict"] = "FAIL"
        report["reason"] = download.get("reason", "download prepare failed")
        (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    exe = Path(download["exe"])
    report["cli"] = cli_checks(exe)

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[smoke] fake provider on 127.0.0.1:{PORT}", flush=True)
    try:
        report["session"] = session_check(exe)
    finally:
        server.shutdown()
        server.server_close()

    report["provider_requests"] = PROVIDER_REQUESTS
    report["provider_request_count"] = len(PROVIDER_REQUESTS)
    (OUT / "fake_provider_requests.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in PROVIDER_REQUESTS),
        encoding="utf-8",
    )
    cli_ok = all(c.get("launched") and c.get("returncode") == 0 for c in report["cli"])
    report["verdict"] = "PASS" if (
        cli_ok and report["session"]["pass"] and report["provider_request_count"] >= 1
    ) else "FAIL"
    (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "verdict": report["verdict"],
        "cli": [{k: c.get(k) for k in ("name", "launched", "returncode", "stdout", "stderr")}
                for c in report["cli"]],
        "session": {k: v for k, v in report["session"].items() if k != "notes"},
        "provider_request_count": report["provider_request_count"],
    }, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
