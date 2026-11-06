try:
    from tortoise import fields
    from tortoise.models import Model
    from base.common.model import BaseModel, TimestampMixin
except ImportError:
    from typing import Optional, Any
    from datetime import datetime

    class BaseModel:
        id = None

    class TimestampMixin:
        created_at = None
        updated_at = None

    class fields:
        @staticmethod
        def CharField(**kwargs):
            return kwargs

        @staticmethod
        def BooleanField(**kwargs):
            return kwargs

        @staticmethod
        def IntField(**kwargs):
            return kwargs

        @staticmethod
        def DatetimeField(**kwargs):
            return kwargs

        @staticmethod
        def DecimalField(**kwargs):
            return kwargs

        @staticmethod
        def TextField(**kwargs):
            return kwargs

        @staticmethod
        def JSONField(**kwargs):
            return kwargs

        @staticmethod
        def FloatField(**kwargs):
            return kwargs

        @staticmethod
        def ForeignKeyField(model_name, **kwargs):
            return kwargs

        @staticmethod
        def ManyToManyField(model_name, **kwargs):
            return kwargs

        @staticmethod
        def BigIntegerField(**kwargs):
            return kwargs


class ShiftDefinition(BaseModel, TimestampMixin):
    verbose_name = "班次"
    """班次定义模型"""
    shift_code = fields.CharField(max_length=20, unique=True, description="班次编码", index=True)
    shift_name = fields.CharField(max_length=50, description="班次名称")
    start_time = fields.CharField(max_length=5, description="班次开始时间(HH:MM)")
    end_time = fields.CharField(max_length=5, description="班次结束时间(HH:MM)")
    work_center_code = fields.CharField(max_length=100, null=True, description="关联工作中心编码")
    is_active = fields.BooleanField(default=True, description="是否启用")
    description = fields.TextField(null=True, description="描述")

    class Meta:
        table = "mes_shift_definition"

    async def to_dict(self):
        return {
            "id": self.id,
            "shift_code": self.shift_code,
            "shift_name": self.shift_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "work_center_code": self.work_center_code,
            "is_active": self.is_active,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class ShiftSchedule(BaseModel, TimestampMixin):
    """排班记录模型"""
    shift_code = fields.CharField(max_length=20, description="班次编码", index=True)
    work_center_code = fields.CharField(max_length=100, description="工作中心编码", index=True)
    date = fields.DateField(description="排班日期", index=True)
    operator_list = fields.JSONField(description="排班人员列表")
    leader = fields.CharField(max_length=100, description="班组长")

    class Meta:
        table = "mes_shift_schedule"

    async def to_dict(self):
        return {
            "id": self.id,
            "shift_code": self.shift_code,
            "work_center_code": self.work_center_code,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "operator_list": self.operator_list,
            "leader": self.leader,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class ShiftHandover(BaseModel, TimestampMixin):
    """交接班记录模型"""
    shift_code = fields.CharField(max_length=20, description="班次编码", index=True)
    work_center_code = fields.CharField(max_length=100, description="工作中心编码", index=True)
    date = fields.DateField(description="交接班日期", index=True)
    outgoing_leader = fields.CharField(max_length=100, description="交班班组长")
    incoming_leader = fields.CharField(max_length=100, description="接班班组长")
    equipment_status = fields.TextField(description="设备状态描述")
    production_progress = fields.TextField(description="生产进度描述")
    exception_items = fields.TextField(description="异常事项")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_shift_handover"

    async def to_dict(self):
        return {
            "id": self.id,
            "shift_code": self.shift_code,
            "work_center_code": self.work_center_code,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "outgoing_leader": self.outgoing_leader,
            "incoming_leader": self.incoming_leader,
            "equipment_status": self.equipment_status,
            "production_progress": self.production_progress,
            "exception_items": self.exception_items,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }