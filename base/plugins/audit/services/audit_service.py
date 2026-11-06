import uuid
import time
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

from base.plugins.audit.models.audit_log import (
    AuditLog,
    InputLayerLog,
    DecisionLayerLog,
    ExecutionLayerLog,
    OutputLayerLog,
    SystemLayerLog,
    AuditReport,
    RiskAuditRecord
)
from base.plugins.audit.schemas.audit_log import (
    AuditLogCreate,
    AuditLogUpdate,
    InputLayerLogCreate,
    DecisionLayerLogCreate,
    ExecutionLayerLogCreate,
    OutputLayerLogCreate,
    SystemLayerLogCreate,
    AuditReportCreate,
    RiskAuditRecordCreate,
    RiskAuditRecordUpdate,
    FullTraceResponse
)
from base.common.context import (
    current_trace_id,
    current_user_id,
    current_username,
    set_trace_id,
    clear_trace_id as clear_context_trace_id
)


def generate_trace_id() -> str:
    """生成唯一的trace_id"""
    return str(uuid.uuid4())


def get_current_trace_id() -> Optional[str]:
    """获取当前的trace_id"""
    return current_trace_id.get()


def set_current_trace_id(trace_id: str) -> None:
    """设置当前的trace_id"""
    set_trace_id(trace_id)


def clear_trace_id() -> None:
    """清除当前的trace_id"""
    clear_context_trace_id()


class AuditTraceService:
    model = "audit_trace"
    """全链路追踪服务"""

    @staticmethod
    async def start_trace(
        user_id: Optional[int] = None,
        username: Optional[str] = None
    ) -> str:
        """开始一个新的追踪链路"""
        trace_id = generate_trace_id()
        set_current_trace_id(trace_id)
        return trace_id

    @staticmethod
    async def get_trace_list(
        page: int = 1,
        page_size: int = 20,
        trace_id: Optional[str] = None,
        user_id: Optional[int] = None,
        module: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[FullTraceResponse], int]:
        """获取追踪链路列表"""
        # 从审计日志中获取唯一的trace_id
        query = AuditLog.all()
        
        if trace_id:
            query = query.filter(trace_id=trace_id)
        if user_id:
            query = query.filter(user_id=user_id)
        if module:
            query = query.filter(module=module)
        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)
        
        # 获取唯一的trace_id
        audit_logs = await query.order_by("-created_at")
        trace_ids = list(set([log.trace_id for log in audit_logs if log.trace_id]))
        
        total = len(trace_ids)
        offset = (page - 1) * page_size
        trace_ids = trace_ids[offset:offset + page_size]
        
        traces = []
        for tid in trace_ids:
            trace = await AuditTraceService.get_full_trace(tid)
            traces.append(trace)
        
        return traces, total

    @staticmethod
    async def get_full_trace(trace_id: str) -> FullTraceResponse:
        """获取完整的追踪链路数据"""
        # 获取各层数据
        input_layer = await InputLayerLog.filter(trace_id=trace_id).first()
        decision_layers = await DecisionLayerLog.filter(trace_id=trace_id).order_by('created_at')
        execution_layers = await ExecutionLayerLog.filter(trace_id=trace_id).order_by('created_at')
        output_layer = await OutputLayerLog.filter(trace_id=trace_id).first()
        system_layers = await SystemLayerLog.filter(trace_id=trace_id).order_by('created_at')
        audit_logs = await AuditLog.filter(trace_id=trace_id).order_by('created_at')
        risk_records = await RiskAuditRecord.filter(trace_id=trace_id).order_by('created_at')

        # 转换为响应格式
        return FullTraceResponse(
            trace_id=trace_id,
            input_layer=await input_layer.to_dict() if input_layer else None,
            decision_layers=[await log.to_dict() for log in decision_layers],
            execution_layers=[await log.to_dict() for log in execution_layers],
            output_layer=await output_layer.to_dict() if output_layer else None,
            system_layers=[await log.to_dict() for log in system_layers],
            audit_logs=[await log.to_dict() for log in audit_logs],
            risk_records=[await log.to_dict() for log in risk_records]
        )


class InputLayerService:
    model = "input_layer"
    """输入层服务"""

    @staticmethod
    async def create_log(data: InputLayerLogCreate) -> InputLayerLog:
        """创建输入层日志"""
        if not data.trace_id:
            data.trace_id = get_current_trace_id() or generate_trace_id()
        
        log = await InputLayerLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[InputLayerLog]:
        """根据ID获取输入层日志"""
        return await InputLayerLog.get_or_none(id=log_id)

    @staticmethod
    async def get_logs_by_trace(trace_id: str) -> List[InputLayerLog]:
        """根据trace_id获取输入层日志"""
        return await InputLayerLog.filter(trace_id=trace_id).order_by('-created_at')


class DecisionLayerService:
    model = "decision_layer"
    """决策层服务"""

    @staticmethod
    async def create_log(data: DecisionLayerLogCreate) -> DecisionLayerLog:
        """创建决策层日志"""
        if not data.trace_id:
            data.trace_id = get_current_trace_id() or generate_trace_id()
        
        log = await DecisionLayerLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[DecisionLayerLog]:
        """根据ID获取决策层日志"""
        return await DecisionLayerLog.get_or_none(id=log_id)

    @staticmethod
    async def get_logs_by_trace(trace_id: str) -> List[DecisionLayerLog]:
        """根据trace_id获取决策层日志"""
        return await DecisionLayerLog.filter(trace_id=trace_id).order_by('created_at')


class ExecutionLayerService:
    model = "execution_layer"
    """执行层服务"""

    @staticmethod
    async def create_log(data: ExecutionLayerLogCreate) -> ExecutionLayerLog:
        """创建执行层日志"""
        if not data.trace_id:
            data.trace_id = get_current_trace_id() or generate_trace_id()
        
        log = await ExecutionLayerLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[ExecutionLayerLog]:
        """根据ID获取执行层日志"""
        return await ExecutionLayerLog.get_or_none(id=log_id)

    @staticmethod
    async def get_logs_by_trace(trace_id: str) -> List[ExecutionLayerLog]:
        """根据trace_id获取执行层日志"""
        return await ExecutionLayerLog.filter(trace_id=trace_id).order_by('created_at')


class OutputLayerService:
    model = "output_layer"
    """输出层服务"""

    @staticmethod
    async def create_log(data: OutputLayerLogCreate) -> OutputLayerLog:
        """创建输出层日志"""
        if not data.trace_id:
            data.trace_id = get_current_trace_id() or generate_trace_id()
        
        log = await OutputLayerLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[OutputLayerLog]:
        """根据ID获取输出层日志"""
        return await OutputLayerLog.get_or_none(id=log_id)

    @staticmethod
    async def get_logs_by_trace(trace_id: str) -> List[OutputLayerLog]:
        """根据trace_id获取输出层日志"""
        return await OutputLayerLog.filter(trace_id=trace_id).order_by('-created_at')


