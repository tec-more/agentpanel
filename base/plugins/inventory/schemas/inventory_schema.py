"""
库存管理模块 Pydantic Schemas
基于Odoo风格模型定义完整的API数据结构
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


# ==================== 库位模型 Schemas ====================

class StockLocationBase(BaseModel):
    """库位基础字段"""
    location_code: str = Field(..., min_length=1, max_length=100, description="库位编码")
    location_name: str = Field(..., min_length=1, max_length=255, description="库位名称")
    parent_id: Optional[int] = Field(None, description="父库位ID")
    parent_code: Optional[str] = Field(None, max_length=100, description="父库位编码")
    warehouse_id: Optional[int] = Field(None, description="所属仓库ID")
    warehouse_code: Optional[str] = Field(None, max_length=100, description="所属仓库编码")
    location_type: str = Field(default="internal", max_length=20, description="库位类型：internal/customer/supplier/view/inventory_loss/production/scrap")
    usage: str = Field(default="internal", max_length=20, description="用途：view/internal/customer/supplier/inventory_loss/production/packing/scrap")
    is_active: bool = Field(default=True, description="是否启用")
    is_scrap: bool = Field(default=False, description="是否报废库位")
    is_inventory_loss: bool = Field(default=False, description="是否盘亏库位")
    posx: int = Field(default=0, ge=0, description="X坐标")
    posy: int = Field(default=0, ge=0, description="Y坐标")
    posz: int = Field(default=0, ge=0, description="Z坐标")
    capacity: int = Field(default=0, ge=0, description="容量")
    description: Optional[str] = Field(None, description="描述")


class StockLocationCreate(StockLocationBase):
    """创建库位"""
    pass


class StockLocationUpdate(BaseModel):
    """更新库位"""
    location_code: Optional[str] = Field(None, min_length=1, max_length=100, description="库位编码")
    location_name: Optional[str] = Field(None, min_length=1, max_length=255, description="库位名称")
    parent_id: Optional[int] = Field(None, description="父库位ID")
    parent_code: Optional[str] = Field(None, max_length=100, description="父库位编码")
    warehouse_id: Optional[int] = Field(None, description="所属仓库ID")
    warehouse_code: Optional[str] = Field(None, max_length=100, description="所属仓库编码")
    location_type: Optional[str] = Field(None, max_length=20, description="库位类型")
    usage: Optional[str] = Field(None, max_length=20, description="用途")
    is_active: Optional[bool] = Field(None, description="是否启用")
    is_scrap: Optional[bool] = Field(None, description="是否报废库位")
    is_inventory_loss: Optional[bool] = Field(None, description="是否盘亏库位")
    posx: Optional[int] = Field(None, ge=0, description="X坐标")
    posy: Optional[int] = Field(None, ge=0, description="Y坐标")
    posz: Optional[int] = Field(None, ge=0, description="Z坐标")
    capacity: Optional[int] = Field(None, ge=0, description="容量")
    description: Optional[str] = Field(None, description="描述")


class StockLocationResponse(StockLocationBase):
    """库位响应"""
    id: int = Field(..., description="库位ID")
    complete_name: Optional[str] = Field(None, max_length=500, description="完整名称（层级路径）")
    path: Optional[str] = Field(None, max_length=500, description="物化路径（如：WH001/A01/B02）")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockLocationQuery(BaseModel):
    """库位查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    location_code: Optional[str] = Field(None, description="库位编码")
    location_name: Optional[str] = Field(None, description="库位名称")
    parent_id: Optional[int] = Field(None, description="父库位ID")
    warehouse_id: Optional[int] = Field(None, description="仓库ID")
    warehouse_code: Optional[str] = Field(None, description="仓库编码")
    location_type: Optional[str] = Field(None, description="库位类型")
    usage: Optional[str] = Field(None, description="用途")
    is_active: Optional[bool] = Field(None, description="是否启用")


# ==================== 仓库模型 Schemas ====================

class StockWarehouseBase(BaseModel):
    """仓库基础字段"""
    warehouse_code: str = Field(..., min_length=1, max_length=100, description="仓库编码")
    warehouse_name: str = Field(..., min_length=1, max_length=255, description="仓库名称")
    warehouse_type: str = Field(default="internal", max_length=20, description="仓库类型：internal/customer/supplier")
    company_code: Optional[str] = Field(None, max_length=100, description="所属公司编码")
    view_location_id: Optional[int] = Field(None, description="视图库位ID")
    view_location_code: Optional[str] = Field(None, max_length=100, description="视图库位编码")
    lot_stock_id: Optional[int] = Field(None, description="存货库位ID")
    lot_stock_code: Optional[str] = Field(None, max_length=100, description="存货库位编码")
    input_location_id: Optional[int] = Field(None, description="入库库位ID")
    input_location_code: Optional[str] = Field(None, max_length=100, description="入库库位编码")
    output_location_id: Optional[int] = Field(None, description="出库库位ID")
    output_location_code: Optional[str] = Field(None, max_length=100, description="出库库位编码")
    qc_location_id: Optional[int] = Field(None, description="质检库位ID")
    qc_location_code: Optional[str] = Field(None, max_length=100, description="质检库位编码")
    pack_location_id: Optional[int] = Field(None, description="打包库位ID")
    pack_location_code: Optional[str] = Field(None, max_length=100, description="打包库位编码")
    scrap_location_id: Optional[int] = Field(None, description="报废库位ID")
    scrap_location_code: Optional[str] = Field(None, max_length=100, description="报废库位编码")
    address: Optional[str] = Field(None, max_length=500, description="仓库地址")
    manager: Optional[str] = Field(None, max_length=100, description="仓库管理员")
    contact_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    is_active: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(None, description="描述")


class StockWarehouseCreate(StockWarehouseBase):
    """创建仓库"""
    pass


class StockWarehouseUpdate(BaseModel):
    """更新仓库"""
    warehouse_code: Optional[str] = Field(None, min_length=1, max_length=100, description="仓库编码")
    warehouse_name: Optional[str] = Field(None, min_length=1, max_length=255, description="仓库名称")
    warehouse_type: Optional[str] = Field(None, max_length=20, description="仓库类型")
    company_code: Optional[str] = Field(None, max_length=100, description="所属公司编码")
    view_location_id: Optional[int] = Field(None, description="视图库位ID")
    view_location_code: Optional[str] = Field(None, max_length=100, description="视图库位编码")
    lot_stock_id: Optional[int] = Field(None, description="存货库位ID")
    lot_stock_code: Optional[str] = Field(None, max_length=100, description="存货库位编码")
    input_location_id: Optional[int] = Field(None, description="入库库位ID")
    input_location_code: Optional[str] = Field(None, max_length=100, description="入库库位编码")
    output_location_id: Optional[int] = Field(None, description="出库库位ID")
    output_location_code: Optional[str] = Field(None, max_length=100, description="出库库位编码")
    qc_location_id: Optional[int] = Field(None, description="质检库位ID")
    qc_location_code: Optional[str] = Field(None, max_length=100, description="质检库位编码")
    pack_location_id: Optional[int] = Field(None, description="打包库位ID")
    pack_location_code: Optional[str] = Field(None, max_length=100, description="打包库位编码")
    scrap_location_id: Optional[int] = Field(None, description="报废库位ID")
    scrap_location_code: Optional[str] = Field(None, max_length=100, description="报废库位编码")
    address: Optional[str] = Field(None, max_length=500, description="仓库地址")
    manager: Optional[str] = Field(None, max_length=100, description="仓库管理员")
    contact_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    is_active: Optional[bool] = Field(None, description="是否启用")
    description: Optional[str] = Field(None, description="描述")


class StockWarehouseResponse(StockWarehouseBase):
    """仓库响应"""
    id: int = Field(..., description="仓库ID")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockWarehouseQuery(BaseModel):
    """仓库查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    warehouse_code: Optional[str] = Field(None, description="仓库编码")
    warehouse_name: Optional[str] = Field(None, description="仓库名称")
    warehouse_type: Optional[str] = Field(None, description="仓库类型")
    is_active: Optional[bool] = Field(None, description="是否启用")


# ==================== 调拨类型模型 Schemas ====================

class StockPickingTypeBase(BaseModel):
    """调拨类型基础字段"""
    picking_type_code: str = Field(..., min_length=1, max_length=100, description="调拨类型编码")
    picking_type_name: str = Field(..., min_length=1, max_length=255, description="调拨类型名称")
    code: str = Field(..., max_length=20, description="类型代码：incoming/outgoing/internal")
    sequence_code: str = Field(default="{type}/{year}/{month}", max_length=50, description="序列码模板")
    warehouse_id: Optional[int] = Field(None, description="所属仓库ID")
    warehouse_code: Optional[str] = Field(None, max_length=100, description="所属仓库编码")
    default_location_src_id: Optional[int] = Field(None, description="默认源库位ID")
    default_location_src_code: Optional[str] = Field(None, max_length=100, description="默认源库位编码")
    default_location_dest_id: Optional[int] = Field(None, description="默认目标库位ID")
    default_location_dest_code: Optional[str] = Field(None, max_length=100, description="默认目标库位编码")
    is_active: bool = Field(default=True, description="是否启用")
    show_operations: bool = Field(default=False, description="是否显示明细行")
    show_reserved: bool = Field(default=True, description="是否显示预留数量")
    color: int = Field(default=0, ge=0, description="颜色标记")
    description: Optional[str] = Field(None, description="描述")


class StockPickingTypeCreate(StockPickingTypeBase):
    """创建调拨类型"""
    pass


class StockPickingTypeUpdate(BaseModel):
    """更新调拨类型"""
    picking_type_code: Optional[str] = Field(None, min_length=1, max_length=100, description="调拨类型编码")
    picking_type_name: Optional[str] = Field(None, min_length=1, max_length=255, description="调拨类型名称")
    code: Optional[str] = Field(None, max_length=20, description="类型代码")
    sequence_code: Optional[str] = Field(None, max_length=50, description="序列码模板")
    warehouse_id: Optional[int] = Field(None, description="所属仓库ID")
    warehouse_code: Optional[str] = Field(None, max_length=100, description="所属仓库编码")
    default_location_src_id: Optional[int] = Field(None, description="默认源库位ID")
    default_location_src_code: Optional[str] = Field(None, max_length=100, description="默认源库位编码")
    default_location_dest_id: Optional[int] = Field(None, description="默认目标库位ID")
    default_location_dest_code: Optional[str] = Field(None, max_length=100, description="默认目标库位编码")
    is_active: Optional[bool] = Field(None, description="是否启用")
    show_operations: Optional[bool] = Field(None, description="是否显示明细行")
    show_reserved: Optional[bool] = Field(None, description="是否显示预留数量")
    color: Optional[int] = Field(None, ge=0, description="颜色标记")
    description: Optional[str] = Field(None, description="描述")


class StockPickingTypeResponse(StockPickingTypeBase):
    """调拨类型响应"""
    id: int = Field(..., description="调拨类型ID")
    last_sequence: int = Field(default=0, description="最后序列号")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockPickingTypeQuery(BaseModel):
    """调拨类型查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    picking_type_code: Optional[str] = Field(None, description="调拨类型编码")
    picking_type_name: Optional[str] = Field(None, description="调拨类型名称")
    code: Optional[str] = Field(None, description="类型代码")
    warehouse_id: Optional[int] = Field(None, description="仓库ID")
    warehouse_code: Optional[str] = Field(None, description="仓库编码")
    is_active: Optional[bool] = Field(None, description="是否启用")


# ==================== 调拨单模型 Schemas ====================

class StockPickingBase(BaseModel):
    """调拨单基础字段"""
    picking_type_id: int = Field(..., description="调拨类型ID")
    picking_type_code: str = Field(..., max_length=100, description="调拨类型编码")
    picking_type_name: str = Field(..., max_length=255, description="调拨类型名称")
    origin: Optional[str] = Field(None, max_length=100, description="来源单号")
    origin_type: Optional[str] = Field(None, max_length=50, description="来源类型：SO/PO/MO/DO")
    partner_code: Optional[str] = Field(None, max_length=100, description="合作伙伴编码")
    partner_name: Optional[str] = Field(None, max_length=255, description="合作伙伴名称")
    location_id: int = Field(..., description="源库位ID")
    location_code: str = Field(..., max_length=100, description="源库位编码")
    location_name: str = Field(..., max_length=255, description="源库位名称")
    location_dest_id: int = Field(..., description="目标库位ID")
    location_dest_code: str = Field(..., max_length=100, description="目标库位编码")
    location_dest_name: str = Field(..., max_length=255, description="目标库位名称")
    move_type: str = Field(default="direct", max_length=20, description="移动方式：direct/one_step/two_step/three_step")
    state: str = Field(default="draft", max_length=20, description="状态：draft/confirmed/assigned/done/cancel")
    scheduled_date: Optional[datetime] = Field(None, description="计划日期")
    date_done: Optional[datetime] = Field(None, description="完成日期")
    owner_code: Optional[str] = Field(None, max_length=100, description="调拨单负责人")
    responsible: Optional[str] = Field(None, max_length=100, description="责任人")
    priority: str = Field(default="normal", max_length=10, description="优先级：urgent/high/normal/low")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    backorder_id: Optional[int] = Field(None, description="回单ID")
    backorder_code: Optional[str] = Field(None, max_length=100, description="回单编码")
    note: Optional[str] = Field(None, description="备注")
    printed: bool = Field(default=False, description="是否已打印")


class StockPickingCreate(StockPickingBase):
    """创建调拨单"""
    picking_code: Optional[str] = Field(None, max_length=100, description="调拨单编码（不提供则自动生成）")
    moves: Optional[List['StockMoveCreate']] = Field(None, description="移动明细列表")


class StockPickingUpdate(BaseModel):
    """更新调拨单"""
    picking_type_id: Optional[int] = Field(None, description="调拨类型ID")
    picking_type_code: Optional[str] = Field(None, max_length=100, description="调拨类型编码")
    picking_type_name: Optional[str] = Field(None, max_length=255, description="调拨类型名称")
    origin: Optional[str] = Field(None, max_length=100, description="来源单号")
    origin_type: Optional[str] = Field(None, max_length=50, description="来源类型")
    partner_code: Optional[str] = Field(None, max_length=100, description="合作伙伴编码")
    partner_name: Optional[str] = Field(None, max_length=255, description="合作伙伴名称")
    location_id: Optional[int] = Field(None, description="源库位ID")
    location_code: Optional[str] = Field(None, max_length=100, description="源库位编码")
    location_name: Optional[str] = Field(None, max_length=255, description="源库位名称")
    location_dest_id: Optional[int] = Field(None, description="目标库位ID")
    location_dest_code: Optional[str] = Field(None, max_length=100, description="目标库位编码")
    location_dest_name: Optional[str] = Field(None, max_length=255, description="目标库位名称")
    move_type: Optional[str] = Field(None, max_length=20, description="移动方式")
    state: Optional[str] = Field(None, max_length=20, description="状态")
    scheduled_date: Optional[datetime] = Field(None, description="计划日期")
    date_done: Optional[datetime] = Field(None, description="完成日期")
    owner_code: Optional[str] = Field(None, max_length=100, description="调拨单负责人")
    responsible: Optional[str] = Field(None, max_length=100, description="责任人")
    priority: Optional[str] = Field(None, max_length=10, description="优先级")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    backorder_id: Optional[int] = Field(None, description="回单ID")
    backorder_code: Optional[str] = Field(None, max_length=100, description="回单编码")
    note: Optional[str] = Field(None, description="备注")
    printed: Optional[bool] = Field(None, description="是否已打印")


