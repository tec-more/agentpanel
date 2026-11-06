"""
M2 节点处理器（04-§4.2 信封契约）

签名：handler(node, resolved_inputs, runtime) -> NodeOutput
  NodeOutput = {status: success|failed|paused, outputs, usage?, error?, next?}
runtime = {emit, control, state, ctx, depth, run_subgraph}

能力开关（R-10 / 04-§4.3）：
- code：用户域（cus/usr）运行时永久拒绝（编辑期校验器已挡，此为双保险）
- http：域名白名单 + DNS 解析后内网二次校验；仅 GET/POST；超时 ≤30s；响应 ≤5MB
- tool：运行时经 ctx.require_resource 复核授权（编辑期 E-110 之后的双保险）
"""
import json
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from base.plugins.agent.services.engine import events as evt
from base.plugins.agent.services.engine.context import DOMAIN_CUS, DOMAIN_USR
from base.plugins.agent.services.engine.errors import (
    ExecutionCancelled,
    HitlTimeout,
    NodeCapabilityDenied,
    NodeExecutionError,
)
from base.plugins.agent.services.engine.http_guard import (
    MAX_RESPONSE_BYTES,
    MAX_TIMEOUT_SECONDS,
    assert_method_allowed,
    assert_url_allowed,
)
from base.plugins.agent.services.engine.llm_gateway import LLMGateway

# loop 迭代硬上限（E-111 防死循环兜底）
LOOP_MAX_ITERATIONS = 100
# HITL 默认超时（F6：72h，节点配置可覆盖）
HITL_DEFAULT_TIMEOUT_S = 72 * 3600

Handler = Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]

_TEMPLATE_RE = __import__("re").compile(r"\{\{\s*([A-Za-z_][\w.]*?)\s*\}\}")


def render_template(template: Any, variables: Dict[str, Any], *,
                    keep_unresolved: Optional[str] = "") -> str:
    """
    {{path}} 插值（04-§4.2 prompt 模板契约；05-§2.4：不引入 {{ }} 之外的模板语法）

    keep_unresolved: 未解析占位替换值（条件表达式场景用 "None" 使 safe_eval 可判空）
    """
    if not isinstance(template, str):
        return template

    def _resolve(path: str) -> Any:
        value: Any = variables
        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _sub(match) -> str:
        value = _resolve(match.group(1))
        if value is None:
            return keep_unresolved if keep_unresolved is not None else match.group(0)
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    return _TEMPLATE_RE.sub(_sub, template)


def _flat_vars(runtime: Dict[str, Any]) -> Dict[str, Any]:
    state = runtime["state"]
    flat = dict(state["vars"])
    for node_id, outputs in state["nodes"].items():
        flat[node_id] = outputs
    return flat


def _declared_outputs(node: Dict[str, Any]) -> List[str]:
    return [o.get("name") for o in (node.get("data") or {}).get("outputs") or [] if o.get("name")]


# ============================================================
# 基础节点
# ============================================================
async def handle_start(node, resolved_inputs, runtime) -> Dict[str, Any]:
    """开始节点：声明输出从用户输入变量取值"""
    outputs = {name: runtime["state"]["vars"].get(name) for name in _declared_outputs(node)}
    if not outputs:
        outputs = dict(runtime["state"]["vars"])
    return {"status": "success", "outputs": outputs}


async def handle_end(node, resolved_inputs, runtime) -> Dict[str, Any]:
    return {"status": "success", "outputs": dict(resolved_inputs)}


async def handle_template(node, resolved_inputs, runtime) -> Dict[str, Any]:
    config = (node.get("data") or {}).get("config") or {}
    rendered = render_template(config.get("template", ""), _flat_vars(runtime))
    return {"status": "success", "outputs": {"output": rendered, "text": rendered}}


async def handle_condition(node, resolved_inputs, runtime) -> Dict[str, Any]:
    """条件节点本体无计算，路由由引擎条件边求值完成"""
    return {"status": "success", "outputs": {}}


# ============================================================
# LLM 节点（M6 统一出口；usage 供 M9 结算）
# ============================================================
async def handle_llm(node, resolved_inputs, runtime) -> Dict[str, Any]:
    ctx = runtime["ctx"]
    emit = runtime["emit"]
    control = runtime["control"]
    data = node.get("data") or {}
    config = data.get("config") or {}
    node_id = node["id"]

    # BUG-T15-008：契约字段 model_ref 优先，兼容旧字段 model_id/modelId
    model_ref = config.get("model_ref") or config.get("model_id") or config.get("modelId")
    if model_ref is None:
        raise NodeExecutionError("MODEL_UNAVAILABLE", "LLM 节点未配置模型", retryable=False)
    # 运行时资源复核（E-110 双保险）
    if not await ctx.require_resource("model", model_ref):
        raise NodeExecutionError("MODEL_UNAVAILABLE", "模型未授权或不可用", retryable=False)

    flat = _flat_vars(runtime)
    # BUG-T15-008：契约字段 user_prompt 优先，兼容旧字段 prompt_template/prompt
    prompt_template = config.get("user_prompt") or config.get("prompt_template") or config.get("prompt") or ""
    user_prompt = render_template(prompt_template, flat)
    messages: List[Dict[str, str]] = []
    if config.get("system_prompt"):
        messages.append({"role": "system",
                         "content": render_template(config["system_prompt"], flat)})
    messages.append({"role": "user", "content": user_prompt})

    stream = bool(config.get("stream"))
    usage_holder: Dict[str, Any] = {}

    async def on_token(delta: str) -> None:
        control.throw_if_cancelled()  # 流式中断（F5：关闭上游连接由调用取消触发）
        await emit(evt.EventType.TOKEN, node_id, evt.token(node_id, delta))

    resource = await LLMGateway.resolve_model(model_ref)
    result = await LLMGateway.call(
        resource,
        messages,
        stream=stream,
        on_token=on_token if stream else None,
        temperature=float(config.get("temperature", 0.7)),
        max_tokens=int(config.get("max_tokens", 2000)),
        timeout_s=int(config.get("timeout_s", 60)),
        trace_id=ctx.trace_id,
    )
    content = result["content"]
    usage = result["usage"]
    usage_holder.update(usage)

    outputs = {"answer": content, "text": content, "response": content}
    return {"status": "success", "outputs": outputs, "usage": usage}


# ============================================================
# RAG 检索节点（M4 入口求交 + M5 复核）
# ============================================================
async def handle_rag_retrieval(node, resolved_inputs, runtime) -> Dict[str, Any]:
    from base.plugins.agent.services.engine import rag as rag_engine
    from base.plugins.agent.services.vector_store import QdrantUnavailableError

    ctx = runtime["ctx"]
    config = (node.get("data") or {}).get("config") or {}
    # BUG-T15-008：契约字段 knowledge_base_refs 优先，兼容旧字段 kb_ids
    kb_ids = config.get("knowledge_base_refs") or config.get("kb_ids") or []
    query = resolved_inputs.get("query") or runtime["state"]["vars"].get("query") or ""
    if isinstance(query, (list, dict)):
        query = json.dumps(query, ensure_ascii=False)
    try:
        chunks = await rag_engine.retrieve(
            ctx.owner, kb_ids, str(query),
            top_k=int(config.get("top_k", 5)),
            score_threshold=config.get("score_threshold"),
        )
    except QdrantUnavailableError as e:
        raise NodeExecutionError("RAG_UNAVAILABLE", str(e), retryable=True) from e
    return {"status": "success", "outputs": {"chunks": chunks},
            "usage": {"resource_type": "kb_search", "amount": 1}}


# ============================================================
# http 节点（R-10 白名单 + DNS 二次校验）
# ============================================================
async def handle_http(node, resolved_inputs, runtime) -> Dict[str, Any]:
    import httpx

    config = (node.get("data") or {}).get("config") or {}
    flat = _flat_vars(runtime)
    method = assert_method_allowed(config.get("method", "GET"))
    url = await assert_url_allowed(render_template(config.get("url", ""), flat))
    headers = {
        k: render_template(str(v), flat)
        for k, v in (config.get("headers") or {}).items()
    }
    body = config.get("body")
    if isinstance(body, str):
        body = render_template(body, flat)
    timeout_s = min(float(config.get("timeout_s", MAX_TIMEOUT_SECONDS)), MAX_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=False) as client:
            response = await client.request(method, url, headers=headers, content=body)
        content = response.content[:MAX_RESPONSE_BYTES]
        try:
            parsed: Any = response.json()
        except Exception:
            parsed = content.decode("utf-8", errors="replace")
        outputs = {
            "status_code": response.status_code,
            "body": parsed,
            "headers": dict(response.headers),
        }
        return {"status": "success", "outputs": outputs}
    except httpx.TimeoutException as e:
        raise NodeExecutionError("HTTP_TIMEOUT", "http 请求超时", retryable=True) from e
    except httpx.HTTPError as e:
        raise NodeExecutionError("HTTP_ERROR", f"http 请求失败: {type(e).__name__}",
                                 retryable=True) from e


