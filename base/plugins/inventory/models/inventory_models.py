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


# ==================== 基础数据模型 ====================

class StockLocation(BaseModel, TimestampMixin):
    verbose_name = "库位"
    """库位模型 - Odoo stock.location
    
    支持层级树形结构，通过parent_id实现父子关系
    """
    location_code = fields.CharField(max_length=100, unique=True, description="库位编码", index=True)
    location_name = fields.CharField(max_length=255, description="库位名称")
    parent_id = fields.IntField(null=True, description="父库位ID", index=True)
    parent_code = fields.CharField(max_length=100, null=True, description="父库位编码")
    warehouse_id = fields.IntField(null=True, description="所属仓库ID", index=True)
    warehouse_code = fields.CharField(max_length=100, null=True, description="所属仓库编码")
    location_type = fields.CharField(max_length=20, default="internal", description="库位类型：internal/customer/supplier/view/inventory_loss/production/scrap")
    usage = fields.CharField(max_length=20, default="internal", description="用途：view/internal/customer/supplier/inventory_loss/production/packing/scrap")
    complete_name = fields.CharField(max_length=500, null=True, description="完整名称（层级路径）")
    path = fields.CharField(max_length=500, null=True, description="物化路径（如：WH001/A01/B02）")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    is_scrap = fields.BooleanField(default=False, description="是否报废库位")
    is_inventory_loss = fields.BooleanField(default=False, description="是否盘亏库位")
    posx = fields.IntField(default=0, description="X坐标")
    posy = fields.IntField(default=0, description="Y坐标")
    posz = fields.IntField(default=0, description="Z坐标")
    capacity = fields.IntField(default=0, description="容量")
    description = fields.TextField(null=True, description="描述")

    class Meta:
        table = "stock_location"

    async def to_dict(self):
        return {
            "id": self.id,
            "location_code": self.location_code,
            "location_name": self.location_name,
            "parent_id": self.parent_id,
            "parent_code": self.parent_code,
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "location_type": self.location_type,
            "usage": self.usage,
            "complete_name": self.complete_name,
            "path": self.path,
            "is_active": self.is_active,
            "is_scrap": self.is_scrap,
            "is_inventory_loss": self.is_inventory_loss,
            "posx": self.posx,
            "posy": self.posy,
            "posz": self.posz,
            "capacity": self.capacity,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class StockWarehouse(BaseModel, TimestampMixin):
    verbose_name = "仓库"
    """仓库模型 - Odoo stock.warehouse
    
    关联关键库位：存货库位、入库库位、出库库位、质检库位、打包库位
    """
    warehouse_code = fields.CharField(max_length=100, unique=True, description="仓库编码", index=True)
    warehouse_name = fields.CharField(max_length=255, description="仓库名称")
    warehouse_type = fields.CharField(max_length=20, default="internal", description="仓库类型：internal/customer/supplier")
    company_code = fields.CharField(max_length=100, null=True, description="所属公司编码")
    view_location_id = fields.IntField(null=True, description="视图库位ID")
    view_location_code = fields.CharField(max_length=100, null=True, description="视图库位编码")
    lot_stock_id = fields.IntField(null=True, description="存货库位ID（主库位）")
    lot_stock_code = fields.CharField(max_length=100, null=True, description="存货库位编码")
    input_location_id = fields.IntField(null=True, description="入库库位ID")
    input_location_code = fields.CharField(max_length=100, null=True, description="入库库位编码")
    output_location_id = fields.IntField(null=True, description="出库库位ID")
    output_location_code = fields.CharField(max_length=100, null=True, description="出库库位编码")
    qc_location_id = fields.IntField(null=True, description="质检库位ID")
    qc_location_code = fields.CharField(max_length=100, null=True, description="质检库位编码")
    pack_location_id = fields.IntField(null=True, description="打包库位ID")
    pack_location_code = fields.CharField(max_length=100, null=True, description="打包库位编码")
    scrap_location_id = fields.IntField(null=True, description="报废库位ID")
    scrap_location_code = fields.CharField(max_length=100, null=True, description="报废库位编码")
    address = fields.CharField(max_length=500, null=True, description="仓库地址")
    manager = fields.CharField(max_length=100, null=True, description="仓库管理员")
    contact_phone = fields.CharField(max_length=50, null=True, description="联系电话")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    description = fields.TextField(null=True, description="描述")

    class Meta:
        table = "stock_warehouse"

    async def to_dict(self):
        return {
            "id": self.id,
            "warehouse_code": self.warehouse_code,
            "warehouse_name": self.warehouse_name,
            "warehouse_type": self.warehouse_type,
            "company_code": self.company_code,
            "view_location_id": self.view_location_id,
            "view_location_code": self.view_location_code,
            "lot_stock_id": self.lot_stock_id,
            "lot_stock_code": self.lot_stock_code,
            "input_location_id": self.input_location_id,
            "input_location_code": self.input_location_code,
            "output_location_id": self.output_location_id,
            "output_location_code": self.output_location_code,
            "qc_location_id": self.qc_location_id,
            "qc_location_code": self.qc_location_code,
            "pack_location_id": self.pack_location_id,
            "pack_location_code": self.pack_location_code,
            "scrap_location_id": self.scrap_location_id,
            "scrap_location_code": self.scrap_location_code,
            "address": self.address,
            "manager": self.manager,
            "contact_phone": self.contact_phone,
            "is_active": self.is_active,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class StockPickingType(BaseModel, TimestampMixin):
    verbose_name = "调拨类型"
    """调拨类型模型 - Odoo stock.picking.type
    
    定义调拨操作类型和序列码生成规则
    """
    picking_type_code = fields.CharField(max_length=100, unique=True, description="调拨类型编码", index=True)
    picking_type_name = fields.CharField(max_length=255, description="调拨类型名称")
    code = fields.CharField(max_length=20, description="类型代码：incoming/outgoing/internal")
    sequence_code = fields.CharField(max_length=50, default="{type}/{year}/{month}", description="序列码模板")
    warehouse_id = fields.IntField(null=True, description="所属仓库ID", index=True)
    warehouse_code = fields.CharField(max_length=100, null=True, description="所属仓库编码")
    default_location_src_id = fields.IntField(null=True, description="默认源库位ID")
    default_location_src_code = fields.CharField(max_length=100, null=True, description="默认源库位编码")
    default_location_dest_id = fields.IntField(null=True, description="默认目标库位ID")
    default_location_dest_code = fields.CharField(max_length=100, null=True, description="默认目标库位编码")
    last_sequence = fields.IntField(default=0, description="最后序列号")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    show_operations = fields.BooleanField(default=False, description="是否显示明细行")
    show_reserved = fields.BooleanField(default=True, description="是否显示预留数量")
    color = fields.IntField(default=0, description="颜色标记")
    description = fields.TextField(null=True, description="描述")

    class Meta:
        table = "stock_picking_type"

    async def to_dict(self):
        return {
            "id": self.id,
            "picking_type_code": self.picking_type_code,
            "picking_type_name": self.picking_type_name,
            "code": self.code,
            "sequence_code": self.sequence_code,
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "default_location_src_id": self.default_location_src_id,
            "default_location_src_code": self.default_location_src_code,
            "default_location_dest_id": self.default_location_dest_id,
            "default_location_dest_code": self.default_location_dest_code,
            "last_sequence": self.last_sequence,
            "is_active": self.is_active,
            "show_operations": self.show_operations,
            "show_reserved": self.show_reserved,
            "color": self.color,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


# ==================== 调拨单相关模型 ====================

class StockPicking(BaseModel, TimestampMixin):
    """调拨单模型 - Odoo stock.picking
    
    完整的出入库流程载体
    状态：draft → confirmed → assigned → done/cancel
    """
    picking_code = fields.CharField(max_length=100, unique=True, description="调拨单编码", index=True)
    picking_type_id = fields.IntField(description="调拨类型ID", index=True)
    picking_type_code = fields.CharField(max_length=100, description="调拨类型编码")
    picking_type_name = fields.CharField(max_length=255, description="调拨类型名称")
    origin = fields.CharField(max_length=100, null=True, description="来源单号", index=True)
    origin_type = fields.CharField(max_length=50, null=True, description="来源类型：SO/PO/MO/DO")
    partner_code = fields.CharField(max_length=100, null=True, description="合作伙伴编码（客户/供应商）")
    partner_name = fields.CharField(max_length=255, null=True, description="合作伙伴名称")
    location_id = fields.IntField(description="源库位ID", index=True)
    location_code = fields.CharField(max_length=100, description="源库位编码")
    location_name = fields.CharField(max_length=255, description="源库位名称")
    location_dest_id = fields.IntField(description="目标库位ID", index=True)
    location_dest_code = fields.CharField(max_length=100, description="目标库位编码")
    location_dest_name = fields.CharField(max_length=255, description="目标库位名称")
    move_type = fields.CharField(max_length=20, default="direct", description="移动方式：direct/one_step/two_step/three_step")
    state = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/assigned/done/cancel", index=True)
    scheduled_date = fields.DatetimeField(null=True, description="计划日期")
    date_done = fields.DatetimeField(null=True, description="完成日期")
    owner_code = fields.CharField(max_length=100, null=True, description="调拨单负责人")
    responsible = fields.CharField(max_length=100, null=True, description="责任人")
    priority = fields.CharField(max_length=10, default="normal", description="优先级：urgent/high/normal/low")
    company_code = fields.CharField(max_length=100, null=True, description="公司编码")
    backorder_id = fields.IntField(null=True, description="回单ID（部分完成时生成）")
    backorder_code = fields.CharField(max_length=100, null=True, description="回单编码")
    note = fields.TextField(null=True, description="备注")
    printed = fields.BooleanField(default=False, description="是否已打印")

    class Meta:
        table = "stock_picking"

    async def to_dict(self):
        return {
            "id": self.id,
            "picking_code": self.picking_code,
            "picking_type_id": self.picking_type_id,
            "picking_type_code": self.picking_type_code,
            "picking_type_name": self.picking_type_name,
            "origin": self.origin,
            "origin_type": self.origin_type,
            "partner_code": self.partner_code,
            "partner_name": self.partner_name,
            "location_id": self.location_id,
            "location_code": self.location_code,
            "location_name": self.location_name,
            "location_dest_id": self.location_dest_id,
            "location_dest_code": self.location_dest_code,
            "location_dest_name": self.location_dest_name,
            "move_type": self.move_type,
            "state": self.state,
            "scheduled_date": self.scheduled_date.strftime("%Y-%m-%d %H:%M:%S") if self.scheduled_date else None,
            "date_done": self.date_done.strftime("%Y-%m-%d %H:%M:%S") if self.date_done else None,
            "owner_code": self.owner_code,
            "responsible": self.responsible,
            "priority": self.priority,
            "company_code": self.company_code,
            "backorder_id": self.backorder_id,
            "backorder_code": self.backorder_code,
            "note": self.note,
            "printed": self.printed,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class StockMove(BaseModel, TimestampMixin):
    verbose_name = "库存移动"
    """移动明细模型 - Odoo stock.move
    
    关联产品和库位，随Picking状态流转
    状态：draft → confirmed → assigned → done/cancel
    """
    move_code = fields.CharField(max_length=100, unique=True, description="移动编码", index=True)
    picking_id = fields.IntField(description="调拨单ID", index=True)
    picking_code = fields.CharField(max_length=100, description="调拨单编码")
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    product_uom = fields.CharField(max_length=20, description="计量单位")
    product_uom_qty = fields.DecimalField(max_digits=12, decimal_places=2, description="需求数量")
    secondary_uom = fields.CharField(max_length=20, null=True, description="辅助单位")
    secondary_uom_qty = fields.DecimalField(max_digits=12, decimal_places=2, null=True, description="辅助单位数量")
    conversion_factor = fields.DecimalField(max_digits=12, decimal_places=4, default=1, description="换算比例")
    location_id = fields.IntField(description="源库位ID", index=True)
    location_code = fields.CharField(max_length=100, description="源库位编码")
    location_name = fields.CharField(max_length=255, description="源库位名称")
    location_dest_id = fields.IntField(description="目标库位ID", index=True)
    location_dest_code = fields.CharField(max_length=100, description="目标库位编码")
    location_dest_name = fields.CharField(max_length=255, description="目标库位名称")
    state = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/assigned/partially_available/done/cancel", index=True)
    quantity_done = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="已完成数量")
    reserved_quantity = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="预留数量")
    origin = fields.CharField(max_length=100, null=True, description="来源单号")
    origin_type = fields.CharField(max_length=50, null=True, description="来源类型")
    reference = fields.CharField(max_length=200, null=True, description="引用")
    procurement_id = fields.IntField(null=True, description="需求单ID")
    procurement_code = fields.CharField(max_length=100, null=True, description="需求单编码")
    rule_id = fields.IntField(null=True, description="规则ID")
    rule_code = fields.CharField(max_length=100, null=True, description="规则编码")
    company_code = fields.CharField(max_length=100, null=True, description="公司编码")
    date_expected = fields.DatetimeField(null=True, description="期望日期")
    date = fields.DatetimeField(null=True, description="日期")
    backorder_id = fields.IntField(null=True, description="回单ID")
    backorder_code = fields.CharField(max_length=100, null=True, description="回单编码")
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "stock_move"

    async def to_dict(self):
        return {
            "id": self.id,
            "move_code": self.move_code,
            "picking_id": self.picking_id,
            "picking_code": self.picking_code,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "product_uom": self.product_uom,
            "product_uom_qty": float(self.product_uom_qty) if self.product_uom_qty and hasattr(self.product_uom_qty, "__float__") else self.product_uom_qty,
            "location_id": self.location_id,
            "location_code": self.location_code,
            "location_name": self.location_name,
            "location_dest_id": self.location_dest_id,
            "location_dest_code": self.location_dest_code,
            "location_dest_name": self.location_dest_name,
            "state": self.state,
            "quantity_done": float(self.quantity_done) if self.quantity_done and hasattr(self.quantity_done, "__float__") else self.quantity_done,
            "reserved_quantity": float(self.reserved_quantity) if self.reserved_quantity and hasattr(self.reserved_quantity, "__float__") else self.reserved_quantity,
            "origin": self.origin,
            "origin_type": self.origin_type,
            "reference": self.reference,
            "procurement_id": self.procurement_id,
            "procurement_code": self.procurement_code,
            "rule_id": self.rule_id,
            "rule_code": self.rule_code,
            "company_code": self.company_code,
            "date_expected": self.date_expected.strftime("%Y-%m-%d %H:%M:%S") if self.date_expected else None,
            "date": self.date.strftime("%Y-%m-%d %H:%M:%S") if self.date else None,
            "backorder_id": self.backorder_id,
            "backorder_code": self.backorder_code,
            "note": self.note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class StockMoveLine(BaseModel, TimestampMixin):
    """移动明细行模型 - Odoo stock.move.line
    
    批次/序列号级别的详细移动记录
    状态：draft → assigned → done
    """
    move_line_code = fields.CharField(max_length=100, unique=True, description="明细行编码", index=True)
    picking_id = fields.IntField(description="调拨单ID", index=True)
    picking_code = fields.CharField(max_length=100, description="调拨单编码")
    move_id = fields.IntField(description="移动明细ID", index=True)
    move_code = fields.CharField(max_length=100, description="移动明细编码")
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    product_uom_id = fields.IntField(null=True, description="计量单位ID")
    product_uom = fields.CharField(max_length=20, description="计量单位")
    product_uom_qty = fields.DecimalField(max_digits=12, decimal_places=2, description="需求数量")
    qty_done = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="已完成数量")
    location_id = fields.IntField(description="源库位ID", index=True)
    location_code = fields.CharField(max_length=100, description="源库位编码")
    location_name = fields.CharField(max_length=255, description="源库位名称")
    location_dest_id = fields.IntField(description="目标库位ID", index=True)
    location_dest_code = fields.CharField(max_length=100, description="目标库位编码")
    location_dest_name = fields.CharField(max_length=255, description="目标库位名称")
    lot_id = fields.IntField(null=True, description="批次ID", index=True)
    lot_name = fields.CharField(max_length=100, null=True, description="批次号")
    lot_ref = fields.CharField(max_length=100, null=True, description="批次参考")
    serial_no = fields.CharField(max_length=100, null=True, description="序列号", index=True)
    package_id = fields.IntField(null=True, description="包裹ID")
    package_code = fields.CharField(max_length=100, null=True, description="包裹编码")
    result_package_id = fields.IntField(null=True, description="结果包裹ID")
    result_package_code = fields.CharField(max_length=100, null=True, description="结果包裹编码")
    owner_id = fields.IntField(null=True, description="所有者ID")
    owner_code = fields.CharField(max_length=100, null=True, description="所有者编码")
    state = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/assigned/done", index=True)
    company_code = fields.CharField(max_length=100, null=True, description="公司编码")
    date = fields.DatetimeField(null=True, description="日期")
    reference = fields.CharField(max_length=200, null=True, description="引用")
    is_done = fields.BooleanField(default=False, description="是否完成")
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "stock_move_line"

    async def to_dict(self):
        return {
            "id": self.id,
            "move_line_code": self.move_line_code,
            "picking_id": self.picking_id,
            "picking_code": self.picking_code,
            "move_id": self.move_id,
            "move_code": self.move_code,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "product_uom_id": self.product_uom_id,
            "product_uom": self.product_uom,
            "product_uom_qty": float(self.product_uom_qty) if self.product_uom_qty and hasattr(self.product_uom_qty, "__float__") else self.product_uom_qty,
            "qty_done": float(self.qty_done) if self.qty_done and hasattr(self.qty_done, "__float__") else self.qty_done,
            "location_id": self.location_id,
            "location_code": self.location_code,
            "location_name": self.location_name,
            "location_dest_id": self.location_dest_id,
            "location_dest_code": self.location_dest_code,
            "location_dest_name": self.location_dest_name,
            "lot_id": self.lot_id,
            "lot_name": self.lot_name,
            "lot_ref": self.lot_ref,
            "serial_no": self.serial_no,
            "package_id": self.package_id,
            "package_code": self.package_code,
            "result_package_id": self.result_package_id,
            "result_package_code": self.result_package_code,
            "owner_id": self.owner_id,
            "owner_code": self.owner_code,
            "state": self.state,
            "company_code": self.company_code,
            "date": self.date.strftime("%Y-%m-%d %H:%M:%S") if self.date else None,
            "reference": self.reference,
            "is_done": self.is_done,
            "note": self.note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


# ==================== 库存数量模型 ====================

class StockQuant(BaseModel, TimestampMixin):
    """库存数量模型 - Odoo stock.quant
    
    按产品+库位+批次+序列号维度存储库存
    """
    quant_code = fields.CharField(max_length=100, unique=True, description="库存编码", index=True)
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    location_id = fields.IntField(description="库位ID", index=True)
    location_code = fields.CharField(max_length=100, description="库位编码")
    location_name = fields.CharField(max_length=255, description="库位名称")
    lot_id = fields.IntField(null=True, description="批次ID", index=True)
    lot_name = fields.CharField(max_length=100, null=True, description="批次号", index=True)
    serial_no = fields.CharField(max_length=100, null=True, description="序列号", index=True)
    package_id = fields.IntField(null=True, description="包裹ID")
    package_code = fields.CharField(max_length=100, null=True, description="包裹编码")
    owner_id = fields.IntField(null=True, description="所有者ID")
    owner_code = fields.CharField(max_length=100, null=True, description="所有者编码")
    quantity = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="库存数量")
    reserved_quantity = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="预留数量")
    available_quantity = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="可用数量")
    uom_id = fields.IntField(null=True, description="单位ID")
    uom_code = fields.CharField(max_length=20, default="unit", description="单位编码")
    uom_name = fields.CharField(max_length=50, default="件", description="单位名称")
    secondary_uom_id = fields.IntField(null=True, description="辅助单位ID")
    secondary_uom_name = fields.CharField(max_length=50, null=True, description="辅助单位名称")
    conversion_factor = fields.DecimalField(max_digits=12, decimal_places=4, default=1, description="换算比例")
    inventory_value = fields.DecimalField(max_digits=15, decimal_places=2, default=0, description="库存价值")
    cost = fields.DecimalField(max_digits=12, decimal_places=2, null=True, description="成本单价")
    company_code = fields.CharField(max_length=100, null=True, description="公司编码")
    in_date = fields.DatetimeField(null=True, description="入库日期")
    expiry_date = fields.DatetimeField(null=True, description="过期日期")
    is_propagated = fields.BooleanField(default=False, description="是否已传播")
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "stock_quant"

    async def to_dict(self):
        return {
            "id": self.id,
            "quant_code": self.quant_code,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "location_id": self.location_id,
            "location_code": self.location_code,
            "location_name": self.location_name,
            "lot_id": self.lot_id,
            "lot_name": self.lot_name,
            "serial_no": self.serial_no,
            "package_id": self.package_id,
            "package_code": self.package_code,
            "owner_id": self.owner_id,
            "owner_code": self.owner_code,
            "quantity": float(self.quantity) if self.quantity and hasattr(self.quantity, "__float__") else self.quantity,
            "reserved_quantity": float(self.reserved_quantity) if self.reserved_quantity and hasattr(self.reserved_quantity, "__float__") else self.reserved_quantity,
            "available_quantity": float(self.available_quantity) if self.available_quantity and hasattr(self.available_quantity, "__float__") else self.available_quantity,
            "uom_id": self.uom_id,
            "uom_code": self.uom_code,
            "uom_name": self.uom_name,
            "secondary_uom_id": self.secondary_uom_id,
            "secondary_uom_name": self.secondary_uom_name,
            "conversion_factor": float(self.conversion_factor) if self.conversion_factor and hasattr(self.conversion_factor, "__float__") else self.conversion_factor,
            "inventory_value": float(self.inventory_value) if self.inventory_value and hasattr(self.inventory_value, "__float__") else self.inventory_value,
            "cost": float(self.cost) if self.cost and hasattr(self.cost, "__float__") else self.cost,
            "company_code": self.company_code,
            "in_date": self.in_date.strftime("%Y-%m-%d %H:%M:%S") if self.in_date else None,
            "expiry_date": self.expiry_date.strftime("%Y-%m-%d %H:%M:%S") if self.expiry_date else None,
            "is_propagated": self.is_propagated,
            "note": self.note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class StockQuantReservation(BaseModel, TimestampMixin):
    verbose_name = "库存预留"
    """库存预留模型
    
    记录库存预留关系
    """
    reservation_code = fields.CharField(max_length=100, unique=True, description="预留编码", index=True)
    quant_id = fields.IntField(description="库存ID", index=True)
    quant_code = fields.CharField(max_length=100, description="库存编码")
    move_id = fields.IntField(description="移动明细ID", index=True)
    move_code = fields.CharField(max_length=100, description="移动明细编码")
    move_line_id = fields.IntField(null=True, description="移动明细行ID")
    move_line_code = fields.CharField(max_length=100, null=True, description="移动明细行编码")
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    location_id = fields.IntField(description="库位ID", index=True)
    location_code = fields.CharField(max_length=100, description="库位编码")
    lot_id = fields.IntField(null=True, description="批次ID")
    lot_name = fields.CharField(max_length=100, null=True, description="批次号")
    serial_no = fields.CharField(max_length=100, null=True, description="序列号")
    quantity = fields.DecimalField(max_digits=12, decimal_places=2, description="预留数量")
    reserved_at = fields.DatetimeField(null=True, description="预留时间")
    released_at = fields.DatetimeField(null=True, description="释放时间")
    state = fields.CharField(max_length=20, default="reserved", description="状态：reserved/released/consumed", index=True)
    company_code = fields.CharField(max_length=100, null=True, description="公司编码")
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "stock_quant_reservation"

    async def to_dict(self):
        return {
            "id": self.id,
            "reservation_code": self.reservation_code,
            "quant_id": self.quant_id,
            "quant_code": self.quant_code,
            "move_id": self.move_id,
            "move_code": self.move_code,
            "move_line_id": self.move_line_id,
            "move_line_code": self.move_line_code,
            "product_code": self.product_code,
            "location_id": self.location_id,
            "location_code": self.location_code,
            "lot_id": self.lot_id,
            "lot_name": self.lot_name,
            "serial_no": self.serial_no,
            "quantity": float(self.quantity) if self.quantity and hasattr(self.quantity, "__float__") else self.quantity,
            "reserved_at": self.reserved_at.strftime("%Y-%m-%d %H:%M:%S") if self.reserved_at else None,
            "released_at": self.released_at.strftime("%Y-%m-%d %H:%M:%S") if self.released_at else None,
            "state": self.state,
            "company_code": self.company_code,
            "note": self.note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }



# ==================== 辅助模型 ====================

class StockLot(BaseModel, TimestampMixin):
    """批次模型 - Odoo stock.production.lot
    
    管理产品批次信息
    """
    lot_code = fields.CharField(max_length=100, unique=True, description="批次编码", index=True)
    lot_name = fields.CharField(max_length=255, description="批次名称")
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    company_code = fields.CharField(max_length=100, null=True, description="公司编码")
    ref = fields.CharField(max_length=100, null=True, description="参考")
    create_date = fields.DatetimeField(null=True, description="创建日期")
    use_date = fields.DatetimeField(null=True, description="使用日期")
    expiry_date = fields.DatetimeField(null=True, description="过期日期")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "stock_lot"

    async def to_dict(self):
        return {
            "id": self.id,
            "lot_code": self.lot_code,
            "lot_name": self.lot_name,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "company_code": self.company_code,
            "ref": self.ref,
            "create_date": self.create_date.strftime("%Y-%m-%d %H:%M:%S") if self.create_date else None,
            "use_date": self.use_date.strftime("%Y-%m-%d %H:%M:%S") if self.use_date else None,
            "expiry_date": self.expiry_date.strftime("%Y-%m-%d %H:%M:%S") if self.expiry_date else None,
            "is_active": self.is_active,
            "note": self.note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class StockPackage(BaseModel, TimestampMixin):
    verbose_name = "包裹"
    """包裹模型 - Odoo stock.quant.package
    
    管理包裹信息
    """
    package_code = fields.CharField(max_length=100, unique=True, description="包裹编码", index=True)
    package_name = fields.CharField(max_length=255, description="包裹名称")
    package_type = fields.CharField(max_length=50, default="box", description="包裹类型：box/bag/pallet/container/other")
    location_id = fields.IntField(null=True, description="当前位置ID", index=True)
    location_code = fields.CharField(max_length=100, null=True, description="当前位置编码")
    location_name = fields.CharField(max_length=255, null=True, description="当前位置名称")
    company_code = fields.CharField(max_length=100, null=True, description="公司编码")
    owner_id = fields.IntField(null=True, description="所有者ID")
    owner_code = fields.CharField(max_length=100, null=True, description="所有者编码")
    parent_id = fields.IntField(null=True, description="父包裹ID")
    parent_code = fields.CharField(max_length=100, null=True, description="父包裹编码")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    weight = fields.DecimalField(max_digits=10, decimal_places=3, null=True, description="重量(kg)")
    length = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="长度(cm)")
    width = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="宽度(cm)")
    height = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="高度(cm)")
    note = fields.TextField(null=True, description="备注")

    class Meta:
        table = "stock_package"

    async def to_dict(self):
        return {
            "id": self.id,
            "package_code": self.package_code,
            "package_name": self.package_name,
            "package_type": self.package_type,
            "location_id": self.location_id,
            "location_code": self.location_code,
            "location_name": self.location_name,
            "company_code": self.company_code,
            "owner_id": self.owner_id,
            "owner_code": self.owner_code,
            "parent_id": self.parent_id,
            "parent_code": self.parent_code,
            "is_active": self.is_active,
            "weight": float(self.weight) if self.weight and hasattr(self.weight, "__float__") else self.weight,
            "length": float(self.length) if self.length and hasattr(self.length, "__float__") else self.length,
            "width": float(self.width) if self.width and hasattr(self.width, "__float__") else self.width,
            "height": float(self.height) if self.height and hasattr(self.height, "__float__") else self.height,
            "note": self.note,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }