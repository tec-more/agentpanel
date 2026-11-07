"""
Harness 插件数据模型

设计要点（P0）：
- client/identity 解决「谁在调用」与「外部身份→本地用户」；
- session 表自己维护 DSH_HOME/cwd/projectKey 索引（SDK 无 session list/delete/close）；
- run 的 hold_id 必须一 run 一键，兼容同一 run 多次结算；
- step/audit 保留 callId、原始事件序号、preset/sandbox 等原文索引；
- 用量按 source 区分 provider/gateway/estimated，禁止跨来源混算。
"""
from tortoise import fields

from base.common.model import BaseModel, TimestampMixin


class HarnessClient(BaseModel, TimestampMixin):
    """业务系统接入凭据（secret 只存哈希，明文仅签发时回显一次）"""

    client_id = fields.CharField(max_length=64, unique=True, index=True, description="客户端 ID")
    name = fields.CharField(max_length=100, description="客户端名称")
    secret_hash = fields.CharField(max_length=128, description="secret SHA-256")
    secret_prefix = fields.CharField(max_length=24, default="", description="secret 前缀（展示用）")
    status = fields.CharField(max_length=20, default="active", description="active/disabled/revoked")
    scopes = fields.JSONField(default=list, description="授权范围")
    allowed_ips = fields.JSONField(null=True, description="IP 白名单（空=不限）")
    expires_at = fields.DatetimeField(null=True, description="凭据过期时间")
    last_used_at = fields.DatetimeField(null=True, description="最近使用时间")
    revoked_at = fields.DatetimeField(null=True, description="吊销时间")
    created_by = fields.BigIntField(null=True, description="创建人（后台用户 ID）")
    description = fields.TextField(null=True, description="备注")

    class Meta:
        table = "harness_client"
        table_description = "Harness 接入客户端表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"HarnessClient({self.client_id})"


class HarnessIdentity(BaseModel, TimestampMixin):
    """外部身份 → 本地用户映射（client 维度隔离）"""

    client_id = fields.CharField(max_length=64, index=True, description="客户端 ID")
    external_type = fields.CharField(max_length=50, description="外部身份类型: feishu_open_id/employee_no/...")
    external_id = fields.CharField(max_length=128, description="外部身份 ID")
    external_name = fields.CharField(max_length=100, null=True, description="外部显示名")
    user_id = fields.BigIntField(description="本地后台用户 ID")
    owner_type = fields.CharField(max_length=3, default="usr", description="配额主体类型")
    owner_id = fields.BigIntField(null=True, description="配额主体 ID（默认同 user_id）")
    status = fields.CharField(max_length=20, default="active", description="active/disabled")
    meta = fields.JSONField(null=True, description="扩展信息")

    class Meta:
        table = "harness_identity"
        table_description = "Harness 外部身份映射表"
        unique_together = (("client_id", "external_type", "external_id"),)
        ordering = ["-created_at"]

    def __str__(self):
        return f"HarnessIdentity({self.client_id}:{self.external_id})"


