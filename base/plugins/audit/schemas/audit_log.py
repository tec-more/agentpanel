from typing import Optional, Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field


class AuditLogBase(BaseModel):
    trace_id: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    module: Optional[str] = None
    operation: str
    method: str
    path: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_params: Optional[Dict[str, Any]] = None
    response_data: Optional[str] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    duration: Optional[int] = None
    level: str = "info"
    business_no: Optional[str] = None
    related_record_id: Optional[str] = None
    status: str = "pending"


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogUpdate(BaseModel):
    status: Optional[str] = None
    review_user_id: Optional[int] = None
    review_time: Optional[datetime] = None
    review_comment: Optional[str] = None


class AuditLogResponse(AuditLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    review_user_id: Optional[int] = None
    review_time: Optional[datetime] = None
    review_comment: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogQuery(BaseModel):
    page: int = 1
    page_size: int = 20
    trace_id: Optional[str] = None
    username: Optional[str] = None
    module: Optional[str] = None
    operation: Optional[str] = None
    method: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    ip_address: Optional[str] = None


class InputLayerLogBase(BaseModel):
    trace_id: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    user_instruction: str
    context_data: Optional[Dict[str, Any]] = None
    prompt_version: Optional[str] = None
    prompt_template: Optional[str] = None
    prompt_variables: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None


class InputLayerLogCreate(InputLayerLogBase):
    pass


class InputLayerLogResponse(InputLayerLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DecisionLayerLogBase(BaseModel):
    trace_id: str
    intent_recognition: Optional[Dict[str, Any]] = None
    task_decomposition: Optional[Dict[str, Any]] = None
    reasoning_path: Optional[Dict[str, Any]] = None
    thought_chain: Optional[str] = None
    confidence: Optional[float] = None
    decision_tree: Optional[Dict[str, Any]] = None
    rule_matches: Optional[Dict[str, Any]] = None
    fallback_reason: Optional[str] = None


class DecisionLayerLogCreate(DecisionLayerLogBase):
    pass


class DecisionLayerLogResponse(DecisionLayerLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExecutionLayerLogBase(BaseModel):
    trace_id: str
    step_id: Optional[str] = None
    execution_type: str
    target_name: str
    parameters: Optional[Dict[str, Any]] = None
    return_value: Optional[Dict[str, Any]] = None
    status: str = "success"
    error_message: Optional[str] = None
    duration: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    permission_check_result: Optional[bool] = None
    permission_details: Optional[Dict[str, Any]] = None
    data_source: Optional[str] = None
    data_operation: Optional[str] = None


class ExecutionLayerLogCreate(ExecutionLayerLogBase):
    pass


class ExecutionLayerLogResponse(ExecutionLayerLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OutputLayerLogBase(BaseModel):
    trace_id: str
    final_output: str
    output_format: Optional[str] = None
    format_compliance: bool = True
    format_issues: Optional[List[Dict[str, Any]]] = None
    is_hallucination: bool = False
    hallucination_details: Optional[str] = None
    hallucination_confidence: Optional[float] = None
    sensitive_content_detected: bool = False
    sensitive_content_filtered: bool = False
    sensitive_content_details: Optional[Dict[str, Any]] = None
    citations: Optional[List[Dict[str, Any]]] = None
    data_sources: Optional[List[Dict[str, Any]]] = None
    reasoning_evidence: Optional[str] = None


class OutputLayerLogCreate(OutputLayerLogBase):
    pass


class OutputLayerLogResponse(OutputLayerLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SystemLayerLogBase(BaseModel):
    trace_id: Optional[str] = None
    event_type: str
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    model_provider: Optional[str] = None
    config_key: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    deployment_version: Optional[str] = None
    deployment_target: Optional[str] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    stack_trace: Optional[str] = None
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    reason: Optional[str] = None


class SystemLayerLogCreate(SystemLayerLogBase):
    pass


class SystemLayerLogResponse(SystemLayerLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditReportBase(BaseModel):
    report_type: str
    report_name: str
    start_time: datetime
    end_time: datetime
    report_data: Dict[str, Any]
    summary: Optional[str] = None
    generated_by: Optional[int] = None
    generated_by_name: Optional[str] = None
    status: str = "generated"


class AuditReportCreate(AuditReportBase):
    pass


class AuditReportResponse(AuditReportBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RiskAuditRecordBase(BaseModel):
    trace_id: Optional[str] = None
    risk_type: str
    risk_level: str
    title: str
    description: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    related_user_id: Optional[int] = None
    related_record_id: Optional[str] = None
    status: str = "open"
    resolved_by: Optional[int] = None
    resolved_time: Optional[datetime] = None
    resolution_note: Optional[str] = None


class RiskAuditRecordCreate(RiskAuditRecordBase):
    pass


class RiskAuditRecordUpdate(BaseModel):
    status: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_time: Optional[datetime] = None
    resolution_note: Optional[str] = None


class RiskAuditRecordResponse(RiskAuditRecordBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FullTraceQuery(BaseModel):
    trace_id: str


class FullTraceResponse(BaseModel):
    trace_id: str
    input_layer: Optional[InputLayerLogResponse] = None
    decision_layers: List[DecisionLayerLogResponse] = []
    execution_layers: List[ExecutionLayerLogResponse] = []
    output_layer: Optional[OutputLayerLogResponse] = None
    system_layers: List[SystemLayerLogResponse] = []
    audit_logs: List[AuditLogResponse] = []
    risk_records: List[RiskAuditRecordResponse] = []


class DataChangeLogBase(BaseModel):
    table_name: str
    record_id: str
    change_type: str
    before_data: Optional[Dict[str, Any]] = None
    after_data: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    business_no: Optional[str] = None
    remark: Optional[str] = None


class DataChangeLogCreate(DataChangeLogBase):
    pass


class DataChangeLogResponse(DataChangeLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataChangeLogQuery(BaseModel):
    page: int = 1
    page_size: int = 20
    table_name: Optional[str] = None
    record_id: Optional[str] = None
    change_type: Optional[str] = None
    username: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class LoginLogBase(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    login_type: str
    login_method: str = "password"
    ip_address: Optional[str] = None
    location: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    success: bool = True
    fail_reason: Optional[str] = None
    session_id: Optional[str] = None
    token_id: Optional[str] = None


class LoginLogCreate(LoginLogBase):
    pass


class LoginLogResponse(LoginLogBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginLogQuery(BaseModel):
    page: int = 1
    page_size: int = 20
    username: Optional[str] = None
    login_type: Optional[str] = None
    login_method: Optional[str] = None
    success: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    ip_address: Optional[str] = None


class AuditConfigBase(BaseModel):
    module_name: str
    display_name: str
    enabled: bool = True
    log_create: bool = True
    log_update: bool = True
    log_delete: bool = True
    log_query: bool = False
    sensitive_fields: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    retention_days: int = 90
    alert_enabled: bool = False
    alert_rules: Optional[Dict[str, Any]] = None
    remark: Optional[str] = None


class AuditConfigCreate(AuditConfigBase):
    pass


class AuditConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    enabled: Optional[bool] = None
    log_create: Optional[bool] = None
    log_update: Optional[bool] = None
    log_delete: Optional[bool] = None
    log_query: Optional[bool] = None
    sensitive_fields: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    retention_days: Optional[int] = None
    alert_enabled: Optional[bool] = None
    alert_rules: Optional[Dict[str, Any]] = None
    remark: Optional[str] = None


class AuditConfigResponse(AuditConfigBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
