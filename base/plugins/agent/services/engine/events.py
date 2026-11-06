"""
M2 SSE 事件类型与载荷构造（04-§5.1 八类事件，PRD 6.5 对齐）

seq 规则：全局单调递增（TraceWriter 分配）；前端按 seq 回放与着色；
token 事件仅在 stream 节点产生；断线经 GET trace?cursor=last_seq 补齐。
"""
from typing import Any, Dict, Optional


class EventType:
    RUN_STARTED = "run_started"
    NODE_STARTED = "node_started"
    TOKEN = "token"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    RUN_PAUSED = "run_paused"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"

    ALL = (
        RUN_STARTED, NODE_STARTED, TOKEN, NODE_COMPLETED,
        NODE_FAILED, RUN_PAUSED, RUN_COMPLETED, RUN_FAILED,
    )


def run_started(execution_id: int, version_id: Optional[int], ts: float) -> Dict[str, Any]:
    return {"execution_id": execution_id, "version_id": version_id, "ts": ts}


def node_started(node_id: str, label: str) -> Dict[str, Any]:
    return {"node_id": node_id, "label": label}


def token(node_id: str, delta: str) -> Dict[str, Any]:
    return {"node_id": node_id, "delta": delta}


def node_completed(node_id: str, usage: Optional[Dict[str, int]], ms: int) -> Dict[str, Any]:
    return {"node_id": node_id, "usage": usage or {}, "ms": ms}


def node_failed(node_id: str, code: str, retryable: bool, message: str = "") -> Dict[str, Any]:
    return {
        "node_id": node_id,
        "error": {"code": code, "retryable": retryable, "message": message},
    }


def run_paused(node_id: str, assignee: Dict[str, Any], deadline: Optional[str]) -> Dict[str, Any]:
    return {"node_id": node_id, "assignee": assignee, "deadline": deadline}


def run_completed(execution_id: int, tokens: Dict[str, int], ms: int) -> Dict[str, Any]:
    return {"execution_id": execution_id, "tokens": tokens, "ms": ms}


def run_failed(execution_id: int, code: str, node_id: Optional[str] = None,
               message: str = "") -> Dict[str, Any]:
    return {
        "execution_id": execution_id,
        "error": {"code": code, "node_id": node_id, "message": message},
    }