# ============================================================
# tool 节点（运行时授权复核）
# ============================================================
async def handle_tool(node, resolved_inputs, runtime) -> Dict[str, Any]:
    import asyncio as _asyncio

    from base.plugins.agent.tools.registry import ToolRegistry

    ctx = runtime["ctx"]
    config = (node.get("data") or {}).get("config") or {}
    tool_ref = config.get("tool_ref") or config.get("tool_name")
    if not tool_ref:
        raise NodeExecutionError("TOOL_UNAVAILABLE", "tool 节点未配置工具", retryable=False)
    if not await ctx.require_resource("tool", tool_ref):
        raise NodeCapabilityDenied(f"工具未授权: {tool_ref}")

    tool_class = ToolRegistry.get_tool(tool_ref)
    if tool_class is None:
        raise NodeExecutionError("TOOL_UNAVAILABLE", f"工具不存在: {tool_ref}", retryable=False)
    flat = _flat_vars(runtime)
    args = {
        k: render_template(v, flat) if isinstance(v, str) else v
        for k, v in (config.get("args") or {}).items()
    }
    result = tool_class.execute(**args)
    if _asyncio.iscoroutine(result):
        result = await result
    else:
        result = await _asyncio.to_thread(lambda: result)
    return {"status": "success", "outputs": {"result": result}}


# ============================================================
# code 节点（R-10：用户域永久拒绝，运行时双保险）
# ============================================================
async def handle_code(node, resolved_inputs, runtime) -> Dict[str, Any]:
    ctx = runtime["ctx"]
    if ctx.domain in (DOMAIN_CUS, DOMAIN_USR):
        raise NodeCapabilityDenied("用户域禁止执行 code 节点（R-10）")
    raise NodeCapabilityDenied("code 节点在当前执行后端未启用沙箱")


# ============================================================
# HITL 节点（F6：暂停 → 审批 → 注入结果变量继续）
# ============================================================
async def handle_hitl(node, resolved_inputs, runtime) -> Dict[str, Any]:
    ctx = runtime["ctx"]
    emit = runtime["emit"]
    control = runtime["control"]
    node_id = node["id"]
    config = (node.get("data") or {}).get("config") or {}

    # BUG-T15-008：契约字段 timeout_minutes（分）优先，×60 转秒；兼容旧字段 timeout_s（秒）
    if config.get("timeout_minutes") is not None:
        timeout_s = min(int(config["timeout_minutes"]) * 60, HITL_DEFAULT_TIMEOUT_S)
    else:
        timeout_s = min(int(config.get("timeout_s", HITL_DEFAULT_TIMEOUT_S)), HITL_DEFAULT_TIMEOUT_S)
    # BUG-T15-008：契约字段 on_timeout（reject/approve/escalate）优先，映射到引擎 timeout_action
    # reject → fail；approve → approve（超时自动通过，新增逻辑于下方异常分支）；escalate → fail（暂降级，升级通知后续完善）
    on_timeout = config.get("on_timeout")
    if on_timeout in ("reject", "escalate"):
        timeout_action = "fail"
    elif on_timeout == "approve":
        timeout_action = "approve"
    else:
        timeout_action = config.get("timeout_action", "fail")
    deadline = (datetime.now() + timedelta(seconds=timeout_s)).isoformat()
    assignee = {"type": config.get("assignee_mode", "self")}

    await emit(evt.EventType.RUN_PAUSED, node_id, evt.run_paused(node_id, assignee, deadline))
    try:
        import asyncio as _asyncio

        await _asyncio.wait_for(control.resume_event.wait(), timeout=timeout_s)
    except Exception:
        if timeout_action == "skip":
            logger.info(f"[engine] HITL 节点 {node_id} 超时跳过")
            return {"status": "success", "outputs": {"approved": None, "comment": "", "skipped": True}}
        # BUG-T15-008：契约 on_timeout=approve 映射（超时自动通过）
        if timeout_action == "approve":
            logger.info(f"[engine] HITL 节点 {node_id} 超时自动通过")
            return {"status": "success", "outputs": {"approved": True, "comment": "超时自动通过", "auto_approved": True}}
        raise HitlTimeout(node_id)

    control.throw_if_cancelled()
    # BUG-T15-014：resume 唤醒回执（供 resume API 唤醒确认；取消路径由 backend 捕获处回执）
    control.ack_event.set()
    payload = control.resume_payload or {}
    outputs = {
        "approved": bool(payload.get("approved")),
        "comment": payload.get("comment", ""),
    }
    runtime["state"]["vars"]["hitl"] = outputs
    return {"status": "paused", "outputs": outputs}


