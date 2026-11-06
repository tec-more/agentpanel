"""
M3 Schema v2 服务端校验器（R-03：服务端校验为唯一安全边界，前端校验仅用于体验）

溯源：
- docs/arch/04-核心流程与接口契约.md §3（Schema v2 结构，VueFlow 同构）、§4.1（变量类型 12 类）、
  §4.3（用户侧节点能力开关 C-04）
- docs/用户侧智能体设计流PRD.md §4.3（类型兼容矩阵）、§4.5（E-101~E-113 错误码语义）、§5（节点定义）
- docs/arch/06 R-03/R-10（用户域禁 code 节点；http 节点强制域名白名单）

设计：
- 纯函数核心 validate_graph_structure()：无 DB、无 IO、无副作用，输入 graph dict 输出结构化错误列表
- 资源授权（E-110）与子工作流引用有效性（E-108）依赖 DB，经注入的异步检查器完成，
  由 validate_graph() 异步入口编排；不注入即跳过（保持纯函数可测）
- 输出统一为 [{code, node_id?, edge_id?, level, message, ...}]，不抛异常（R-15：校验错误携带 E-1xx 明细）

错误码段位（PRD §4.5 为准；arch/04 §4.1 与 F8 中 E-104/E-112 的表述与 PRD §4.5 不一致，
按任务基线以 PRD §4.5 语义实现）：
- E-100（服务端补充段）：结构/Schema/必填配置错误（PRD 未编号，服务端兜底）
- E-101 类型不兼容 / E-102 必填输入未连接 / E-103 成环 / E-104 重复连线
- E-105 输入端已占用 / E-106 输出端口悬空（警告）/ E-107 引用未声明变量
- E-108 子工作流版本失效/被删除 / E-109 未授权节点类型（含用户域 code/vector、http 域名未入白名单）
- E-110 未授权资源（模型/知识库/工具/子Agent）/ E-111 循环缺退出条件或超上限 / E-112 HITL 未配置
- E-113 运行期配额超限（仅运行期产生，编辑器校验不输出）
"""
import ipaddress
import os
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Set
from urllib.parse import urlparse

# ============================================================
# 常量定义
# ============================================================

DOMAIN_ADMIN = "admin"  # 后台画布域（usr 管理侧）：节点类型不受限（现有后台画布兼容）
DOMAIN_USER = "user"    # 用户域（cus / 用户侧 usr）：节点白名单严格（C-04/R-10）

LEVEL_ERROR = "error"
LEVEL_WARNING = "warning"

# 节点类型别名归一（Schema v2 与 PRD 命名兼容）
_TYPE_ALIASES = {
    "trigger": "start",
    "rag": "rag_retrieval",
    "tool_call": "tool",
}

# 用户域开放节点（arch/04 §4.3，10 类）
USER_OPEN_NODE_TYPES = {
    "start", "end", "llm", "rag_retrieval", "condition",
    "loop", "sub_workflow", "hitl", "sub_agent", "template",
}
# 用户域受控节点：http（域名白名单）；tool（开放但 tool_ref 必须已授权，走 E-110）
USER_CONTROLLED_NODE_TYPES = {"http", "tool"}
# 用户域永久禁用（R-10 code；PRD §5.11 vector P0 不开放）
USER_FORBIDDEN_NODE_TYPES = {"code", "vector"}

KNOWN_NODE_TYPES = (
    USER_OPEN_NODE_TYPES | USER_CONTROLLED_NODE_TYPES | USER_FORBIDDEN_NODE_TYPES
)

# 变量类型（arch/04 §4.1 12 类 + PRD §4.2 integer/image/message[]/document/chunk[]/unknown）
_SCALAR_TYPES = {
    "string", "number", "integer", "boolean", "date",
    "file", "image", "object", "chunk", "message", "document",
    "any", "unknown", "secret", "stream",
}

_TEMPLATE_REF_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*?)\s*\}\}")
_ARRAY_RE = re.compile(r"^array<(.+)>$")


# ============================================================
# 错误构造
# ============================================================

def _issue(code: str, message: str, *, node_id: Optional[str] = None,
           edge_id: Optional[str] = None, level: str = LEVEL_ERROR,
           field: Optional[str] = None, resource: Optional[str] = None,
           missing: Optional[list] = None) -> Dict[str, Any]:
    item: Dict[str, Any] = {"code": code, "level": level, "message": message}
    if node_id is not None:
        item["node_id"] = node_id
    if edge_id is not None:
        item["edge_id"] = edge_id
    if field is not None:
        item["field"] = field
    if resource is not None:
        item["resource"] = resource
    if missing is not None:
        item["missing"] = missing
    return item


# ============================================================
# 类型系统（PRD §4.2/§4.3）
# ============================================================

def normalize_type(t: Any) -> str:
    """归一类型写法：chunk[] → array<chunk>；message[] → array<message>；去空白小写"""
    if not isinstance(t, str):
        return "unknown"
    t = t.strip().lower()
    if t.endswith("[]"):
        return f"array<{t[:-2].strip()}>"
    return t


def _array_inner(t: str) -> Optional[str]:
    m = _ARRAY_RE.match(t)
    return m.group(1).strip() if m else None


def is_valid_type(t: Any) -> bool:
    nt = normalize_type(t)
    inner = _array_inner(nt)
    if inner is not None:
        return is_valid_type(inner)
    return nt in _SCALAR_TYPES


def types_compatible(src: Any, dst: Any) -> bool:
    """
    类型兼容矩阵（PRD §4.3）：
    同型直连；integer→number 加宽；任意→any 透传；any→具体禁止；
    array<T>→array<any> 允许；array<T>→array<U> 按元素兼容；unknown→任意禁止。
    """
    s, d = normalize_type(src), normalize_type(dst)
    if d == "any":
        return s != "unknown"
    if s == "any":
        return d == "any"
    if s == "unknown" or d == "unknown":
        return False
    if s == d:
        return True
    if s == "integer" and d == "number":
        return True
    s_inner, d_inner = _array_inner(s), _array_inner(d)
    if s_inner is not None and d_inner is not None:
        return types_compatible(s_inner, d_inner)
    return False


# ============================================================
# 节点契约（PRD §5：config 必填与约束；必填输入端口）
# ============================================================

def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) \
        or (isinstance(v, (list, dict)) and len(v) == 0)


def _check_llm(cfg: dict, nid: str, issues: list) -> None:
    # O-01：契约字段优先，兼容旧字段 model_id/modelId、prompt_template/prompt（对齐引擎 nodes.py BUG-T15-008）
    model_ref = cfg.get("model_ref") or cfg.get("model_id") or cfg.get("modelId")
    if _is_blank(model_ref):
        issues.append(_issue("E-100", f"llm 节点缺少必填配置 model_ref", node_id=nid, field="model_ref"))
    user_prompt = cfg.get("user_prompt") or cfg.get("prompt_template") or cfg.get("prompt")
    if _is_blank(user_prompt):
        issues.append(_issue("E-100", f"llm 节点缺少必填配置 user_prompt", node_id=nid, field="user_prompt"))
    temp = cfg.get("temperature")
    if temp is not None and not (isinstance(temp, (int, float)) and 0 <= temp <= 2):
        issues.append(_issue("E-100", "llm 节点 temperature 须在 0-2 之间", node_id=nid, field="temperature"))
    hm = cfg.get("history_mode")
    if hm is not None and hm not in ("none", "last_n", "summary"):
        issues.append(_issue("E-100", "llm 节点 history_mode 非法", node_id=nid, field="history_mode"))


def _check_rag(cfg: dict, nid: str, issues: list) -> None:
    # O-01：契约字段优先，兼容旧字段 kb_ids；or 语义使 knowledge_base_refs 为 None/空时兜底（对齐引擎）
    refs = cfg.get("knowledge_base_refs") or cfg.get("kb_ids")
    if _is_blank(refs) or not isinstance(refs, list):
        issues.append(_issue("E-100", "rag_retrieval 节点缺少必填配置 knowledge_base_refs（≥1）",
                             node_id=nid, field="knowledge_base_refs"))
    top_k = cfg.get("top_k")
    if top_k is None or not isinstance(top_k, int) or not (1 <= top_k <= 50):
        issues.append(_issue("E-100", "rag_retrieval 节点 top_k 必填且须在 1-50 之间",
                             node_id=nid, field="top_k"))


def _check_condition(cfg: dict, nid: str, issues: list) -> None:
    mode = cfg.get("mode", "binary")
    if mode not in ("binary", "multi_case"):
        issues.append(_issue("E-100", "condition 节点 mode 须为 binary/multi_case", node_id=nid, field="mode"))
    rules = cfg.get("rules")
    if not isinstance(rules, list) or len(rules) < 1:
        issues.append(_issue("E-100", "condition 节点 rules 必填且至少 1 条", node_id=nid, field="rules"))
    else:
        for i, r in enumerate(rules):
            if not isinstance(r, dict) or _is_blank(r.get("field")) or _is_blank(r.get("operator")):
                issues.append(_issue("E-100", f"condition 节点 rules[{i}] 缺少 field/operator",
                                     node_id=nid, field=f"rules[{i}]"))


def _check_loop(cfg: dict, nid: str, issues: list) -> None:
    loop_type = cfg.get("loop_type", "array")
    if loop_type not in ("fixed", "array", "while"):
        issues.append(_issue("E-100", "loop 节点 loop_type 须为 fixed/array/while", node_id=nid, field="loop_type"))
    max_it = cfg.get("max_iterations")
    if max_it is None or not isinstance(max_it, int) or max_it < 1:
        issues.append(_issue("E-111", "loop 节点 max_iterations 必填且 ≥1", node_id=nid, field="max_iterations"))
    elif max_it > 100:
        issues.append(_issue("E-111", f"loop 节点 max_iterations={max_it} 超出上限 100",
                             node_id=nid, field="max_iterations"))
    if loop_type == "while" and _is_blank(cfg.get("condition")):
        issues.append(_issue("E-111", "loop 节点 while 模式缺少退出条件 condition",
                             node_id=nid, field="condition"))
    if loop_type == "fixed":
        fc = cfg.get("fixed_count")
        if fc is None or not isinstance(fc, int) or fc < 1:
            issues.append(_issue("E-100", "loop 节点 fixed 模式 fixed_count 必填且 ≥1",
                                 node_id=nid, field="fixed_count"))


def _check_sub_workflow(cfg: dict, nid: str, issues: list) -> None:
    # O-01-ext：契约字段优先，兼容旧字段 workflow_id（对齐引擎 nodes.py BUG-T15-008）
    wf_ref = cfg.get("workflow_ref") or cfg.get("workflow_id")
    if _is_blank(wf_ref):
        issues.append(_issue("E-100", "sub_workflow 节点缺少必填配置 workflow_ref",
                             node_id=nid, field="workflow_ref"))
    policy = cfg.get("version_policy", "pinned")
    if policy not in ("pinned", "latest"):
        issues.append(_issue("E-100", "sub_workflow 节点 version_policy 须为 pinned/latest",
                             node_id=nid, field="version_policy"))
    if policy == "pinned" and cfg.get("pinned_version") is None:
        issues.append(_issue("E-100", "sub_workflow 节点 pinned 模式缺少 pinned_version",
                             node_id=nid, field="pinned_version"))
    if _is_blank(cfg.get("input_mapping")) or not isinstance(cfg.get("input_mapping"), dict):
        issues.append(_issue("E-100", "sub_workflow 节点 input_mapping 必填（对象）",
                             node_id=nid, field="input_mapping"))
    depth = cfg.get("max_depth")
    if depth is not None and (not isinstance(depth, int) or not (1 <= depth <= 5)):
        issues.append(_issue("E-100", "sub_workflow 节点 max_depth 须在 1-5 之间", node_id=nid, field="max_depth"))


def _check_hitl(cfg: dict, nid: str, issues: list) -> None:
    mode = cfg.get("assignee_mode", "self")
    if mode not in ("self", "org_role", "specific_user"):
        issues.append(_issue("E-112", f"hitl 节点 assignee_mode 非法: {mode}",
                             node_id=nid, field="assignee_mode"))
    elif mode != "self" and _is_blank(cfg.get("assignee_refs")):
        issues.append(_issue("E-112", "hitl 节点未配置审批人 assignee_refs",
                             node_id=nid, field="assignee_refs"))
    # O-01：契约字段优先，兼容旧字段 timeout_s（秒→分钟换算）、timeout_action（approve→approve，其余→reject）
    timeout = cfg.get("timeout_minutes")
    if timeout is None and isinstance(cfg.get("timeout_s"), int):
        timeout = cfg["timeout_s"] // 60  # 旧字段 timeout_s 秒→分钟（对齐引擎 BUG-T15-008 口径）
    if timeout is None or not isinstance(timeout, int) or not (5 <= timeout <= 10080):
        issues.append(_issue("E-112", "hitl 节点 timeout_minutes 必填且须在 5-10080 之间",
                             node_id=nid, field="timeout_minutes"))
    on_timeout = cfg.get("on_timeout")
    if on_timeout is None:
        ta = cfg.get("timeout_action", "fail")  # 旧字段映射：approve→approve，fail/其他→reject
        on_timeout = "approve" if ta == "approve" else "reject"
    if on_timeout not in ("reject", "approve", "escalate"):
        issues.append(_issue("E-112", "hitl 节点 on_timeout 非法", node_id=nid, field="on_timeout"))
    elif on_timeout == "escalate" and _is_blank(cfg.get("escalate_to")):
        issues.append(_issue("E-112", "hitl 节点 on_timeout=escalate 缺少 escalate_to",
                             node_id=nid, field="escalate_to"))


def _check_sub_agent(cfg: dict, nid: str, issues: list) -> None:
    # O-01-ext：契约字段优先，兼容旧字段 agent_id（对齐引擎 nodes.py BUG-T15-008）
    agent_ref = cfg.get("agent_ref") or cfg.get("agent_id")
    if _is_blank(agent_ref):
        issues.append(_issue("E-100", "sub_agent 节点缺少必填配置 agent_ref", node_id=nid, field="agent_ref"))
    steps = cfg.get("max_steps")
    if steps is None or not isinstance(steps, int) or not (1 <= steps <= 30):
        issues.append(_issue("E-100", "sub_agent 节点 max_steps 必填且须在 1-30 之间",
                             node_id=nid, field="max_steps"))
    mm = cfg.get("memory_mode")
    if mm is not None and mm not in ("private", "none"):
        issues.append(_issue("E-100", "sub_agent 节点 memory_mode 须为 private/none",
                             node_id=nid, field="memory_mode"))


def _check_tool(cfg: dict, nid: str, issues: list) -> None:
    if _is_blank(cfg.get("tool_ref")):
        issues.append(_issue("E-100", "tool 节点缺少必填配置 tool_ref", node_id=nid, field="tool_ref"))
    if cfg.get("param_mapping") is None or not isinstance(cfg.get("param_mapping"), dict):
        issues.append(_issue("E-100", "tool 节点 param_mapping 必填（对象）", node_id=nid, field="param_mapping"))


def _check_vector(cfg: dict, nid: str, issues: list) -> None:
    if _is_blank(cfg.get("collection_ref")):
        issues.append(_issue("E-100", "vector 节点缺少必填配置 collection_ref", node_id=nid, field="collection_ref"))
    if cfg.get("operation") not in ("upsert", "update", "delete", "query"):
        issues.append(_issue("E-100", "vector 节点 operation 必填（upsert/update/delete/query）",
                             node_id=nid, field="operation"))


def _check_template(cfg: dict, nid: str, issues: list) -> None:
    if _is_blank(cfg.get("template")):
        issues.append(_issue("E-100", "template 节点缺少必填配置 template", node_id=nid, field="template"))


def _check_http(cfg: dict, nid: str, issues: list) -> None:
    if _is_blank(cfg.get("url")):
        issues.append(_issue("E-100", "http 节点缺少必填配置 url", node_id=nid, field="url"))


_NODE_CONFIG_CHECKERS = {
    "llm": _check_llm,
    "rag_retrieval": _check_rag,
    "condition": _check_condition,
    "loop": _check_loop,
    "sub_workflow": _check_sub_workflow,
    "hitl": _check_hitl,
    "sub_agent": _check_sub_agent,
    "tool": _check_tool,
    "vector": _check_vector,
    "template": _check_template,
    "http": _check_http,
}

# 必填输入端口（PRD §5 出入参：必填=是）；loop.items 在 array 模式必填
_NODE_REQUIRED_INPUTS: Dict[str, List[str]] = {
    "rag_retrieval": ["query"],
    "condition": ["input"],
    "loop": ["body_in"],
    "sub_workflow": ["inputs"],
    "hitl": ["context"],
    "sub_agent": ["task"],
    "tool": ["params"],
}

# 资源引用（E-110）：(配置字段, resource_type, 是否列表)
_NODE_RESOURCE_REFS = {
    "llm": [("model_ref", "model", False)],
    "rag_retrieval": [("knowledge_base_refs", "kb", True), ("kb_ids", "kb", True)],
    "tool": [("tool_ref", "tool", False)],
    "sub_agent": [("agent_ref", "agent", False)],
}


# ============================================================
# http 域名白名单（R-10；占位读取配置，默认空=拒绝）
# ============================================================

def load_http_allowed_domains() -> List[str]:
    """读取 http 节点域名白名单配置（环境变量 WORKFLOW_HTTP_ALLOWED_DOMAINS，逗号分隔）。
    默认空 = 用户域拒绝一切 http 节点（任务口径：占位，管理员后续维护）。"""
    raw = os.environ.get("WORKFLOW_HTTP_ALLOWED_DOMAINS", "") or ""
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _host_in_whitelist(host: str, whitelist: Sequence[str]) -> bool:
    host = (host or "").lower()
    for d in whitelist:
        d = d.lower()
        if host == d or host.endswith("." + d):
            return True
    return False


def _is_internal_host(host: str) -> bool:
    """内网段判定（arch/04 §4.3：禁 10/172.16/192.168/127/169.254 与本机名）"""
    if not host:
        return True
    if host in ("localhost",):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False  # 域名交由白名单判定；DNS 二次校验在运行期（R-10，T6）


# ============================================================
# 纯函数结构校验（无副作用）
# ============================================================

def validate_graph_structure(
    graph: Any,
    *,
    domain: str = DOMAIN_ADMIN,
    http_allowed_domains: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Schema v2 结构与图校验（纯函数，无 DB/IO）。

    Returns:
        结构化错误列表 [{code, node_id?, edge_id?, level, message, ...}]；空列表 = 通过
    """
    issues: List[Dict[str, Any]] = []
    if not isinstance(graph, dict):
        return [_issue("E-100", "graph 必须是对象")]

    # ---- 顶层结构 ----
    sv = graph.get("schema_version")
    if sv not in (2, "2", "v2"):
        issues.append(_issue("E-100", f"schema_version 必须为 2，实际: {sv!r}", field="schema_version"))
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    variables = graph.get("variables")
    settings = graph.get("settings")
    if not isinstance(nodes, list):
        issues.append(_issue("E-100", "nodes 必填且为数组", field="nodes"))
        nodes = []
    if not isinstance(edges, list):
        issues.append(_issue("E-100", "edges 必填且为数组", field="edges"))
        edges = []
    if variables is None:
        variables = []
    if not isinstance(variables, list):
        issues.append(_issue("E-100", "variables 必须为数组", field="variables"))
        variables = []
    if settings is not None and not isinstance(settings, dict):
        issues.append(_issue("E-100", "settings 必须为对象", field="settings"))

    # ---- 节点基础与去重 ----
    node_map: Dict[str, dict] = {}
    node_types: Dict[str, str] = {}
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            issues.append(_issue("E-100", f"nodes[{idx}] 必须为对象"))
            continue
        nid = node.get("id")
        if _is_blank(nid):
            issues.append(_issue("E-100", f"nodes[{idx}] 缺少 id"))
            continue
        nid = str(nid)
        if nid in node_map:
            issues.append(_issue("E-100", f"节点 id 重复: {nid}", node_id=nid))
            continue
        node_map[nid] = node
        ntype = _TYPE_ALIASES.get(str(node.get("type", "")).strip(), str(node.get("type", "")).strip())
        node_types[nid] = ntype
        if not isinstance(node.get("position"), dict):
            issues.append(_issue("E-100", f"节点 {nid} 缺少 position", node_id=nid, field="position"))
        data = node.get("data")
        if not isinstance(data, dict):
            issues.append(_issue("E-100", f"节点 {nid} 缺少 data 对象", node_id=nid, field="data"))

    # ---- start/end 唯一性与出入边约束（PRD §5.1：每个工作流有且仅 1 个触发节点）----
    starts = [n for n, t in node_types.items() if t == "start"]
    ends = [n for n, t in node_types.items() if t == "end"]
    if len(starts) != 1:
        issues.append(_issue("E-100", f"必须有且仅有 1 个 start 节点，实际 {len(starts)} 个"))
    if len(ends) != 1:
        issues.append(_issue("E-100", f"必须有且仅有 1 个 end 节点，实际 {len(ends)} 个"))

    # ---- 节点类型域开关（E-109）----
    for nid, ntype in node_types.items():
        if ntype not in KNOWN_NODE_TYPES:
            issues.append(_issue("E-109", f"未知节点类型: {ntype}", node_id=nid))
            continue
        if domain == DOMAIN_USER:
            if ntype in USER_FORBIDDEN_NODE_TYPES:
                if ntype == "code":
                    msg = "code 节点在用户域永久禁用（R-10）"
                else:
                    msg = f"{ntype} 节点未对用户域开放（P0）"
                issues.append(_issue("E-109", msg, node_id=nid))
            elif ntype == "http":
                wl = list(http_allowed_domains) if http_allowed_domains is not None \
                    else load_http_allowed_domains()
                cfg = (node_map[nid].get("data") or {}).get("config") or {}
                url = cfg.get("url", "")
                host = urlparse(str(url)).hostname or ""
                if not wl:
                    issues.append(_issue("E-109", "http 节点未开放：域名白名单为空（默认拒绝）",
                                         node_id=nid, field="url"))
                elif _is_internal_host(host):
                    issues.append(_issue("E-109", f"http 节点目标 {host} 为内网地址，禁止访问",
                                         node_id=nid, field="url"))
                elif not _host_in_whitelist(host, wl):
                    issues.append(_issue("E-109", f"http 节点域名 {host} 不在白名单内",
                                         node_id=nid, field="url"))

    # ---- 节点 config 校验（PRD §5）----
    for nid, node in node_map.items():
        ntype = node_types.get(nid, "")
        if ntype not in KNOWN_NODE_TYPES:
            continue
        data = node.get("data") or {}
        cfg = data.get("config")
        if cfg is None:
            cfg = {}
        if not isinstance(cfg, dict):
            issues.append(_issue("E-100", f"节点 {nid} config 必须为对象", node_id=nid, field="config"))
            continue
        checker = _NODE_CONFIG_CHECKERS.get(ntype)
        if checker is not None:
            checker(cfg, nid, issues)

    # ---- 变量声明 ----
    var_names: Set[str] = set()
    for i, v in enumerate(variables):
        if not isinstance(v, dict) or _is_blank(v.get("name")):
            issues.append(_issue("E-100", f"variables[{i}] 缺少 name", field=f"variables[{i}]"))
            continue
        name = str(v["name"])
        if name in var_names:
            issues.append(_issue("E-100", f"变量名重复: {name}", field="variables"))
        var_names.add(name)
        if not is_valid_type(v.get("type", "string")):
            issues.append(_issue("E-100", f"变量 {name} 类型非法: {v.get('type')!r}", field="variables"))

    # ---- 节点输出端口表（node_id -> {output_name: type}）----
    outputs_of: Dict[str, Dict[str, str]] = {}
    for nid, node in node_map.items():
        outs: Dict[str, str] = {}
        data = node.get("data") or {}
        for o in data.get("outputs") or []:
            if isinstance(o, dict) and not _is_blank(o.get("name")):
                outs[str(o["name"])] = normalize_type(o.get("type", "any"))
        outputs_of[nid] = outs

    all_output_names: Set[str] = set()
    for outs in outputs_of.values():
        all_output_names.update(outs.keys())

    def _ref_exists(ref: str) -> bool:
        """bare 引用：已声明变量或任一节点输出；dotted 引用：node.output 必须存在"""
        if "." in ref:
            rn, ro = ref.split(".", 1)
            return rn in outputs_of and ro in outputs_of[rn]
        return ref in var_names or ref in all_output_names

    # ---- 输入绑定校验（E-102/E-107/E-101）----
    referenced_outputs: Set[str] = set()  # "node.output"，供 E-106 判定
    for nid, node in node_map.items():
        ntype = node_types.get(nid, "")
        data = node.get("data") or {}
        inputs = data.get("inputs") or []
        if not isinstance(inputs, list):
            issues.append(_issue("E-100", f"节点 {nid} inputs 必须为数组", node_id=nid, field="inputs"))
            inputs = []
        bound_names: Set[str] = set()
        for inp in inputs:
            if not isinstance(inp, dict):
                continue
            iname = inp.get("name")
            if _is_blank(iname):
                issues.append(_issue("E-100", f"节点 {nid} 存在未命名输入", node_id=nid, field="inputs"))
                continue
            iname = str(iname)
            bound_names.add(iname)
            from_ref = inp.get("from")
            if _is_blank(from_ref):
                continue  # 未连接：若是必填端口由下方 E-102 统一报
            from_ref = str(from_ref)
            referenced_outputs.add(from_ref)
            if "." not in from_ref:
                issues.append(_issue("E-107", f"节点 {nid} 输入 {iname} 的 from 引用 {from_ref} 无效"
                                     f"（须为 node.output 形式）", node_id=nid, field=iname))
                continue
            src_node, src_out = from_ref.split(".", 1)
            if src_node not in outputs_of:
                issues.append(_issue("E-107", f"节点 {nid} 输入 {iname} 引用了不存在的节点 {src_node}",
                                     node_id=nid, field=iname))
                continue
            if src_out not in outputs_of[src_node]:
                issues.append(_issue("E-107",
                                     f"节点 {nid} 输入 {iname} 引用了节点 {src_node} 未声明的输出 {src_out}",
                                     node_id=nid, field=iname))
                continue
            src_type = outputs_of[src_node][src_out]
            dst_type = inp.get("type")
            if dst_type is not None and not types_compatible(src_type, dst_type):
                issues.append(_issue(
                    "E-101",
                    f"节点 {nid} 输入 {iname} 类型不兼容: {normalize_type(src_type)} → {normalize_type(dst_type)}",
                    node_id=nid, field=iname))

        # E-102 必填输入未连接（按 PRD §5 端口契约）
        for req_port in _NODE_REQUIRED_INPUTS.get(ntype, []):
            hit = next((i for i in inputs if isinstance(i, dict) and str(i.get("name")) == req_port), None)
            if hit is None or _is_blank(hit.get("from")):
                issues.append(_issue("E-102", f"节点 {nid} 必填输入 {req_port} 未连接",
                                     node_id=nid, field=req_port))
        if ntype == "loop":
            cfg = data.get("config") or {}
            if cfg.get("loop_type", "array") == "array":
                hit = next((i for i in inputs if isinstance(i, dict) and str(i.get("name")) == "items"), None)
                if hit is None or _is_blank(hit.get("from")):
                    issues.append(_issue("E-102", "loop 节点 array 模式必填输入 items 未连接",
                                         node_id=nid, field="items"))

    # ---- 模板插值与条件字段变量引用（E-107）----
    def _scan_refs(text: Any, nid: str, field: str) -> None:
        if not isinstance(text, str):
            return
        for m in _TEMPLATE_REF_RE.finditer(text):
            ref = m.group(1)
            if not _ref_exists(ref):
                issues.append(_issue("E-107", f"节点 {nid} 配置 {field} 引用了未声明变量 {{{{{ref}}}}}",
                                     node_id=nid, field=field))
            elif "." in ref:
                referenced_outputs.add(ref)

    for nid, node in node_map.items():
        data = node.get("data") or {}
        cfg = data.get("config") or {}
        for key in ("user_prompt", "system_prompt", "prompt_template", "template", "url", "body"):
            if key in cfg:
                _scan_refs(cfg.get(key), nid, key)
        # condition / loop.while 的规则字段引用
        if node_types.get(nid) == "condition":
            for i, r in enumerate(cfg.get("rules") or []):
                if isinstance(r, dict) and not _is_blank(r.get("field")):
                    f = str(r["field"])
                    if not _ref_exists(f):
                        issues.append(_issue("E-107", f"condition 节点 rules[{i}].field 引用未声明变量 {f}",
                                             node_id=nid, field=f"rules[{i}]"))
        if node_types.get(nid) == "loop" and isinstance(cfg.get("condition"), dict):
            f = cfg["condition"].get("field")
            if not _is_blank(f) and not _ref_exists(str(f)):
                issues.append(_issue("E-107", f"loop 节点退出条件引用未声明变量 {f}",
                                     node_id=nid, field="condition"))

    # ---- 边校验（E-104/E-105/E-103）----
    edge_keys: Set[tuple] = set()
    in_handle_count: Dict[tuple, int] = {}
    adjacency: Dict[str, List[str]] = {nid: [] for nid in node_map}
    in_degree: Dict[str, int] = {nid: 0 for nid in node_map}
    valid_edges: List[dict] = []
    for idx, e in enumerate(edges):
        if not isinstance(e, dict):
            issues.append(_issue("E-100", f"edges[{idx}] 必须为对象"))
            continue
        eid = str(e.get("id") or f"e_{idx}")
        src, tgt = e.get("source"), e.get("target")
        sh, th = str(e.get("sourceHandle") or "out"), str(e.get("targetHandle") or "in")
        if src not in node_map or tgt not in node_map:
            issues.append(_issue("E-100", f"边 {eid} 端点不存在: {src} -> {tgt}", edge_id=eid))
            continue
        key = (str(src), sh, str(tgt), th)
        if key in edge_keys:
            issues.append(_issue("E-104", f"重复连线: {src}.{sh} -> {tgt}.{th}", edge_id=eid))
        edge_keys.add(key)
        if str(src) == str(tgt):
            issues.append(_issue("E-103", f"节点 {src} 不允许自连", edge_id=eid, node_id=str(src)))
        # E-105 输入端已占用（声明 multiplicity=multi 的输入端口除外）
        tgt_node = node_map[str(tgt)]
        tgt_inputs = ((tgt_node.get("data") or {}).get("inputs")) or []
        port = next((i for i in tgt_inputs if isinstance(i, dict) and str(i.get("name")) == th), None)
        multi = isinstance(port, dict) and port.get("multiplicity") == "multi"
        if not multi:
            tk = (str(tgt), th)
            in_handle_count[tk] = in_handle_count.get(tk, 0) + 1
            if in_handle_count[tk] > 1:
                issues.append(_issue("E-105", f"节点 {tgt} 输入端 {th} 已被占用", edge_id=eid, node_id=str(tgt)))
        adjacency[str(src)].append(str(tgt))
        in_degree[str(tgt)] += 1
        valid_edges.append(e)

    # start 不允许入边；end 不允许出边（PRD §5.1/图结构）
    for nid in starts:
        if in_degree.get(nid, 0) > 0:
            issues.append(_issue("E-100", f"start 节点 {nid} 不允许配置入边", node_id=nid))
    for nid in ends:
        if adjacency.get(nid):
            issues.append(_issue("E-100", f"end 节点 {nid} 不允许配置出边", node_id=nid))

    # ---- 环检测（E-103，Kahn 拓扑）----
    deg = dict(in_degree)
    queue = [n for n in node_map if deg[n] == 0]
    visited = 0
    while queue:
        cur = queue.pop()
        visited += 1
        for nxt in adjacency.get(cur, []):
            deg[nxt] -= 1
            if deg[nxt] == 0:
                queue.append(nxt)
    if visited < len(node_map):
        in_cycle = [n for n, d in deg.items() if d > 0]
        issues.append(_issue("E-103", f"图存在环，涉及节点: {', '.join(sorted(in_cycle))}",
                             node_id=in_cycle[0] if in_cycle else None))

    # ---- 连通性：所有节点须从 start 可达 ----
    if starts and node_map:
        seen: Set[str] = set()
        stack = [starts[0]]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adjacency.get(cur, []))
        unreachable = sorted(set(node_map) - seen)
        for nid in unreachable:
            issues.append(_issue("E-100", f"节点 {nid} 从 start 不可达（孤立节点）", node_id=nid))

    # ---- E-106 输出端口悬空（警告级，发布前统一检查）----
    for nid, outs in outputs_of.items():
        if not outs:
            continue
        dangling = [name for name in outs if f"{nid}.{name}" not in referenced_outputs]
        if dangling and len(dangling) == len(outs) and node_types.get(nid) not in ("end",):
            issues.append(_issue(
                "E-106", f"节点 {nid} 的输出端口全部悬空: {', '.join(sorted(dangling))}",
                node_id=nid, level=LEVEL_WARNING, missing=sorted(dangling)))

    return issues


# ============================================================
# 异步入口：资源授权（E-110）与子工作流引用（E-108）
# ============================================================

ResourceChecker = Callable[[str, List[str]], Awaitable[Set[str]]]
SubWorkflowChecker = Callable[[str, Optional[int]], Awaitable[Optional[str]]]


async def validate_graph(
    graph: Any,
    *,
    domain: str = DOMAIN_ADMIN,
    resource_checker: Optional[ResourceChecker] = None,
    subworkflow_checker: Optional[SubWorkflowChecker] = None,
    http_allowed_domains: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    全量校验（R-03）：纯结构校验 + 资源授权校验（E-110）+ 子工作流引用有效性（E-108）。

    Args:
        graph: Schema v2 图 JSON
        domain: admin（后台画布，节点类型不限）/ user（用户域，白名单严格）
        resource_checker: 注入的资源授权批量判定 (resource_type, ids) -> 已授权 id 集合；
                          通常为 ResourceGrantService.check_many 的偏函数（owner 绑定）
        subworkflow_checker: 注入的子工作流引用判定 (workflow_ref, pinned_version) ->
                             None（有效）或错误消息（无效，用于 E-108）
        http_allowed_domains: http 节点域名白名单；None 时读取配置（默认空=拒绝）

    Returns:
        结构化错误列表（不抛异常）
    """
    issues = validate_graph_structure(
        graph, domain=domain, http_allowed_domains=http_allowed_domains
    )
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        return issues

    # ---- 收集资源引用并批量授权判定（E-110）----
    if resource_checker is not None:
        pending: Dict[str, Set[str]] = {}  # resource_type -> ids
        ref_sites: List[tuple] = []        # (resource_type, resource_id, node_id)
        for node in graph["nodes"]:
            if not isinstance(node, dict):
                continue
            nid = str(node.get("id") or "")
            ntype = _TYPE_ALIASES.get(str(node.get("type", "")).strip(),
                                      str(node.get("type", "")).strip())
            cfg = ((node.get("data") or {}).get("config")) or {}
            for field_name, rtype, is_list in _NODE_RESOURCE_REFS.get(ntype, []):
                val = cfg.get(field_name)
                if _is_blank(val):
                    continue
                values = [str(v) for v in val] if is_list and isinstance(val, list) else [str(val)]
                for rid in values:
                    pending.setdefault(rtype, set()).add(rid)
                    ref_sites.append((rtype, rid, nid))
        granted_cache: Dict[str, Set[str]] = {}
        for rtype, ids in pending.items():
            try:
                granted_cache[rtype] = set(await resource_checker(rtype, sorted(ids)))
            except Exception:
                granted_cache[rtype] = set()  # 授权服务异常：按未授权处理（安全侧，R-03）
        missing_by_node: Dict[str, List[str]] = {}
        for rtype, rid, nid in ref_sites:
            if rid not in granted_cache.get(rtype, set()):
                missing_by_node.setdefault(nid, []).append(f"{rtype}:{rid}")
        for nid, missing in missing_by_node.items():
            issues.append(_issue(
                "E-110",
                f"节点 {nid} 使用了未授权资源: {', '.join(sorted(set(missing)))}",
                node_id=nid, missing=sorted(set(missing))))

    # ---- 子工作流引用有效性（E-108）----
    if subworkflow_checker is not None:
        for node in graph["nodes"]:
            if not isinstance(node, dict):
                continue
            ntype = _TYPE_ALIASES.get(str(node.get("type", "")).strip(),
                                      str(node.get("type", "")).strip())
            if ntype != "sub_workflow":
                continue
            nid = str(node.get("id") or "")
            cfg = ((node.get("data") or {}).get("config")) or {}
            wf_ref = cfg.get("workflow_ref")
            if _is_blank(wf_ref):
                continue
            pinned = cfg.get("pinned_version")
            try:
                err = await subworkflow_checker(str(wf_ref), pinned)
            except Exception:
                err = "子工作流引用校验失败"
            if err:
                issues.append(_issue("E-108", f"节点 {nid}: {err}", node_id=nid,
                                     resource=str(wf_ref)))

    return issues


def has_blocking_errors(issues: Sequence[Dict[str, Any]]) -> bool:
    """发布阻断判定：存在 error 级问题即阻断（warning 不阻断）"""
    return any(i.get("level", LEVEL_ERROR) == LEVEL_ERROR for i in issues)


def collect_resource_refs(graph: Any) -> Dict[str, List[str]]:
    """
    收集图中引用的资源 ID 快照清单（发布时写入 workflow_version.resource_refs，04-F1）

    Returns:
        {resource_type: [id, ...]}，如 {"model": ["m_gpt4o"], "kb": ["3"], "tool": [], "agent": []}
    """
    refs: Dict[str, Set[str]] = {}
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        return {}
    for node in graph["nodes"]:
        if not isinstance(node, dict):
            continue
        ntype = _TYPE_ALIASES.get(str(node.get("type", "")).strip(),
                                  str(node.get("type", "")).strip())
        cfg = ((node.get("data") or {}).get("config")) or {}
        for field_name, rtype, is_list in _NODE_RESOURCE_REFS.get(ntype, []):
            val = cfg.get(field_name)
            if _is_blank(val):
                continue
            values = [str(v) for v in val] if is_list and isinstance(val, list) else [str(val)]
            refs.setdefault(rtype, set()).update(values)
        # 子工作流引用一并留痕（resource_type=workflow）
        if ntype == "sub_workflow" and not _is_blank(cfg.get("workflow_ref")):
            refs.setdefault("workflow", set()).add(str(cfg["workflow_ref"]))
    return {k: sorted(v) for k, v in refs.items()}
