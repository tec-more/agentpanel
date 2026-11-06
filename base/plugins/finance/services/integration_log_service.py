from typing import Optional, List, Dict, Any
try:
    from base.plugins.finance.models.integration_log import IntegrationLog
except ImportError:
    IntegrationLog = None


class IntegrationLogService:
    model = "integration_log"
    @staticmethod
    async def get_all_logs(page: int = 1, page_size: int = 20, event_name: Optional[str] = None, source_type: Optional[str] = None, result: Optional[str] = None) -> List[IntegrationLog]:
        offset = (page - 1) * page_size
        query = IntegrationLog.all().order_by("-created_at")
        if event_name:
            query = query.filter(event_name=event_name)
        if source_type:
            query = query.filter(source_type=source_type)
        if result:
            query = query.filter(result=result)
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def get_log_count(event_name: Optional[str] = None, source_type: Optional[str] = None, result: Optional[str] = None) -> int:
        query = IntegrationLog.all()
        if event_name:
            query = query.filter(event_name=event_name)
        if source_type:
            query = query.filter(source_type=source_type)
        if result:
            query = query.filter(result=result)
        return await query.count()

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[IntegrationLog]:
        return await IntegrationLog.get_or_none(id=log_id)

    @staticmethod
    async def create_log(data: Dict[str, Any]) -> IntegrationLog:
        return await IntegrationLog.create(
            event_name=data["event_name"],
            source_type=data["source_type"],
            source_id=data.get("source_id"),
            source_no=data.get("source_no"),
            result=data["result"],
            payable_id=data.get("payable_id"),
            receivable_id=data.get("receivable_id"),
            payment_id=data.get("payment_id"),
            receipt_id=data.get("receipt_id"),
            journal_id=data.get("journal_id"),
            inventory_cost_ids=data.get("inventory_cost_ids"),
            error_message=data.get("error_message"),
            processing_time_ms=data.get("processing_time_ms", 0),
        )

    @staticmethod
    async def get_logs_by_source(source_type: str, source_id: int) -> List[IntegrationLog]:
        return await IntegrationLog.filter(source_type=source_type, source_id=source_id).order_by("-created_at")

    @staticmethod
    async def get_failed_logs(page: int = 1, page_size: int = 20) -> List[IntegrationLog]:
        offset = (page - 1) * page_size
        return await IntegrationLog.filter(result="failed").order_by("-created_at").offset(offset).limit(page_size)

    @staticmethod
    async def retry_failed_log(log_id: int) -> bool:
        log = await IntegrationLog.get_or_none(id=log_id)
        if not log or log.result != "failed":
            return False
        await IntegrationLog.filter(id=log_id).update(result="retrying")
        return True