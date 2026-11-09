"""模型价格与成本计算服务

口径：
- 计费输入 = inputTokens + cacheReadTokens + cacheWriteTokens（互不重叠）
- outputTokens 单独计；reasoningTokens 默认已包含在 output 内
- 返回价格快照，随 usage_record/step 一起落库，便于对账与价格版本追溯
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

from packages.common.models.model_price import ModelPrice


def _as_instant(value: Optional[datetime]) -> Optional[datetime]:
    """把时间统一成带时区的绝对时刻。

    DB 字段是 timestamptz，Tortoise（use_tz=True + timezone=Asia/Shanghai）读出来
    是带 +08:00 的 aware datetime；容器进程本地时区通常是 UTC，`datetime.now()`
    是 naive UTC。直接 strip tzinfo 比较会得到“生效时间在未来”的错误结论，
    导致 L3 容器内价格解析永远 missing_price。
    """
    if value is None:
        return None
    if value.tzinfo is None:
        # naive 值一律视为进程本地时间（与 `datetime.now()` 语义一致）
        return value.astimezone()
    return value


def _d(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _money(value: Decimal, places: int = 8) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


class ModelPriceService:
    @classmethod
    async def resolve(
        cls, provider: Optional[str], model: Optional[str], at: Optional[datetime] = None
    ) -> Optional[ModelPrice]:
        if not model:
            return None
        now = _as_instant(at) or datetime.now().astimezone()
        query = ModelPrice.filter(model=model, status="active")
        if provider:
            query = query.filter(provider=provider)
        rows = await query.order_by("-effective_from", "-id").all()
        for row in rows:
            start = _as_instant(row.effective_from)
            end = _as_instant(row.effective_to)
            if start and start > now:
                continue
            if end and end <= now:
                continue
            return row
        return None

    @classmethod
    async def estimate_cost(
        cls,
        provider: Optional[str],
        model: Optional[str],
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        rounding_places: int = 8,
    ) -> Dict[str, Any]:
        price = await cls.resolve(provider, model)
        if price is None:
            return {
                "cost": 0.0,
                "currency": "CNY",
                "price_snapshot": None,
                "missing_price": True,
                "unrounded_cost": "0",
            }

        in_price = _d(price.input_price_per_1k)
        out_price = _d(price.output_price_per_1k)
        cache_read_price = _d(price.cache_read_price_per_1k) or in_price
        cache_write_price = _d(price.cache_write_price_per_1k) or in_price

        billed_input = int(input_tokens or 0) + int(cache_read_tokens or 0) + int(cache_write_tokens or 0)
        unrounded = (
            _d(billed_input) * in_price
            + _d(cache_read_tokens) * (cache_read_price - in_price)
            + _d(cache_write_tokens) * (cache_write_price - in_price)
            + _d(output_tokens) * out_price
        ) / Decimal("1000")
        cost = _money(unrounded, rounding_places)

        return {
            "cost": float(cost),
            "unrounded_cost": format(unrounded, "f"),
            "currency": price.currency,
            "price_snapshot": {
                "provider": price.provider,
                "model": price.model,
                "price_version": price.price_version,
                "currency": price.currency,
                "input_price_per_1k": float(in_price),
                "output_price_per_1k": float(out_price),
                "cache_read_price_per_1k": float(cache_read_price),
                "cache_write_price_per_1k": float(cache_write_price),
                "billed_input_tokens": billed_input,
            },
            "missing_price": False,
        }
