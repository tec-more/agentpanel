from enum import Enum
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class FollowUpTask(BaseModel, TimestampMixin):
    title = fields.CharField(max_length=200, description="任务标题")
    description = fields.TextField(null=True, description="任务描述")
    lead_id = fields.BigIntField(null=True, description="关联线索ID")
    opportunity_id = fields.BigIntField(null=True, description="关联商机ID")
    assigned_to = fields.BigIntField(description="执行人ID")
    due_date = fields.DatetimeField(description="截止时间")
    status = fields.CharEnumField(TaskStatus, max_length=20, default=TaskStatus.TODO, description="任务状态")
    completed_at = fields.DatetimeField(null=True, description="完成时间")
    create_activity_on_complete = fields.BooleanField(default=False, description="完成时是否创建活动记录")

    class Meta:
        table = "crm_follow_up_task"
        table_description = "CRM跟进任务表"
        ordering = ["due_date"]

    def __str__(self):
        return f"FollowUpTask({self.title})"