from fastapi import APIRouter, Depends, Query, status
from typing import Optional, List, Dict, Any
from datetime import datetime

from base.plugins.audit.models.audit_log import (
    InputLayerLog, DecisionLayerLog, ExecutionLayerLog, 
    OutputLayerLog, SystemLayerLog, AuditLog
)
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

trace_router = APIRouter(prefix="/trace", tags=["全链路追踪"])


@trace_router.get("/list")
async def get_trace_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    trace_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="no permission", status_code=status.HTTP_403_FORBIDDEN)

    query = AuditLog.filter(trace_id__isnull=False)
    
    if user_id:
        try:
            user_id_int = int(user_id)
            query = query.filter(user_id=user_id_int)
        except ValueError:
            pass
    if module:
        query = query.filter(module=module)
    if start_time:
        query = query.filter(created_at__gte=start_time)
    if end_time:
        query = query.filter(created_at__lte=end_time)

    audit_logs = await query.all()
    trace_ids = list({log.trace_id for log in audit_logs if log.trace_id})
    
    if trace_id:
        trace_ids = [t for t in trace_ids if trace_id in t]

    total = len(trace_ids)
    offset = (page - 1) * page_size
    paginated_trace_ids = trace_ids[offset:offset + page_size]

    trace_list = []
    for tid in paginated_trace_ids:
        input_log = await InputLayerLog.get_or_none(trace_id=tid)
        decision_log = await DecisionLayerLog.get_or_none(trace_id=tid)
        execution_logs = await ExecutionLayerLog.filter(trace_id=tid).order_by("created_at")
        output_log = await OutputLayerLog.get_or_none(trace_id=tid)
        system_log = await SystemLayerLog.get_or_none(trace_id=tid)
        
        audit_log = await AuditLog.get_or_none(trace_id=tid)
        
        trace_data = {
            "trace_id": tid,
            "level": audit_log.level if audit_log else "info",
            "module": audit_log.module if audit_log else None,
            "operation": audit_log.operation if audit_log else None,
            "user_id": input_log.user_id if input_log else (audit_log.user_id if audit_log else None),
            "username": input_log.username if input_log else (audit_log.username if audit_log else None),
            "phase": "completed",
            "duration": None,
            "status": "success",
            "created_at": None
        }
        
        if execution_logs:
            durations = [log.duration for log in execution_logs if log.duration]
            trace_data["duration"] = sum(durations) if durations else None
            
            if any(log.status == "failed" for log in execution_logs):
                trace_data["status"] = "failed"
        
        if output_log and output_log.is_hallucination:
            trace_data["status"] = "failed"
        
        first_created = None
        if input_log:
            first_created = input_log.created_at
        elif audit_log:
            first_created = audit_log.created_at
        elif execution_logs:
            first_created = execution_logs[0].created_at
        
        trace_data["created_at"] = first_created
        
        trace_list.append(trace_data)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": trace_list,
    }

    return SuccessResponse(data=response_data)


@trace_router.get("/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="no permission", status_code=status.HTTP_403_FORBIDDEN)

    input_log = await InputLayerLog.get_or_none(trace_id=trace_id)
    decision_log = await DecisionLayerLog.get_or_none(trace_id=trace_id)
    execution_logs = await ExecutionLayerLog.filter(trace_id=trace_id).order_by("created_at")
    output_log = await OutputLayerLog.get_or_none(trace_id=trace_id)
    system_log = await SystemLayerLog.get_or_none(trace_id=trace_id)
    
    input_dict = await input_log.to_dict() if input_log else None
    decision_dict = await decision_log.to_dict() if decision_log else None
    execution_list = [await e.to_dict() for e in execution_logs]
    output_dict = await output_log.to_dict() if output_log else None
    system_dict = await system_log.to_dict() if system_log else None
    
    audit_logs = await AuditLog.filter(trace_id=trace_id).order_by("created_at")
    audit_list = [await a.to_dict() for a in audit_logs]

    trace_detail = {
        "trace_id": trace_id,
        "input_layer": input_dict,
        "decision_layer": decision_dict,
        "execution_layer": execution_list,
        "output_layer": output_dict,
        "system_layer": system_dict,
        "audit_logs": audit_list
    }

    return SuccessResponse(data=trace_detail)