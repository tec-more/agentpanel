"""容器内可控假 provider（OpenAI Chat Completions 兼容）。

用途：让 dsh 在不调用真实模型的情况下触发指定工具调用。
- 只监听容器内 127.0.0.1 高位端口；
- 不记录 Authorization 头，不记录任何真实密钥；
- 根据最后一条 user 消息中的 `SCENARIO:<name>` 选择工具与参数；
- 工具返回结果后，返回一段最终文本结束该轮。
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

PORT = int(os.environ.get("FAKE_PROVIDER_PORT", "18080"))
LOG_PATH = os.path.join(os.environ.get("VERIFY_OUTDIR", "/out"), "fake_provider_requests.jsonl")

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "hook_deny": {
        "kind": "bash",
        "command": "touch /work/should_not_exist_hook.txt",
    },
    "bash_escape": {
        "kind": "bash",
        # 写到 workspace 的父目录（OS 可写，但不是 workspace），验证沙箱边界
        "command": "echo escaped > /work/agentpanel_escape_bash.txt; cat /etc/hostname",
    },
    "fs_escape": {
        "kind": "write",
        "path": "/work/agentpanel_escape_fs.txt",
        "content": "ESCAPE",
    },
    "approval_allow": {
        "kind": "bash",
        "command": "touch /work/agentpanel_approval_executed.txt",
    },
    "egress_ok": {
        "kind": "web",
        # 运行时用 --add-host api.deepseek.com:127.0.0.1 把白名单域名指向容器内假 provider
        "url": f"http://api.deepseek.com:{PORT}/egress-ok",
    },
    "egress_deny": {
        "kind": "web",
        "url": "http://example.com/agentpanel-egress-deny",
    },
    # 仅在联网容器中运行，用于判断 dsh 自身是否有域名白名单
    "egress_public_ok": {
        "kind": "web",
        "url": "https://api.deepseek.com/",
    },
    "egress_public_deny": {
        "kind": "web",
        "url": "https://example.com/",
    },
}

_lock = threading.Lock()


def _log(payload: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with _lock, open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return ""


def _scenario_from_messages(messages: List[Any]) -> Optional[str]:
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        match = re.search(r"SCENARIO:([a-z_]+)", _text_of(message.get("content")))
        if match:
            return match.group(1)
    return None


def _last_user_index(messages: List[Any]) -> int:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if isinstance(message, dict) and message.get("role") == "user":
            return index
    return -1


def _tool_step_count(messages: List[Any]) -> int:
    start = _last_user_index(messages)
    return sum(
        1 for message in messages[start + 1:]
        if isinstance(message, dict) and message.get("role") == "tool"
    )


def _pick_tool(tools: List[Any], kind: str) -> Optional[Dict[str, Any]]:
    candidates = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = str(fn.get("name") or "")
        if name:
            candidates.append(fn)
    if kind == "bash":
        exact = ("bash", "shell", "terminal", "exec")
    elif kind == "write":
        exact = ("write", "edit", "multi_edit", "apply_patch", "create_file")
    else:
        exact = ("web_fetch", "fetch")
    for name in exact:
        for fn in candidates:
            if str(fn.get("name", "")) == name:
                return fn
    for pattern in exact:
        for fn in candidates:
            name = str(fn.get("name", ""))
            if pattern in name and "todo" not in name:
                return fn
    return candidates[0] if candidates else None


def _build_arguments(fn: Dict[str, Any], spec: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
    props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
    required = params.get("required") if isinstance(params.get("required"), list) else []

    def first(keys: List[str]) -> Optional[str]:
        for key in keys:
            if key in props:
                return key
        return keys[0] if keys else None

    args: Dict[str, Any] = {}
    if spec["kind"] == "bash":
        args[first(["command", "cmd", "script"]) or "command"] = spec["command"]
    elif spec["kind"] == "write":
        args[first(["path", "file_path", "filepath", "target"]) or "path"] = spec["path"]
        content_key = first(["content", "text", "contents", "new_string"])
        if content_key:
            args[content_key] = spec["content"]
    else:
        args[first(["url", "uri", "href"]) or "url"] = spec["url"]

    if spec.get("elevated"):
        args["sandbox_permissions"] = "danger-full-access"
        args["justification"] = "agentpanel verify: single elevated retry for approval test"

    # 补齐 schema 必填项（如 bash 的 description），避免参数校验先于安全检查失败
    for key in required:
        if key in args:
            continue
        prop = props.get(key) if isinstance(props.get(key), dict) else {}
        prop_type = prop.get("type")
        if key == "description":
            args[key] = f"agentpanel verify {scenario}"
        elif isinstance(prop_type, list):
            prop_type = prop_type[0] if prop_type else ""
        if key in args:
            continue
        if prop_type == "boolean":
            args[key] = False
        elif prop_type in ("number", "integer"):
            args[key] = 0
        elif prop_type == "array":
            args[key] = []
        elif prop_type == "object":
            args[key] = {}
        else:
            args[key] = "agentpanel-verify"
    if "description" in props and "description" not in args:
        args["description"] = f"agentpanel verify {scenario}"
    return args


def _sse_chunks(chunk: Dict[str, Any]) -> bytes:
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # 只保留路径，不输出请求头/正文
        pass

    def do_GET(self) -> None:
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}
        messages = body.get("messages") if isinstance(body.get("messages"), list) else []
        tools = body.get("tools") if isinstance(body.get("tools"), list) else []
        scenario = _scenario_from_messages(messages)
        spec = SCENARIOS.get(scenario or "")
        steps = _tool_step_count(messages)
        has_result = steps > 0
        if scenario == "fs_escape" and steps == 1 and spec:
            # 第一步是绝对路径越界写；第二步验证 ../ 相对路径越界写
            spec = {**spec, "path": "../agentpanel_escape_fs_rel.txt"}
        if scenario == "approval_allow" and steps == 1 and spec:
            # 越界写被沙箱拒绝后，模型按 dsh 约定发起一次更宽权限的重试，触发原生审批
            spec = {**spec, "elevated": True}

        _log({
            "path": self.path,
            "scenario": scenario,
            "stream": bool(body.get("stream")),
            "messages": messages,
            "tool_names": [
                (t.get("function") or {}).get("name") if isinstance(t, dict) else None
                for t in tools
            ],
            "tool_result_seen": has_result,
        })

        tool_call: Optional[Dict[str, Any]] = None
        should_call = bool(spec) and (
            steps == 0
            or (scenario in ("fs_escape", "approval_allow") and steps == 1)
        )
        if should_call:
            fn = _pick_tool(tools, spec["kind"])
            if fn:
                tool_call = {
                    "id": "call_agentpanel_verify",
                    "type": "function",
                    "function": {
                        "name": fn.get("name"),
                        "arguments": json.dumps(
                            _build_arguments(fn, spec, scenario or ""), ensure_ascii=False
                        ),
                    },
                }

        if body.get("stream"):
            self._stream(tool_call)
        else:
            self._json(tool_call)

    def _base(self) -> Dict[str, Any]:
        return {
            "id": "chatcmpl-agentpanel-verify",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "deepseek-v4-flash",
        }

    def _json(self, tool_call: Optional[Dict[str, Any]]) -> None:
        if tool_call:
            message = {"role": "assistant", "content": None, "tool_calls": [tool_call]}
            finish = "tool_calls"
        else:
            message = {"role": "assistant", "content": "VERIFY_FAKE_PROVIDER_DONE"}
            finish = "stop"
        payload = {
            **self._base(),
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _stream(self, tool_call: Optional[Dict[str, Any]]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        base = self._base()
        first = {
            **base,
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        }
        self.wfile.write(_sse_chunks(first))
        if tool_call:
            delta = {"tool_calls": [{"index": 0, **tool_call}]}
            chunk = {
                **base,
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            self.wfile.write(_sse_chunks(chunk))
            finish = {
                **base,
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            }
            self.wfile.write(_sse_chunks(finish))
        else:
            chunk = {
                **base,
                "object": "chat.completion.chunk",
                "choices": [{
                    "index": 0,
                    "delta": {"content": "VERIFY_FAKE_PROVIDER_DONE"},
                    "finish_reason": None,
                }],
            }
            self.wfile.write(_sse_chunks(chunk))
            finish = {
                **base,
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            self.wfile.write(_sse_chunks(finish))
        usage = {
            **base,
            "object": "chat.completion.chunk",
            "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        self.wfile.write(_sse_chunks(usage))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def serve() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, name="fake-provider", daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    server = serve()
    print(f"[fake-provider] listening on 127.0.0.1:{PORT}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
