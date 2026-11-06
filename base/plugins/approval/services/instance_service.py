"""
审批实例 Service
"""
from typing import Optional, List, Dict, Any
from tortoise.expressions import Q
from datetime import datetime
from loguru import logger

from base.plugins.approval.models.approval_instance import ApprovalInstance
from base.plugins.approval.models.approval_task import ApprovalTask
from base.plugins.approval.models.approval_record import ApprovalRecord
from base.plugins.approval.models.approval_flow import ApprovalFlow
from base.plugins.approval.schemas.instance_schema import InstanceCreate, InstanceListQuery
from base.plugins.approval.services.approval_engine import ApprovalEngine


class InstanceService:
    """审批实例服务"""

    @staticmethod
    async def create_instance(data: InstanceCreate, applicant_id: int) -> ApprovalInstance:
        """发起审批（创建审批实例）"""
        # 获取流程
        flow = None
        if data.flow_id:
            flow = await ApprovalFlow.get_or_none(id=data.flow_id)
        elif data.business_type:
            flow = await ApprovalFlow.get_or_none(business_type=data.business_type, is_active=True)

        if not flow:
            raise ValueError("审批流程不存在或未启用")

        if not flow.is_active:
            raise ValueError("审批流程未启用")

        # 创建实例
        instance = await ApprovalInstance.create(
            flow_id=flow.id,
            business_type=flow.business_type or data.business_type,
            business_id=data.business_id,
            business_data=data.business_data,
            title=data.title,
            applicant_id=applicant_id,
            status=ApprovalEngine.STATUS_PENDING,
            form_data=data.form_data,
            action=data.action
        )

        # 创建审批记录
        await ApprovalRecord.create(
            instance_id=instance.id,
            node_id=None,
            operator_id=applicant_id,
            action="submit",
            comment="发起审批",
            after_status=ApprovalEngine.STATUS_PENDING
        )

        # 启动审批流程
        await InstanceService._start_approval_flow(instance, flow, data.form_data, applicant_id)

        return instance

    @staticmethod
    async def _start_approval_flow(instance: ApprovalInstance, flow: ApprovalFlow,
                                   form_data: Dict[str, Any], applicant_id: int):
        """启动审批流程，进入第一个审批节点"""
        flow_config = flow.flow_config
        start_node = ApprovalEngine.get_start_node(flow_config)

        if not start_node:
            logger.error(f"流程 {flow.id} 没有开始节点")
            return

        # 从开始节点找到第一个审批节点
        next_node = ApprovalEngine.get_next_node(flow_config, start_node, form_data, "approve")

        if not next_node:
            logger.error(f"流程 {flow.id} 没有后续审批节点")
            return

        # 进入审批节点
        await InstanceService._enter_approve_node(instance, flow, next_node, form_data)

    @staticmethod
    async def _enter_approve_node(instance: ApprovalInstance, flow: ApprovalFlow,
                                  node_config: Dict[str, Any], form_data: Dict[str, Any]):
        """进入审批节点，创建审批任务"""
        # 获取审批人
        approver_ids = await ApprovalEngine.get_approver_ids(node_config, instance)

        if not approver_ids:
            logger.warning(f"节点 {node_config.get('id')} 没有找到审批人，跳过")
            # 如果没有审批人，直接通过进入下一节点
            await InstanceService._process_node_complete(
                instance, flow, node_config, form_data, action="approve"
            )
            return

        # 创建审批任务
        await ApprovalEngine.create_approval_tasks(instance, node_config, approver_ids)

        # 更新实例当前节点
        instance.current_node = node_config["id"]
        await instance.save()

    @staticmethod
    async def _complete_instance_with_execute(instance: ApprovalInstance, action: str = "approve"):
        """完成审批实例，并在审批通过时自动回调执行器执行业务落库。"""
        status = ApprovalEngine.STATUS_APPROVED if action == "approve" else ApprovalEngine.STATUS_REJECTED
        result = "审批通过" if action == "approve" else "审批拒绝"
        await ApprovalEngine.complete_instance(instance, status, result)
        # 审批通过：自动执行业务（失败不影响已置为 approved 的状态）
        if status == ApprovalEngine.STATUS_APPROVED:
            try:
                from base.plugins.approval.services.approval_gate import ApprovalExecutor
                await ApprovalExecutor.execute(instance)
            except Exception as e:
                logger.error(f"审批通过后自动执行业务失败 instance={instance.id}: {e}")
        return instance

    @staticmethod
    async def _process_node_complete(instance: ApprovalInstance, flow: ApprovalFlow,
                                     node_config: Dict[str, Any], form_data: Dict[str, Any],
                                     action: str = "approve"):
        """处理节点完成，进入下一节点"""
        # 如果是结束节点，完成实例
        if node_config.get("type") == ApprovalEngine.NODE_END:
            await InstanceService._complete_instance_with_execute(instance, action)
            return

        # 计算下一节点
        next_node = ApprovalEngine.get_next_node(flow.flow_config, node_config, form_data, action)

        if not next_node:
            # 没有下一节点，结束审批
            await InstanceService._complete_instance_with_execute(instance, action)
            return

        # 如果下一节点是审批节点，进入审批
        if next_node.get("type") == ApprovalEngine.NODE_APPROVE:
            await InstanceService._enter_approve_node(instance, flow, next_node, form_data)
        elif next_node.get("type") == ApprovalEngine.NODE_CONDITION:
            # 条件节点直接处理
            await InstanceService._process_node_complete(instance, flow, next_node, form_data, action)
        else:
            # 其他类型节点，继续处理
            await InstanceService._process_node_complete(instance, flow, next_node, form_data, action)

    @staticmethod
    async def get_instance(instance_id: int) -> Optional[ApprovalInstance]:
        """获取审批实例"""
        return await ApprovalInstance.get_or_none(id=instance_id)

    @staticmethod
    async def get_instance_list(query: InstanceListQuery, user_id: int = None,
                                scope: str = None) -> Dict[str, Any]:
        """
        获取审批实例列表
        scope: "my_initiated"(我发起的) / "my_todo"(我的待办) / "my_done"(我的已办) / None(全部)
        """
        q = Q()

        if query.status:
            q &= Q(status=query.status)
        if query.business_type:
            q &= Q(business_type=query.business_type)
        if query.title:
            q &= Q(title__icontains=query.title)

        if scope == "my_initiated" and user_id:
            q &= Q(applicant_id=user_id)
        elif scope == "my_todo" and user_id:
            # 我的待办：当前节点有我的待审批任务
            todo_instance_ids = await InstanceService._get_my_todo_instance_ids(user_id)
            q &= Q(id__in=todo_instance_ids)
        elif scope == "my_done" and user_id:
            # 我的已办：我有已完成的审批任务
            done_instance_ids = await InstanceService._get_my_done_instance_ids(user_id)
            q &= Q(id__in=done_instance_ids)

        total = await ApprovalInstance.filter(q).count()
        instances = await ApprovalInstance.filter(q).offset(
            (query.page - 1) * query.page_size
        ).limit(query.page_size)

        items = []
        for instance in instances:
            item = await instance.to_dict(include_flow=True)
            items.append(item)

        return {
            "total": total,
            "items": items,
            "page": query.page,
            "page_size": query.page_size
        }

    @staticmethod
    async def _get_my_todo_instance_ids(user_id: int) -> List[int]:
        """获取我的待办实例ID列表"""
        tasks = await ApprovalTask.filter(
            approver_id=user_id,
            status=ApprovalEngine.STATUS_PENDING
        ).all()
        return [t.instance_id for t in tasks]

    @staticmethod
    async def _get_my_done_instance_ids(user_id: int) -> List[int]:
        """获取我的已办实例ID列表"""
        tasks = await ApprovalTask.filter(
            approver_id=user_id,
            status__in=["approved", "rejected", "transferred"]
        ).distinct().all()
        return [t.instance_id for t in tasks]

    @staticmethod
    async def cancel_instance(instance_id: int, operator_id: int) -> Optional[ApprovalInstance]:
        """撤销审批实例"""
        instance = await ApprovalInstance.get_or_none(id=instance_id)
        if not instance:
            return None

        if instance.applicant_id != operator_id:
            raise ValueError("只有申请人可以撤销审批")

        if instance.status != ApprovalEngine.STATUS_PENDING:
            raise ValueError("只有审批中的实例可以撤销")

        # 更新所有待审批任务为已跳过
        await ApprovalTask.filter(
            instance_id=instance_id,
            status=ApprovalEngine.STATUS_PENDING
        ).update(status="skipped")

        # 创建撤销记录
        await ApprovalRecord.create(
            instance_id=instance_id,
            node_id=instance.current_node,
            operator_id=operator_id,
            action="cancel",
            comment="撤销审批",
            after_status=ApprovalEngine.STATUS_CANCELLED
        )

        # 完成实例
        await ApprovalEngine.complete_instance(
            instance, ApprovalEngine.STATUS_CANCELLED, "已撤销"
        )

        return instance

    @staticmethod
    async def get_instance_progress(instance_id: int) -> Dict[str, Any]:
        """获取审批进度"""
        instance = await ApprovalInstance.get_or_none(id=instance_id)
        if not instance:
            return {}

        flow = await ApprovalFlow.get_or_none(id=instance.flow_id)
        if not flow:
            return {}

        # 获取所有任务
        tasks = await ApprovalTask.filter(instance_id=instance_id).all()
        task_list = [await t.to_dict(include_approver=True) for t in tasks]

        # 获取所有记录
        records = await ApprovalRecord.filter(instance_id=instance_id).all()
        record_list = [await r.to_dict(include_operator=True) for r in records]

        return {
            "instance": await instance.to_dict(include_flow=True),
            "tasks": task_list,
            "records": record_list,
            "flow_config": flow.flow_config
        }
