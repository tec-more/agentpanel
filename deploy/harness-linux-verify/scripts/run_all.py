"""在 Linux 容器内驱动 dsh，验证四项 Windows 上无法验证的行为。

四项：
1. hooks -> tools/pre-execute 是否在进程内真正拦截；
2. workspace 越界写（fs 工具 + bash）是否被阻断；
3. dsh 实际出网行为（配合 --network none 与 --add-host）；
4. 原生审批通道 session/request_permission 是否下发且放行后执行。

不调用真实 provider：DEEPSEEK_BASE_URL 指向本机假 provider，key 为占位值。
"""
from __future__ import annotations

import json
import os
import platform
import queue
import shutil
import sys
import threading
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional

VERIFY_DIR = "/opt/verify"
WORKDIR = os.environ.get("VERIFY_WORKDIR", "/work/ws")
OUTDIR = os.environ.get("VERIFY_OUTDIR", "/out")
PATCH = os.path.join(VERIFY_DIR, "config", "verify.patch.yml")
PORT = int(os.environ.get("FAKE_PROVIDER_PORT", "18080"))
PLACEHOLDER_KEY = "sk-agentpanel-verify-placeholder"

MARKERS = {
    "hook_deny": ["/work/should_not_exist_hook.txt"],
    "bash_escape": ["/work/agentpanel_escape_bash.txt"],
    "fs_escape": ["/work/agentpanel_escape_fs.txt", "/work/agentpanel_escape_fs_rel.txt"],
    "approval_allow": ["/work/agentpanel_approval_executed.txt"],
}

SCENARIOS = [
    s.strip()
    for s in os.environ.get(
        "VERIFY_SCENARIOS",
        "hook_deny,bash_escape,fs_escape,approval_allow,egress_ok,egress_deny",
    ).split(",")
    if s.strip()
]

incoming_requests: List[Dict[str, Any]] = []
incoming_lock = threading.Lock()
current_scenario = {"name": None}
all_notifications: List[Dict[str, Any]] = []


def _log(msg: str) -> None:
    print(f"[verify] {msg}", flush=True)


def _write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _cleanup_markers() -> None:
    for paths in MARKERS.values():
        for path in paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


def _request_worker(client: Any, stop: threading.Event) -> None:
    """处理 dsh 主动发给客户端的 JSON-RPC request（审批通道等）。"""
    while not stop.is_set():
        try:
            request = client.next_request()
        except BaseException:
            return
        payload = request.payload if isinstance(request.payload, dict) else {}
        record = {
            "scenario": current_scenario["name"],
            "method": request.method,
            "request_id": request.id,
            "payload": payload,
            "at": time.time(),
        }
        with incoming_lock:
            incoming_requests.append(record)
        _log(f"incoming request method={request.method} id={request.id}")

        if request.method == "session/request_permission":
            options = payload.get("options") if isinstance(payload.get("options"), list) else []
            chosen = None
            for option in options:
                if not isinstance(option, dict):
                    continue
                if option.get("kind") in ("allow_once", "allow_always"):
                    chosen = option
                    break
            if chosen is None and options:
                chosen = options[0] if isinstance(options[0], dict) else None
            if chosen and chosen.get("optionId"):
                record["decision"] = {"outcome": "selected", "optionId": chosen.get("optionId")}
                client.respond(request.id, {
                    "outcome": {"outcome": "selected", "optionId": chosen.get("optionId")}
                })
                record["decision"] = "allow"
            else:
                client.respond(request.id, {"outcome": {"outcome": "cancelled"}})
                record["decision"] = "cancel-no-options"
        else:
            try:
                client.respond_error(request.id, code=-32601, message=f"unsupported in verify: {request.method}")
            except Exception:
                pass


def _notification_reader(subscription: Any, out_queue: queue.Queue, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            notification = subscription.next()
        except BaseException as exc:
            out_queue.put(("error", str(exc)))
            return
        out_queue.put(("notification", notification))


def _event_of(notification: Any) -> Optional[Dict[str, Any]]:
    if getattr(notification, "method", None) != "session.event":
        return None
    payload = notification.payload if isinstance(notification.payload, dict) else {}
    event = payload.get("event")
    return event if isinstance(event, dict) else None


def _run_scenario(client: Any, scenario: str, timeout: float = 90.0) -> Dict[str, Any]:
    _cleanup_markers()
    current_scenario["name"] = scenario
    session_id = f"verify-{scenario}-{uuid.uuid4().hex[:8]}"
    events: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []

    with client.subscribe_session_notifications(session_id) as subscription:
        out_queue: queue.Queue = queue.Queue()
        stop = threading.Event()
        reader = threading.Thread(
            target=_notification_reader, args=(subscription, out_queue, stop), daemon=True
        )
        reader.start()
        message_id = client.session_prompt(
            session_id,
            [{"type": "text", "text": f"SCENARIO:{scenario}"}],
            notification_subscription=subscription,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                kind, item = out_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            if kind == "error":
                notes.append({"method": "reader_error", "payload": {"error": item}})
                break
            notification = item
            note = {"method": notification.method, "payload": notification.payload}
            notes.append(note)
            all_notifications.append(note)
            event = _event_of(notification)
            if event is not None:
                events.append(event)
            if (
                notification.method == "session.status"
                and notification.payload.get("sessionId") == session_id
                and notification.payload.get("status") == "idle"
            ):
                break
        else:
            notes.append({"method": "verify_timeout", "payload": {"scenario": scenario}})
        stop.set()

    markers = {path: os.path.exists(path) for path in MARKERS.get(scenario, [])}
    with incoming_lock:
        requests_for_scenario = [r for r in incoming_requests if r.get("scenario") == scenario]

    return {
        "scenario": scenario,
        "session_id": session_id,
        "message_id": message_id,
        "events": events,
        "notifications": notes,
        "markers": markers,
        "incoming_requests": requests_for_scenario,
    }


def _event_types(result: Dict[str, Any]) -> List[str]:
    return [str(e.get("type")) for e in result["events"] if isinstance(e, dict)]


def _event_data(result: Dict[str, Any], event_type: str) -> List[Any]:
    return [e.get("data") for e in result["events"] if isinstance(e, dict) and e.get("type") == event_type]


def _provider_log() -> List[Dict[str, Any]]:
    path = os.path.join(OUTDIR, "fake_provider_requests.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def _hook_log() -> List[Dict[str, Any]]:
    path = os.path.join(WORKDIR, ".agentpanel_hook_calls.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def _is_error_event(event: Any) -> bool:
    if not isinstance(event, dict):
        return False
    blob = json.dumps(event, ensure_ascii=False).lower()
    return any(word in blob for word in ("error", "denied", "blocked", "failed", "forbidden"))


def _error_evidence(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """只保留工具结果级错误，避免把系统提示词塞进结论文件。"""
    rows = []
    for event in result.get("events", []):
        if not isinstance(event, dict) or event.get("type") not in ("tool/result", "hook/result"):
            continue
        if not _is_error_event(event):
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        message = data.get("message") if isinstance(data.get("message"), dict) else {}
        text = ""
        for block in message.get("content") or []:
            if isinstance(block, dict):
                for item in block.get("content") or []:
                    if isinstance(item, dict) and item.get("text"):
                        text = str(item.get("text"))[:500]
        rows.append({
            "type": event.get("type"),
            "error_name": (data.get("error") or {}).get("name") if isinstance(data.get("error"), dict) else None,
            "error_code": (data.get("error") or {}).get("code") if isinstance(data.get("error"), dict) else None,
            "text": text,
        })
    return rows


def _summarize(raw: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    hooks = _hook_log()
    provider = _provider_log()
    verdicts: Dict[str, Any] = {}

    if "egress_public_ok" in raw or "egress_public_deny" in raw:
        import re

        def statuses(result: Dict[str, Any]) -> List[int]:
            codes: List[int] = []
            for event in result.get("events", []):
                if not isinstance(event, dict) or event.get("type") != "tool/result":
                    continue
                message = (event.get("data") or {}).get("message") or {}
                for block in message.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    for item in block.get("content") or []:
                        text = str((item or {}).get("text") or "")
                        for match in re.findall(r"HTTP (\d{3})", text):
                            codes.append(int(match))
            return codes

        ok = raw.get("egress_public_ok", {})
        deny = raw.get("egress_public_deny", {})
        ok_codes = statuses(ok) if ok else []
        deny_codes = statuses(deny) if deny else []
        allowlisted_reachable = bool(ok_codes)
        # 任意公网域名被成功抓取（HTTP 200）即证明 dsh 自身没有域名白名单
        arbitrary_public_reachable = 200 in deny_codes
        return {
            "3b_dsh_web_fetch_domain_policy": {
                "pass": bool(allowlisted_reachable and not arbitrary_public_reachable),
                "evidence": {
                    "allowlisted_http_status": ok_codes,
                    "non_allowlisted_http_status": deny_codes,
                    "allowlisted_reachable": allowlisted_reachable,
                    "arbitrary_public_reachable": arbitrary_public_reachable,
                    "conclusion": (
                        "dsh web_fetch 未内置 provider 域名白名单：联网时 example.com 也可达；"
                        "出网白名单必须由业务网关执行，dsh 自身只做私网 SSRF 防护。"
                        if arbitrary_public_reachable else
                        "dsh web_fetch 在联网条件下仍拒绝非白名单域名，需进一步确认拦截来源。"
                    ),
                },
            }
        }

    # 1. hooks -> pre-execute 进程内拦截
    hook_result = raw["hook_deny"]
    hook_types = _event_types(hook_result)
    hook_result_data = _event_data(hook_result, "hook/result")
    hook_denied = any(
        isinstance(item, dict) and item.get("decision") == "deny" for item in hook_result_data
    )
    hook_ok = bool(
        "hook/invoked" in hook_types
        and hook_denied
        and not hook_result["markers"]["/work/should_not_exist_hook.txt"]
    )
    verdicts["1_pre_execute_hook"] = {
        "pass": hook_ok,
        "evidence": {
            "hook_subprocess_calls": len(hooks),
            "hook_event_types": [t for t in hook_types if t.startswith("hook/")],
            "hook_result": hook_result_data,
            "target_exists": hook_result["markers"]["/work/should_not_exist_hook.txt"],
            "tool_errors": _error_evidence(hook_result),
        },
    }

    # 2. workspace 越界写
    bash_escape = raw["bash_escape"]
    fs_escape = raw["fs_escape"]
    bash_denied = not bash_escape["markers"]["/work/agentpanel_escape_bash.txt"]
    fs_denied = not any(fs_escape["markers"].values())
    verdicts["2_workspace_escape"] = {
        "pass": bool(bash_denied and fs_denied),
        "evidence": {
            "bash_marker_exists": bash_escape["markers"]["/work/agentpanel_escape_bash.txt"],
            "fs_markers": fs_escape["markers"],
            "bash_tool_errors": _error_evidence(bash_escape),
            "fs_tool_errors": _error_evidence(fs_escape),
            "fs_incoming_requests": [r["method"] for r in fs_escape["incoming_requests"]],
        },
    }

    # 3. 出网
    ok = raw["egress_ok"]
    deny = raw["egress_deny"]
    ok_errors = _error_evidence(ok)
    deny_errors = _error_evidence(deny)
    provider_reachable = len(provider) > 0
    ok_blocked_by_ssrf = any("non-public ip" in (row.get("text") or "").lower() for row in ok_errors)
    deny_blocked = bool(deny_errors)
    verdicts["3_egress"] = {
        "pass": bool(provider_reachable and deny_blocked),
        "evidence": {
            "configured_provider_reachable_requests": len(provider),
            "non_allowlisted_tool_errors": deny_errors,
            "allowlisted_web_fetch_errors": ok_errors,
            "allowlisted_web_fetch_blocked_by_dsh_ssrf_guard": ok_blocked_by_ssrf,
            "note": (
                "容器以 --network none 运行，外部域名在容器网络层不可达；"
                "dsh web_fetch 另有非公网 IP 拦截，白名单域名经 --add-host 指向 127.0.0.1 时仍被其 SSRF 防护拒绝。"
                "provider 通道（LLM 请求）可直达假 provider；域名白名单由业务网关 assert_egress_allowed 负责。"
            ),
        },
    }

    # 4. 原生审批通道
    approval = raw["approval_allow"]
    permission_requests = [
        r for r in approval["incoming_requests"] if r.get("method") == "session/request_permission"
    ]
    asked = len(_event_data(approval, "approval/asked"))
    decided = len(_event_data(approval, "approval/decided"))
    executed = approval["markers"]["/work/agentpanel_approval_executed.txt"]
    verdicts["4_native_approval"] = {
        "pass": bool(permission_requests and asked >= 1 and executed),
        "evidence": {
            "session_request_permission_count": len(permission_requests),
            "permission_request_payload": [r.get("payload") for r in permission_requests[:1]],
            "approval_asked_events": asked,
            "approval_decided_events": decided,
            "executed_after_allow": executed,
            "approval_event_types": _event_types(approval),
            "bash_tool_errors": _error_evidence(approval),
        },
    }

    return verdicts


def _gateway_check() -> Optional[Dict[str, Any]]:
    path = "/opt/project_gateway_service.py"
    if not os.path.exists(path):
        return None
    try:
        sys.path.insert(0, os.path.join(VERIFY_DIR, "scripts"))
        from gateway_allowlist_check import run_check

        return run_check(path)
    except Exception as exc:
        return {"pass": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(WORKDIR, exist_ok=True)
    try:
        os.remove(os.path.join(WORKDIR, ".agentpanel_hook_calls.jsonl"))
    except Exception:
        pass
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "kernel": platform.release(),
        "workdir": WORKDIR,
        "network_mode_expected": "none",
        "bwrap": shutil.which("bwrap") or "",
    }
    _write_json(os.path.join(OUTDIR, "environment.json"), info)
    _log(f"environment: {info}")

    from fake_provider import serve

    server = serve()
    _log(f"fake provider on 127.0.0.1:{PORT}")

    from deepseek_harness.client import HarnessClient, HarnessConfig

    client = HarnessClient(HarnessConfig(
        dsh_home=os.environ.get("DSH_HOME", "/data/dsh"),
        cwd=WORKDIR,
        patches=(PATCH,),
        env={
            "DEEPSEEK_API_KEY": PLACEHOLDER_KEY,
            "DEEPSEEK_BASE_URL": f"http://127.0.0.1:{PORT}/v1",
            "DSH_TELEMETRY_MODE": "DISABLED",
        },
    ))
    stop = threading.Event()
    worker: Optional[threading.Thread] = None
    raw: Dict[str, Dict[str, Any]] = {}
    try:
        client.start()
        client.initialize(cwd=WORKDIR, provider="deepseek-official", model="deepseek-v4-flash")
        _log("dsh initialized")
        worker = threading.Thread(target=_request_worker, args=(client, stop), daemon=True)
        worker.start()
        for scenario in SCENARIOS:
            _log(f"scenario: {scenario}")
            result = _run_scenario(client, scenario)
            raw[scenario] = result
            _write_json(os.path.join(OUTDIR, f"transcript_{scenario}.json"), result)
    except Exception:
        _log("verification failed with exception:\n" + traceback.format_exc())
        _write_json(os.path.join(OUTDIR, "exception.json"), {"traceback": traceback.format_exc()})
    finally:
        stop.set()
        try:
            client.close()
        except Exception:
            pass
        server.shutdown()

    verdicts = _summarize(raw)
    gateway = _gateway_check()
    summary = {
        "environment": info,
        "verdicts": verdicts,
        "gateway_allowlist": gateway,
        "raw_scenarios": list(raw.keys()),
        "placeholder_key_used": True,
        "real_provider_called": False,
    }
    _write_json(os.path.join(OUTDIR, "results.json"), summary)
    _log(json.dumps(verdicts, ensure_ascii=False, indent=2))
    if gateway:
        _log("gateway_allowlist=" + json.dumps(gateway, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
