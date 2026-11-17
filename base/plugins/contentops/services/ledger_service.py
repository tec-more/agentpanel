"""发布台账 + 数据回填服务。"""
import csv
import io
from datetime import datetime
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import PublishLedger, EffectData
from base.plugins.contentops.schemas.content_schema import LedgerCreate, LedgerUpdate, EffectCreate, EffectCSVImport


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class LedgerService:
    """发布台账服务。"""

    @staticmethod
    async def create(data: LedgerCreate, owner: Optional[OwnerContext]):
        ledger = await PublishLedger.create(
            version_id=data.version_id, platform=data.platform,
            planned_at=_parse_dt(data.planned_at), note=data.note, status="pending",
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
        )
        return await ledger.to_dict()

    @staticmethod
    async def get_list(status: Optional[str], owner: Optional[OwnerContext]):
        qs = owned_queryset(PublishLedger, owner) if owner else PublishLedger.all()
        if status:
            qs = qs.filter(status=status)
        rows = await qs.order_by("-created_at")
        return [await r.to_dict() for r in rows]

    @staticmethod
    async def update(ledger_id: int, data: LedgerUpdate, owner: Optional[OwnerContext]):
        ledger = await get_owned_or_404(PublishLedger, ledger_id, owner, for_write=True) if owner else await PublishLedger.get_or_none(id=ledger_id)
        if not ledger:
            raise ValueError("台账记录不存在或无权修改")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "published_at":
                value = _parse_dt(value)
            setattr(ledger, field, value)
        if data.status == "published" and not ledger.published_at:
            ledger.published_at = datetime.now()
        await ledger.save()
        return await ledger.to_dict()

    @staticmethod
    async def add_effect(ledger_id: int, data: EffectCreate, owner: Optional[OwnerContext]):
        ledger = await get_owned_or_404(PublishLedger, ledger_id, owner) if owner else await PublishLedger.get_or_none(id=ledger_id)
        if not ledger:
            raise ValueError("台账记录不存在")
        eff = await EffectData.create(
            ledger_id=ledger_id, views=data.views, likes=data.likes,
            comments=data.comments, favorites=data.favorites, source=data.source,
            stat_date=_parse_dt(data.stat_date).date() if data.stat_date else None,
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
        )
        return await eff.to_dict()

    @staticmethod
    async def import_effect_csv(ledger_id: int, data: EffectCSVImport, owner: Optional[OwnerContext]):
        """CSV 导入效果数据：column_mapping 把第三方列名映射到标准字段。"""
        mapping = data.column_mapping or {}
        reader = csv.DictReader(io.StringIO(data.csv_content))
        created = []
        for row in reader:
            values = {"source": "csv"}
            for std_field in ("views", "likes", "comments", "favorites"):
                col = mapping.get(std_field, std_field)
                raw = row.get(col, "0") or "0"
                try:
                    values[std_field] = int(float(str(raw).replace(",", "")))
                except (ValueError, TypeError):
                    values[std_field] = 0
            eff = await EffectData.create(
                ledger_id=ledger_id,
                owner_type=owner.owner_type if owner else "usr",
                owner_id=owner.owner_id if owner else None,
                **values,
            )
            created.append(await eff.to_dict())
        return {"imported": len(created), "items": created}

    @staticmethod
    async def get_effect(ledger_id: int, owner: Optional[OwnerContext]):
        qs = owned_queryset(EffectData, owner).filter(ledger_id=ledger_id) if owner else EffectData.filter(ledger_id=ledger_id)
        rows = await qs.order_by("-created_at")
        return [await r.to_dict() for r in rows]
