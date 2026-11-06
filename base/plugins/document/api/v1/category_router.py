"""
文档分类管理 API 路由
"""
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.document.services.document_service import CategoryService
    from base.plugins.document.schemas.document_schema import (
        DocumentCategoryCreate,
        DocumentCategoryUpdate,
        DocumentCategoryResponse,
        DocumentCategoryFlatResponse,
        ListResponse,
    )
    from base.common.response import success_response, fail_response
    from base.common.permissions import require_permission
except ImportError:
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

        def put(self, path):
            def decorator(func):
                return func
            return decorator

        def delete(self, path):
            def decorator(func):
                return func
            return decorator

    class CategoryService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def get_all(**kwargs):
            return []
        @staticmethod
        async def get_tree():
            return []
        @staticmethod
        async def create(data):
            return None
        @staticmethod
        async def update(id, data):
            return None
        @staticmethod
        async def delete(id):
            return False
        @staticmethod
        async def sort_update(ids):
            return True

    class DocumentCategoryCreate(BaseModel): pass
    class DocumentCategoryUpdate(BaseModel): pass
    class DocumentCategoryResponse(BaseModel): pass
    class DocumentCategoryFlatResponse(BaseModel): pass
    class ListResponse(BaseModel): pass


category_router = APIRouter(prefix="/categories", tags=["文档分类"])


@category_router.get("/tree", summary="获取分类树")
async def get_category_tree():
    tree = await CategoryService.get_tree()
    return success_response(data=tree)


@category_router.get("", summary="获取分类列表")
async def list_categories(
    page: int = 1,
    page_size: int = 50,
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    user_id: int = require_permission("document:category:list")
):
    items = await CategoryService.get_all(name=name, is_active=is_active)
    return success_response(data={"items": items, "total": len(items), "page": page, "page_size": page_size})


@category_router.get("/{category_id}", summary="获取分类详情")
async def get_category(category_id: int, user_id: int = require_permission("document:category:list")):
    category = await CategoryService.get_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    return success_response(data=category)


@category_router.post("", summary="创建分类")
async def create_category(data: DocumentCategoryCreate, user_id: int = require_permission("document:category:manage")):
    try:
        category = await CategoryService.create(data)
        return success_response(data=category, msg="分类创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@category_router.put("/{category_id}", summary="更新分类")
async def update_category(category_id: int, data: DocumentCategoryUpdate, user_id: int = require_permission("document:category:manage")):
    try:
        category = await CategoryService.update(category_id, data)
        if not category:
            raise HTTPException(status_code=404, detail="分类不存在")
        return success_response(data=category, msg="分类更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@category_router.delete("/{category_id}", summary="删除分类")
async def delete_category(category_id: int, user_id: int = require_permission("document:category:manage")):
    try:
        success = await CategoryService.delete(category_id)
        if not success:
            raise HTTPException(status_code=404, detail="分类不存在")
        return success_response(msg="分类删除成功")
    except ValueError as e:
        return fail_response(msg=str(e))


class SortRequest(BaseModel):
    ids: List[int] = []


@category_router.put("/sort/batch", summary="批量更新分类排序")
async def batch_sort(data: SortRequest, user_id: int = require_permission("document:category:manage")):
    success = await CategoryService.sort_update(data.ids)
    if success:
        return success_response(msg="排序更新成功")
    return fail_response(msg="排序更新失败")
