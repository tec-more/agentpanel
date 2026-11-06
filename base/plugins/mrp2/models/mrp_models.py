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


class SalesForecast(BaseModel, TimestampMixin):
    verbose_name = "销售预测"
    """销售预测模型"""
    forecast_code = fields.CharField(max_length=100, unique=True, description="预测编号", index=True)
    forecast_name = fields.CharField(max_length=255, description="预测名称")
    forecast_type = fields.CharField(max_length=20, default="monthly", description="预测类型：monthly/quarterly/yearly")
    forecast_date = fields.DateField(description="预测日期")
    start_date = fields.DateField(description="预测开始日期")
    end_date = fields.DateField(description="预测结束日期")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/review/approved/executed", index=True)
    source = fields.CharField(max_length=50, default="manual", description="预测来源：manual/history/market")
    description = fields.TextField(null=True, description="描述")
    created_by = fields.CharField(max_length=100, null=True, description="创建人")

    class Meta:
        table = "mrp2_sales_forecast"

    async def to_dict(self):
        return {
            "id": self.id,
            "forecast_code": self.forecast_code,
            "forecast_name": self.forecast_name,
            "forecast_type": self.forecast_type,
            "forecast_date": self.forecast_date.strftime("%Y-%m-%d") if self.forecast_date else None,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "status": self.status,
            "source": self.source,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class SalesForecastDetail(BaseModel, TimestampMixin):
    """销售预测明细模型"""
    forecast_id = fields.IntField(description="预测ID", index=True)
    forecast_code = fields.CharField(max_length=100, description="预测编号", index=True)
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    period_type = fields.CharField(max_length=20, default="month", description="周期类型：week/month/quarter")
    period_start = fields.DateField(description="周期开始日期")
    period_end = fields.DateField(description="周期结束日期")
    forecast_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="预测数量")
    unit = fields.CharField(max_length=20, description="计量单位")
    confidence = fields.DecimalField(max_digits=5, decimal_places=2, default=80, description="置信度(%)")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mrp2_sales_forecast_detail"

    async def to_dict(self):
        return {
            "id": self.id,
            "forecast_id": self.forecast_id,
            "forecast_code": self.forecast_code,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "period_type": self.period_type,
            "period_start": self.period_start.strftime("%Y-%m-%d") if self.period_start else None,
            "period_end": self.period_end.strftime("%Y-%m-%d") if self.period_end else None,
            "forecast_quantity": float(self.forecast_quantity) if self.forecast_quantity and hasattr(self.forecast_quantity, "__float__") else self.forecast_quantity,
            "unit": self.unit,
            "confidence": float(self.confidence) if self.confidence and hasattr(self.confidence, "__float__") else self.confidence,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MasterProductionSchedule(BaseModel, TimestampMixin):
    """主生产计划模型"""
    mps_code = fields.CharField(max_length=100, unique=True, description="MPS编号", index=True)
    mps_name = fields.CharField(max_length=255, description="MPS名称")
    start_date = fields.DateField(description="计划开始日期")
    end_date = fields.DateField(description="计划结束日期")
    period_type = fields.CharField(max_length=20, default="week", description="计划周期：week/month")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/submitted/approved/released/closed/canceled", index=True)
    forecast_id = fields.IntField(null=True, description="关联销售预测ID")
    forecast_code = fields.CharField(max_length=100, null=True, description="关联销售预测编号")
    plan_name = fields.CharField(max_length=255, null=True, description="计划名称")
    approved_by = fields.CharField(max_length=100, null=True, description="审核人")
    approved_at = fields.DatetimeField(null=True, description="审核时间")
    released_by = fields.CharField(max_length=100, null=True, description="下达人")
    released_at = fields.DatetimeField(null=True, description="下达时间")
    demand_time_fence = fields.IntField(default=7, description="需求时界(天)")
    planning_time_fence = fields.IntField(default=14, description="计划时界(天)")
    description = fields.TextField(null=True, description="描述")
    created_by = fields.CharField(max_length=100, null=True, description="创建人")

    class Meta:
        table = "mrp2_master_production_schedule"

    async def to_dict(self):
        return {
            "id": self.id,
            "mps_code": self.mps_code,
            "mps_name": self.mps_name,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "period_type": self.period_type,
            "status": self.status,
            "forecast_id": self.forecast_id,
            "forecast_code": self.forecast_code,
            "plan_name": self.plan_name,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.strftime("%Y-%m-%d %H:%M:%S") if self.approved_at else None,
            "released_by": self.released_by,
            "released_at": self.released_at.strftime("%Y-%m-%d %H:%M:%S") if self.released_at else None,
            "demand_time_fence": self.demand_time_fence,
            "planning_time_fence": self.planning_time_fence,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MPSDetail(BaseModel, TimestampMixin):
    """主生产计划明细模型"""
    mps_id = fields.IntField(description="MPS ID", index=True)
    mps_code = fields.CharField(max_length=100, description="MPS编号", index=True)
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    bom_version = fields.CharField(max_length=20, null=True, description="BOM版本")
    route_code = fields.CharField(max_length=100, null=True, description="工艺路线编码")
    period_start = fields.DateField(description="周期开始日期")
    period_end = fields.DateField(description="周期结束日期")
    forecast_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="预测数量")
    planned_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="计划数量")
    production_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="实际生产数量")
    unit = fields.CharField(max_length=20, description="计量单位")
    safety_stock = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="安全库存")
    planned_inventory = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="计划库存")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mrp2_mps_detail"

    async def to_dict(self):
        return {
            "id": self.id,
            "mps_id": self.mps_id,
            "mps_code": self.mps_code,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "bom_version": self.bom_version,
            "route_code": self.route_code,
            "period_start": self.period_start.strftime("%Y-%m-%d") if self.period_start else None,
            "period_end": self.period_end.strftime("%Y-%m-%d") if self.period_end else None,
            "forecast_quantity": float(self.forecast_quantity) if self.forecast_quantity and hasattr(self.forecast_quantity, "__float__") else self.forecast_quantity,
            "planned_quantity": float(self.planned_quantity) if self.planned_quantity and hasattr(self.planned_quantity, "__float__") else self.planned_quantity,
            "production_quantity": float(self.production_quantity) if self.production_quantity and hasattr(self.production_quantity, "__float__") else self.production_quantity,
            "unit": self.unit,
            "safety_stock": float(self.safety_stock) if self.safety_stock and hasattr(self.safety_stock, "__float__") else self.safety_stock,
            "planned_inventory": float(self.planned_inventory) if self.planned_inventory and hasattr(self.planned_inventory, "__float__") else self.planned_inventory,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MPSPlanLine(BaseModel, TimestampMixin):
    """主生产计划行模型"""
    mps_id = fields.IntField(description="MPS ID", index=True)
    mps_code = fields.CharField(max_length=100, description="MPS编号", index=True)
    line_no = fields.IntField(description="行号")
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    plan_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="计划数量")
    plan_start_date = fields.DateField(description="计划开始日期")
    plan_end_date = fields.DateField(description="计划结束日期")
    priority = fields.IntField(default=5, description="优先级(1-10，数字越小优先级越高)")
    sales_order_no = fields.CharField(max_length=100, null=True, description="关联销售订单号")
    sales_order_line_no = fields.IntField(null=True, description="关联销售订单行号")
    bom_code = fields.CharField(max_length=100, null=True, description="BOM编码")
    route_code = fields.CharField(max_length=100, null=True, description="工艺路线编码")
    capacity_check_result = fields.CharField(max_length=20, default="pass", description="产能校验结果：pass/warning/overload")
    capacity_check_remark = fields.TextField(null=True, description="产能校验备注")
    actual_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="实际完成数量")
    status = fields.CharField(max_length=20, default="planned", description="状态：planned/released/completed/canceled", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mrp2_mps_plan_line"

    async def to_dict(self):
        return {
            "id": self.id,
            "mps_id": self.mps_id,
            "mps_code": self.mps_code,
            "line_no": self.line_no,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "plan_quantity": float(self.plan_quantity) if self.plan_quantity and hasattr(self.plan_quantity, "__float__") else self.plan_quantity,
            "plan_start_date": self.plan_start_date.strftime("%Y-%m-%d") if self.plan_start_date else None,
            "plan_end_date": self.plan_end_date.strftime("%Y-%m-%d") if self.plan_end_date else None,
            "priority": self.priority,
            "sales_order_no": self.sales_order_no,
            "sales_order_line_no": self.sales_order_line_no,
            "bom_code": self.bom_code,
            "route_code": self.route_code,
            "capacity_check_result": self.capacity_check_result,
            "capacity_check_remark": self.capacity_check_remark,
            "actual_quantity": float(self.actual_quantity) if self.actual_quantity and hasattr(self.actual_quantity, "__float__") else self.actual_quantity,
            "status": self.status,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MRPCalculation(BaseModel, TimestampMixin):
    """MRP计算模型"""
    mrp_code = fields.CharField(max_length=100, unique=True, description="MRP编号", index=True)
    mrp_name = fields.CharField(max_length=255, description="MRP名称")
    mps_id = fields.IntField(null=True, description="关联MPS ID")
    mps_code = fields.CharField(max_length=100, null=True, description="关联MPS编号")
    calculation_date = fields.DatetimeField(description="计算日期")
    status = fields.CharField(max_length=20, default="calculating", description="状态：calculating/complete/failed", index=True)
    start_date = fields.DateField(description="需求开始日期")
    end_date = fields.DateField(description="需求结束日期")
    net_requirement_only = fields.BooleanField(default=False, description="是否仅计算净需求")
    include_safety_stock = fields.BooleanField(default=True, description="是否包含安全库存")
    include_wip = fields.BooleanField(default=True, description="是否包含在制品")
    calculation_result = fields.JSONField(null=True, description="计算结果摘要")
    error_message = fields.TextField(null=True, description="错误信息")
    created_by = fields.CharField(max_length=100, null=True, description="创建人")

    class Meta:
        table = "mrp2_mrp_calculation"

    async def to_dict(self):
        return {
            "id": self.id,
            "mrp_code": self.mrp_code,
            "mrp_name": self.mrp_name,
            "mps_id": self.mps_id,
            "mps_code": self.mps_code,
            "calculation_date": self.calculation_date.strftime("%Y-%m-%d %H:%M:%S") if self.calculation_date else None,
            "status": self.status,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "net_requirement_only": self.net_requirement_only,
            "include_safety_stock": self.include_safety_stock,
            "include_wip": self.include_wip,
            "calculation_result": self.calculation_result,
            "error_message": self.error_message,
            "created_by": self.created_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MRPResultDetail(BaseModel, TimestampMixin):
    """MRP结果明细模型"""
    mrp_id = fields.IntField(description="MRP计算ID", index=True)
    mrp_code = fields.CharField(max_length=100, description="MRP编号", index=True)
    level = fields.IntField(default=1, description="BOM层级")
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    period_start = fields.DateField(description="周期开始日期")
    period_end = fields.DateField(description="周期结束日期")
    gross_requirement = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="毛需求")
    scheduled_receipts = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="计划入库")
    projected_available = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="预计可用库存")
    net_requirement = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="净需求")
    planned_order_receipt = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="计划订单入库")
    planned_order_release = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="计划订单下达")
    planned_release_date = fields.DateField(null=True, description="计划下达日期")
    planned_receipt_date = fields.DateField(null=True, description="计划入库日期")
    lot_size = fields.DecimalField(max_digits=15, decimal_places=6, default=1, description="批量")
    lead_time = fields.IntField(default=0, description="提前期(天)")
    safety_stock = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="安全库存")
    unit = fields.CharField(max_length=20, description="计量单位")
    parent_item_code = fields.CharField(max_length=100, null=True, description="父项编码")
    bom_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=1, description="BOM用量")

    class Meta:
        table = "mrp2_mrp_result_detail"

    async def to_dict(self):
        return {
            "id": self.id,
            "mrp_id": self.mrp_id,
            "mrp_code": self.mrp_code,
            "level": self.level,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "period_start": self.period_start.strftime("%Y-%m-%d") if self.period_start else None,
            "period_end": self.period_end.strftime("%Y-%m-%d") if self.period_end else None,
            "gross_requirement": float(self.gross_requirement) if self.gross_requirement and hasattr(self.gross_requirement, "__float__") else self.gross_requirement,
            "scheduled_receipts": float(self.scheduled_receipts) if self.scheduled_receipts and hasattr(self.scheduled_receipts, "__float__") else self.scheduled_receipts,
            "projected_available": float(self.projected_available) if self.projected_available and hasattr(self.projected_available, "__float__") else self.projected_available,
            "net_requirement": float(self.net_requirement) if self.net_requirement and hasattr(self.net_requirement, "__float__") else self.net_requirement,
            "planned_order_receipt": float(self.planned_order_receipt) if self.planned_order_receipt and hasattr(self.planned_order_receipt, "__float__") else self.planned_order_receipt,
            "planned_order_release": float(self.planned_order_release) if self.planned_order_release and hasattr(self.planned_order_release, "__float__") else self.planned_order_release,
            "planned_release_date": self.planned_release_date.strftime("%Y-%m-%d") if self.planned_release_date else None,
            "planned_receipt_date": self.planned_receipt_date.strftime("%Y-%m-%d") if self.planned_receipt_date else None,
            "lot_size": float(self.lot_size) if self.lot_size and hasattr(self.lot_size, "__float__") else self.lot_size,
            "lead_time": self.lead_time,
            "safety_stock": float(self.safety_stock) if self.safety_stock and hasattr(self.safety_stock, "__float__") else self.safety_stock,
            "unit": self.unit,
            "parent_item_code": self.parent_item_code,
            "bom_quantity": float(self.bom_quantity) if self.bom_quantity and hasattr(self.bom_quantity, "__float__") else self.bom_quantity,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class CapacityRequirementPlan(BaseModel, TimestampMixin):
    """能力需求计划模型"""
    crp_code = fields.CharField(max_length=100, unique=True, description="CRP编号", index=True)
    crp_name = fields.CharField(max_length=255, description="CRP名称")
    mrp_id = fields.IntField(null=True, description="关联MRP ID")
    mrp_code = fields.CharField(max_length=100, null=True, description="关联MRP编号")
    mps_id = fields.IntField(null=True, description="关联MPS ID")
    mps_code = fields.CharField(max_length=100, null=True, description="关联MPS编号")
    status = fields.CharField(max_length=20, default="calculating", description="状态：calculating/complete/failed", index=True)
    start_date = fields.DateField(description="计划开始日期")
    end_date = fields.DateField(description="计划结束日期")
    calculation_date = fields.DatetimeField(description="计算日期")
    overall_capacity_utilization = fields.DecimalField(max_digits=5, decimal_places=2, default=0, description="总体能力利用率(%)")
    bottleneck_work_centers = fields.JSONField(null=True, description="瓶颈工作中心列表")
    calculation_summary = fields.JSONField(null=True, description="计算摘要")
    error_message = fields.TextField(null=True, description="错误信息")
    created_by = fields.CharField(max_length=100, null=True, description="创建人")

    class Meta:
        table = "mrp2_capacity_requirement_plan"

    async def to_dict(self):
        return {
            "id": self.id,
            "crp_code": self.crp_code,
            "crp_name": self.crp_name,
            "mrp_id": self.mrp_id,
            "mrp_code": self.mrp_code,
            "mps_id": self.mps_id,
            "mps_code": self.mps_code,
            "status": self.status,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "calculation_date": self.calculation_date.strftime("%Y-%m-%d %H:%M:%S") if self.calculation_date else None,
            "overall_capacity_utilization": float(self.overall_capacity_utilization) if self.overall_capacity_utilization and hasattr(self.overall_capacity_utilization, "__float__") else self.overall_capacity_utilization,
            "bottleneck_work_centers": self.bottleneck_work_centers,
            "calculation_summary": self.calculation_summary,
            "error_message": self.error_message,
            "created_by": self.created_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class CRPDetail(BaseModel, TimestampMixin):
    """能力需求计划明细模型"""
    crp_id = fields.IntField(description="CRP ID", index=True)
    crp_code = fields.CharField(max_length=100, description="CRP编号", index=True)
    work_center_code = fields.CharField(max_length=100, description="工作中心编码", index=True)
    work_center_name = fields.CharField(max_length=255, description="工作中心名称")
    period_start = fields.DateField(description="周期开始日期")
    period_end = fields.DateField(description="周期结束日期")
    available_capacity = fields.DecimalField(max_digits=15, decimal_places=2, description="可用能力(工时)")
    required_capacity = fields.DecimalField(max_digits=15, decimal_places=2, description="需求能力(工时)")
    utilized_capacity = fields.DecimalField(max_digits=15, decimal_places=2, default=0, description="已用能力(工时)")
    capacity_utilization = fields.DecimalField(max_digits=5, decimal_places=2, default=0, description="能力利用率(%)")
    is_overloaded = fields.BooleanField(default=False, description="是否过载")
    overload_hours = fields.DecimalField(max_digits=15, decimal_places=2, default=0, description="过载工时")
    recommended_action = fields.TextField(null=True, description="建议措施")
    detail_items = fields.JSONField(null=True, description="详细工序需求")

    class Meta:
        table = "mrp2_crp_detail"

    async def to_dict(self):
        return {
            "id": self.id,
            "crp_id": self.crp_id,
            "crp_code": self.crp_code,
            "work_center_code": self.work_center_code,
            "work_center_name": self.work_center_name,
            "period_start": self.period_start.strftime("%Y-%m-%d") if self.period_start else None,
            "period_end": self.period_end.strftime("%Y-%m-%d") if self.period_end else None,
            "available_capacity": float(self.available_capacity) if self.available_capacity and hasattr(self.available_capacity, "__float__") else self.available_capacity,
            "required_capacity": float(self.required_capacity) if self.required_capacity and hasattr(self.required_capacity, "__float__") else self.required_capacity,
            "utilized_capacity": float(self.utilized_capacity) if self.utilized_capacity and hasattr(self.utilized_capacity, "__float__") else self.utilized_capacity,
            "capacity_utilization": float(self.capacity_utilization) if self.capacity_utilization and hasattr(self.capacity_utilization, "__float__") else self.capacity_utilization,
            "is_overloaded": self.is_overloaded,
            "overload_hours": float(self.overload_hours) if self.overload_hours and hasattr(self.overload_hours, "__float__") else self.overload_hours,
            "recommended_action": self.recommended_action,
            "detail_items": self.detail_items,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class PlanExecutionMonitor(BaseModel, TimestampMixin):
    """计划执行监控模型"""
    monitor_code = fields.CharField(max_length=100, unique=True, description="监控编号", index=True)
    monitor_name = fields.CharField(max_length=255, description="监控名称")
    mps_id = fields.IntField(null=True, description="关联MPS ID")
    mps_code = fields.CharField(max_length=100, null=True, description="关联MPS编号")
    mrp_id = fields.IntField(null=True, description="关联MRP ID")
    mrp_code = fields.CharField(max_length=100, null=True, description="关联MRP编号")
    start_date = fields.DateField(description="监控开始日期")
    end_date = fields.DateField(description="监控结束日期")
    status = fields.CharField(max_length=20, default="monitoring", description="状态：monitoring/completed", index=True)
    overall_progress = fields.DecimalField(max_digits=5, decimal_places=2, default=0, description="总体进度(%)")
    on_time_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=0, description="准时交付率(%)")
    quality_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=0, description="合格率(%)")
    efficiency_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=0, description="效率(%)")
    alert_count = fields.IntField(default=0, description="告警数量")
    exception_count = fields.IntField(default=0, description="异常数量")
    metrics_summary = fields.JSONField(null=True, description="指标汇总")
    created_by = fields.CharField(max_length=100, null=True, description="创建人")

    class Meta:
        table = "mrp2_plan_execution_monitor"

    async def to_dict(self):
        return {
            "id": self.id,
            "monitor_code": self.monitor_code,
            "monitor_name": self.monitor_name,
            "mps_id": self.mps_id,
            "mps_code": self.mps_code,
            "mrp_id": self.mrp_id,
            "mrp_code": self.mrp_code,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "status": self.status,
            "overall_progress": float(self.overall_progress) if self.overall_progress and hasattr(self.overall_progress, "__float__") else self.overall_progress,
            "on_time_rate": float(self.on_time_rate) if self.on_time_rate and hasattr(self.on_time_rate, "__float__") else self.on_time_rate,
            "quality_rate": float(self.quality_rate) if self.quality_rate and hasattr(self.quality_rate, "__float__") else self.quality_rate,
            "efficiency_rate": float(self.efficiency_rate) if self.efficiency_rate and hasattr(self.efficiency_rate, "__float__") else self.efficiency_rate,
            "alert_count": self.alert_count,
            "exception_count": self.exception_count,
            "metrics_summary": self.metrics_summary,
            "created_by": self.created_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MRPExceptionAlert(BaseModel, TimestampMixin):
    """MRP异常告警模型"""
    alert_code = fields.CharField(max_length=100, unique=True, description="告警编号", index=True)
    monitor_id = fields.IntField(null=True, description="关联监控ID")
    alert_type = fields.CharField(max_length=50, description="告警类型：material_shortage/capacity_overload/delay/due_date")
    alert_level = fields.CharField(max_length=20, default="warning", description="告警级别：info/warning/critical")
    alert_status = fields.CharField(max_length=20, default="active", description="告警状态：active/resolved", index=True)
    related_code = fields.CharField(max_length=100, null=True, description="关联编号(物料/工作中心/订单)")
    related_name = fields.CharField(max_length=255, null=True, description="关联名称")
    description = fields.TextField(description="告警描述")
    recommended_action = fields.TextField(null=True, description="建议措施")
    resolved_by = fields.CharField(max_length=100, null=True, description="处理人")
    resolved_at = fields.DatetimeField(null=True, description="处理时间")
    resolved_note = fields.TextField(null=True, description="处理备注")

    class Meta:
        table = "mrp2_exception_alert"

    async def to_dict(self):
        return {
            "id": self.id,
            "alert_code": self.alert_code,
            "monitor_id": self.monitor_id,
            "alert_type": self.alert_type,
            "alert_level": self.alert_level,
            "alert_status": self.alert_status,
            "related_code": self.related_code,
            "related_name": self.related_name,
            "description": self.description,
            "recommended_action": self.recommended_action,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if self.resolved_at else None,
            "resolved_note": self.resolved_note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class PlannedOrder(BaseModel, TimestampMixin):
    verbose_name = "计划订单"
    """计划订单模型"""
    order_code = fields.CharField(max_length=100, unique=True, description="计划订单编号", index=True)
    mrp_id = fields.IntField(null=True, description="关联MRP计算ID", index=True)
    mrp_code = fields.CharField(max_length=100, null=True, description="关联MRP编号")
    order_type = fields.CharField(max_length=20, description="订单类型：manufacture/purchase/subcontracting", index=True)
    material_code = fields.CharField(max_length=100, description="物料编码", index=True)
    material_name = fields.CharField(max_length=255, description="物料名称")
    net_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="净需求数量")
    plan_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="计划数量")
    unit = fields.CharField(max_length=20, description="计量单位")
    require_date = fields.DateField(description="需求日期")
    plan_release_date = fields.DateField(null=True, description="计划下达日期")
    lead_time = fields.IntField(default=0, description="提前期(天)")
    batch_rule = fields.CharField(max_length=20, default="lot_for_lot", description="批量规则：lot_for_lot/fixed/multiple")
    batch_size = fields.DecimalField(max_digits=15, decimal_places=6, default=1, description="批量大小")
    safety_stock = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="安全库存")
    current_stock = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="当前库存")
    on_order_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="在途量")
    gross_requirement = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="毛需求")
    net_requirement = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="净需求")
    bom_level = fields.IntField(default=0, description="BOM层级")
    parent_material_code = fields.CharField(max_length=100, null=True, description="父项物料编码")
    status = fields.CharField(max_length=20, default="planned", description="状态：planned/confirmed/canceled", index=True)
    source_mps_id = fields.IntField(null=True, description="来源MPS ID")
    source_mps_line_id = fields.IntField(null=True, description="来源MPS计划行ID")
    converted_mo_code = fields.CharField(max_length=100, null=True, description="转化后的制造单编码")
    converted_sc_code = fields.CharField(max_length=100, null=True, description="转化后的委外工单编码")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mrp2_planned_order"

    async def to_dict(self):
        return {
            "id": self.id,
            "order_code": self.order_code,
            "mrp_id": self.mrp_id,
            "mrp_code": self.mrp_code,
            "order_type": self.order_type,
            "material_code": self.material_code,
            "material_name": self.material_name,
            "net_quantity": float(self.net_quantity) if self.net_quantity and hasattr(self.net_quantity, "__float__") else self.net_quantity,
            "plan_quantity": float(self.plan_quantity) if self.plan_quantity and hasattr(self.plan_quantity, "__float__") else self.plan_quantity,
            "unit": self.unit,
            "require_date": self.require_date.strftime("%Y-%m-%d") if self.require_date else None,
            "plan_release_date": self.plan_release_date.strftime("%Y-%m-%d") if self.plan_release_date else None,
            "lead_time": self.lead_time,
            "batch_rule": self.batch_rule,
            "batch_size": float(self.batch_size) if self.batch_size and hasattr(self.batch_size, "__float__") else self.batch_size,
            "safety_stock": float(self.safety_stock) if self.safety_stock and hasattr(self.safety_stock, "__float__") else self.safety_stock,
            "current_stock": float(self.current_stock) if self.current_stock and hasattr(self.current_stock, "__float__") else self.current_stock,
            "on_order_quantity": float(self.on_order_quantity) if self.on_order_quantity and hasattr(self.on_order_quantity, "__float__") else self.on_order_quantity,
            "gross_requirement": float(self.gross_requirement) if self.gross_requirement and hasattr(self.gross_requirement, "__float__") else self.gross_requirement,
            "net_requirement": float(self.net_requirement) if self.net_requirement and hasattr(self.net_requirement, "__float__") else self.net_requirement,
            "bom_level": self.bom_level,
            "parent_material_code": self.parent_material_code,
            "status": self.status,
            "source_mps_id": self.source_mps_id,
            "source_mps_line_id": self.source_mps_line_id,
            "converted_mo_code": self.converted_mo_code,
            "converted_sc_code": self.converted_sc_code,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }