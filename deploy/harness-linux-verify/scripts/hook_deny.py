"""PreToolUse 命令钩子：模拟业务侧危险命令拦截规则。

只拦截带 agentpanel 专用标记的命令，避免干扰其它验证场景。
输出 Claude Code 兼容的 hookSpecificOutput（dsh 桥接层会映射到 tools/pre-execute 的 deny）。
"""
import json
import os
import sys
import time

# 钩子运行在 dsh 的 workspace 沙箱内，/out 不可写，故落在 workspace 内。
OUT = os.path.join(os.environ.get("VERIFY_WORKDIR", "/work/ws"), ".agentpanel_hook_calls.jsonl")


def log(payload):
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else ""
    log({
        "at": time.time(),
        "hook_event_name": payload.get("hook_event_name"),
        "tool_name": tool_name,
        "tool_input": tool_input,
        "pid": os.getpid(),
    })
    if isinstance(command, str) and "should_not_exist_hook" in command:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "agentpanel verify: blocked by PreToolUse hook",
            }
        }))
        return 0
    # 不输出 decision，避免把“应由审批处理”的调用提前放行
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
