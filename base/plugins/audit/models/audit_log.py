from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class AuditLog(BaseModel, TimestampMixin):
    """审计日志模型 - 基础审计记录"""
    
    # 审计级别常量
    AUDIT_LEVEL_INFO = "info"
    AUDIT_LEVEL_WARNING = "warning"
    AUDIT_LEVEL_ERROR = "error"
    AUDIT_LEVEL_CRITICAL = "critical"
    
    # 审计状态常量
    AUDIT_STATUS_PENDING = "pending"
    AUDIT_STATUS_REVIEWED = "reviewed"
    AUDIT_STATUS_ARCHIVED = "archived"

    trace_id = fields.CharField(max_length=100, null=True, description="全链路追踪ID", index=True)
    
    user_id = fields.BigIntField(null=True, description="操作用户ID", index=True)
    username = fields.CharField(max_length=50, null=True, description="操作用户名", index=True)
    module = fields.CharField(max_length=50, null=True, description="操作模块", index=True)
    operation = fields.CharField(max_length=100, description="操作类型", index=True)
    method = fields.CharField(max_length=10, description="请求方法", index=True)
    path = fields.CharField(max_length=500, description="请求路径")
    ip_address = fields.CharField(max_length=50, null=True, description="IP地址", index=True)
    user_agent = fields.CharField(max_length=500, null=True, description="用户代理")
    request_params = fields.JSONField(null=True, description="请求参数")
    response_data = fields.TextField(null=True, description="响应数据")
    status_code = fields.IntField(null=True, description="响应状态码", index=True)
    error_message = fields.TextField(null=True, description="错误信息")
    duration = fields.IntField(null=True, description="执行时长(毫秒)")
    
    level = fields.CharField(max_length=20, default=AUDIT_LEVEL_INFO, description="审计级别", index=True)
    business_no = fields.CharField(max_length=100, null=True, description="业务流水号", index=True)
    related_record_id = fields.CharField(max_length=100, null=True, description="关联记录ID")
    status = fields.CharField(max_length=20, default=AUDIT_STATUS_PENDING, description="审计状态", index=True)
    review_user_id = fields.BigIntField(null=True, description="审核人ID")
    review_time = fields.DatetimeField(null=True, description="审核时间")
    review_comment = fields.TextField(null=True, description="审核备注")

    class Meta:
        table = "audit_log"
        table_description = "审计日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AuditLog {self.id}: {self.operation} by {self.username}"


class InputLayerLog(BaseModel, TimestampMixin):
    """输入层日志 - 记录用户指令、上下文等"""

    trace_id = fields.CharField(max_length=100, description="全链路追踪ID", index=True)
    
    user_id = fields.BigIntField(null=True, description="用户ID", index=True)
    username = fields.CharField(max_length=50, null=True, description="用户名")
    
    user_instruction = fields.TextField(description="用户指令")
    context_data = fields.JSONField(null=True, description="上下文数据")
    prompt_version = fields.CharField(max_length=50, null=True, description="Prompt版本")
    prompt_template = fields.TextField(null=True, description="Prompt模板")
    prompt_variables = fields.JSONField(null=True, description="Prompt变量")
    
    session_id = fields.CharField(max_length=100, null=True, description="会话ID")
    request_id = fields.CharField(max_length=100, null=True, description="请求ID")
    
    class Meta:
        table = "audit_input_layer"
        table_description = "输入层审计日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"InputLayerLog {self.id}: trace={self.trace_id}"


class DecisionLayerLog(BaseModel, TimestampMixin):
    """决策层日志 - 记录意图识别、任务拆解、推理路径等"""

    trace_id = fields.CharField(max_length=100, description="全链路追踪ID", index=True)
    
    intent_recognition = fields.JSONField(null=True, description="意图识别结果")
    task_decomposition = fields.JSONField(null=True, description="任务拆解结果")
    reasoning_path = fields.JSONField(null=True, description="推理路径")
    thought_chain = fields.TextField(null=True, description="思维链(CoT)")
    confidence = fields.FloatField(null=True, description="置信度")
    
    decision_tree = fields.JSONField(null=True, description="决策树")
    rule_matches = fields.JSONField(null=True, description="规则匹配结果")
    fallback_reason = fields.TextField(null=True, description="降级原因")
    
    class Meta:
        table = "audit_decision_layer"
        table_description = "决策层审计日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"DecisionLayerLog {self.id}: trace={self.trace_id}"


class ExecutionLayerLog(BaseModel, TimestampMixin):
    """执行层日志 - 记录工具调用、API访问、数据读写等"""

    # 执行类型常量
    EXECUTION_TYPE_TOOL_CALL = "tool_call"
    EXECUTION_TYPE_API_CALL = "api_call"
    EXECUTION_TYPE_DATA_READ = "data_read"
    EXECUTION_TYPE_DATA_WRITE = "data_write"
    EXECUTION_TYPE_PERMISSION_CHECK = "permission_check"

    trace_id = fields.CharField(max_length=100, description="全链路追踪ID", index=True)
    step_id = fields.CharField(max_length=100, null=True, description="步骤ID")
    
    execution_type = fields.CharField(max_length=50, description="执行类型", index=True)
    target_name = fields.CharField(max_length=200, description="目标名称(工具名/API名/表名等)")
    
    parameters = fields.JSONField(null=True, description="调用参数")
    return_value = fields.JSONField(null=True, description="返回值")
    status = fields.CharField(max_length=20, description="执行状态(success/failed)")
    error_message = fields.TextField(null=True, description="错误信息")
    
    duration = fields.IntField(null=True, description="执行时长(毫秒)")
    start_time = fields.DatetimeField(null=True, description="开始时间")
    end_time = fields.DatetimeField(null=True, description="结束时间")
    
    permission_check_result = fields.BooleanField(null=True, description="权限校验结果")
    permission_details = fields.JSONField(null=True, description="权限详情")
    
    data_source = fields.CharField(max_length=200, null=True, description="数据来源")
    data_operation = fields.CharField(max_length=50, null=True, description="数据操作类型")
    
    class Meta:
        table = "audit_execution_layer"
        table_description = "执行层审计日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"ExecutionLayerLog {self.id}: {self.execution_type} - {self.target_name}"


class OutputLayerLog(BaseModel, TimestampMixin):
    """输出层日志 - 记录最终结果、格式合规性、是否幻觉等"""

    trace_id = fields.CharField(max_length=100, description="全链路追踪ID", index=True)
    
    final_output = fields.TextField(description="最终输出结果")
    output_format = fields.CharField(max_length=50, null=True, description="输出格式")
    format_compliance = fields.BooleanField(default=True, description="格式合规性")
    format_issues = fields.JSONField(null=True, description="格式问题列表")
    
    is_hallucination = fields.BooleanField(default=False, description="是否存在幻觉")
    hallucination_details = fields.TextField(null=True, description="幻觉详情")
    hallucination_confidence = fields.FloatField(null=True, description="幻觉检测置信度")
    
    sensitive_content_detected = fields.BooleanField(default=False, description="是否检测到敏感内容")
    sensitive_content_filtered = fields.BooleanField(default=False, description="是否已过滤敏感内容")
    sensitive_content_details = fields.JSONField(null=True, description="敏感内容详情")
    
    citations = fields.JSONField(null=True, description="引用来源列表")
    data_sources = fields.JSONField(null=True, description="数据来源列表")
    reasoning_evidence = fields.TextField(null=True, description="推理依据")
    
    class Meta:
        table = "audit_output_layer"
        table_description = "输出层审计日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"OutputLayerLog {self.id}: trace={self.trace_id}"


class SystemLayerLog(BaseModel, TimestampMixin):
    """系统层日志 - 记录模型版本、配置变更、部署记录等"""

    # 系统事件类型常量
    SYSTEM_EVENT_MODEL_VERSION_CHANGE = "model_version_change"
    SYSTEM_EVENT_CONFIG_CHANGE = "config_change"
    SYSTEM_EVENT_DEPLOYMENT = "deployment"
    SYSTEM_EVENT_ROLLBACK = "rollback"
    SYSTEM_EVENT_EXCEPTION = "exception"
    SYSTEM_EVENT_SYSTEM_ERROR = "system_error"

    trace_id = fields.CharField(max_length=100, null=True, description="全链路追踪ID", index=True)
    
    event_type = fields.CharField(max_length=50, description="事件类型", index=True)
    
    model_name = fields.CharField(max_length=100, null=True, description="模型名称")
    model_version = fields.CharField(max_length=50, null=True, description="模型版本")
    model_provider = fields.CharField(max_length=50, null=True, description="模型提供商")
    
    config_key = fields.CharField(max_length=200, null=True, description="配置键")
    old_value = fields.TextField(null=True, description="旧值")
    new_value = fields.TextField(null=True, description="新值")
    
    deployment_version = fields.CharField(max_length=50, null=True, description="部署版本")
    deployment_target = fields.CharField(max_length=100, null=True, description="部署目标")
    
    exception_type = fields.CharField(max_length=200, null=True, description="异常类型")
    exception_message = fields.TextField(null=True, description="异常信息")
    stack_trace = fields.TextField(null=True, description="异常堆栈")
    
    operator_id = fields.BigIntField(null=True, description="操作人ID")
    operator_name = fields.CharField(max_length=50, null=True, description="操作人姓名")
    reason = fields.TextField(null=True, description="操作原因")
    
    class Meta:
        table = "audit_system_layer"
        table_description = "系统层审计日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"SystemLayerLog {self.id}: {self.event_type}"


class AuditReport(BaseModel, TimestampMixin):
    """审计报告模型"""

    # 报告类型常量
    REPORT_TYPE_DAILY = "daily"
    REPORT_TYPE_WEEKLY = "weekly"
    REPORT_TYPE_MONTHLY = "monthly"
    REPORT_TYPE_CUSTOM = "custom"
    REPORT_TYPE_COMPLIANCE = "compliance"
    REPORT_TYPE_RISK = "risk"

    report_type = fields.CharField(max_length=20, description="报告类型", index=True)
    report_name = fields.CharField(max_length=200, description="报告名称")
    
    start_time = fields.DatetimeField(description="报告开始时间")
    end_time = fields.DatetimeField(description="报告结束时间")
    
    report_data = fields.JSONField(description="报告数据")
    summary = fields.TextField(null=True, description="报告摘要")
    
    generated_by = fields.BigIntField(null=True, description="生成人ID")
    generated_by_name = fields.CharField(max_length=50, null=True, description="生成人姓名")
    
    status = fields.CharField(max_length=20, default="generated", description="状态")
    
    class Meta:
        table = "audit_report"
        table_description = "审计报告表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AuditReport {self.id}: {self.report_name}"


class RiskAuditRecord(BaseModel, TimestampMixin):
    """风险审计记录模型"""

    # 风险类型常量
    RISK_TYPE_UNAUTHORIZED_ACCESS = "unauthorized_access"
    RISK_TYPE_SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    RISK_TYPE_OUTPUT_BIAS = "output_bias"
    RISK_TYPE_COST_ANOMALY = "cost_anomaly"
    RISK_TYPE_HALLUCINATION = "hallucination"
    RISK_TYPE_SECURITY_RISK = "security_risk"
    RISK_TYPE_COMPLIANCE_RISK = "compliance_risk"

    # 风险级别常量
    RISK_LEVEL_LOW = "low"
    RISK_LEVEL_MEDIUM = "medium"
    RISK_LEVEL_HIGH = "high"
    RISK_LEVEL_CRITICAL = "critical"

    trace_id = fields.CharField(max_length=100, null=True, description="全链路追踪ID", index=True)
    
    risk_type = fields.CharField(max_length=50, description="风险类型", index=True)
    risk_level = fields.CharField(max_length=20, description="风险级别", index=True)
    
    title = fields.CharField(max_length=500, description="风险标题")
    description = fields.TextField(null=True, description="风险描述")
    details = fields.JSONField(null=True, description="风险详情")
    
    related_user_id = fields.BigIntField(null=True, description="关联用户ID")
    related_record_id = fields.CharField(max_length=100, null=True, description="关联记录ID")
    
    status = fields.CharField(max_length=20, default="open", description="状态(open/resolved/ignored)")
    resolved_by = fields.BigIntField(null=True, description="处理人ID")
    resolved_time = fields.DatetimeField(null=True, description="处理时间")
    resolution_note = fields.TextField(null=True, description="处理说明")
    
    class Meta:
        table = "audit_risk_record"
        table_description = "风险审计记录表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"RiskAuditRecord {self.id}: {self.risk_type} - {self.risk_level}"


class AuditConfig(BaseModel, TimestampMixin):
    """审计配置模型"""

    module_name = fields.CharField(max_length=100, unique=True, description="模块名称", index=True)
    display_name = fields.CharField(max_length=100, description="显示名称")
    enabled = fields.BooleanField(default=True, description="是否启用")
    
    log_create = fields.BooleanField(default=True, description="记录创建操作")
    log_update = fields.BooleanField(default=True, description="记录更新操作")
    log_delete = fields.BooleanField(default=True, description="记录删除操作")
    log_query = fields.BooleanField(default=False, description="记录查询操作")
    
    sensitive_fields = fields.JSONField(null=True, description="敏感字段列表")
    exclude_paths = fields.JSONField(null=True, description="排除路径列表")
    retention_days = fields.IntField(default=90, description="保留天数")
    
    alert_enabled = fields.BooleanField(default=False, description="是否启用告警")
    alert_rules = fields.JSONField(null=True, description="告警规则")
    
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "audit_config"
        table_description = "审计配置表"
        ordering = ["module_name"]

    def __str__(self):
        return f"AuditConfig {self.id}: {self.module_name}"


class DataChangeLog(BaseModel, TimestampMixin):
    """数据变更日志模型"""

    table_name = fields.CharField(max_length=100, description="表名", index=True)
    record_id = fields.CharField(max_length=100, description="记录ID", index=True)
    change_type = fields.CharField(max_length=50, description="变更类型", index=True)
    before_data = fields.JSONField(null=True, description="变更前数据")
    after_data = fields.JSONField(null=True, description="变更后数据")
    changed_fields = fields.JSONField(null=True, description="变更字段列表")
    
    user_id = fields.BigIntField(null=True, description="操作用户ID", index=True)
    username = fields.CharField(max_length=50, null=True, description="操作用户名")
    ip_address = fields.CharField(max_length=50, null=True, description="IP地址")
    user_agent = fields.CharField(max_length=500, null=True, description="用户代理")
    
    trace_id = fields.CharField(max_length=100, null=True, description="全链路追踪ID", index=True)
    business_no = fields.CharField(max_length=100, null=True, description="业务流水号")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "data_change_log"
        table_description = "数据变更日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"DataChangeLog {self.id}: {self.change_type} on {self.table_name}"


class LoginLog(BaseModel, TimestampMixin):
    """登录审计日志模型"""

    user_id = fields.BigIntField(null=True, description="用户ID", index=True)
    username = fields.CharField(max_length=50, null=True, description="用户名", index=True)
    login_type = fields.CharField(max_length=50, description="登录类型", index=True)
    login_method = fields.CharField(max_length=50, default="password", description="登录方式")
    
    ip_address = fields.CharField(max_length=50, null=True, description="IP地址", index=True)
    location = fields.CharField(max_length=200, null=True, description="地理位置")
    user_agent = fields.CharField(max_length=500, null=True, description="用户代理")
    device_info = fields.JSONField(null=True, description="设备信息")
    
    success = fields.BooleanField(default=True, description="是否成功", index=True)
    fail_reason = fields.TextField(null=True, description="失败原因")
    
    session_id = fields.CharField(max_length=100, null=True, description="会话ID")
    token_id = fields.CharField(max_length=100, null=True, description="Token ID")

    class Meta:
        table = "login_log"
        table_description = "登录审计日志表"
        ordering = ["-created_at"]

    def __str__(self):
        return f"LoginLog {self.id}: {self.login_type} by {self.username}"
