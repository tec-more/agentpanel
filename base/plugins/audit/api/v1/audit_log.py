from fastapi import APIRouter, Depends, Query, status
from typing import Optional
from datetime import datetime

from base.plugins.audit.schemas.audit_log import (
    AuditLogResponse,
    AuditLogUpdate,
    AuditLogQuery,
    InputLayerLogResponse,
    DecisionLayerLogResponse,
    ExecutionLayerLogResponse,
    OutputLayerLogResponse,
    SystemLayerLogResponse,
    AuditReportResponse,
    RiskAuditRecordResponse,
    RiskAuditRecordUpdate,
    FullTraceResponse
)
from base.plugins.audit.services.audit_service import (
    AuditLogService,
    AuditTraceService,
    InputLayerService,
    DecisionLayerService,
    ExecutionLayerService,
    OutputLayerService,
    SystemLayerService,
    AuditReportService,
    RiskAuditService
)
from base.plugins.audit.services.data_change_service import MIN_RETENTION_DAYS
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

audit_log_router = APIRouter(prefix="/audit-logs", tags=["审计日志"])

# 全链路追踪路由
@audit_log_router.get("/trace/list")
async def get_trace_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    trace_id: Optional[str] = Query(None, description="追踪ID"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    module: Optional[str] = Query(None, description="模块"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    traces, total = await AuditTraceService.get_trace_list(
        page=page,
        page_size=page_size,
        trace_id=trace_id,
        user_id=user_id,
        module=module,
        start_time=start_time,
        end_time=end_time
    )
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": traces
    })


@audit_log_router.get("/trace/{trace_id}")
async def get_full_trace(
    trace_id: str,
    current_user_id: int = Depends(get_current_user_id)
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    trace = await AuditTraceService.get_full_trace(trace_id)
    return SuccessResponse(data=trace)


@audit_log_router.get("/list")
async def get_audit_log_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    trace_id: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    ip_address: Optional[str] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    logs, total = await AuditLogService.get_log_list(
        page=page,
        page_size=page_size,
        trace_id=trace_id,
        username=username,
        module=module,
        operation=operation,
        method=method,
        level=level,
        status=status,
        start_time=start_time,
        end_time=end_time,
        ip_address=ip_address
    )
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [await log.to_dict() for log in logs]
    })


@audit_log_router.get("/{log_id}")
async def get_audit_log_detail(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    log = await AuditLogService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="审计日志不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await log.to_dict())


@audit_log_router.put("/{log_id}")
async def update_audit_log(
    log_id: int,
    data: AuditLogUpdate,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    log = await AuditLogService.update_log(log_id, data, review_user_id=current_user_id)
    if not log:
        return ErrorResponse(msg="审计日志不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await log.to_dict(), msg="审核成功")


@audit_log_router.delete("/cleanup")
async def cleanup_old_logs(
    days: int = Query(90, description=f"保留天数，最小 {MIN_RETENTION_DAYS} 天"),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    if days < MIN_RETENTION_DAYS:
        return ErrorResponse(
            msg=f"保留天数最小为 {MIN_RETENTION_DAYS} 天（当前 {days} 天），过小会误删近期审计数据",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    count = await AuditLogService.delete_old_logs(days)
    return SuccessResponse(data={"deleted": count}, msg=f"清理了{count}条旧日志")


@audit_log_router.get("/statistics/overview")
async def get_audit_statistics(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    stats = await AuditLogService.get_statistics(start_time=start_time, end_time=end_time)
    return SuccessResponse(data=stats)


@audit_log_router.get("/input-layers/{log_id}")
async def get_input_layer_log(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    log = await InputLayerService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="日志不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await log.to_dict())


@audit_log_router.get("/decision-layers/{log_id}")
async def get_decision_layer_log(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    log = await DecisionLayerService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="日志不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await log.to_dict())


@audit_log_router.get("/execution-layers/{log_id}")
async def get_execution_layer_log(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    log = await ExecutionLayerService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="日志不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await log.to_dict())


@audit_log_router.get("/output-layers/{log_id}")
async def get_output_layer_log(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    log = await OutputLayerService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="日志不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await log.to_dict())


@audit_log_router.get("/system-layers/{log_id}")
async def get_system_layer_log(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    log = await SystemLayerService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="日志不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await log.to_dict())


@audit_log_router.get("/reports/list")
async def get_reports_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    report_type: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    reports, total = await AuditReportService.get_report_list(
        page=page,
        page_size=page_size,
        report_type=report_type,
        start_time=start_time,
        end_time=end_time
    )
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [await report.to_dict() for report in reports]
    })


@audit_log_router.get("/reports/{report_id}")
async def get_report_detail(
    report_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    report = await AuditReportService.get_report_by_id(report_id)
    if not report:
        return ErrorResponse(msg="报告不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await report.to_dict())


@audit_log_router.post("/reports/generate/compliance")
async def generate_compliance_report(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    report = await AuditReportService.generate_compliance_report(
        start_time=start_time,
        end_time=end_time,
        generated_by=current_user_id,
        generated_by_name=current_user.username
    )
    
    return SuccessResponse(data=await report.to_dict(), msg="合规审计报告生成成功")


@audit_log_router.post("/reports/generate/risk")
async def generate_risk_report(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    report = await AuditReportService.generate_risk_report(
        start_time=start_time,
        end_time=end_time,
        generated_by=current_user_id,
        generated_by_name=current_user.username
    )
    
    return SuccessResponse(data=await report.to_dict(), msg="风险审计报告生成成功")


@audit_log_router.get("/risks/list")
async def get_risk_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    trace_id: Optional[str] = Query(None),
    risk_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    records, total = await RiskAuditService.get_record_list(
        page=page,
        page_size=page_size,
        trace_id=trace_id,
        risk_type=risk_type,
        risk_level=risk_level,
        status=status,
        start_time=start_time,
        end_time=end_time
    )
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [await record.to_dict() for record in records]
    })


@audit_log_router.get("/risks/{record_id}")
async def get_risk_record_detail(
    record_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    record = await RiskAuditService.get_record_by_id(record_id)
    if not record:
        return ErrorResponse(msg="风险记录不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    return SuccessResponse(data=await record.to_dict())


@audit_log_router.put("/risks/{record_id}")
async def update_risk_record(
    record_id: int,
    data: RiskAuditRecordUpdate,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    record = await RiskAuditService.update_record(record_id, data)
    if not record:
        return ErrorResponse(msg="风险记录不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    record_dict = await record.to_dict()
    return SuccessResponse(data=record_dict, msg="风险记录更新成功")


@audit_log_router.put("/risks/{record_id}/status")
async def update_risk_status(
    record_id: int,
    status_val: str = Query(..., alias="status", description="新状态"),
    comment: Optional[str] = Query(None, description="处理备注"),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    record = await RiskAuditService.update_status(
        record_id, 
        status_val, 
        resolved_by=current_user_id, 
        resolution_note=comment
    )
    if not record:
        return ErrorResponse(msg="风险记录不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    record_dict = await record.to_dict()
    return SuccessResponse(data=record_dict, msg="状态更新成功")


@audit_log_router.get("/risks/statistics")
async def get_risk_statistics(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    stats = await RiskAuditService.get_statistics(start_time=start_time, end_time=end_time)
    return SuccessResponse(data=stats)


@audit_log_router.post("/reports")
async def create_audit_report(
    report_name: str = Query(...),
    report_type: str = Query(...),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    summary: Optional[str] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    report = await AuditReportService.create_report_simple(
        report_name=report_name,
        report_type=report_type,
        start_time=start_time,
        end_time=end_time,
        summary=summary,
        modules=[],
        generated_by=current_user_id,
        generated_by_name=current_user.username
    )
    
    report_dict = await report.to_dict()
    return SuccessResponse(data=report_dict, msg="报告创建成功")


@audit_log_router.put("/reports/{report_id}")
async def update_audit_report(
    report_id: int,
    report_name: Optional[str] = Query(None),
    summary: Optional[str] = Query(None),
    status_val: Optional[str] = Query(None, alias="status"),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    report = await AuditReportService.update_report(
        report_id,
        report_name=report_name,
        summary=summary,
        status=status_val
    )
    if not report:
        return ErrorResponse(msg="报告不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    report_dict = await report.to_dict()
    return SuccessResponse(data=report_dict, msg="报告更新成功")


@audit_log_router.get("/reports/{report_id}/download")
async def download_audit_report(
    report_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    from fastapi.responses import FileResponse
    import tempfile
    import json
    
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)
    
    report = await AuditReportService.get_report_by_id(report_id)
    if not report:
        return ErrorResponse(msg="报告不存在", status_code=status.HTTP_404_NOT_FOUND)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(json.dumps(await report.to_dict(), ensure_ascii=False, indent=2))
        temp_file = f.name
    
    return FileResponse(temp_file, filename=f"{report.report_name}.json")
