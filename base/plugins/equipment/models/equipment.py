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


class Equipment(BaseModel, TimestampMixin):
    verbose_name = "设备"
    """设备模型"""
    equipment_code = fields.CharField(max_length=100, unique=True, description="设备编码", index=True)
    equipment_name = fields.CharField(max_length=255, description="设备名称", index=True)
    equipment_type = fields.CharField(max_length=50, description="设备类型")
    model = fields.CharField(max_length=100, null=True, description="设备型号")
    manufacturer = fields.CharField(max_length=255, null=True, description="制造商")
    location = fields.CharField(max_length=255, null=True, description="位置")
    work_center_code = fields.CharField(max_length=100, null=True, description="所属工作中心")
    status = fields.CharField(max_length=20, default="idle", description="状态：idle/running/maintenance/fault/down", index=True)
    purchase_date = fields.DatetimeField(null=True, description="购入日期")
    warranty_date = fields.DatetimeField(null=True, description="保修到期日期")
    daily_capacity = fields.DecimalField(max_digits=15, decimal_places=2, default=0, description="日产能")
    next_maintenance_date = fields.DateField(null=True, description="下次保养日期")
    description = fields.TextField(null=True, description="描述")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "mes_equipment"

    async def to_dict(self):
        return {
            "id": self.id,
            "equipment_code": self.equipment_code,
            "equipment_name": self.equipment_name,
            "equipment_type": self.equipment_type,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "location": self.location,
            "work_center_code": self.work_center_code,
            "status": self.status,
            "purchase_date": self.purchase_date.strftime("%Y-%m-%d %H:%M:%S") if self.purchase_date else None,
            "warranty_date": self.warranty_date.strftime("%Y-%m-%d %H:%M:%S") if self.warranty_date else None,
            "daily_capacity": float(self.daily_capacity) if self.daily_capacity and hasattr(self.daily_capacity, "__float__") else self.daily_capacity,
            "next_maintenance_date": self.next_maintenance_date.strftime("%Y-%m-%d") if self.next_maintenance_date else None,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class EquipmentMaintenance(BaseModel, TimestampMixin):
    verbose_name = "设备保养"
    """设备维护保养模型"""
    maintenance_code = fields.CharField(max_length=100, unique=True, description="保养单号", index=True)
    equipment_code = fields.CharField(max_length=100, description="设备编码", index=True)
    equipment_name = fields.CharField(max_length=255, description="设备名称")
    maintenance_type = fields.CharField(max_length=20, description="保养类型：daily/weekly/monthly/quarterly/yearly")
    planned_date = fields.DatetimeField(null=True, description="计划保养日期")
    actual_date = fields.DatetimeField(null=True, description="实际保养日期")
    status = fields.CharField(max_length=20, default="pending", description="状态：pending/completed", index=True)
    operator = fields.CharField(max_length=100, null=True, description="操作员")
    items = fields.JSONField(null=True, description="保养项目")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_equipment_maintenance"

    async def to_dict(self):
        return {
            "id": self.id,
            "maintenance_code": self.maintenance_code,
            "equipment_code": self.equipment_code,
            "equipment_name": self.equipment_name,
            "maintenance_type": self.maintenance_type,
            "planned_date": self.planned_date.strftime("%Y-%m-%d %H:%M:%S") if self.planned_date else None,
            "actual_date": self.actual_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_date else None,
            "status": self.status,
            "operator": self.operator,
            "items": self.items,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class EquipmentFault(BaseModel, TimestampMixin):
    verbose_name = "设备故障"
    """设备故障模型"""
    fault_code = fields.CharField(max_length=100, unique=True, description="故障单号", index=True)
    equipment_code = fields.CharField(max_length=100, description="设备编码", index=True)
    equipment_name = fields.CharField(max_length=255, description="设备名称")
    fault_type = fields.CharField(max_length=50, description="故障类型")
    fault_level = fields.CharField(max_length=20, default="minor", description="故障级别：minor/major/critical")
    fault_time = fields.DatetimeField(null=True, description="故障发生时间")
    recovery_time = fields.DatetimeField(null=True, description="恢复时间")
    status = fields.CharField(max_length=20, default="open", description="状态：open/processing/resolved/closed", index=True)
    description = fields.TextField(null=True, description="故障描述")
    solution = fields.TextField(null=True, description="解决方案")
    operator = fields.CharField(max_length=100, null=True, description="处理人")

    class Meta:
        table = "mes_equipment_fault"

    async def to_dict(self):
        return {
            "id": self.id,
            "fault_code": self.fault_code,
            "equipment_code": self.equipment_code,
            "equipment_name": self.equipment_name,
            "fault_type": self.fault_type,
            "fault_level": self.fault_level,
            "fault_time": self.fault_time.strftime("%Y-%m-%d %H:%M:%S") if self.fault_time else None,
            "recovery_time": self.recovery_time.strftime("%Y-%m-%d %H:%M:%S") if self.recovery_time else None,
            "status": self.status,
            "description": self.description,
            "solution": self.solution,
            "operator": self.operator,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }