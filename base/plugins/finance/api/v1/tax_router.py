from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

tax_router = APIRouter(prefix="/tax", tags=["税务管理"])


@tax_router.get("/invoices", summary="获取发票列表")
async def get_tax_invoices(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    is_input: bool = Query(True, description="是否进项"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    supplier_id: Optional[int] = Query(None, description="供应商ID"),
    invoice_type: Optional[str] = Query(None, description="发票类型"),
    status: Optional[str] = Query(None, description="状态")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@tax_router.post("/invoices", summary="创建发票")
async def create_tax_invoice():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@tax_router.post("/invoices/{tax_id}/verify", summary="认证进项发票")
async def verify_tax_invoice(tax_id: int):
    return SuccessResponse(msg="认证成功")


@tax_router.get("/out", summary="获取销项发票列表")
async def get_tax_out(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    period: Optional[str] = Query(None, description="期间")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@tax_router.post("/out", summary="开具销项发票")
async def create_tax_out():
    return SuccessResponse(data={"id": 1}, msg="开具成功")


@tax_router.get("/in", summary="获取进项发票列表")
async def get_tax_in(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    supplier_id: Optional[int] = Query(None, description="供应商ID"),
    period: Optional[str] = Query(None, description="期间")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@tax_router.post("/in", summary="录入进项发票")
async def create_tax_in():
    return SuccessResponse(data={"id": 1}, msg="录入成功")


@tax_router.post("/in/{tax_id}/verify", summary="认证进项发票")
async def verify_tax_in(tax_id: int):
    return SuccessResponse(msg="认证成功")