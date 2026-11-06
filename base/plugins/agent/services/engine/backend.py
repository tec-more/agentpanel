"""
M2 执行后端抽象与进程内实现（InProcessBackend）

溯源：
- docs/arch/03 §2.4/§2.5：进程内 asyncio 执行（Q-E），ExecutorBackend 接口预留 MqBackend（P1+）
- docs/arch/04 §4.2 节点信封：NodeInput={config, resolved_inputs, context}，
  NodeOutput={status, outputs, usage?, error?, next?}
- docs/arch/04 F4：可重试错误退避 1s/2s/4s 上限 3 次（节点配置可下调不可上调）；
  重试耗尽按图策略 fail_fast（默认）/continue_with_default（仅声明默认值的节点）
- docs/arch/06 R-02：引擎只消费上下文，不做 JWT/归属判断；R-10：用户域 code 拒绝

调度模型（P0）：自 start 节点沿边递归推进；condition 节点按条件边路由（优先级排序，
空条件为默认边）；visited 集合保证每节点至多执行一次（校验器 E-103 已保证无环）；
步数护栏防异常图失控。
"""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from base.plugins.agent.services.engine import events as evt
from base.plugins.agent.services.engine.context import ExecutionContext
from base.plugins.agent.services.engine.errors import (
    ExecutionCancelled,
    HitlTimeout,
    KBAccessDenied,
    NodeCapabilityDenied,
    NodeExecutionError,
)
from base.plugins.agent.services.engine.nodes import NODE_HANDLERS, render_template
from base.plugins.agent.utils.safe_eval import safe_eval

# 步数护栏（防异常图失控；正常图节点 ≤200，03-§3.1）
MAX_STEPS = 500
# 重试退避（F4：1s/2s/4s，上限 3 次不可上调）
RETRY_BACKOFF = (1.0, 2.0, 4.0)
RETRY_MAX = 3


class RunControl:
    """
    运行控制面（协作式取消 / HITL 恢复）

    由 ExecutionService 注册到执行实例注册表；cancel/resume API 仅置位，
    引擎在节点边界与流式 token 间检查（04-F5 协作式取消）。
    """

    def __init__(self) -> None:
        self.cancel_requested = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.resume_payload: Optional[Dict[str, Any]] = None
        # BUG-T15-014：唤醒确认与保底自救（cancel/resume API 置位后等 ack 回执；
        # 超时说明 runner 卡死/传输层异常，API 侧走保底强制收尾，杜绝槽永久泄漏）
        self.ack_event = asyncio.Event()              # 引擎观察到 cancel/resume 的回执
        self.runner_task: Optional[asyncio.Task] = None   # 保底路径强制取消用
        self.ctx: Any = None                          # 保底路径 _finalize 入参
        self.writer: Any = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.finalize_lock = asyncio.Lock()           # 收尾互斥（保底 vs runner done_callback）
        self.finalized = False

    def request_cancel(self) -> None:
        self.cancel_requested.set()

    def resume(self, payload: Dict[str, Any]) -> None:
        self.resume_payload = payload
        self.resume_event.set()

    def throw_if_cancelled(self) -> None:
        if self.cancel_requested.is_set():
            raise ExecutionCancelled()


# emit(event_type, node_id, payload) -> awaitable；由服务层接入 Trace/SSE
EmitFunc = Any


class ExecutorBackend(ABC):
    """执行后端抽象（03-§2.4：P0 InProcessBackend，P1+ MqBackend 可插拔）"""

    @abstractmethod
    async def execute(
        self,
        ctx: ExecutionContext,
        graph: Dict[str, Any],
        inputs: Dict[str, Any],
        emit: EmitFunc,
        control: RunControl,
    ) -> Dict[str, Any]:
        """
        执行图并通过 emit 推送八类事件。

        Returns:
            {"status": "success|failed|cancelled|paused_timeout", "outputs": {...},
             "tokens": {"in": int, "out": int}, "error": {...}?}
        """