class StockPickingResponse(StockPickingBase):
    """调拨单响应"""
    id: int = Field(..., description="调拨单ID")
    picking_code: str = Field(..., max_length=100, description="调拨单编码")
    moves: Optional[List['StockMoveResponse']] = Field(None, description="移动明细列表")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockPickingQuery(BaseModel):
    """调拨单查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    picking_code: Optional[str] = Field(None, description="调拨单编码")
    picking_type_id: Optional[int] = Field(None, description="调拨类型ID")
    picking_type_code: Optional[str] = Field(None, description="调拨类型编码")
    origin: Optional[str] = Field(None, description="来源单号")
    partner_code: Optional[str] = Field(None, description="合作伙伴编码")
    location_id: Optional[int] = Field(None, description="源库位ID")
    location_dest_id: Optional[int] = Field(None, description="目标库位ID")
    state: Optional[str] = Field(None, description="状态")
    scheduled_date_start: Optional[datetime] = Field(None, description="计划日期开始")
    scheduled_date_end: Optional[datetime] = Field(None, description="计划日期结束")
    priority: Optional[str] = Field(None, description="优先级")


# ==================== 移动明细模型 Schemas ====================

class StockMoveBase(BaseModel):
    """移动明细基础字段"""
    picking_id: int = Field(..., description="调拨单ID")
    picking_code: str = Field(..., max_length=100, description="调拨单编码")
    product_id: Optional[int] = Field(None, description="产品ID")
    product_code: str = Field(..., max_length=100, description="产品编码")
    product_name: str = Field(..., max_length=255, description="产品名称")
    product_uom: str = Field(..., max_length=20, description="计量单位")
    product_uom_qty: Decimal = Field(..., ge=0, description="需求数量")
    secondary_uom: Optional[str] = Field(None, max_length=20, description="辅助单位")
    secondary_uom_qty: Optional[Decimal] = Field(None, ge=0, description="辅助单位数量")
    conversion_factor: Decimal = Field(default=1, description="换算比例")
    location_id: int = Field(..., description="源库位ID")
    location_code: str = Field(..., max_length=100, description="源库位编码")
    location_name: str = Field(..., max_length=255, description="源库位名称")
    location_dest_id: int = Field(..., description="目标库位ID")
    location_dest_code: str = Field(..., max_length=100, description="目标库位编码")
    location_dest_name: str = Field(..., max_length=255, description="目标库位名称")
    state: str = Field(default="draft", max_length=20, description="状态：draft/confirmed/assigned/partially_available/done/cancel")
    quantity_done: Decimal = Field(default=0, ge=0, description="已完成数量")
    reserved_quantity: Decimal = Field(default=0, ge=0, description="预留数量")
    origin: Optional[str] = Field(None, max_length=100, description="来源单号")
    origin_type: Optional[str] = Field(None, max_length=50, description="来源类型")
    reference: Optional[str] = Field(None, max_length=200, description="引用")
    procurement_id: Optional[int] = Field(None, description="需求单ID")
    procurement_code: Optional[str] = Field(None, max_length=100, description="需求单编码")
    rule_id: Optional[int] = Field(None, description="规则ID")
    rule_code: Optional[str] = Field(None, max_length=100, description="规则编码")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    date_expected: Optional[datetime] = Field(None, description="期望日期")
    date: Optional[datetime] = Field(None, description="日期")
    backorder_id: Optional[int] = Field(None, description="回单ID")
    backorder_code: Optional[str] = Field(None, max_length=100, description="回单编码")
    note: Optional[str] = Field(None, description="备注")


class StockMoveCreate(StockMoveBase):
    """创建移动明细"""
    picking_id: Optional[int] = Field(None, description="调拨单ID（创建调拨单时自动填充）")
    picking_code: Optional[str] = Field(None, max_length=100, description="调拨单编码（创建调拨单时自动填充）")
    move_code: Optional[str] = Field(None, max_length=100, description="移动编码（不提供则自动生成）")
    move_lines: Optional[List['StockMoveLineCreate']] = Field(None, description="移动明细行列表")


class StockMoveUpdate(BaseModel):
    """更新移动明细"""
    picking_id: Optional[int] = Field(None, description="调拨单ID")
    picking_code: Optional[str] = Field(None, max_length=100, description="调拨单编码")
    product_code: Optional[str] = Field(None, max_length=100, description="产品编码")
    product_name: Optional[str] = Field(None, max_length=255, description="产品名称")
    product_uom: Optional[str] = Field(None, max_length=20, description="计量单位")
    product_uom_qty: Optional[Decimal] = Field(None, ge=0, description="需求数量")
    location_id: Optional[int] = Field(None, description="源库位ID")
    location_code: Optional[str] = Field(None, max_length=100, description="源库位编码")
    location_name: Optional[str] = Field(None, max_length=255, description="源库位名称")
    location_dest_id: Optional[int] = Field(None, description="目标库位ID")
    location_dest_code: Optional[str] = Field(None, max_length=100, description="目标库位编码")
    location_dest_name: Optional[str] = Field(None, max_length=255, description="目标库位名称")
    state: Optional[str] = Field(None, max_length=20, description="状态")
    quantity_done: Optional[Decimal] = Field(None, ge=0, description="已完成数量")
    reserved_quantity: Optional[Decimal] = Field(None, ge=0, description="预留数量")
    origin: Optional[str] = Field(None, max_length=100, description="来源单号")
    origin_type: Optional[str] = Field(None, max_length=50, description="来源类型")
    reference: Optional[str] = Field(None, max_length=200, description="引用")
    procurement_id: Optional[int] = Field(None, description="需求单ID")
    procurement_code: Optional[str] = Field(None, max_length=100, description="需求单编码")
    rule_id: Optional[int] = Field(None, description="规则ID")
    rule_code: Optional[str] = Field(None, max_length=100, description="规则编码")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    date_expected: Optional[datetime] = Field(None, description="期望日期")
    date: Optional[datetime] = Field(None, description="日期")
    backorder_id: Optional[int] = Field(None, description="回单ID")
    backorder_code: Optional[str] = Field(None, max_length=100, description="回单编码")
    note: Optional[str] = Field(None, description="备注")


class StockMoveResponse(StockMoveBase):
    """移动明细响应"""
    id: int = Field(..., description="移动明细ID")
    move_code: str = Field(..., max_length=100, description="移动编码")
    move_lines: Optional[List['StockMoveLineResponse']] = Field(None, description="移动明细行列表")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockMoveQuery(BaseModel):
    """移动明细查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    move_code: Optional[str] = Field(None, description="移动编码")
    picking_id: Optional[int] = Field(None, description="调拨单ID")
    picking_code: Optional[str] = Field(None, description="调拨单编码")
    product_code: Optional[str] = Field(None, description="产品编码")
    location_id: Optional[int] = Field(None, description="源库位ID")
    location_dest_id: Optional[int] = Field(None, description="目标库位ID")
    state: Optional[str] = Field(None, description="状态")
    date_expected_start: Optional[datetime] = Field(None, description="期望日期开始")
    date_expected_end: Optional[datetime] = Field(None, description="期望日期结束")


# ==================== 移动明细行模型 Schemas ====================

class StockMoveLineBase(BaseModel):
    """移动明细行基础字段"""
    picking_id: int = Field(..., description="调拨单ID")
    picking_code: str = Field(..., max_length=100, description="调拨单编码")
    move_id: int = Field(..., description="移动明细ID")
    move_code: str = Field(..., max_length=100, description="移动明细编码")
    product_id: Optional[int] = Field(None, description="产品ID")
    product_code: str = Field(..., max_length=100, description="产品编码")
    product_name: str = Field(..., max_length=255, description="产品名称")
    product_uom_id: Optional[int] = Field(None, description="计量单位ID")
    product_uom: str = Field(..., max_length=20, description="计量单位")
    product_uom_qty: Decimal = Field(..., ge=0, description="需求数量")
    qty_done: Decimal = Field(default=0, ge=0, description="已完成数量")
    location_id: int = Field(..., description="源库位ID")
    location_code: str = Field(..., max_length=100, description="源库位编码")
    location_name: str = Field(..., max_length=255, description="源库位名称")
    location_dest_id: int = Field(..., description="目标库位ID")
    location_dest_code: str = Field(..., max_length=100, description="目标库位编码")
    location_dest_name: str = Field(..., max_length=255, description="目标库位名称")
    lot_id: Optional[int] = Field(None, description="批次ID")
    lot_name: Optional[str] = Field(None, max_length=100, description="批次号")
    lot_ref: Optional[str] = Field(None, max_length=100, description="批次参考")
    serial_no: Optional[str] = Field(None, max_length=100, description="序列号")
    package_id: Optional[int] = Field(None, description="包裹ID")
    package_code: Optional[str] = Field(None, max_length=100, description="包裹编码")
    result_package_id: Optional[int] = Field(None, description="结果包裹ID")
    result_package_code: Optional[str] = Field(None, max_length=100, description="结果包裹编码")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    owner_code: Optional[str] = Field(None, max_length=100, description="所有者编码")
    state: str = Field(default="draft", max_length=20, description="状态：draft/confirmed/assigned/done")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    date: Optional[datetime] = Field(None, description="日期")
    reference: Optional[str] = Field(None, max_length=200, description="引用")
    is_done: bool = Field(default=False, description="是否完成")
    note: Optional[str] = Field(None, description="备注")


class StockMoveLineCreate(StockMoveLineBase):
    """创建移动明细行"""
    move_line_code: Optional[str] = Field(None, max_length=100, description="明细行编码（不提供则自动生成）")


class StockMoveLineUpdate(BaseModel):
    """更新移动明细行"""
    picking_id: Optional[int] = Field(None, description="调拨单ID")
    picking_code: Optional[str] = Field(None, max_length=100, description="调拨单编码")
    move_id: Optional[int] = Field(None, description="移动明细ID")
    move_code: Optional[str] = Field(None, max_length=100, description="移动明细编码")
    product_code: Optional[str] = Field(None, max_length=100, description="产品编码")
    product_name: Optional[str] = Field(None, max_length=255, description="产品名称")
    product_uom_id: Optional[int] = Field(None, description="计量单位ID")
    product_uom: Optional[str] = Field(None, max_length=20, description="计量单位")
    product_uom_qty: Optional[Decimal] = Field(None, ge=0, description="需求数量")
    qty_done: Optional[Decimal] = Field(None, ge=0, description="已完成数量")
    location_id: Optional[int] = Field(None, description="源库位ID")
    location_code: Optional[str] = Field(None, max_length=100, description="源库位编码")
    location_name: Optional[str] = Field(None, max_length=255, description="源库位名称")
    location_dest_id: Optional[int] = Field(None, description="目标库位ID")
    location_dest_code: Optional[str] = Field(None, max_length=100, description="目标库位编码")
    location_dest_name: Optional[str] = Field(None, max_length=255, description="目标库位名称")
    lot_id: Optional[int] = Field(None, description="批次ID")
    lot_name: Optional[str] = Field(None, max_length=100, description="批次号")
    lot_ref: Optional[str] = Field(None, max_length=100, description="批次参考")
    serial_no: Optional[str] = Field(None, max_length=100, description="序列号")
    package_id: Optional[int] = Field(None, description="包裹ID")
    package_code: Optional[str] = Field(None, max_length=100, description="包裹编码")
    result_package_id: Optional[int] = Field(None, description="结果包裹ID")
    result_package_code: Optional[str] = Field(None, max_length=100, description="结果包裹编码")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    owner_code: Optional[str] = Field(None, max_length=100, description="所有者编码")
    state: Optional[str] = Field(None, max_length=20, description="状态")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    date: Optional[datetime] = Field(None, description="日期")
    reference: Optional[str] = Field(None, max_length=200, description="引用")
    is_done: Optional[bool] = Field(None, description="是否完成")
    note: Optional[str] = Field(None, description="备注")