# ============================================================
# loop / sub_workflow / sub_agent
# ============================================================
async def handle_loop(node, resolved_inputs, runtime) -> Dict[str, Any]:
    config = (node.get("data") or {}).get("config") or {}
    max_iterations = min(int(config.get("max_iterations", 1)), LOOP_MAX_ITERATIONS)
    items = resolved_inputs.get("items")
    body = config.get("body") or {}
    run_subgraph = runtime["run_subgraph"]
    depth = runtime["depth"]

    results: List[Any] = []
    if isinstance(items, list):
        iterations = min(len(items), max_iterations)
        iterable = [(i, items[i]) for i in range(iterations)]
    else:
        iterable = [(i, None) for i in range(max_iterations)]

    for index, item in iterable:
        runtime["control"].throw_if_cancelled()
        sub_inputs = {"item": item, "index": index, **runtime["state"]["vars"]}
        if body.get("nodes"):
            sub_result = await run_subgraph(body, sub_inputs, depth + 1)
            results.append(sub_result.get("outputs"))
        else:
            results.append({"index": index, "item": item})
    return {"status": "success", "outputs": {"results": results, "count": len(results)}}


async def handle_sub_workflow(node, resolved_inputs, runtime) -> Dict[str, Any]:
    """子工作流：绑定发布版本快照内联执行（E-108 引用有效性编辑期已校验）"""
    from base.plugins.agent.models.workflow_version import WorkflowVersion

    config = (node.get("data") or {}).get("config") or {}
    # BUG-T15-008：契约字段 workflow_ref 优先，兼容旧字段 workflow_id
    workflow_id = config.get("workflow_ref") or config.get("workflow_id")
    version_id = config.get("version_id")
    if not workflow_id:
        raise NodeExecutionError("SUB_WORKFLOW_INVALID", "sub_workflow 未配置 workflow_id",
                                 retryable=False)
    if version_id:
        version = await WorkflowVersion.get_or_none(id=version_id, status="published")
    else:
        version = await WorkflowVersion.filter(
            workflow_id=workflow_id, status="published"
        ).order_by("-version_no").first()
    if version is None:
        raise NodeExecutionError("SUB_WORKFLOW_INVALID", "子工作流版本失效或不存在",
                                 retryable=False)
    sub_result = await runtime["run_subgraph"](version.graph_json, resolved_inputs,
                                               runtime["depth"] + 1)
    return {"status": "success", "outputs": dict(sub_result.get("outputs") or {})}


async def handle_sub_agent(node, resolved_inputs, runtime) -> Dict[str, Any]:
    """子智能体：以其 v2 图内联执行（v1 旧图由 T9 转换器升级后可用）"""
    from base.plugins.agent.models.agent import Agent

    config = (node.get("data") or {}).get("config") or {}
    # BUG-T15-008：契约字段 agent_ref 优先，兼容旧字段 agent_id
    agent_id = config.get("agent_ref") or config.get("agent_id")
    if not agent_id:
        raise NodeExecutionError("SUB_AGENT_INVALID", "sub_agent 未配置 agent_id", retryable=False)
    if not await runtime["ctx"].require_resource("agent", agent_id):
        raise NodeCapabilityDenied(f"子智能体未授权: {agent_id}")
    agent = await Agent.get_or_none(id=agent_id)
    if agent is None or not agent.graph_definition:
        raise NodeExecutionError("SUB_AGENT_INVALID", "子智能体不存在或未配置图", retryable=False)
    graph = agent.graph_definition
    if isinstance(graph, str):
        graph = json.loads(graph)
    sub_result = await runtime["run_subgraph"](graph, resolved_inputs, runtime["depth"] + 1)
    return {"status": "success", "outputs": dict(sub_result.get("outputs") or {})}


NODE_HANDLERS: Dict[str, Handler] = {
    "start": handle_start,
    "end": handle_end,
    "template": handle_template,
    "condition": handle_condition,
    "llm": handle_llm,
    "rag_retrieval": handle_rag_retrieval,
    "http": handle_http,
    "tool": handle_tool,
    "code": handle_code,
    "hitl": handle_hitl,
    "loop": handle_loop,
    "sub_workflow": handle_sub_workflow,
    "sub_agent": handle_sub_agent,
}
