from fastapi import APIRouter, Depends, Query, status
from typing import Optional, List, Dict, Any
from datetime import datetime

from base.plugins.audit.models.audit_log import RiskAuditRecord
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

risks_router = APIRouter(prefix="/risks", tags=["风险审计"])


@risks_router.get("/list")
async def get_risk_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    risk_type: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="no permission", status_code=status.HTTP_403_FORBIDDEN)

    query = RiskAuditRecord.all()

    if risk_level:
        query = query.filter(risk_level=risk_level)
    if status:
        query = query.filter(status=status)
    if risk_type:
        query = query.filter(risk_type__icontains=risk_type)
    if start_time:
        query = query.filter(created_at__gte=start_time)
    if end_time:
        query = query.filter(created_at__lte=end_time)

    total = await query.count()
    offset = (page - 1) * page_size
    risks = await query.offset(offset).limit(page_size).order_by("-created_at")

    risk_list = []
    for risk in risks:
        risk_dict = await risk.to_dict()
        risk_list.append(risk_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": risk_list,
    }

    return SuccessResponse(data=response_data)


@risks_router.get("/{risk_id}")
async def get_risk_detail(
    risk_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="no permission", status_code=status.HTTP_403_FORBIDDEN)

    risk = await RiskAuditRecord.get_or_none(id=risk_id)
    if not risk:
        return ErrorResponse(msg="risk not found", status_code=status.HTTP_404_NOT_FOUND)

    risk_dict = await risk.to_dict()
    return SuccessResponse(data=risk_dict)


@risks_router.put("/{risk_id}/status")
async def update_risk_status(
    risk_id: int,
    status: str = Query(...),
    comment: Optional[str] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="no permission", status_code=status.HTTP_403_FORBIDDEN)

    risk = await RiskAuditRecord.get_or_none(id=risk_id)
    if not risk:
        return ErrorResponse(msg="risk not found", status_code=status.HTTP_404_NOT_FOUND)

    risk.status = status
    risk.resolved_by = current_user_id
    risk.resolved_time = datetime.now()
    risk.resolution_note = comment
    await risk.save()

    risk_dict = await risk.to_dict()
    return SuccessResponse(data=risk_dict, msg="updated")


@risks_router.get("/statistics")
async def get_risk_statistics(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
):
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="no permission", status_code=status.HTTP_403_FORBIDDEN)

    query = RiskAuditRecord.all()

    if start_time:
        query = query.filter(created_at__gte=start_time)
    if end_time:
        query = query.filter(created_at__lte=end_time)

    total = await query.count()
    critical = await query.filter(risk_level="critical").count()
    high = await query.filter(risk_level="high").count()
    medium = await query.filter(risk_level="medium").count()
    low = await query.filter(risk_level="low").count()
    pending = await query.filter(status="open").count()
    resolved = await query.filter(status="resolved").count()

    statistics = {
        "total": total,
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "pending": pending,
        "resolved": resolved,
    }

    return SuccessResponse(data=statistics)