from typing import Optional
from fastapi import APIRouter, HTTPException, Query

try:
    from base.plugins.inventory.services.inventory_service import PackageService
    from base.plugins.inventory.schemas.inventory_schema import (
        StockPackageCreate, StockPackageUpdate, StockPackageResponse,
        ListResponse, MessageResponse
    )
    from base.common.response import success_response
except ImportError:
    class APIRouter:
        def __init__(self, prefix="", tags=None):
            self.prefix = prefix
            self.tags = tags or []

        def get(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

        def post(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

        def put(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

        def delete(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    class Query:
        def __init__(self, default=None, **kwargs):
            self.default = default

    class PackageService:
        @staticmethod
        async def get_by_id(id): return None
        @staticmethod
        async def create_package(data): return None
        @staticmethod
        async def update_package(id, data): return None
        @staticmethod
        async def delete_package(id): return False
        @staticmethod
        async def get_list(**kwargs): return [], 0

    class StockPackageCreate: pass
    class StockPackageUpdate: pass
    class StockPackageResponse: pass
    class ListResponse: pass
    class MessageResponse: pass


package_router = APIRouter(prefix="/packages", tags=["包裹管理"])


@package_router.get("/{package_id}", summary="获取包裹详情")
async def get_package(package_id: int):
    """根据ID获取包裹详情"""
    package = await PackageService.get_by_id(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="包裹不存在")
    return success_response(data=await package.to_dict())


@package_router.post("", summary="创建包裹")
async def create_package(data: StockPackageCreate):
    """创建新包裹"""
    try:
        package = await PackageService.create_package(data)
        return success_response(data=await package.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@package_router.put("/{package_id}", summary="更新包裹")
async def update_package(package_id: int, data: StockPackageUpdate):
    """更新包裹信息"""
    try:
        package = await PackageService.update_package(package_id, data)
        if not package:
            raise HTTPException(status_code=404, detail="包裹不存在")
        return success_response(data=await package.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@package_router.delete("/{package_id}", summary="删除包裹")
async def delete_package(package_id: int):
    """删除包裹（需无子包裹和库存）"""
    try:
        success = await PackageService.delete_package(package_id)
        if not success:
            raise HTTPException(status_code=404, detail="包裹不存在")
        return success_response(data={"message": "包裹删除成功"}, msg="包裹删除成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@package_router.get("", summary="获取包裹列表")
async def list_packages(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    package_code: Optional[str] = Query(None, description="包裹编码"),
    package_name: Optional[str] = Query(None, description="包裹名称"),
    package_type: Optional[str] = Query(None, description="包裹类型"),
    location_id: Optional[int] = Query(None, description="当前位置ID"),
    owner_id: Optional[int] = Query(None, description="所有者ID"),
    parent_id: Optional[int] = Query(None, description="父包裹ID"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    """获取包裹列表，支持多条件过滤"""
    items, total = await PackageService.get_list(
        page=page, page_size=page_size,
        package_code=package_code, package_name=package_name,
        package_type=package_type, location_id=location_id,
        owner_id=owner_id, parent_id=parent_id, is_active=is_active
    )
    items_dict = [await item.to_dict() for item in items]
    return success_response(data={"items": items_dict, "total": total, "page": page, "page_size": page_size})