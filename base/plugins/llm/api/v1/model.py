"""
大模型管理API
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from base.common.response import SuccessResponse, ErrorResponse
from base.common.security import get_current_user_id
from base.plugins.llm.models.model import LLMModel

# 导入管理员权限验证
try:
    from base.plugins.llm.utils.auth import check_admin_permission
except ImportError:
    from fastapi import Depends
    async def check_admin_permission():
        return 1
from base.plugins.llm.models.provider import LLMProvider
from base.plugins.llm.schemas.llm import (
    ModelCreate,
    ModelUpdate,
    ModelResponse
)

model_router = APIRouter(
    prefix="/models",
    tags=["大模型管理"],
    dependencies=[Depends(get_current_user_id)]
)


@model_router.get("", summary="获取大模型列表")
async def get_models(
    provider_id: Optional[int] = Query(None, description="厂商ID筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(1000, ge=1, le=20000, description="每页数量")
):
    """获取大模型列表"""
    query = LLMModel.all()

    if provider_id:
        query = query.filter(provider_id=provider_id)
    if status:
        query = query.filter(status=status)

    total = await query.count()
    
    # 如果 page_size >= 1000，返回所有记录（不分页）
    if page_size >= 1000:
        models = await query.prefetch_related('provider')
    else:
        models = await query.offset((page - 1) * page_size).limit(page_size).prefetch_related('provider')

    # 转换为响应格式
    result = []
    for model in models:
        result.append({
            "id": model.id,
            "provider_id": model.provider_id,
            "provider_name": model.provider.name if model.provider else None,
            "model_id": model.model_id,
            "model_name": model.model_name,
            "endpoint_url": model.endpoint_url,
            "context_length": model.context_length,
            "input_price": float(model.input_price),
            "output_price": float(model.output_price),
            "supports_streaming": model.supports_streaming,
            "supports_vision": model.supports_vision,
            "supports_function": model.supports_function,
            "status": model.status,
            "description": model.description,
            "is_free": model.is_free,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        })

    return SuccessResponse(data={
        "items": result,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@model_router.get("/{model_id}", summary="获取大模型详情")
async def get_model(model_id: int):
    """获取大模型详情"""
    model = await LLMModel.get_or_none(id=model_id).prefetch_related('provider')
    if not model:
        raise HTTPException(status_code=404, detail="大模型不存在")

    return SuccessResponse(data={
        "id": model.id,
        "provider_id": model.provider_id,
        "provider": {
            "id": model.provider.id,
            "name": model.provider.name,
            "name_en": model.provider.name_en,
            "logo_url": model.provider.logo_url
        } if model.provider else None,
        "model_id": model.model_id,
        "model_name": model.model_name,
        "endpoint_url": model.endpoint_url,
        "context_length": model.context_length,
        "input_price": float(model.input_price),
        "output_price": float(model.output_price),
        "supports_streaming": model.supports_streaming,
        "supports_vision": model.supports_vision,
        "supports_function": model.supports_function,
        "status": model.status,
        "description": model.description,
        "is_free": model.is_free,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None
    })


@model_router.post("", summary="创建大模型")
async def create_model(
    data: ModelCreate,
    user_id: int = Depends(check_admin_permission)
):
    """创建大模型"""
    # 检查厂商是否存在
    provider = await LLMProvider.get_or_none(id=data.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="厂商不存在")

    # 检查同一厂商下模型标识是否重复
    existing = await LLMModel.get_or_none(
        provider_id=data.provider_id,
        model_id=data.model_id
    )
    if existing:
        raise HTTPException(status_code=400, detail="该厂商下已存在此模型标识")

    model = await LLMModel.create(**data.model_dump())

    return SuccessResponse(data={
        "id": model.id,
        "model_id": model.model_id,
        "model_name": model.model_name,
        "provider_name": provider.name
    }, msg="大模型创建成功")


@model_router.put("/{model_id}", summary="更新大模型")
async def update_model(
    model_id: int,
    data: ModelUpdate,
    user_id: int = Depends(check_admin_permission)
):
    """更新大模型"""
    model = await LLMModel.get_or_none(id=model_id)
    if not model:
        raise HTTPException(status_code=404, detail="大模型不存在")

    # 如果更新provider_id，检查新厂商是否存在
    if data.provider_id is not None:
        provider = await LLMProvider.get_or_none(id=data.provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="厂商不存在")

    # 如果更新model_id，检查是否重复
    update_data = data.model_dump(exclude_unset=True)
    if 'model_id' in update_data:
        provider_id = update_data.get('provider_id', model.provider_id)
        existing = await LLMModel.get_or_none(
            provider_id=provider_id,
            model_id=update_data['model_id']
        )
        if existing and existing.id != model_id:
            raise HTTPException(status_code=400, detail="该厂商下已存在此模型标识")

    # 只更新提供的字段
    for key, value in update_data.items():
        setattr(model, key, value)

    await model.save()

    return SuccessResponse(data={
        "id": model.id,
        "model_id": model.model_id,
        "model_name": model.model_name
    }, msg="大模型更新成功")


@model_router.delete("/{model_id}", summary="删除大模型")
async def delete_model(
    model_id: int,
    user_id: int = Depends(check_admin_permission)
):
    """删除大模型"""
    model = await LLMModel.get_or_none(id=model_id)
    if not model:
        raise HTTPException(status_code=404, detail="大模型不存在")

    await model.delete()

    return SuccessResponse(msg="大模型删除成功")