class HarnessSession(BaseModel, TimestampMixin):
    """Harness 会话（业务侧建、Harness 执行）"""

    session_no = fields.CharField(max_length=64, unique=True, index=True, description="会话编号")
    client_id = fields.CharField(max_length=64, index=True, description="客户端 ID")
    identity_id = fields.BigIntField(null=True, index=True, description="身份映射 ID")
    user_id = fields.BigIntField(null=True, index=True, description="本地用户 ID")
    owner_type = fields.CharField(max_length=3, default="usr", description="配额主体类型")
    owner_id = fields.BigIntField(null=True, description="配额主体 ID")
    title = fields.CharField(max_length=200, null=True, description="会话标题")
    status = fields.CharField(max_length=20, default="open", description="open/closing/closed/expired")
    # 会话日志索引（SDK 无 list 接口，必须自行维护）
    home_path = fields.CharField(max_length=500, null=True, description="DSH_HOME")
    cwd = fields.CharField(max_length=500, null=True, description="工作目录")
    project_key = fields.CharField(max_length=200, null=True, index=True, description="项目标识")
    parent_session_no = fields.CharField(max_length=64, null=True, index=True, description="父会话（子代理）")
    origin = fields.CharField(max_length=50, null=True, description="会话来源")
    runtime_version = fields.CharField(max_length=50, null=True, description="runtime 版本")
    format_version = fields.CharField(
        max_length=20, null=True, description="会话日志格式版本（以 header.version 为准，兼容 v3/v4 并存）",
    )
    # 会话 JSONL 路径（<DSH_HOME>/sessions/--<slug>--/<session_id>/session.v{n}.jsonl）；归档需 runtime 停止后做
    session_log_path = fields.CharField(max_length=500, null=True, description="会话 JSONL 路径")
    # 网关虚拟 key 归属预留（一租户一 key，网关层后续接入）
    gateway_key = fields.CharField(max_length=128, null=True, index=True, description="网关虚拟 key")
    trace_id = fields.CharField(max_length=100, null=True, index=True, description="全链路追踪 ID")
    context = fields.JSONField(null=True, description="会话上下文")
    started_at = fields.DatetimeField(null=True, description="开始时间")
    closed_at = fields.DatetimeField(null=True, description="关闭时间")
    expires_at = fields.DatetimeField(null=True, description="过期时间")
    last_activity_at = fields.DatetimeField(null=True, description="最近活动时间")
    run_count = fields.IntField(default=0, description="运行次数")

    class Meta:
        table = "harness_session"
        table_description = "Harness 会话表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"HarnessSession({self.session_no})"


