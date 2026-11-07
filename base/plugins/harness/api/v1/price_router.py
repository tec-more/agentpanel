"""模型价格管理（管理员）"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from base.common.permissions import require_superuser
from base.common.response import success_response, fail_response
from base.plugins.harness.models.model_price import ModelPrice
from base.plugins.harness.schemas.harness import PriceCreate

price_router = APIRouter(prefix="/model-prices", tags=["Harness-模型价格"])


def _price_dict(row: ModelPrice) -> dict:
    return {
        "id": row.id,
        "provider": row.provider,
        "model": row.model,
        "currency": row.currency,
        "input_price_per_1k": float(row.input_price_per_1k or 0),
        "output_price_per_1k": float(row.output_price_per_1k or 0),
        "cache_read_price_per_1k": float(row.cache_read_price_per_1k or 0),
        "cache_write_price_per_1k": float(row.cache_write_price_per_1k or 0),
        "price_version": row.price_version,
        "source": row.source,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "status": row.status,
        "description": row.description,
    }


@price_router.post("", summary="新增/更新模型价格版本")
async def create_price(payload: PriceCreate, admin_id: int = require_superuser()):
    existing = await ModelPrice.get_or_none(
        provider=payload.provider, model=payload.model, price_version=payload.price_version
    )
    if existing is not None:
        return fail_response(msg="该价格版本已存在", code=409, status_code=409)

    data = payload.model_dump()
    data["effective_from"] = datetime.fromisoformat(data["effective_from"]) if data.get("effective_from") else None
    data["effective_to"] = datetime.fromisoformat(data["effective_to"]) if data.get("effective_to") else None
    price = await ModelPrice.create(**data)
    return success_response(data=_price_dict(price), msg="价格已创建")


@price_router.get("", summary="模型价格列表")
async def list_prices(
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    status_filter: str = Query("active", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    query = ModelPrice.all()
    if provider:
        query = query.filter(provider=provider)
    if model:
        query = query.filter(model=model)
    if status_filter and status_filter != "all":
        query = query.filter(status=status_filter)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("provider", "model", "-effective_from")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_price_dict(r) for r in rows],
    })


@price_router.post("/{price_id}/disable", summary="停用价格版本")
async def disable_price(price_id: int, admin_id: int = require_superuser()):
    price = await ModelPrice.get_or_none(id=price_id)
    if price is None:
        return fail_response(msg="价格版本不存在", code=404, status_code=404)
    price.status = "disabled"
    await price.save()
    return success_response(msg="已停用")
