from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

tax_declaration_router = APIRouter(prefix="/tax-declarations", tags=["税务申报"])


@tax_declaration_router.get("/", summary="获取税务申报列表")
async def get_tax_declarations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    period: Optional[str] = Query(None, description="期间"),
    tax_type: Optional[str] = Query(None, description="税种"),
    status: Optional[str] = Query(None, description="状态")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@tax_declaration_router.post("/", summary="创建税务申报")
async def create_tax_declaration(
    period: str = Query(..., description="期间"),
    tax_type: str = Query(..., description="税种")
):
    return SuccessResponse(data={"id": 1}, msg="申报创建成功")


@tax_declaration_router.post("/{declaration_id}/declare", summary="执行申报")
async def declare_tax(declaration_id: int):
    return SuccessResponse(msg="申报成功")


@tax_declaration_router.post("/{declaration_id}/pay", summary="缴税")
async def pay_tax(declaration_id: int):
    return SuccessResponse(msg="缴税成功")