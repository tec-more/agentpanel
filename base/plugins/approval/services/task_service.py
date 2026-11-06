"""
审批任务 Service
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from tortoise.expressions import Q
from loguru import logger

from base.plugins.approval.models.approval_instance import ApprovalInstance
from base.plugins.approval.models.approval_task import ApprovalTask
from base.plugins.approval.models.approval_record import ApprovalRecord
from base.plugins.approval.models.approval_flow import ApprovalFlow
from base.plugins.approval.schemas.task_schema import TaskApprove, TaskReject, TaskTransfer
from base.plugins.approval.services.approval_engine import ApprovalEngine
from base.plugins.approval.services.instance_service import InstanceService


class TaskService:
    """审批任务服务"""

    @staticmethod
    async def approve_task(task_id: int, operator_id: int, comment: str = None,
                           approved: bool = True) -> Dict[str, Any]:
        """审批任务（通过/拒绝）"""
        task = await ApprovalTask.get_or_none(id=task_id)
        if not task:
            raise ValueError("审批任务不存在")

        if task.status != ApprovalEngine.STATUS_PENDING:
            raise ValueError("该任务已处理")

        if task.approver_id != operator_id:
            raise ValueError("无权处理该审批任务")

        instance = await ApprovalInstance.get_or_none(id=task.instance_id)
        if not instance:
            raise ValueError("审批实例不存在")

        if instance.status != ApprovalEngine.STATUS_PENDING:
            raise ValueError("审批实例已结束")

        flow = await ApprovalFlow.get_or_none(id=instance.flow_id)
        if not flow:
            raise ValueError("审批流程不存在")

        # 更新任务状态
        task.status = "approved" if approved else "rejected"
        task.comment = comment
        task.approve_time = datetime.now()
        await task.save()

        # 创建审批记录
        await ApprovalRecord.create(
            instance_id=instance.id,
            task_id=task.id,
            node_id=task.node_id,
            operator_id=operator_id,
            action="approve" if approved else "reject",
            comment=comment,
            after_status=instance.status
        )

        # 检查节点是否完成
        node_config = ApprovalEngine.get_node_config(flow.flow_config, task.node_id)
        if node_config:
            is_complete, is_approved, next_action = await ApprovalEngine.check_node_complete(
                instance, node_config
            )

            if is_complete:
                # 节点完成，进入下一节点
                await InstanceService._process_node_complete(
                    instance, flow, node_config,
                    instance.form_data or {}, "approve" if is_approved else "reject"
                )

        return {
            "task_id": task.id,
            "status": task.status,
            "instance_status": instance.status
        }

    @staticmethod
    async def transfer_task(task_id: int, operator_id: int, transfer_to: int,
                            comment: str = None) -> Dict[str, Any]:
        """转审任务"""
        task = await ApprovalTask.get_or_none(id=task_id)
        if not task:
            raise ValueError("审批任务不存在")

        if task.status != ApprovalEngine.STATUS_PENDING:
            raise ValueError("该任务已处理")

        if task.approver_id != operator_id:
            raise ValueError("无权处理该审批任务")

        # 更新原任务
        task.status = "transferred"
        task.transfer_to = transfer_to
        task.comment = comment
        task.approve_time = datetime.now()
        await task.save()

        # 创建新任务
        new_task = await ApprovalTask.create(
            instance_id=task.instance_id,
            node_id=task.node_id,
            approver_id=transfer_to,
            status=ApprovalEngine.STATUS_PENDING,
            transfer_to=None
        )

        # 创建审批记录
        await ApprovalRecord.create(
            instance_id=task.instance_id,
            task_id=task.id,
            node_id=task.node_id,
            operator_id=operator_id,
            action="transfer",
            comment=comment,
            after_status="pending"
        )

        return {
            "task_id": task.id,
            "new_task_id": new_task.id,
            "status": "transferred"
        }

    @staticmethod
    async def get_my_tasks(user_id: int, status: str = "pending",
                           page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """获取我的审批任务"""
        q = Q(approver_id=user_id)
        if status:
            q &= Q(status=status)

        total = await ApprovalTask.filter(q).count()
        tasks = await ApprovalTask.filter(q).offset(
            (page - 1) * page_size
        ).limit(page_size)

        # 补充实例信息
        items = []
        for task in tasks:
            task_dict = await task.to_dict(include_approver=True)
            instance = await ApprovalInstance.get_or_none(id=task.instance_id)
            if instance:
                task_dict["instance"] = await instance.to_dict()
            items.append(task_dict)

        return {
            "total": total,
            "items": items,
            "page": page,
            "page_size": page_size
        }

    @staticmethod
    async def get_task_detail(task_id: int) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        task = await ApprovalTask.get_or_none(id=task_id)
        if not task:
            return None

        task_dict = await task.to_dict(include_approver=True)
        instance = await ApprovalInstance.get_or_none(id=task.instance_id)
        if instance:
            task_dict["instance"] = await InstanceService.get_instance_progress(instance.id)
        return task_dict