class InProcessBackend(ExecutorBackend):
    """进程内执行后端（P0）"""

    def __init__(self) -> None:
        self._tokens_in = 0
        self._tokens_out = 0
        self._steps = 0

    # ============================================================
    # 主流程
    # ============================================================
    async def execute(
        self,
        ctx: ExecutionContext,
        graph: Dict[str, Any],
        inputs: Dict[str, Any],
        emit: EmitFunc,
        control: RunControl,
    ) -> Dict[str, Any]:
        self._ctx = ctx
        self._emit = emit
        self._control = control
        self._nodes = {n.get("id"): n for n in (graph.get("nodes") or []) if n.get("id")}
        self._out_edges: Dict[str, List[Dict[str, Any]]] = {}
        for edge in graph.get("edges") or []:
            src, tgt = edge.get("source"), edge.get("target")
            if src and tgt:
                self._out_edges.setdefault(src, []).append(edge)
        self._state: Dict[str, Any] = {
            "vars": dict(inputs or {}),
            "nodes": {},
        }
        self._outputs: Dict[str, Any] = {}
        self._visited: set = set()
        self._steps = 0
        self._tokens_in = 0
        self._tokens_out = 0

        started = time.monotonic()
        await emit(evt.EventType.RUN_STARTED, None,
                   evt.run_started(ctx.execution_id, ctx.version_id, time.time()))

        start_node = next((n for n in self._nodes.values() if n.get("type") == "start"), None)
        if start_node is None:
            await emit(evt.EventType.RUN_FAILED, None,
                       evt.run_failed(ctx.execution_id, "NO_START_NODE"))
            return {"status": "failed", "outputs": {}, "tokens": self._tokens(),
                    "error": {"code": "NO_START_NODE"}}

        try:
            await self._run_from(start_node["id"], depth=0)
            ms = int((time.monotonic() - started) * 1000)
            await emit(evt.EventType.RUN_COMPLETED, None,
                       evt.run_completed(ctx.execution_id, self._tokens(), ms))
            return {"status": "success", "outputs": self._outputs, "tokens": self._tokens()}
        except ExecutionCancelled:
            # BUG-T15-014：取消被引擎观察到，回执供 cancel API 唤醒确认
            self._control.ack_event.set()
            logger.info(f"[engine] 执行被取消 execution_id={ctx.execution_id}")
            return {"status": "cancelled", "outputs": self._outputs, "tokens": self._tokens()}
        except NodeExecutionError as e:
            await emit(evt.EventType.RUN_FAILED, None,
                       evt.run_failed(ctx.execution_id, e.code, message=e.message))
            return {"status": "failed", "outputs": self._outputs, "tokens": self._tokens(),
                    "error": {"code": e.code, "message": e.message}}
        except Exception as e:  # 引擎级未捕获异常（05-§1.4：node_failed(internal) → run_failed）
            logger.exception(f"[engine] 引擎异常 execution_id={ctx.execution_id}: {e}")
            await emit(evt.EventType.RUN_FAILED, None,
                       evt.run_failed(ctx.execution_id, "ENGINE_INTERNAL", message=type(e).__name__))
            return {"status": "failed", "outputs": self._outputs, "tokens": self._tokens(),
                    "error": {"code": "ENGINE_INTERNAL", "message": str(e)}}

    def _tokens(self) -> Dict[str, int]:
        return {"in": self._tokens_in, "out": self._tokens_out}

    # ============================================================
    # 调度
    # ============================================================
    async def _run_from(self, node_id: str, depth: int) -> None:
        self._control.throw_if_cancelled()
        if node_id in self._visited:
            return
        self._steps += 1
        if self._steps > MAX_STEPS:
            raise NodeExecutionError("MAX_STEPS_EXCEEDED", "执行步数超限", retryable=False)
        node = self._nodes.get(node_id)
        if node is None:
            return
        self._visited.add(node_id)

        result = await self._run_node(node, depth)
        if result.get("status") == "paused":
            # HITL 暂停后恢复继续推进
            pass
        elif result.get("status") != "success":
            # 失败策略已在 _run_node 内处理（fail_fast 抛错 / continue_with_default 转成功）
            raise NodeExecutionError(
                (result.get("error") or {}).get("code", "NODE_FAILED"),
                (result.get("error") or {}).get("message", "节点执行失败"),
            )

        for next_id in self._route(node, result):
            await self._run_from(next_id, depth)

    def _route(self, node: Dict[str, Any], result: Dict[str, Any]) -> List[str]:
        """路由：节点显式 next 优先；condition 走条件边；其余沿全部出边"""
        explicit_next = result.get("next")
        if explicit_next:
            return [n for n in explicit_next if n in self._nodes]
        edges = self._out_edges.get(node["id"], [])
        if node.get("type") != "condition":
            return [e["target"] for e in edges if e.get("enabled", True)]
        return self._route_condition(edges)

    def _route_condition(self, edges: List[Dict[str, Any]]) -> List[str]:
        """条件边路由：按优先级求值，首条命中即走；无命中走默认边（空条件）"""
        conditional = sorted(
            [e for e in edges if (e.get("condition") or "").strip()],
            key=lambda e: e.get("priority", 0),
        )
        defaults = sorted(
            [e for e in edges if not (e.get("condition") or "").strip()],
            key=lambda e: e.get("priority", 0),
        )
        variables = self._flat_vars()
        for edge in conditional:
            if not edge.get("enabled", True):
                continue
            expr = render_template(edge["condition"], variables, keep_unresolved="None")
            try:
                if safe_eval(expr, {"variables": variables}):
                    return [edge["target"]]
            except Exception as e:
                logger.warning(f"[engine] 条件表达式求值失败 edge={edge.get('id')}: {e}")
        return [defaults[0]["target"]] if defaults else []

    # ============================================================
    # 节点执行（信封契约 + 重试 + 失败策略）
    # ============================================================
    async def _run_node(self, node: Dict[str, Any], depth: int) -> Dict[str, Any]:
        node_id = node["id"]
        node_type = node.get("type", "")
        data = node.get("data") or {}
        config = data.get("config") or {}
        label = data.get("label") or node_id

        self._control.throw_if_cancelled()
        await self._emit(evt.EventType.NODE_STARTED, node_id, evt.node_started(node_id, label))
        started = time.monotonic()

        handler = NODE_HANDLERS.get(node_type)
        resolved_inputs = self._resolve_inputs(data.get("inputs") or [])
        runtime = {
            "emit": self._emit,
            "control": self._control,
            "state": self._state,
            "ctx": self._ctx,
            "depth": depth,
            "run_subgraph": self._run_subgraph,
        }

        result: Dict[str, Any]
        if handler is None:
            result = {"status": "failed",
                      "error": {"code": "UNKNOWN_NODE_TYPE", "message": f"未知节点类型: {node_type}",
                                "retryable": False}}
        else:
            result = await self._with_retry(node, handler, config, resolved_inputs, runtime)

        ms = int((time.monotonic() - started) * 1000)
        if result.get("status") == "success":
            usage = result.get("usage") or {}
            self._tokens_in += int(usage.get("tokens_in") or 0)
            self._tokens_out += int(usage.get("tokens_out") or 0)
            outputs = result.get("outputs") or {}
            self._state["nodes"][node_id] = outputs
            if node_type == "end":
                self._outputs = dict(resolved_inputs) or dict(outputs)
            await self._emit(evt.EventType.NODE_COMPLETED, node_id,
                             evt.node_completed(node_id, usage, ms))
            return result

        if result.get("status") == "paused":
            await self._emit(evt.EventType.NODE_COMPLETED, node_id,
                             evt.node_completed(node_id, result.get("usage") or {}, ms))
            self._state["nodes"][node_id] = result.get("outputs") or {}
            return result

        # 失败：事件 + 图策略
        error = result.get("error") or {"code": "NODE_FAILED", "message": "", "retryable": False}
        await self._emit(evt.EventType.NODE_FAILED, node_id,
                         evt.node_failed(node_id, error.get("code", "NODE_FAILED"),
                                         bool(error.get("retryable")), error.get("message", "")))
        policy = (config.get("on_error") or "").strip() or self._default_failure_policy()
        if policy == "continue_with_default":
            defaults = self._node_defaults(data)
            if defaults is not None:
                self._state["nodes"][node_id] = defaults
                return {"status": "success", "outputs": defaults,
                        "usage": {}, "degraded": True}
        return result

    async def _with_retry(self, node: Dict[str, Any], handler, config: Dict[str, Any],
                          resolved_inputs: Dict[str, Any], runtime: Dict[str, Any]) -> Dict[str, Any]:
        """重试编排（F4：可重试错误 1s/2s/4s，上限 3 次；429 尊重 Retry-After）"""
        max_retries = self._max_retries(config)
        attempt = 0
        while True:
            try:
                output = await handler(node, resolved_inputs, runtime)
                return output
            except ExecutionCancelled:
                raise
            except NodeExecutionError as e:
                if not e.retryable or attempt >= max_retries:
                    return {"status": "failed",
                            "error": {"code": e.code, "message": e.message,
                                      "retryable": e.retryable}}
                delay = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                if e.retry_after:
                    delay = max(delay, e.retry_after)
                logger.info(f"[engine] 节点 {node['id']} 第 {attempt + 1} 次重试，等待 {delay}s")
                await asyncio.sleep(delay)
                attempt += 1
            except (KBAccessDenied, NodeCapabilityDenied, HitlTimeout) as e:
                return {"status": "failed",
                        "error": {"code": e.code, "message": e.message, "retryable": False}}
            except Exception as e:
                logger.exception(f"[engine] 节点 {node['id']} 未捕获异常: {e}")
                return {"status": "failed",
                        "error": {"code": "NODE_INTERNAL", "message": str(e), "retryable": False}}

    def _max_retries(self, config: Dict[str, Any]) -> int:
        """节点配置可下调不可上调（N4-4：上限 3 固定）"""
        graph_max = ((self._ctx.settings or {}).get("retry") or {}).get("max", RETRY_MAX)
        node_max = config.get("max_retries", graph_max)
        try:
            return max(0, min(int(node_max), RETRY_MAX))
        except (TypeError, ValueError):
            return RETRY_MAX

    def _default_failure_policy(self) -> str:
        return ((self._ctx.settings or {}).get("on_failure") or "fail_fast")

    @staticmethod
    def _node_defaults(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """continue_with_default 的默认值（仅允许声明默认值的节点，F4）"""
        outputs = data.get("outputs") or []
        defaults = {o["name"]: o["default"] for o in outputs
                    if o.get("name") and "default" in o}
        return defaults if defaults else None

    # ============================================================
    # 变量
    # ============================================================
    def _resolve_inputs(self, inputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for spec in inputs:
            name = spec.get("name")
            ref = spec.get("from")
            if not name:
                continue
            if ref:
                resolved[name] = self._lookup(ref)
            elif "value" in spec:
                resolved[name] = spec["value"]
        return resolved

    def _lookup(self, ref: str) -> Any:
        """from 引用求值：node_id.port → 节点输出；裸名 → 变量"""
        if not isinstance(ref, str):
            return ref
        if "." in ref:
            node_id, _, path = ref.partition(".")
            value: Any = (self._state["nodes"].get(node_id) or {})
            for part in path.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value
        return self._state["vars"].get(ref)

    def _flat_vars(self) -> Dict[str, Any]:
        """条件/模板求值的扁平变量视图（节点输出并入）"""
        flat = dict(self._state["vars"])
        for node_id, outputs in self._state["nodes"].items():
            flat[node_id] = outputs
        return flat

    async def _run_subgraph(self, graph: Dict[str, Any], inputs: Dict[str, Any],
                            depth: int) -> Dict[str, Any]:
        """子图执行（loop/sub_workflow/sub_agent 复用）；深度护栏防递归失控"""
        if depth >= 3:
            raise NodeExecutionError("SUBGRAPH_DEPTH_EXCEEDED", "子图嵌套深度超限", retryable=False)
        sub = InProcessBackend()
        sub._nodes = {n.get("id"): n for n in (graph.get("nodes") or []) if n.get("id")}
        sub._out_edges = {}
        for edge in graph.get("edges") or []:
            src, tgt = edge.get("source"), edge.get("target")
            if src and tgt:
                sub._out_edges.setdefault(src, []).append(edge)
        sub._ctx = self._ctx
        sub._emit = self._emit
        sub._control = self._control
        sub._state = {"vars": dict(inputs or {}), "nodes": {}}
        sub._outputs = {}
        sub._visited = set()
        sub._steps = 0
        sub._tokens_in = 0
        sub._tokens_out = 0
        start_node = next((n for n in sub._nodes.values() if n.get("type") == "start"), None)
        if start_node is None:
            raise NodeExecutionError("NO_START_NODE", "子图缺少开始节点", retryable=False)
        await sub._run_from(start_node["id"], depth + 1)
        self._tokens_in += sub._tokens_in
        self._tokens_out += sub._tokens_out
        return {"outputs": sub._outputs, "nodes": sub._state["nodes"]}