class HarnessRun(BaseModel, TimestampMixin):
    """一次 Harness 执行（业务下发、Harness 回传）"""

    run_no = fields.CharField(max_length=64, unique=True, index=True, description="运行编号")
    session_no = fields.CharField(max_length=64, index=True, description="会话编号")
    session_id = fields.BigIntField(null=True, index=True, description="会话 ID")
    client_id = fields.CharField(max_length=64, index=True, description="客户端 ID")
    identity_id = fields.BigIntField(null=True, description="身份映射 ID")
    user_id = fields.BigIntField(null=True, index=True, description="本地用户 ID")
    owner_type = fields.CharField(max_length=3, default="usr", description="配额主体类型")
    owner_id = fields.BigIntField(null=True, description="配额主体 ID")

    task_type = fields.CharField(max_length=50, default="agent", description="任务类型")
    task_payload = fields.JSONField(null=True, description="任务载荷")
    input_summary = fields.TextField(null=True, description="输入摘要")

    status = fields.CharField(
        max_length=30, default="created",
        description="created/queued/running/waiting_approval/succeeded/failed/cancelled/timeout",
    )
    priority = fields.IntField(default=0, description="优先级")

    model = fields.CharField(max_length=100, null=True, description="模型标识")
    provider = fields.CharField(max_length=50, null=True, description="模型提供商")
    estimated_input_tokens = fields.BigIntField(default=0, description="输入预估 token")
    max_output_tokens = fields.BigIntField(default=0, description="最大输出预留 token")
    reserved_tokens = fields.BigIntField(default=0, description="预占 token 合计")
    estimated_cost = fields.DecimalField(max_digits=14, decimal_places=8, default=0, description="预估成本")
    currency = fields.CharField(max_length=8, default="CNY", description="币种")
    price_snapshot = fields.JSONField(null=True, description="计价快照")

    # 关键修复：一 run 一 hold_id（禁止 str(execution_id)），空串表示不计量
    hold_id = fields.CharField(max_length=128, null=True, index=True, description="配额预占键")
    output_summary = fields.TextField(null=True, description="输出摘要")
    error_code = fields.CharField(max_length=100, null=True, description="错误码")
    error_message = fields.TextField(null=True, description="错误信息")
    started_at = fields.DatetimeField(null=True, description="开始时间")
    finished_at = fields.DatetimeField(null=True, description="结束时间")
    last_heartbeat_at = fields.DatetimeField(null=True, description="最近心跳")
    metrics = fields.JSONField(null=True, description="运行指标")
    created_by = fields.BigIntField(null=True, description="创建人")

    class Meta:
        table = "harness_run"
        table_description = "Harness 运行表"
        indexes = [
            ("session_no", "status"),
            ("owner_type", "owner_id", "created_at"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"HarnessRun({self.run_no}, {self.status})"


class HarnessStep(BaseModel, TimestampMixin):
    """运行内步骤/事件（含 callId 与原始事件序号）"""

    run_id = fields.BigIntField(index=True, description="运行 ID")
    run_no = fields.CharField(max_length=64, index=True, description="运行编号")
    session_no = fields.CharField(max_length=64, null=True, index=True, description="会话编号")
    node_id = fields.CharField(max_length=100, description="节点/事件 ID")
    seq = fields.BigIntField(default=0, description="事件序号")
    step_type = fields.CharField(
        max_length=50, description="llm_call/tool_call/tool_result/approval/compaction/decision/action",
    )
    name = fields.CharField(max_length=200, null=True, description="步骤名称")
    status = fields.CharField(max_length=30, default="completed", description="状态")
    call_id = fields.CharField(max_length=100, null=True, index=True, description="工具调用 callId")
    input = fields.JSONField(null=True, description="输入（arguments 原文等）")
    output = fields.JSONField(null=True, description="输出（content/isError/error）")
    tokens_in = fields.BigIntField(default=0, description="未缓存输入 token")
    tokens_out = fields.BigIntField(default=0, description="输出 token")
    cache_read_tokens = fields.BigIntField(default=0, description="缓存读取 token")
    cache_write_tokens = fields.BigIntField(default=0, description="缓存写入 token")
    reasoning_tokens = fields.BigIntField(default=0, description="推理 token")
    total_tokens = fields.BigIntField(default=0, description="totalTokens 原值")
    model = fields.CharField(max_length=100, null=True, description="模型")
    provider = fields.CharField(max_length=50, null=True, description="提供商")
    source = fields.CharField(max_length=30, default="provider", description="用量来源 provider/gateway/estimated")
    cost = fields.DecimalField(max_digits=14, decimal_places=8, default=0, description="成本")
    price_snapshot = fields.JSONField(null=True, description="计价快照")
    raw_seq = fields.BigIntField(default=0, description="原始事件序号/JSONL 行号")
    started_at = fields.DatetimeField(null=True, description="开始时间")
    finished_at = fields.DatetimeField(null=True, description="结束时间")
    duration_ms = fields.IntField(null=True, description="耗时毫秒")

    class Meta:
        table = "harness_step"
        table_description = "Harness 运行步骤表"
        unique_together = (("run_id", "node_id", "seq"),)
        ordering = ["run_id", "seq"]

    def __str__(self):
        return f"HarnessStep({self.run_no}:{self.node_id}#{self.seq})"


class HarnessAuditEvent(BaseModel, TimestampMixin):
    """Harness 安全审计事件（谁在何时对 harness 做了什么）"""

    event_no = fields.CharField(max_length=64, unique=True, index=True, description="事件编号")
    client_id = fields.CharField(max_length=64, null=True, index=True, description="客户端 ID")
    identity_id = fields.BigIntField(null=True, description="身份映射 ID")
    session_no = fields.CharField(max_length=64, null=True, index=True, description="会话编号")
    run_no = fields.CharField(max_length=64, null=True, index=True, description="运行编号")
    step_id = fields.BigIntField(null=True, description="步骤 ID")

    actor_type = fields.CharField(max_length=20, default="client", description="client/user/system")
    actor_id = fields.CharField(max_length=128, null=True, description="操作者标识")
    action = fields.CharField(max_length=100, index=True, description="事件动作")
    target_type = fields.CharField(max_length=50, null=True, description="目标类型")
    target_id = fields.CharField(max_length=128, null=True, description="目标 ID")

    risk_level = fields.CharField(max_length=20, default="low", description="low/medium/high/critical")
    decision = fields.CharField(max_length=20, null=True, description="allow/deny/ask/pending")
    policy_code = fields.CharField(max_length=100, null=True, description="命中策略编码")
    call_id = fields.CharField(max_length=100, null=True, index=True, description="工具 callId")
    raw_seq = fields.BigIntField(default=0, description="原始事件序号")
    # P1：事件采集来源与原始事件类型（api/jsonl/notification/gateway）
    event_source = fields.CharField(max_length=20, default="api", description="事件来源")
    raw_type = fields.CharField(max_length=100, null=True, description="原始事件类型")
    detail = fields.JSONField(null=True, description="事件详情（脱敏）")

    request_id = fields.CharField(max_length=100, null=True, description="请求 ID")
    trace_id = fields.CharField(max_length=100, null=True, index=True, description="追踪 ID")
    ip_address = fields.CharField(max_length=64, null=True, description="来源 IP")
    user_agent = fields.CharField(max_length=500, null=True, description="User-Agent")
    occurred_at = fields.DatetimeField(null=True, index=True, description="事件发生时间")

    class Meta:
        table = "harness_audit_event"
        table_description = "Harness 审计事件表"
        indexes = [
            ("session_no", "action"),
            ("run_no", "occurred_at"),
        ]
        ordering = ["-occurred_at", "-created_at"]

    def __str__(self):
        return f"HarnessAuditEvent({self.event_no}, {self.action})"


class HarnessActionPolicy(BaseModel, TimestampMixin):
    """高危动作策略（未匹配即拒绝，fail-closed）"""

    code = fields.CharField(max_length=100, unique=True, index=True, description="策略编码")
    name = fields.CharField(max_length=150, description="策略名称")
    action_pattern = fields.CharField(max_length=200, index=True, description="动作匹配（支持 * 通配）")
    effect = fields.CharField(max_length=20, default="deny", description="allow/deny/approve")
    risk_level = fields.CharField(max_length=20, default="high", description="low/medium/high/critical")
    require_approval = fields.BooleanField(default=None, null=True, description="是否需审批（None=跟随 effect）")
    approval_flow_code = fields.CharField(max_length=100, null=True, description="审批流编码")
    conditions = fields.JSONField(null=True, description="匹配条件")
    priority = fields.IntField(default=100, description="优先级（大者优先）")
    status = fields.CharField(max_length=20, default="active", description="active/disabled")
    description = fields.TextField(null=True, description="说明")

    class Meta:
        table = "harness_action_policy"
        table_description = "Harness 动作安全策略表"
        ordering = ["-priority", "code"]

    def __str__(self):
        return f"HarnessActionPolicy({self.code})"


class HarnessPolicyRule(BaseModel, TimestampMixin):
    """三档审批策略规则（可配置、可版本化）

    tier=1/2/3 对应：默认可放行 / 规则自动判定 / 人工审批。
    rule_code 即审计中的 policy_code；version 为单条规则版本，
    审计同时记录 manifest 的 ruleset_version。
    """

    rule_code = fields.CharField(max_length=100, unique=True, index=True, description="规则编码（审计 policy_code）")
    name = fields.CharField(max_length=150, description="规则名称")
    version = fields.IntField(default=1, description="规则版本")
    tier = fields.SmallIntField(default=2, description="档位: 1/2/3")
    effect = fields.CharField(max_length=10, default="allow", description="allow/deny/ask")
    category = fields.CharField(max_length=50, default="general", description="safe_read/test_build/network/fs_write/secret/privilege/system")
    action_pattern = fields.CharField(max_length=200, default="*", description="动作匹配（fnmatch）")
    command_pattern = fields.CharField(max_length=500, null=True, description="命令正则（re.search，大小写不敏感）")
    risk_level = fields.CharField(max_length=20, default="low", description="low/medium/high/critical")
    priority = fields.IntField(default=100, description="优先级（大者优先）")
    status = fields.CharField(max_length=20, default="active", description="active/disabled")
    description = fields.TextField(null=True, description="规则说明")

    class Meta:
        table = "harness_policy_rule"
        table_description = "Harness 三档审批策略规则表"
        ordering = ["-priority", "rule_code"]

    def __str__(self):
        return f"HarnessPolicyRule({self.rule_code})"


class HarnessApprovalRequest(BaseModel, TimestampMixin):
    """人工审批单（二档转人工/三档风险升级）

    默认 300 秒超时，超时按拒绝处理（fail-closed）。
    授权粒度：once（默认）/ session_pattern（本会话内同一命令模式）。
    """

    approval_no = fields.CharField(max_length=40, unique=True, index=True, description="审批单号")
    client_id = fields.CharField(max_length=64, index=True, description="客户端 ID")
    run_no = fields.CharField(max_length=64, null=True, index=True, description="运行编号")
    session_no = fields.CharField(max_length=64, null=True, index=True, description="会话编号")
    action = fields.CharField(max_length=200, description="动作/工具名")
    call_id = fields.CharField(max_length=100, null=True, index=True, description="工具 callId")
    command_text = fields.TextField(null=True, description="命令原文（审计用）")
    initiator_user_id = fields.BigIntField(null=True, index=True, description="任务发起人（默认审批人）")
    approver_user_id = fields.BigIntField(null=True, description="指定审批人（高危为管理员）")
    approver_role = fields.CharField(max_length=20, default="initiator", description="initiator/admin")
    risk_level = fields.CharField(max_length=20, default="medium", description="low/medium/high/critical")
    policy_code = fields.CharField(max_length=100, null=True, description="命中规则编码")
    reason = fields.TextField(null=True, description="转人工原因")
    scope = fields.CharField(max_length=20, default="once", description="once/session_pattern")
    pattern = fields.CharField(max_length=200, null=True, description="会话内授权命令模式")
    status = fields.CharField(
        max_length=20, default="pending", index=True,
        description="pending/approved/denied/expired/cancelled",
    )
    decision = fields.CharField(max_length=20, null=True, description="allow/deny")
    timeout_seconds = fields.IntField(default=300, description="审批超时秒数（默认 300）")
    requested_at = fields.DatetimeField(null=True, description="发起时间")
    expires_at = fields.DatetimeField(null=True, index=True, description="超时时间")
    decided_at = fields.DatetimeField(null=True, description="决策时间")
    decided_by = fields.CharField(max_length=128, null=True, description="审批人标识")
    comment = fields.TextField(null=True, description="审批理由")
    detail = fields.JSONField(null=True, description="附加信息（风险信号/规则版本）")

    class Meta:
        table = "harness_approval_request"
        table_description = "Harness 人工审批单表"
        ordering = ["-id"]

    def __str__(self):
        return f"HarnessApprovalRequest({self.approval_no}, {self.status})"


class HarnessApprovalGrant(BaseModel, TimestampMixin):
    """会话内命令模式授权（不做永久放行；会话关闭即失效）"""

    approval_no = fields.CharField(max_length=40, index=True, description="来源审批单号")
    client_id = fields.CharField(max_length=64, index=True, description="客户端 ID")
    session_no = fields.CharField(max_length=64, index=True, description="会话编号")
    pattern = fields.CharField(max_length=200, description="命令模式")
    scope = fields.CharField(max_length=20, default="session_pattern", description="session_pattern")
    status = fields.CharField(max_length=20, default="active", description="active/revoked")
    uses = fields.IntField(default=0, description="命中次数")
    expires_at = fields.DatetimeField(null=True, description="失效时间（随会话关闭）")

    class Meta:
        table = "harness_approval_grant"
        table_description = "Harness 会话内审批授权表"
        unique_together = (("session_no", "pattern"),)

    def __str__(self):
        return f"HarnessApprovalGrant({self.session_no}, {self.pattern})"


class HarnessGatewayLease(BaseModel, TimestampMixin):
    """网关虚拟 key 租约（数据面鉴权）

    安全约定：
    - DB 只存虚拟 key 的 SHA-256 与不可逆指纹，明文仅在签发响应中回显一次；
    - 绑定 client / session / run 与配额主体（owner_type/owner_id/member_id）；
    - 分钟级过期，可续期、可吊销、按 lease 限流。
    """

    lease_id = fields.CharField(max_length=64, unique=True, index=True, description="租约 ID")
    key_hash = fields.CharField(max_length=128, description="虚拟 key SHA-256")
    key_prefix = fields.CharField(max_length=64, description="虚拟 key 前缀（非敏感）")
    key_fingerprint = fields.CharField(max_length=16, description="虚拟 key 指纹（哈希前 12 位）")
    client_id = fields.CharField(max_length=64, index=True, description="来源客户端 ID")
    session_no = fields.CharField(max_length=64, null=True, index=True, description="绑定会话")
    run_no = fields.CharField(max_length=64, null=True, index=True, description="绑定运行")
    owner_type = fields.CharField(max_length=8, null=True, description="配额主体类型 cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="配额主体 ID")
    member_id = fields.BigIntField(null=True, description="组织成员 ID")
    provider = fields.CharField(max_length=50, null=True, description="provider")
    model = fields.CharField(max_length=100, null=True, description="model")
    status = fields.CharField(
        max_length=20, default="active", index=True, description="active/revoked/invalid"
    )
    expires_at = fields.DatetimeField(index=True, description="过期时间")
    last_used_at = fields.DatetimeField(null=True, description="最近使用时间")
    revoked_at = fields.DatetimeField(null=True, description="吊销时间")
    invalidated_at = fields.DatetimeField(null=True, description="失效时间（续期失败等）")
    invalid_reason = fields.CharField(max_length=100, null=True, description="失效原因")
    request_count = fields.BigIntField(default=0, description="累计请求数")
    rate_window_started = fields.DatetimeField(null=True, description="限流窗口起点")
    rate_window_count = fields.IntField(default=0, description="限流窗口请求数")
    rpm_limit = fields.IntField(default=60, description="每分钟请求上限")
    meta = fields.JSONField(null=True, description="附加信息（签发来源等）")

    class Meta:
        table = "harness_gateway_lease"
        table_description = "Harness 网关虚拟 key 租约表"
        indexes = [
            ("client_id", "status"),
            ("status", "expires_at"),
        ]
        ordering = ["-id"]

    def __str__(self):
        return f"HarnessGatewayLease({self.lease_id}, {self.status})"


class HarnessGatewayBudget(BaseModel, TimestampMixin):
    """租约级额度账本（Redis 不可用时的共享兜底事实源）

    - 预算与计数只存一份，多副本通过行锁串行扣减，禁止各算一份；
    - DB 兜底语义为“预占先计入 used”，结算时按实际差额修正；
    - rejected/truncated 为“因额度被拒绝/截断”的累计次数，供看板展示。
    """

    lease_id = fields.CharField(max_length=64, unique=True, index=True, description="租约 ID")
    owner_type = fields.CharField(max_length=8, null=True, description="配额主体类型 cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="配额主体 ID")
    budget_tokens = fields.FloatField(default=0, description="租约 token 预算（0=不限）")
    used_tokens = fields.FloatField(default=0, description="已结算 token（DB 兜底含在途预占）")
    reserved_tokens = fields.FloatField(default=0, description="在途预占 token")
    request_count = fields.BigIntField(default=0, description="累计请求数")
    rejected_count = fields.BigIntField(default=0, description="因额度被拒绝次数")
    truncated_count = fields.BigIntField(default=0, description="因估算触发截断次数")
    over_budget_count = fields.BigIntField(default=0, description="非流式超预留次数")
    status = fields.CharField(max_length=20, default="active", description="active/exhausted/revoked")
    last_settled_at = fields.DatetimeField(null=True, description="最近结算时间")

    class Meta:
        table = "harness_gateway_budget"
        table_description = "Harness 网关额度账本"
        indexes = [("owner_type", "owner_id")]

    def __str__(self):
        return f"HarnessGatewayBudget({self.lease_id}, {self.used_tokens}/{self.budget_tokens})"


class HarnessGatewayConcurrency(BaseModel, TimestampMixin):
    """单租户网关在途请求数（DB 兜底的共享并发计数）

    updated_at 超过看门狗窗口未刷新时，下一次获取会归零（崩溃自动恢复）。
    """

    owner_type = fields.CharField(max_length=8, description="配额主体类型 cus/usr/org")
    owner_id = fields.BigIntField(description="配额主体 ID")
    inflight = fields.IntField(default=0, description="当前在途请求数")

    class Meta:
        table = "harness_gateway_concurrency"
        table_description = "Harness 网关单租户并发计数"
        unique_together = (("owner_type", "owner_id"),)


class HarnessReconcileBatch(BaseModel, TimestampMixin):
    """网关对账批次（每次执行一条，保留历史）"""

    batch_no = fields.CharField(max_length=40, unique=True, index=True, description="批次编号")
    trigger = fields.CharField(max_length=20, default="manual", description="manual/scheduled")
    window_start = fields.DatetimeField(description="窗口开始（含）")
    window_end = fields.DatetimeField(description="窗口结束（不含）")
    status = fields.CharField(max_length=20, default="running", description="running/completed/failed")
    stats = fields.JSONField(null=True, description="本次统计")
    operator_id = fields.BigIntField(null=True, description="手动触发管理员")
    duration_ms = fields.IntField(default=0, description="耗时毫秒")
    error_message = fields.TextField(null=True, description="失败原因")

    class Meta:
        table = "harness_reconcile_batch"
        table_description = "Harness 网关对账批次表"
        indexes = [("trigger", "created_at")]
        ordering = ["-id"]

    def __str__(self):
        return f"HarnessReconcileBatch({self.batch_no}, {self.status})"


class HarnessReconcileDiff(BaseModel, TimestampMixin):
    """网关记账与客户端上报差异（fingerprint 幂等，不重复插入）"""

    fingerprint = fields.CharField(max_length=180, unique=True, index=True, description="幂等指纹")
    batch_no = fields.CharField(max_length=40, null=True, index=True, description="最近命中批次")
    run_no = fields.CharField(max_length=64, null=True, index=True, description="运行编号")
    session_no = fields.CharField(max_length=64, null=True, index=True, description="会话编号")
    client_id = fields.CharField(max_length=64, null=True, index=True, description="客户端 ID")
    owner_type = fields.CharField(max_length=8, null=True, description="配额主体类型")
    owner_id = fields.BigIntField(null=True, index=True, description="配额主体 ID")
    gateway_key = fields.CharField(max_length=128, null=True, index=True, description="网关租约 ID")
    category = fields.CharField(
        max_length=30, index=True,
        description="only_gateway/only_client/value_mismatch/duplicate_count/"
                    "failure_timeout/unmatched_gateway/unmatched_client",
    )
    severity = fields.CharField(max_length=10, default="low", index=True, description="high/low")
    gateway_amount = fields.FloatField(default=0, description="网关 token 汇总")
    client_amount = fields.FloatField(default=0, description="客户端 token 汇总")
    diff_amount = fields.FloatField(default=0, description="客户端 - 网关")
    diff_rate = fields.FloatField(default=0, description="diff_amount / max(网关,1)")
    gateway_cost = fields.DecimalField(max_digits=14, decimal_places=8, default=0, description="网关成本")
    client_cost = fields.DecimalField(max_digits=14, decimal_places=8, default=0, description="客户端成本")
    gateway_count = fields.IntField(default=0, description="网关成功请求数")
    client_count = fields.IntField(default=0, description="客户端记录数")
    detail = fields.JSONField(null=True, description="统计明细与样本")
    status = fields.CharField(max_length=20, default="open", index=True, description="open/resolved/ignored")
    resolved_by = fields.BigIntField(null=True, description="处理人")
    resolved_at = fields.DatetimeField(null=True, description="处理时间")
    resolve_note = fields.TextField(null=True, description="处理备注")
    last_seen_at = fields.DatetimeField(null=True, description="最近命中时间")
    occurrence_count = fields.IntField(default=1, description="累计命中次数")

    class Meta:
        table = "harness_reconcile_diff"
        table_description = "Harness 网关对账差异表"
        indexes = [
            ("category", "severity", "status"),
            ("run_no", "created_at"),
            ("session_no", "created_at"),
            ("owner_type", "owner_id", "created_at"),
        ]
        ordering = ["-last_seen_at", "-id"]

    def __str__(self):
        return f"HarnessReconcileDiff({self.fingerprint}, {self.category}, {self.severity})"
