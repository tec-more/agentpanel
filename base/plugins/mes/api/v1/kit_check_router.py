from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.mes.services.kit_check_service import KitCheckService
    from base.common.response import SuccessResponse, ErrorResponse
    KIT_CHECK_AVAILABLE = True
except ImportError:
    KitCheckService = None
    KIT_CHECK_AVAILABLE = False

    class BaseModel:
        pass

    class APIRouter:
        def __init__(self, prefix="", tags=None):
            self.prefix = prefix
            self.tags = tags or []

        def get(self, path):
            def decorator(func):
                return func
            return decorator

        def post(self, path):
            def decorator(func):
                return func
            return decorator

    class Query:
        def __init__(self, default=None, description=None):
            self.default = default
            self.description = description

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            pass

    class SuccessResponse:
        def __init__(self, data=None, msg=None):
            pass

    class ErrorResponse:
        def __init__(self, msg=None, status_code=None):
            pass

    class KitCheckService:
        @staticmethod
        async def check_kit_by_mo(mo_id):
            return {"error": "KitCheckService not available"}

        @staticmethod
        async def check_kit_by_bom(product_code, quantity):
            return {"error": "KitCheckService not available"}

        @staticmethod
        async def get_shortage_list(mo_id):
            return []

        @staticmethod
        async def get_kit_status_by_mo(mo_code):
            return "unknown"

        @staticmethod
        async def batch_check_kit(mo_ids):
            return []


kit_check_router = APIRouter(prefix="/mes/kit-check", tags=["齐套检查"])


class BatchKitCheckRequest(BaseModel):
    mo_ids: List[int]


@kit_check_router.get("/{mo_id}", summary="检查制造订单齐套情况")
async def check_kit_by_mo(mo_id: int):
    if not KIT_CHECK_AVAILABLE or KitCheckService is None:
        return ErrorResponse(msg="齐套检查服务不可用", status_code=503)

    try:
        result = await KitCheckService.check_kit_by_mo(mo_id)
        if "error" in result:
            return ErrorResponse(msg=result["error"], status_code=404)
        return SuccessResponse(data=result, msg="齐套检查成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=400)


@kit_check_router.get("/bom/{product_code}", summary="检查BOM齐套情况")
async def check_kit_by_bom(
    product_code: str,
    quantity: int = Query(1, description="生产数量")
):
    if not KIT_CHECK_AVAILABLE or KitCheckService is None:
        return ErrorResponse(msg="齐套检查服务不可用", status_code=503)

    try:
        result = await KitCheckService.check_kit_by_bom(product_code, quantity)
        if "msg" in result and result["msg"]:
            return ErrorResponse(msg=result["msg"], status_code=400)
        return SuccessResponse(data=result, msg="BOM齐套检查成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=400)


@kit_check_router.get("/{mo_id}/shortage", summary="获取制造订单缺料清单")
async def get_shortage_list(mo_id: int):
    if not KIT_CHECK_AVAILABLE or KitCheckService is None:
        return ErrorResponse(msg="齐套检查服务不可用", status_code=503)

    try:
        shortage_list = await KitCheckService.get_shortage_list(mo_id)
        return SuccessResponse(data={"shortage_list": shortage_list}, msg="缺料清单获取成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=400)


@kit_check_router.get("/status/{mo_code}", summary="获取制造订单齐套状态")
async def get_kit_status_by_mo(mo_code: str):
    if not KIT_CHECK_AVAILABLE or KitCheckService is None:
        return ErrorResponse(msg="齐套检查服务不可用", status_code=503)

    try:
        status = await KitCheckService.get_kit_status_by_mo(mo_code)
        status_desc = {
            "full_kit": "完全齐套",
            "partial_kit": "部分齐套",
            "no_kit": "不齐套",
            "unknown": "未知"
        }
        return SuccessResponse(data={
            "mo_code": mo_code,
            "kit_status": status,
            "kit_status_desc": status_desc.get(status, "未知")
        }, msg="齐套状态获取成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=400)


@kit_check_router.post("/batch", summary="批量检查制造订单齐套情况")
async def batch_check_kit(request: BatchKitCheckRequest):
    if not KIT_CHECK_AVAILABLE or KitCheckService is None:
        return ErrorResponse(msg="齐套检查服务不可用", status_code=503)

    try:
        results = await KitCheckService.batch_check_kit(request.mo_ids)
        return SuccessResponse(data=results, msg="批量齐套检查成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=400)