class SystemLayerService:
    model = "system_layer"
    """系统层服务"""

    @staticmethod
    async def create_log(data: SystemLayerLogCreate) -> SystemLayerLog:
        """创建系统层日志"""
        if not data.trace_id:
            data.trace_id = get_current_trace_id()
        
        log = await SystemLayerLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[SystemLayerLog]:
        """根据ID获取系统层日志"""
        return await SystemLayerLog.get_or_none(id=log_id)

    @staticmethod
    async def get_logs_by_trace(trace_id: str) -> List[SystemLayerLog]:
        """根据trace_id获取系统层日志"""
        return await SystemLayerLog.filter(trace_id=trace_id).order_by('-created_at')

    @staticmethod
    async def record_config_change(
        config_key: str,
        old_value: Optional[str],
        new_value: Optional[str],
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> SystemLayerLog:
        """记录配置变更"""
        log_data = SystemLayerLogCreate(
            trace_id=trace_id or get_current_trace_id(),
            event_type="config_change",
            config_key=config_key,
            old_value=old_value,
            new_value=new_value,
            operator_id=operator_id,
            operator_name=operator_name,
            reason=reason
        )
        return await SystemLayerService.create_log(log_data)

    @staticmethod
    async def record_exception(
        exception_type: str,
        exception_message: str,
        stack_trace: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> SystemLayerLog:
        """记录异常"""
        log_data = SystemLayerLogCreate(
            trace_id=trace_id or get_current_trace_id(),
            event_type="exception",
            exception_type=exception_type,
            exception_message=exception_message,
            stack_trace=stack_trace
        )
        return await SystemLayerService.create_log(log_data)


class AuditLogService:
    model = "audit_log"
    """审计日志服务"""

    @staticmethod
    async def create_log(data: AuditLogCreate) -> AuditLog:
        """创建审计日志"""
        if not data.trace_id:
            data.trace_id = get_current_trace_id()
        
        log = await AuditLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[AuditLog]:
        """根据ID获取审计日志"""
        return await AuditLog.get_or_none(id=log_id)

    @staticmethod
    async def get_log_list(
        page: int = 1,
        page_size: int = 20,
        trace_id: Optional[str] = None,
        username: Optional[str] = None,
        module: Optional[str] = None,
        operation: Optional[str] = None,
        method: Optional[str] = None,
        level: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[List[AuditLog], int]:
        """获取审计日志列表"""
        query = AuditLog.all()

        if trace_id:
            query = query.filter(trace_id=trace_id)
        if username:
            query = query.filter(username__icontains=username)
        if module:
            query = query.filter(module=module)
        if operation:
            query = query.filter(operation__icontains=operation)
        if method:
            query = query.filter(method=method)
        if level:
            query = query.filter(level=level)
        if status:
            query = query.filter(status=status)
        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)
        if ip_address:
            query = query.filter(ip_address__icontains=ip_address)

        total = await query.count()
        offset = (page - 1) * page_size
        logs = await query.offset(offset).limit(page_size).order_by("-created_at")

        return logs, total

    @staticmethod
    async def update_log(log_id: int, data: AuditLogUpdate, review_user_id: Optional[int] = None) -> Optional[AuditLog]:
        """更新审计日志"""
        log = await AuditLog.get_or_none(id=log_id)
        if not log:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if review_user_id:
            update_data["review_user_id"] = review_user_id
            update_data["review_time"] = datetime.now()

        for key, value in update_data.items():
            setattr(log, key, value)
        await log.save()
        return log

    @staticmethod
    async def delete_old_logs(days: int = 90) -> int:
        """删除旧日志"""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = await AuditLog.filter(created_at__lt=cutoff_date).delete()
        return deleted_count

    @staticmethod
    async def get_statistics(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取审计统计信息"""
        query = AuditLog.all()

        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)

        total = await query.count()
        info_count = await query.filter(level="info").count()
        warning_count = await query.filter(level="warning").count()
        error_count = await query.filter(level="error").count()
        critical_count = await query.filter(level="critical").count()

        return {
            "total": total,
            "info": info_count,
            "warning": warning_count,
            "error": error_count,
            "critical": critical_count,
        }


class AuditReportService:
    model = "audit_report"
    """审计报告服务"""

    @staticmethod
    async def create_report(data: AuditReportCreate) -> AuditReport:
        """创建审计报告"""
        report = await AuditReport.create(**data.model_dump(exclude_unset=True))
        return report

    @staticmethod
    async def get_report_by_id(report_id: int) -> Optional[AuditReport]:
        """根据ID获取审计报告"""
        return await AuditReport.get_or_none(id=report_id)

    @staticmethod
    async def get_report_list(
        page: int = 1,
        page_size: int = 20,
        report_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[AuditReport], int]:
        """获取审计报告列表"""
        query = AuditReport.all()

        if report_type:
            query = query.filter(report_type=report_type)
        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)

        total = await query.count()
        offset = (page - 1) * page_size
        reports = await query.offset(offset).limit(page_size).order_by("-created_at")

        return reports, total

    @staticmethod
    async def create_report_simple(
        report_name: str,
        report_type: str,
        start_time: datetime,
        end_time: datetime,
        summary: Optional[str] = None,
        modules: Optional[List[str]] = None,
        generated_by: Optional[int] = None,
        generated_by_name: Optional[str] = None
    ) -> AuditReport:
        """创建审计报告（简化版）"""
        report_data = {
            "modules": modules or [],
            "summary": summary
        }
        
        report = await AuditReport.create(
            report_type=report_type,
            report_name=report_name,
            start_time=start_time,
            end_time=end_time,
            report_data=report_data,
            summary=summary,
            generated_by=generated_by,
            generated_by_name=generated_by_name,
            status="generated"
        )
        return report

    @staticmethod
    async def update_report(
        report_id: int,
        report_name: Optional[str] = None,
        summary: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[AuditReport]:
        """更新审计报告"""
        report = await AuditReport.get_or_none(id=report_id)
        if not report:
            return None
        
        if report_name:
            report.report_name = report_name
        if summary:
            report.summary = summary
        if status:
            report.status = status
        await report.save()
        return report

    @staticmethod
    async def generate_compliance_report(
        start_time: datetime,
        end_time: datetime,
        generated_by: Optional[int] = None,
        generated_by_name: Optional[str] = None
    ) -> AuditReport:
        """生成合规审计报告"""
        # 收集各项统计数据
        audit_stats = await AuditLogService.get_statistics(start_time, end_time)
        
        # 获取风险记录
        risk_records = await RiskAuditRecord.filter(created_at__gte=start_time, created_at__lte=end_time).all()
        risk_stats = {
            "total": len(risk_records),
            "open": len([r for r in risk_records if r.status == "open"]),
            "resolved": len([r for r in risk_records if r.status == "resolved"]),
            "by_level": {}
        }
        
        # 按风险级别统计
        for record in risk_records:
            level = record.risk_level
            risk_stats["by_level"][level] = risk_stats["by_level"].get(level, 0) + 1

        report_data = {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "audit_logs": audit_stats,
            "risks": risk_stats,
            "compliance_checklist": {
                "data_encryption": True,
                "access_controls": True,
                "audit_trail": True,
                "retention_policy": True,
                "incident_response": True
            }
        }

        report = AuditReportCreate(
            report_type="compliance",
            report_name=f"合规审计报告 {start_time.strftime('%Y%m%d')}-{end_time.strftime('%Y%m%d')}",
            start_time=start_time,
            end_time=end_time,
            report_data=report_data,
            summary=f"涵盖了从{start_time}到{end_time}的审计数据",
            generated_by=generated_by,
            generated_by_name=generated_by_name,
            status="generated"
        )

        return await AuditReportService.create_report(report)

    @staticmethod
    async def generate_risk_report(
        start_time: datetime,
        end_time: datetime,
        generated_by: Optional[int] = None,
        generated_by_name: Optional[str] = None
    ) -> AuditReport:
        """生成风险审计报告"""
        # 获取风险记录
        risk_records = await RiskAuditRecord.filter(created_at__gte=start_time, created_at__lte=end_time).all()
        
        report_data = {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "risks": {
                "total": len(risk_records),
                "by_type": {},
                "by_level": {},
                "by_status": {}
            },
            "trends": {},
            "recommendations": []
        }

        # 统计风险数据
        for record in risk_records:
            # 按类型统计
            report_data["risks"]["by_type"][record.risk_type] = \
                report_data["risks"]["by_type"].get(record.risk_type, 0) + 1
            # 按级别统计
            report_data["risks"]["by_level"][record.risk_level] = \
                report_data["risks"]["by_level"].get(record.risk_level, 0) + 1
            # 按状态统计
            report_data["risks"]["by_status"][record.status] = \
                report_data["risks"]["by_status"].get(record.status, 0) + 1

        # 添加建议
        if report_data["risks"]["by_level"].get("critical", 0) > 0:
            report_data["recommendations"].append("立即处理严重级别的风险")
        if report_data["risks"]["by_type"].get("unauthorized_access", 0) > 0:
            report_data["recommendations"].append("加强访问控制和监控")

        report = AuditReportCreate(
            report_type="risk",
            report_name=f"风险审计报告 {start_time.strftime('%Y%m%d')}-{end_time.strftime('%Y%m%d')}",
            start_time=start_time,
            end_time=end_time,
            report_data=report_data,
            summary=f"分析了{len(risk_records)}条风险记录",
            generated_by=generated_by,
            generated_by_name=generated_by_name,
            status="generated"
        )

        return await AuditReportService.create_report(report)


class RiskAuditService:
    model = "risk_audit"
    """风险审计服务"""

    @staticmethod
    async def create_record(data: RiskAuditRecordCreate) -> RiskAuditRecord:
        """创建风险记录"""
        if not data.trace_id:
            data.trace_id = get_current_trace_id()
        
        record = await RiskAuditRecord.create(**data.model_dump(exclude_unset=True))
        return record

    @staticmethod
    async def get_record_by_id(record_id: int) -> Optional[RiskAuditRecord]:
        """根据ID获取风险记录"""
        return await RiskAuditRecord.get_or_none(id=record_id)

    @staticmethod
    async def get_record_list(
        page: int = 1,
        page_size: int = 20,
        trace_id: Optional[str] = None,
        risk_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[RiskAuditRecord], int]:
        """获取风险记录列表"""
        query = RiskAuditRecord.all()

        if trace_id:
            query = query.filter(trace_id=trace_id)
        if risk_type:
            query = query.filter(risk_type=risk_type)
        if risk_level:
            query = query.filter(risk_level=risk_level)
        if status:
            query = query.filter(status=status)
        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)

        total = await query.count()
        offset = (page - 1) * page_size
        records = await query.offset(offset).limit(page_size).order_by("-created_at")

        return records, total

    @staticmethod
    async def update_record(record_id: int, data: RiskAuditRecordUpdate) -> Optional[RiskAuditRecord]:
        """更新风险记录"""
        record = await RiskAuditRecord.get_or_none(id=record_id)
        if not record:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(record, key, value)
        await record.save()
        return record

    @staticmethod
    async def record_risk(
        risk_type: str,
        risk_level: str,
        title: str,
        description: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        related_user_id: Optional[int] = None,
        related_record_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> RiskAuditRecord:
        """记录风险"""
        if not trace_id:
            trace_id = get_current_trace_id()
        
        record_data = RiskAuditRecordCreate(
            trace_id=trace_id,
            risk_type=risk_type,
            risk_level=risk_level,
            title=title,
            description=description,
            details=details,
            related_user_id=related_user_id,
            related_record_id=related_record_id,
            status="open"
        )
        
        return await RiskAuditService.create_record(record_data)

    @staticmethod
    async def check_and_record_hallucination(
        output: str,
        hallucination_detected: bool,
        hallucination_confidence: Optional[float] = None,
        trace_id: Optional[str] = None
    ) -> Optional[RiskAuditRecord]:
        """检查并记录幻觉风险"""
        if hallucination_detected:
            risk_level = "high" if hallucination_confidence and hallucination_confidence > 0.7 else "medium"
            return await RiskAuditService.record_risk(
                risk_type="hallucination",
                risk_level=risk_level,
                title="检测到可能的幻觉输出",
                description="AI输出可能包含幻觉内容",
                details={
                    "output": output[:500] if output else None,
                    "confidence": hallucination_confidence
                },
                trace_id=trace_id
            )
        return None

    @staticmethod
    async def check_and_record_sensitive_data_access(
        data_type: str,
        data_size: int,
        user_id: Optional[int] = None,
        trace_id: Optional[str] = None
    ) -> Optional[RiskAuditRecord]:
        """检查并记录敏感数据访问风险"""
        # 这里可以添加敏感数据访问的检查逻辑
        if data_size > 1000:  # 示例：超过1000条记录
            return await RiskAuditService.record_risk(
                risk_type="sensitive_data_access",
                risk_level="medium",
                title=f"大量敏感{data_type}数据访问",
                description=f"用户访问了{data_size}条{data_type}数据",
                details={
                    "data_type": data_type,
                    "data_size": data_size
                },
                related_user_id=user_id,
                trace_id=trace_id
            )
        return None

    @staticmethod
    async def update_status(
        record_id: int,
        status: str,
        resolved_by: Optional[int] = None,
        resolution_note: Optional[str] = None
    ) -> Optional[RiskAuditRecord]:
        """更新风险记录状态"""
        record = await RiskAuditRecord.get_or_none(id=record_id)
        if not record:
            return None
        
        record.status = status
        if resolved_by:
            record.resolved_by = resolved_by
            record.resolved_time = datetime.now()
        if resolution_note:
            record.resolution_note = resolution_note
        await record.save()
        return record

    @staticmethod
    async def get_statistics(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取风险统计信息"""
        query = RiskAuditRecord.all()

        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)

        total = await query.count()
        critical_count = await query.filter(risk_level="critical").count()
        high_count = await query.filter(risk_level="high").count()
        medium_count = await query.filter(risk_level="medium").count()
        low_count = await query.filter(risk_level="low").count()
        pending_count = await query.filter(status="open").count()
        resolved_count = await query.filter(status="resolved").count()

        return {
            "total": total,
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "pending": pending_count,
            "resolved": resolved_count
        }
