"""
API密钥管理API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime

from base.common.response import SuccessResponse, ErrorResponse
from base.common.security import get_current_user_id
from base.plugins.llm.models.api_key import LLMApiKey
from base.plugins.llm.models.enums import CallMode

# 导入管理员权限验证
try:
    from base.plugins.llm.utils.auth import check_admin_permission
except ImportError:
    from fastapi import Depends
    async def check_admin_permission():
        return 1
from base.plugins.llm.models.provider import LLMProvider
from base.plugins.llm.schemas.llm import (
    ApiKeyCreate,
    ApiKeyUpdate,
    ApiKeyResponse
)

api_key_router = APIRouter(
    prefix="/api-keys",
    tags=["API密钥管理"],
    dependencies=[Depends(get_current_user_id)]
)


def mask_secret(secret: str) -> str:
    """遮蔽密钥显示"""
    if not secret or len(secret) < 8:
        return "****"
    return secret[:4] + "****" + secret[-4:]


@api_key_router.get("", summary="获取API密钥列表")
async def get_api_keys(
    provider_id: Optional[int] = Query(None, description="厂商ID筛选"),
    model_id: Optional[int] = Query(None, description="模型ID筛选"),
    model_service_type: Optional[str] = Query(None, description="服务类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量")
):
    """获取API密钥列表"""
    query = LLMApiKey.all()
    
    if provider_id:
        query = query.filter(provider_id=provider_id)
    if model_id:
        query = query.filter(model_id=model_id)
    if model_service_type:
        query = query.filter(model_service_type=model_service_type)
    if status:
        query = query.filter(status=status)

    total = await query.count()
    api_keys = await query.offset((page - 1) * page_size).limit(page_size).prefetch_related('provider', 'model')

    from base.plugins.llm.models.enums import ModelServiceType
    
    result = []
    for key in api_keys:
        service_type_display = ModelServiceType.display_name(key.model_service_type)
        call_mode_display = CallMode.display_name(key.call_mode)
        
        model_info = None
        if key.model:
            model_info = {
                "id": key.model.id,
                "model_id": key.model.model_id,
                "model_name": key.model.model_name
            }
        
        record = {
            "id": key.id,
            "provider_id": key.provider_id,
            "provider_name": key.provider.name if key.provider else None,
            "model_id": key.model_id,
            "model": model_info,
            "model_service_type": key.model_service_type,
            "model_service_type_display": service_type_display,
            "call_mode": key.call_mode,
            "call_mode_display": call_mode_display,
            "api_id": key.api_id,
            "api_key": mask_secret(key.api_key) if key.api_key else None,
            "api_secret": mask_secret(key.api_secret) if key.api_secret else None,
            "access_token": key.access_token,
            "endpoint_url": key.endpoint_url,
            "is_voice_service": key.is_voice_service,
            "is_openapi_mode": hasattr(key, 'is_openapi_mode') and key.is_openapi_mode,
            "max_quota": key.max_quota,
            "used_quota": key.used_quota,
            "remaining_quota": key.remaining_quota,
            "is_available": key.is_available,
            "status": key.status,
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "description": key.description,
            "created_at": key.created_at.isoformat() if key.created_at else None,
            "updated_at": key.updated_at.isoformat() if key.updated_at else None
        }
        result.append(record)

    return SuccessResponse(data={
        "items": result,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@api_key_router.get("/{key_id}", summary="获取API密钥详情")
async def get_api_key(key_id: int):
    """获取API密钥详情"""
    key = await LLMApiKey.get_or_none(id=key_id).prefetch_related('provider', 'model')
    if not key:
        raise HTTPException(status_code=404, detail="API密钥不存在")

    from base.plugins.llm.models.enums import ModelServiceType
    service_type_display = ModelServiceType.display_name(key.model_service_type)
    call_mode_display = CallMode.display_name(key.call_mode)
    
    model_info = None
    if key.model:
        model_info = {
            "id": key.model.id,
            "model_id": key.model.model_id,
            "model_name": key.model.model_name,
            "provider": {
                "id": key.model.provider.id,
                "name": key.model.provider.name,
                "name_en": key.model.provider.name_en,
                "logo_url": key.model.provider.logo_url
            } if key.model.provider else None
        }

    return SuccessResponse(data={
        "id": key.id,
        "provider_id": key.provider_id,
        "provider": {
            "id": key.provider.id,
            "name": key.provider.name,
            "name_en": key.provider.name_en,
            "logo_url": key.provider.logo_url
        } if key.provider else None,
        "model_id": key.model_id,
        "model": model_info,
        "model_service_type": key.model_service_type,
        "model_service_type_display": service_type_display,
        "call_mode": key.call_mode,
        "call_mode_display": call_mode_display,
        "api_id": key.api_id,
        "api_key": mask_secret(key.api_key) if key.api_key else None,
        "api_secret": mask_secret(key.api_secret) if key.api_secret else None,
        "access_token": key.access_token,
        "endpoint_url": key.endpoint_url,
        "is_voice_service": key.is_voice_service,
        "is_openapi_mode": key.is_openapi_mode,
        "max_quota": key.max_quota,
        "used_quota": key.used_quota,
        "remaining_quota": key.remaining_quota,
        "is_available": key.is_available,
        "status": key.status,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "quota_reset_date": key.quota_reset_date.isoformat() if key.quota_reset_date else None,
        "description": key.description,
        "created_at": key.created_at.isoformat() if key.created_at else None,
        "updated_at": key.updated_at.isoformat() if key.updated_at else None
    })


@api_key_router.post("", summary="创建API密钥")
async def create_api_key(
    data: ApiKeyCreate,
    user_id: int = Depends(check_admin_permission)
):
    """创建API密钥"""
    provider = await LLMProvider.get_or_none(id=data.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="厂商不存在")

    api_key = await LLMApiKey.create(
        provider_id=data.provider_id,
        model_id=data.model_id,
        model_service_type=data.model_service_type,
        call_mode=data.call_mode,
        api_id=data.api_id,
        api_key=data.api_key,
        api_secret=data.api_secret,
        access_token=data.access_token,
        endpoint_url=data.endpoint_url,
        max_quota=data.max_quota,
        description=data.description
    )

    from base.plugins.llm.models.enums import ModelServiceType
    service_type_display = ModelServiceType.display_name(api_key.model_service_type)
    call_mode_display = CallMode.display_name(api_key.call_mode)

    return SuccessResponse(data={
        "id": api_key.id,
        "model_service_type": api_key.model_service_type,
        "model_service_type_display": service_type_display,
        "call_mode": api_key.call_mode,
        "call_mode_display": call_mode_display,
        "api_id": api_key.api_id,
        "api_key": mask_secret(api_key.api_key) if api_key.api_key else None,
        "api_secret": mask_secret(api_key.api_secret) if api_key.api_secret else None,
        "access_token": api_key.access_token,
        "endpoint_url": api_key.endpoint_url,
        "provider_name": provider.name,
        "is_voice_service": api_key.is_voice_service
    }, msg="API密钥创建成功")


@api_key_router.put("/{key_id}", summary="更新API密钥")
async def update_api_key(
    key_id: int,
    data: ApiKeyUpdate,
    user_id: int = Depends(check_admin_permission)
):
    """更新API密钥"""
    key = await LLMApiKey.get_or_none(id=key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API密钥不存在")

    if data.provider_id is not None:
        provider = await LLMProvider.get_or_none(id=data.provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="厂商不存在")

    update_data = data.model_dump(exclude_unset=True)
    
    # 处理空字符串转换为None
    for field_name, value in list(update_data.items()):
        if value == '':
            update_data[field_name] = None

    # 使用 update_fields 来明确指定要更新的字段，确保 Tortoise ORM 正确更新
    update_fields = []
    for field_name, value in update_data.items():
        setattr(key, field_name, value)
        update_fields.append(field_name)

    # 明确保存，指定要更新的字段
    await key.save(update_fields=update_fields)

    from base.plugins.llm.models.enums import ModelServiceType
    service_type_display = ModelServiceType.display_name(key.model_service_type)
    call_mode_display = CallMode.display_name(key.call_mode)

    return SuccessResponse(data={
        "id": key.id,
        "model_service_type": key.model_service_type,
        "model_service_type_display": service_type_display,
        "call_mode": key.call_mode,
        "call_mode_display": call_mode_display,
        "api_id": key.api_id,
        "api_key": mask_secret(key.api_key) if key.api_key else None,
        "api_secret": mask_secret(key.api_secret) if key.api_secret else None,
        "access_token": key.access_token,
        "endpoint_url": key.endpoint_url,
        "is_voice_service": key.is_voice_service,
        "description": key.description
    }, msg="API密钥更新成功")


@api_key_router.delete("/{key_id}", summary="删除API密钥")
async def delete_api_key(
    key_id: int,
    user_id: int = Depends(check_admin_permission)
):
    """删除API密钥"""
    key = await LLMApiKey.get_or_none(id=key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API密钥不存在")

    await key.delete()
    return SuccessResponse(msg="API密钥删除成功")


@api_key_router.post("/{key_id}/reset-quota", summary="重置配额")
async def reset_quota(
    key_id: int,
    user_id: int = Depends(check_admin_permission)
):
    """重置API密钥配额"""
    key = await LLMApiKey.get_or_none(id=key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API密钥不存在")

    await key.reset_quota_if_needed()
    return SuccessResponse(data={
        "used_quota": key.used_quota,
        "remaining_quota": key.remaining_quota
    }, msg="配额重置成功")


@api_key_router.get("/{key_id}/test", summary="测试API密钥")
async def test_api_key(
    key_id: int,
    user_id: int = Depends(check_admin_permission)
):
    """测试API密钥是否可用"""
    key = await LLMApiKey.get_or_none(id=key_id).prefetch_related('provider')
    if not key:
        raise HTTPException(status_code=404, detail="API密钥不存在")

    if not key.is_available:
        reason = []
        if key.status != "active":
            reason.append("状态未激活")
        if key.expires_at and key.expires_at < datetime.now():
            reason.append("已过期")
        if key.max_quota > 0 and key.used_quota >= key.max_quota:
            reason.append("配额已用尽")

        return SuccessResponse(data={
            "available": False,
            "reason": ", ".join(reason),
            "remaining_quota": key.remaining_quota
        })

    return SuccessResponse(data={
        "available": True,
        "remaining_quota": key.remaining_quota,
        "message": "API密钥可用"
    })
