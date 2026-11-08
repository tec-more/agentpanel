"""Harness 接口 Schema（P0）"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------- 客户端凭据 ----------------
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="客户端名称")
    scopes: List[str] = Field(default_factory=list, description="授权范围")
    allowed_ips: Optional[List[str]] = Field(None, description="IP 白名单")
    expires_at: Optional[str] = Field(None, description="过期时间 ISO8601")
    description: Optional[str] = Field(None, description="备注")


class ClientResponse(BaseModel):
    client_id: str
    name: str
    status: str
    secret_prefix: str
    scopes: List[str] = Field(default_factory=list)
    expires_at: Optional[str] = None
    created_at: Optional[str] = None


# ---------------- 身份映射 ----------------
class IdentityBind(BaseModel):
    client_id: str = Field(..., description="客户端 ID")
    external_type: str = Field(..., description="外部身份类型")
    external_id: str = Field(..., description="外部身份 ID")
    external_name: Optional[str] = None
    user_id: int = Field(..., description="本地后台用户 ID")
    owner_type: str = Field(default="usr", description="配额主体类型")
    owner_id: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


class IdentityResponse(BaseModel):
    id: int
    client_id: str
    external_type: str
    external_id: str
    external_name: Optional[str] = None
    user_id: int
    status: str


# ---------------- 会话 ----------------
class SessionCreate(BaseModel):
    client_id: str = Field(..., description="客户端 ID")
    external_type: str = Field(default="user_id", description="外部身份类型")
    external_id: Optional[str] = Field(None, description="外部身份 ID；为空则用 user_id 映射")
    user_id: Optional[int] = Field(None, description="直接指定本地用户（有身份映射时忽略）")
    title: Optional[str] = None
    home_path: Optional[str] = Field(None, description="DSH_HOME")
    cwd: Optional[str] = Field(None, description="工作目录")
    project_key: Optional[str] = Field(None, description="项目标识")
    parent_session_no: Optional[str] = Field(None, description="父会话（子代理）")
    origin: Optional[str] = None
    runtime_version: Optional[str] = Field(None, description="runtime 版本（锁 0.1.5rc1）")
    format_version: Optional[str] = Field(
        None, description="会话日志格式版本；留空则按 session.v{n}.jsonl 文件名或 header.version 推断",
    )
    session_log_path: Optional[str] = Field(None, description="会话 JSONL 路径")
    gateway_key: Optional[str] = Field(None, description="网关虚拟 key（预留）")
    context: Optional[Dict[str, Any]] = None
    expires_at: Optional[str] = None


class SessionResponse(BaseModel):
    id: int
    session_no: str
    client_id: str
    user_id: Optional[int] = None
    status: str
    home_path: Optional[str] = None
    cwd: Optional[str] = None
    project_key: Optional[str] = None
    parent_session_no: Optional[str] = None
    runtime_version: Optional[str] = None
    format_version: Optional[str] = None
    run_count: int = 0
    created_at: Optional[str] = None


# ---------------- 运行 ----------------
class RunCreate(BaseModel):
    task_type: str = Field(default="agent", max_length=50)
    task_payload: Optional[Dict[str, Any]] = None
    input_summary: Optional[str] = None
    model: Optional[str] = Field(default=None, description="模型标识，如 deepseek-chat")
    provider: Optional[str] = Field(default=None, description="提供商，默认 deepseek")
    estimated_input_tokens: int = Field(default=0, ge=0, description="输入预估 token")
    max_output_tokens: int = Field(default=0, ge=0, description="最大输出预留 token")
    priority: int = 0
    metadata: Optional[Dict[str, Any]] = None


class RunResponse(BaseModel):
    id: int
    run_no: str
    session_no: str
    status: str
    model: Optional[str] = None
    provider: Optional[str] = None
    estimated_input_tokens: int = 0
    max_output_tokens: int = 0
    reserved_tokens: int = 0
    estimated_cost: float = 0
    currency: str = "CNY"
    hold_id: Optional[str] = None
    output_summary: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None


class RunStatusUpdate(BaseModel):
    status: str = Field(..., description="running/waiting_approval")
    message: Optional[str] = None


class StepEvent(BaseModel):
    node_id: str = Field(..., max_length=100)
    seq: int = Field(default=0, ge=0)
    step_type: str = Field(..., description="llm_call/tool_call/tool_result/approval/compaction/...")
    name: Optional[str] = None
    status: str = "completed"
    call_id: Optional[str] = None
    input: Optional[Dict[str, Any] | List[Any] | str] = None
    output: Optional[Dict[str, Any] | List[Any] | str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    model: Optional[str] = None
    provider: Optional[str] = None
    source: str = Field(default="provider", description="provider/gateway/estimated")
    cost: Optional[float] = None
    raw_seq: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None


class UsageEntry(BaseModel):
    node_id: str
    seq: int = 0
    source: str = Field(default="provider", description="provider/gateway/estimated")
    tokens_in: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    tokens_out: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    model: Optional[str] = None
    provider: Optional[str] = None
    cost: Optional[float] = None
    raw_seq: int = 0


class RunComplete(BaseModel):
    status: str = Field(default="succeeded", description="succeeded/failed/cancelled/timeout")
    output_summary: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    usage: List[UsageEntry] = Field(default_factory=list)


# ---------------- 事件采集 ----------------
class EventBatch(BaseModel):
    """原始事件批量上报：events 为解析后的对象，lines 为 JSONL 原始行（可含截断行）。"""

    events: List[Dict[str, Any]] = Field(default_factory=list)
    lines: List[str] = Field(default_factory=list, description="JSONL 原始行，容忍截断/非法行")
    default_source: str = Field(default="provider", description="usage 来源: provider/gateway/estimated")
    source: str = Field(default="api", description="采集通道: api/jsonl/notification/gateway")
    gateway_key: Optional[str] = Field(None, description="网关虚拟 key（预留）")
    truncated_lines: int = Field(default=0, description="上游已检测到的截断行数")
    model: Optional[str] = None
    provider: Optional[str] = None


# ---------------- 审批联动 ----------------
class ApprovalRequest(BaseModel):
    run_no: str
    action: str = Field(..., description="动作/工具名，如 tool.git.push")
    call_id: Optional[str] = None
    arguments: Optional[Dict[str, Any] | List[Any] | str] = None
    context: Optional[Dict[str, Any]] = None
    requested_by: Optional[str] = None


class ApprovalDecide(BaseModel):
    decision: str = Field(..., description="approved/denied")
    approver: Optional[str | int] = Field(
        None, description="审批人：用户 ID 或用户名；默认审批人为发起人，高危/跨租户由管理员兜底",
    )
    scope: Optional[str] = Field(
        None, description="授权粒度：once（默认，仅本次）/ session_pattern（本会话同一命令模式）",
    )
    pattern: Optional[str] = Field(None, description="session_pattern 时的命令模式，默认取命令前 1~2 个 token")
    comment: Optional[str] = None
    run_no: Optional[str] = None
    call_id: Optional[str] = None
    session_no: Optional[str] = None


# ---------------- 审计 ----------------
class AuditIngest(BaseModel):
    action: str = Field(..., max_length=100)
    session_no: Optional[str] = None
    run_no: Optional[str] = None
    step_id: Optional[int] = None
    call_id: Optional[str] = None
    raw_seq: int = 0
    risk_level: str = "low"
    decision: Optional[str] = None
    policy_code: Optional[str] = None
    trace_id: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None


# ---------------- 策略/价格 ----------------
class PolicyCreate(BaseModel):
    code: str
    name: str
    action_pattern: str
    effect: str = Field(default="deny", description="allow/deny/approve")
    risk_level: str = "high"
    require_approval: Optional[bool] = None
    approval_flow_code: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    priority: int = 100
    status: str = "active"
    description: Optional[str] = None


class ActionEvaluate(BaseModel):
    action: str = Field(..., description="动作标识，如 tool.git.push")
    session_no: Optional[str] = None
    run_no: Optional[str] = None
    call_id: Optional[str] = None
    arguments: Optional[Dict[str, Any] | List[Any] | str] = Field(
        None, description="工具调用参数（用于提取命令原文、命中白/黑名单）",
    )
    context: Optional[Dict[str, Any]] = None


class PolicyRuleUpsert(BaseModel):
    rule_code: str = Field(..., max_length=100, description="规则编码（审计 policy_code）")
    name: str = Field(..., max_length=150)
    tier: int = Field(default=2, ge=1, le=3, description="档位：1 默认可放行 / 2 自动判定 / 3 人工审批")
    effect: str = Field(default="allow", description="allow/deny/ask")
    category: str = Field(default="general", max_length=50)
    action_pattern: str = Field(default="*", max_length=200, description="动作匹配（fnmatch）")
    command_pattern: Optional[str] = Field(None, max_length=500, description="命令正则（re.search）")
    risk_level: str = Field(default="low", description="low/medium/high/critical")
    priority: int = Field(default=100, description="优先级（大者优先）")
    status: str = "active"
    description: Optional[str] = None


class PriceCreate(BaseModel):
    provider: str = "deepseek"
    model: str
    currency: str = "CNY"
    input_price_per_1k: float = 0
    output_price_per_1k: float = 0
    cache_read_price_per_1k: float = 0
    cache_write_price_per_1k: float = 0
    price_version: str = "v1"
    source: str = "manual"
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    status: str = "active"
    description: Optional[str] = None
