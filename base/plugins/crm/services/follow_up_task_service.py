from typing import Optional, List, Tuple
from datetime import datetime
from loguru import logger

from base.plugins.crm.models.follow_up_task import FollowUpTask, TaskStatus
from base.plugins.crm.schemas.task_schema import FollowUpTaskCreate, FollowUpTaskUpdate, TaskListQuery, TaskCompleteRequest
from base.plugins.crm.services.crm_data_filter import get_crm_data_filter
class FollowUpTaskService:
    model = "follow_up_task"

    @staticmethod
    async def create_task(task_data: FollowUpTaskCreate, created_by: int) -> FollowUpTask:
        if task_data.lead_id:
            from base.plugins.crm.models.lead import Lead
            lead = await Lead.get_or_none(id=task_data.lead_id)
            if not lead:
                raise ValueError("CRM_OBJECT_NOT_FOUND: 关联的线索不存在")
        if task_data.opportunity_id:
            from base.plugins.crm.models.opportunity import Opportunity
            opp = await Opportunity.get_or_none(id=task_data.opportunity_id)
            if not opp:
                raise ValueError("CRM_OBJECT_NOT_FOUND: 关联的商机不存在")
        status = TaskStatus.TODO
        if task_data.due_date < datetime.now():
            status = TaskStatus.OVERDUE
        task = await FollowUpTask.create(
            title=task_data.title,
            description=task_data.description,
            lead_id=task_data.lead_id,
            opportunity_id=task_data.opportunity_id,
            assigned_to=task_data.assigned_to,
            due_date=task_data.due_date,
            status=status,
            create_activity_on_complete=task_data.create_activity_on_complete,
        )
        return task

    @staticmethod
    async def get_task_list(query_params: TaskListQuery, user_id: int) -> Tuple[List[FollowUpTask], int]:
        data_filter = await get_crm_data_filter(user_id)
        query = FollowUpTask.all()
        if data_filter:
            query = query.filter(**data_filter)
        if query_params.status:
            query = query.filter(status=query_params.status)
        if query_params.assigned_to is not None:
            query = query.filter(assigned_to=query_params.assigned_to)
        if query_params.lead_id is not None:
            query = query.filter(lead_id=query_params.lead_id)
        if query_params.opportunity_id is not None:
            query = query.filter(opportunity_id=query_params.opportunity_id)
        total = await query.count()
        offset = (query_params.page - 1) * query_params.page_size
        tasks = await query.offset(offset).limit(query_params.page_size).order_by("due_date")
        return tasks, total

    @staticmethod
    async def get_my_tasks(user_id: int) -> List[FollowUpTask]:
        tasks = await FollowUpTask.filter(
            assigned_to=user_id,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS],
        ).order_by("due_date")
        return tasks

    @staticmethod
    async def update_task(task_id: int, task_data: FollowUpTaskUpdate) -> Optional[FollowUpTask]:
        task = await FollowUpTask.get_or_none(id=task_id)
        if not task:
            return None
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise ValueError("CRM_TASK_CLOSED: 已完成或已取消的任务不可修改")
        update_data = task_data.model_dump(exclude_unset=True)
        await task.update_from_dict(update_data).save()
        return task

    @staticmethod
    async def complete_task(task_id: int, complete_data: TaskCompleteRequest, operated_by: int) -> Optional[FollowUpTask]:
        task = await FollowUpTask.get_or_none(id=task_id)
        if not task:
            return None
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        await task.save()
        if complete_data.create_activity or task.create_activity_on_complete:
            from base.plugins.crm.models.activity import Activity
            await Activity.create(
                type="other",
                subject=f"完成任务: {task.title}",
                content=complete_data.activity_content or task.description,
                activity_time=datetime.now(),
                lead_id=task.lead_id,
                opportunity_id=task.opportunity_id,
                created_by=operated_by,
            )
        return task

    @staticmethod
    async def cancel_task(task_id: int) -> Optional[FollowUpTask]:
        task = await FollowUpTask.get_or_none(id=task_id)
        if not task:
            return None
        task.status = TaskStatus.CANCELLED
        await task.save()
        return task