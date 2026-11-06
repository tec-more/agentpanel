"""
审批记录 Service
"""
from typing import Optional, List, Dict, Any
from tortoise.expressions import Q

from base.plugins.approval.models.approval_record import ApprovalRecord
from base.plugins.approval.models.approval_instance import ApprovalInstance


class RecordService:
    """审批记录服务"""

    @staticmethod
    async def get_instance_records(instance_id: int) -> List[Dict[str, Any]]:
        """获取审批实例的所有记录"""
        records = await ApprovalRecord.filter(instance_id=instance_id).all()
        return [await r.to_dict(include_operator=True) for r in records]

    @staticmethod
    async def get_my_records(user_id: int, page: int = 1,
                             page_size: int = 10) -> Dict[str, Any]:
        """获取我的审批操作记录"""
        q = Q(operator_id=user_id)

        total = await ApprovalRecord.filter(q).count()
        records = await ApprovalRecord.filter(q).offset(
            (page - 1) * page_size
        ).limit(page_size)

        items = []
        for record in records:
            record_dict = await record.to_dict(include_operator=True)
            instance = await ApprovalInstance.get_or_none(id=record.instance_id)
            if instance:
                record_dict["instance_title"] = instance.title
                record_dict["instance_status"] = instance.status
            items.append(record_dict)

        return {
            "total": total,
            "items": items,
            "page": page,
            "page_size": page_size
        }
