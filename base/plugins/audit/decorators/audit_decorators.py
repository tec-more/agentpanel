import json
import traceback
from typing import Optional, Any, Callable
from functools import wraps
from datetime import datetime

from fastapi import Request
from base.plugins.audit.models.audit_log import (
    AuditLog,
    InputLayerLog,
    DecisionLayerLog,
    ExecutionLayerLog,
    OutputLayerLog,
    SystemLayerLog
)
from base.plugins.audit.schemas.audit_log import (
    AuditLogCreate,
    InputLayerLogCreate,
    DecisionLayerLogCreate,
    ExecutionLayerLogCreate,
    OutputLayerLogCreate,
    SystemLayerLogCreate
)
from base.plugins.audit.services.audit_service import (
    AuditLogService,
    InputLayerService,
    DecisionLayerService,
    ExecutionLayerService,
    OutputLayerService,
    SystemLayerService,
    RiskAuditService,
    generate_trace_id,
    get_current_trace_id,
    set_current_trace_id,
    clear_trace_id
)


# ============ 全链路追踪装饰器 ============

def trace_audit(
    module: Optional[str] = None,
    operation: Optional[str] = None,
    include_input: bool = True,
    include_output: bool = True
):
    """
    全链路追踪装饰器
    
    Args:
        module: 模块名称
        operation: 操作描述
        include_input: 是否记录输入层
        include_output: 是否记录输出层
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 开始追踪
            trace_id = generate_trace_id()
            set_current_trace_id(trace_id)
            
            request = kwargs.get("request")
            user_id = None
            username = None
            
            if request and hasattr(request.state, "user_id"):
                user_id = request.state.user_id
            if request and hasattr(request.state, "username"):
                username = request.state.username
            
            if not module:
                module = func.__module__.split(".")[-2] if len(func.__module__.split(".")) >= 2 else "default"
            if not operation:
                operation = func.__name__
            
            start_time = datetime.now()
            error_message = None
            status_code = 200
            result = None
            
            try:
                # 记录输入层
                if include_input:
                    input_data = {}
                    if request:
                        try:
                            body = await request.body()
                            if body:
                                input_data = json.loads(body.decode("utf-8"))
                        except:
                            pass
                        
                        # 获取查询参数
                        input_data.update(dict(request.query_params))
                    
                    input_log = InputLayerLogCreate(
                        trace_id=trace_id,
                        user_id=user_id,
                        username=username,
                        user_instruction=operation,
                        context_data=input_data if input_data else None
                    )
                    await InputLayerService.create_log(input_log)
                
                # 执行实际函数
                result = await func(*args, **kwargs)
                
                # 记录输出层
                if include_output:
                    output_data = str(result) if result else None
                    output_log = OutputLayerLogCreate(
                        trace_id=trace_id,
                        final_output=output_data or "",
                        format_compliance=True
                    )
                    await OutputLayerService.create_log(output_log)
                
                return result
                
            except Exception as e:
                error_message = str(e)
                status_code = 500
                
                # 记录系统层异常
                system_log = SystemLayerLogCreate(
                    trace_id=trace_id,
                    event_type="exception",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                await SystemLayerService.create_log(system_log)
                
                # 记录风险
                await RiskAuditService.record_risk(
                    risk_type="system_error",
                    risk_level="high",
                    title=f"系统异常: {type(e).__name__}",
                    description=str(e),
                    details={"stack_trace": traceback.format_exc()},
                    trace_id=trace_id
                )
                
                raise
            finally:
                # 计算执行时长
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                
                # 记录审计日志
                try:
                    audit_log_data = AuditLogCreate(
                        trace_id=trace_id,
                        user_id=user_id,
                        username=username,
                        module=module,
                        operation=operation,
                        method=request.method if request else "UNKNOWN",
                        path=str(request.url.path) if request else "",
                        ip_address=request.client.host if (request and request.client) else None,
                        user_agent=request.headers.get("user-agent") if request else None,
                        status_code=status_code,
                        error_message=error_message,
                        duration=duration,
                        level="error" if status_code >= 400 else "info",
                        business_no=trace_id
                    )
                    await AuditLogService.create_log(audit_log_data)
                except Exception as e:
                    print(f"Failed to create audit log: {e}")
                
                # 清除追踪ID
                clear_trace_id()
        
        return wrapper
    return decorator


# ============ 决策层审计装饰器 ============

def decision_audit(
    decision_type: str = "decision",
    include_thought_chain: bool = True
):
    """
    决策层审计装饰器
    
    Args:
        decision_type: 决策类型
        include_thought_chain: 是否记录思维链
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            trace_id = get_current_trace_id() or generate_trace_id()
            start_time = datetime.now()
            
            try:
                # 提取决策前的参数
                intent_recognition = kwargs.get("intent_data")
                task_decomposition = kwargs.get("task_data")
                
                # 执行决策函数
                result = await func(*args, **kwargs)
                
                # 记录决策层
                try:
                    decision_log = DecisionLayerLogCreate(
                        trace_id=trace_id,
                        intent_recognition=intent_recognition,
                        task_decomposition=task_decomposition,
                        reasoning_path=kwargs.get("reasoning_path"),
                        thought_chain=str(result) if include_thought_chain and result else None,
                        confidence=kwargs.get("confidence")
                    )
                    await DecisionLayerService.create_log(decision_log)
                except Exception as e:
                    print(f"Failed to create decision log: {e}")
                
                return result
                
            except Exception as e:
                # 记录决策失败
                try:
                    decision_log = DecisionLayerLogCreate(
                        trace_id=trace_id,
                        intent_recognition=kwargs.get("intent_data"),
                        task_decomposition=kwargs.get("task_data"),
                        fallback_reason=str(e)
                    )
                    await DecisionLayerService.create_log(decision_log)
                except Exception as log_error:
                    print(f"Failed to create decision log: {log_error}")
                
                raise
        
        return wrapper
    return decorator