class StockMoveLineResponse(StockMoveLineBase):
    """移动明细行响应"""
    id: int = Field(..., description="移动明细行ID")
    move_line_code: str = Field(..., max_length=100, description="明细行编码")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockMoveLineQuery(BaseModel):
    """移动明细行查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    move_line_code: Optional[str] = Field(None, description="明细行编码")
    picking_id: Optional[int] = Field(None, description="调拨单ID")
    move_id: Optional[int] = Field(None, description="移动明细ID")
    product_code: Optional[str] = Field(None, description="产品编码")
    lot_id: Optional[int] = Field(None, description="批次ID")
    lot_name: Optional[str] = Field(None, description="批次号")
    serial_no: Optional[str] = Field(None, description="序列号")
    location_id: Optional[int] = Field(None, description="源库位ID")
    location_dest_id: Optional[int] = Field(None, description="目标库位ID")
    state: Optional[str] = Field(None, description="状态")
    is_done: Optional[bool] = Field(None, description="是否完成")


# ==================== 库存数量模型 Schemas ====================

class StockQuantBase(BaseModel):
    """库存数量基础字段"""
    product_id: Optional[int] = Field(None, description="产品ID")
    product_code: str = Field(..., max_length=100, description="产品编码")
    product_name: str = Field(..., max_length=255, description="产品名称")
    location_id: int = Field(..., description="库位ID")
    location_code: str = Field(..., max_length=100, description="库位编码")
    location_name: str = Field(..., max_length=255, description="库位名称")
    lot_id: Optional[int] = Field(None, description="批次ID")
    lot_name: Optional[str] = Field(None, max_length=100, description="批次号")
    serial_no: Optional[str] = Field(None, max_length=100, description="序列号")
    package_id: Optional[int] = Field(None, description="包裹ID")
    package_code: Optional[str] = Field(None, max_length=100, description="包裹编码")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    owner_code: Optional[str] = Field(None, max_length=100, description="所有者编码")
    quantity: Decimal = Field(default=0, description="库存数量")
    reserved_quantity: Decimal = Field(default=0, ge=0, description="预留数量")
    available_quantity: Decimal = Field(default=0, ge=0, description="可用数量")
    uom_id: Optional[int] = Field(None, description="单位ID")
    uom_code: str = Field(default="unit", max_length=20, description="单位编码")
    uom_name: str = Field(default="件", max_length=50, description="单位名称")
    secondary_uom_id: Optional[int] = Field(None, description="辅助单位ID")
    secondary_uom_name: Optional[str] = Field(None, max_length=50, description="辅助单位名称")
    conversion_factor: Decimal = Field(default=1, description="换算比例")
    inventory_value: Decimal = Field(default=0, description="库存价值")
    cost: Optional[Decimal] = Field(None, description="成本单价")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    in_date: Optional[datetime] = Field(None, description="入库日期")
    expiry_date: Optional[datetime] = Field(None, description="过期日期")
    is_propagated: bool = Field(default=False, description="是否已传播")
    note: Optional[str] = Field(None, description="备注")


class StockQuantCreate(StockQuantBase):
    """创建库存数量"""
    quant_code: Optional[str] = Field(None, max_length=100, description="库存编码（不提供则自动生成）")


class StockQuantUpdate(BaseModel):
    """更新库存数量"""
    product_code: Optional[str] = Field(None, max_length=100, description="产品编码")
    product_name: Optional[str] = Field(None, max_length=255, description="产品名称")
    location_id: Optional[int] = Field(None, description="库位ID")
    location_code: Optional[str] = Field(None, max_length=100, description="库位编码")
    location_name: Optional[str] = Field(None, max_length=255, description="库位名称")
    lot_id: Optional[int] = Field(None, description="批次ID")
    lot_name: Optional[str] = Field(None, max_length=100, description="批次号")
    serial_no: Optional[str] = Field(None, max_length=100, description="序列号")
    package_id: Optional[int] = Field(None, description="包裹ID")
    package_code: Optional[str] = Field(None, max_length=100, description="包裹编码")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    owner_code: Optional[str] = Field(None, max_length=100, description="所有者编码")
    quantity: Optional[Decimal] = Field(None, description="库存数量")
    reserved_quantity: Optional[Decimal] = Field(None, ge=0, description="预留数量")
    available_quantity: Optional[Decimal] = Field(None, ge=0, description="可用数量")
    inventory_value: Optional[Decimal] = Field(None, description="库存价值")
    cost: Optional[Decimal] = Field(None, description="成本单价")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    in_date: Optional[datetime] = Field(None, description="入库日期")
    expiry_date: Optional[datetime] = Field(None, description="过期日期")
    is_propagated: Optional[bool] = Field(None, description="是否已传播")
    note: Optional[str] = Field(None, description="备注")


class StockQuantResponse(StockQuantBase):
    """库存数量响应"""
    id: int = Field(..., description="库存ID")
    quant_code: str = Field(..., max_length=100, description="库存编码")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockQuantQuery(BaseModel):
    """库存数量查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    quant_code: Optional[str] = Field(None, description="库存编码")
    product_code: Optional[str] = Field(None, description="产品编码")
    location_id: Optional[int] = Field(None, description="库位ID")
    location_code: Optional[str] = Field(None, description="库位编码")
    lot_id: Optional[int] = Field(None, description="批次ID")
    lot_name: Optional[str] = Field(None, description="批次号")
    serial_no: Optional[str] = Field(None, description="序列号")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    in_date_start: Optional[datetime] = Field(None, description="入库日期开始")
    in_date_end: Optional[datetime] = Field(None, description="入库日期结束")
    expiry_date_start: Optional[datetime] = Field(None, description="过期日期开始")
    expiry_date_end: Optional[datetime] = Field(None, description="过期日期结束")


# ==================== 库存预留模型 Schemas ====================

class StockQuantReservationBase(BaseModel):
    """库存预留基础字段"""
    quant_id: int = Field(..., description="库存ID")
    quant_code: str = Field(..., max_length=100, description="库存编码")
    move_id: int = Field(..., description="移动明细ID")
    move_code: str = Field(..., max_length=100, description="移动明细编码")
    move_line_id: Optional[int] = Field(None, description="移动明细行ID")
    move_line_code: Optional[str] = Field(None, max_length=100, description="移动明细行编码")
    product_code: str = Field(..., max_length=100, description="产品编码")
    location_id: int = Field(..., description="库位ID")
    location_code: str = Field(..., max_length=100, description="库位编码")
    lot_id: Optional[int] = Field(None, description="批次ID")
    lot_name: Optional[str] = Field(None, max_length=100, description="批次号")
    serial_no: Optional[str] = Field(None, max_length=100, description="序列号")
    quantity: Decimal = Field(..., ge=0, description="预留数量")
    reserved_at: Optional[datetime] = Field(None, description="预留时间")
    released_at: Optional[datetime] = Field(None, description="释放时间")
    state: str = Field(default="reserved", max_length=20, description="状态：reserved/released/consumed")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    note: Optional[str] = Field(None, description="备注")


class StockQuantReservationCreate(StockQuantReservationBase):
    """创建库存预留"""
    reservation_code: Optional[str] = Field(None, max_length=100, description="预留编码（不提供则自动生成）")


class StockQuantReservationResponse(StockQuantReservationBase):
    """库存预留响应"""
    id: int = Field(..., description="预留ID")
    reservation_code: str = Field(..., max_length=100, description="预留编码")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockQuantReservationQuery(BaseModel):
    """库存预留查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    reservation_code: Optional[str] = Field(None, description="预留编码")
    quant_id: Optional[int] = Field(None, description="库存ID")
    move_id: Optional[int] = Field(None, description="移动明细ID")
    move_line_id: Optional[int] = Field(None, description="移动明细行ID")
    product_code: Optional[str] = Field(None, description="产品编码")
    location_id: Optional[int] = Field(None, description="库位ID")
    lot_id: Optional[int] = Field(None, description="批次ID")
    serial_no: Optional[str] = Field(None, description="序列号")
    state: Optional[str] = Field(None, description="状态")
    reserved_at_start: Optional[datetime] = Field(None, description="预留时间开始")
    reserved_at_end: Optional[datetime] = Field(None, description="预留时间结束")


# ==================== 批次模型 Schemas ====================

class StockLotBase(BaseModel):
    """批次基础字段"""
    lot_code: str = Field(..., min_length=1, max_length=100, description="批次编码")
    lot_name: str = Field(..., min_length=1, max_length=255, description="批次名称")
    product_id: Optional[int] = Field(None, description="产品ID")
    product_code: str = Field(..., max_length=100, description="产品编码")
    product_name: str = Field(..., max_length=255, description="产品名称")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    ref: Optional[str] = Field(None, max_length=100, description="参考")
    create_date: Optional[datetime] = Field(None, description="创建日期")
    use_date: Optional[datetime] = Field(None, description="使用日期")
    expiry_date: Optional[datetime] = Field(None, description="过期日期")
    is_active: bool = Field(default=True, description="是否启用")
    note: Optional[str] = Field(None, description="备注")


class StockLotCreate(StockLotBase):
    """创建批次"""
    pass


class StockLotUpdate(BaseModel):
    """更新批次"""
    lot_code: Optional[str] = Field(None, min_length=1, max_length=100, description="批次编码")
    lot_name: Optional[str] = Field(None, min_length=1, max_length=255, description="批次名称")
    product_code: Optional[str] = Field(None, max_length=100, description="产品编码")
    product_name: Optional[str] = Field(None, max_length=255, description="产品名称")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    ref: Optional[str] = Field(None, max_length=100, description="参考")
    create_date: Optional[datetime] = Field(None, description="创建日期")
    use_date: Optional[datetime] = Field(None, description="使用日期")
    expiry_date: Optional[datetime] = Field(None, description="过期日期")
    is_active: Optional[bool] = Field(None, description="是否启用")
    note: Optional[str] = Field(None, description="备注")


class StockLotResponse(StockLotBase):
    """批次响应"""
    id: int = Field(..., description="批次ID")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockLotQuery(BaseModel):
    """批次查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    lot_code: Optional[str] = Field(None, description="批次编码")
    lot_name: Optional[str] = Field(None, description="批次名称")
    product_code: Optional[str] = Field(None, description="产品编码")
    is_active: Optional[bool] = Field(None, description="是否启用")
    expiry_date_start: Optional[datetime] = Field(None, description="过期日期开始")
    expiry_date_end: Optional[datetime] = Field(None, description="过期日期结束")


# ==================== 包裹模型 Schemas ====================

class StockPackageBase(BaseModel):
    """包裹基础字段"""
    package_code: str = Field(..., min_length=1, max_length=100, description="包裹编码")
    package_name: str = Field(..., min_length=1, max_length=255, description="包裹名称")
    package_type: str = Field(default="box", max_length=50, description="包裹类型：box/bag/pallet/container/other")
    location_id: Optional[int] = Field(None, description="当前位置ID")
    location_code: Optional[str] = Field(None, max_length=100, description="当前位置编码")
    location_name: Optional[str] = Field(None, max_length=255, description="当前位置名称")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    owner_code: Optional[str] = Field(None, max_length=100, description="所有者编码")
    parent_id: Optional[int] = Field(None, description="父包裹ID")
    parent_code: Optional[str] = Field(None, max_length=100, description="父包裹编码")
    is_active: bool = Field(default=True, description="是否启用")
    weight: Optional[Decimal] = Field(None, ge=0, description="重量(kg)")
    length: Optional[Decimal] = Field(None, ge=0, description="长度(cm)")
    width: Optional[Decimal] = Field(None, ge=0, description="宽度(cm)")
    height: Optional[Decimal] = Field(None, ge=0, description="高度(cm)")
    note: Optional[str] = Field(None, description="备注")


class StockPackageCreate(StockPackageBase):
    """创建包裹"""
    pass


class StockPackageUpdate(BaseModel):
    """更新包裹"""
    package_code: Optional[str] = Field(None, min_length=1, max_length=100, description="包裹编码")
    package_name: Optional[str] = Field(None, min_length=1, max_length=255, description="包裹名称")
    package_type: Optional[str] = Field(None, max_length=50, description="包裹类型")
    location_id: Optional[int] = Field(None, description="当前位置ID")
    location_code: Optional[str] = Field(None, max_length=100, description="当前位置编码")
    location_name: Optional[str] = Field(None, max_length=255, description="当前位置名称")
    company_code: Optional[str] = Field(None, max_length=100, description="公司编码")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    owner_code: Optional[str] = Field(None, max_length=100, description="所有者编码")
    parent_id: Optional[int] = Field(None, description="父包裹ID")
    parent_code: Optional[str] = Field(None, max_length=100, description="父包裹编码")
    is_active: Optional[bool] = Field(None, description="是否启用")
    weight: Optional[Decimal] = Field(None, ge=0, description="重量(kg)")
    length: Optional[Decimal] = Field(None, ge=0, description="长度(cm)")
    width: Optional[Decimal] = Field(None, ge=0, description="宽度(cm)")
    height: Optional[Decimal] = Field(None, ge=0, description="高度(cm)")
    note: Optional[str] = Field(None, description="备注")


class StockPackageResponse(StockPackageBase):
    """包裹响应"""
    id: int = Field(..., description="包裹ID")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class StockPackageQuery(BaseModel):
    """包裹查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    package_code: Optional[str] = Field(None, description="包裹编码")
    package_name: Optional[str] = Field(None, description="包裹名称")
    package_type: Optional[str] = Field(None, description="包裹类型")
    location_id: Optional[int] = Field(None, description="当前位置ID")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    parent_id: Optional[int] = Field(None, description="父包裹ID")
    is_active: Optional[bool] = Field(None, description="是否启用")


# ==================== 统计汇总 Schemas ====================

class StockQuantSummary(BaseModel):
    """库存汇总统计"""
    product_code: Optional[str] = Field(None, description="产品编码")
    product_name: Optional[str] = Field(None, description="产品名称")
    total_quantity: Decimal = Field(..., description="总数量")
    total_reserved: Decimal = Field(..., description="总预留数量")
    total_available: Decimal = Field(..., description="总可用数量")
    total_value: Decimal = Field(..., description="总价值")
    location_count: int = Field(..., description="库位数量")
    lot_count: int = Field(default=0, description="批次数量")


class InventoryHistory(BaseModel):
    """库存移动历史"""
    product_code: str = Field(..., description="产品编码")
    product_name: str = Field(..., description="产品名称")
    lot_name: Optional[str] = Field(None, description="批次号")
    serial_no: Optional[str] = Field(None, description="序列号")
    move_lines: List[StockMoveLineResponse] = Field(..., description="移动明细行列表")


# ==================== 通用响应格式 ====================

class ListResponse(BaseModel):
    """列表响应格式"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[Any] = Field(..., description="数据列表")


class MessageResponse(BaseModel):
    """消息响应"""
    message: str = Field(..., description="消息内容")
    success: bool = Field(default=True, description="是否成功")


# ==================== 更新模型引用 ====================
# 需要在最后更新这些引用，因为它们在前面的类中使用了字符串引用
StockPickingCreate.model_rebuild()
StockPickingResponse.model_rebuild()
StockMoveCreate.model_rebuild()
StockMoveResponse.model_rebuild()