# ============ 执行层审计装饰器 ============

def execution_audit(
    execution_type: str = "tool_call",
    target_name: Optional[str] = None,
    mask_sensitive: bool = True,
    sensitive_fields: Optional[list] = None
):
    """
    执行层审计装饰器
    
    Args:
        execution_type: 执行类型 (tool_call, api_call, data_read, data_write, permission_check)
        target_name: 目标名称
        mask_sensitive: 是否脱敏敏感字段
        sensitive_fields: 敏感字段列表
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            trace_id = get_current_trace_id() or generate_trace_id()
            start_time = datetime.now()
            
            if not target_name:
                target = func.__name__
            else:
                target = target_name
            
            # 准备参数（可能需要脱敏）
            params = {}
            for key, value in kwargs.items():
                if key not in ["request", "call_next"]:
                    params[key] = value
            
            if mask_sensitive and sensitive_fields:
                params = _mask_sensitive_fields(params, sensitive_fields)
            
            error_message = None
            status = "success"
            result_data = None
            
            try:
                # 执行函数
                result = await func(*args, **kwargs)
                result_data = result
                
                # 脱敏返回值
                if mask_sensitive and sensitive_fields and result_data:
                    if isinstance(result_data, dict):
                        result_data = _mask_sensitive_fields(result_data, sensitive_fields)
                
                return result
                
            except Exception as e:
                error_message = str(e)
                status = "failed"
                
                # 记录风险
                await RiskAuditService.record_risk(
                    risk_type="execution_error",
                    risk_level="medium",
                    title=f"执行失败: {target}",
                    description=str(e),
                    details={"execution_type": execution_type, "target": target},
                    trace_id=trace_id
                )
                
                raise
            finally:
                # 计算执行时长
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                
                # 记录执行层日志
                try:
                    execution_log = ExecutionLayerLogCreate(
                        trace_id=trace_id,
                        execution_type=execution_type,
                        target_name=target,
                        parameters=params,
                        return_value=result_data,
                        status=status,
                        error_message=error_message,
                        duration=duration,
                        start_time=start_time,
                        end_time=datetime.now()
                    )
                    await ExecutionLayerService.create_log(execution_log)
                except Exception as e:
                    print(f"Failed to create execution log: {e}")
        
        return wrapper
    return decorator


# ============ 工具函数 ============

def _mask_sensitive_fields(data: Any, sensitive_fields: list) -> Any:
    """
    脱敏敏感字段
    
    Args:
        data: 数据
        sensitive_fields: 敏感字段列表
    
    Returns:
        脱敏后的数据
    """
    if not data or not sensitive_fields:
        return data
    
    if isinstance(data, dict):
        masked_data = data.copy()
        for key, value in masked_data.items():
            if key.lower() in [field.lower() for field in sensitive_fields]:
                masked_data[key] = "***"
            elif isinstance(value, dict):
                masked_data[key] = _mask_sensitive_fields(value, sensitive_fields)
            elif isinstance(value, list):
                masked_data[key] = [
                    _mask_sensitive_fields(item, sensitive_fields) if isinstance(item, dict) else item
                    for item in value
                ]
        return masked_data
    elif isinstance(data, list):
        return [
            _mask_sensitive_fields(item, sensitive_fields) if isinstance(item, dict) else item
            for item in data
        ]
    return data


def _get_changed_fields(before_data: dict, after_data: dict) -> list:
    """
    获取变更的字段列表
    
    Args:
        before_data: 变更前数据
        after_data: 变更后数据
    
    Returns:
        变更字段列表
    """
    changed_fields = []
    
    all_keys = set(before_data.keys()).union(set(after_data.keys()))
    
    for key in all_keys:
        before_value = before_data.get(key)
        after_value = after_data.get(key)
        
        if before_value != after_value:
            changed_fields.append(key)
    
    return changed_fields
