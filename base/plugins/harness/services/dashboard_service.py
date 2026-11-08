"""Harness 对账与看板服务

- 用量汇总：session/run 维度，按 source/usage_kind/model 分组，禁止跨来源合并展示
- 预占对账：超期预占释放、终态 run 遗留预占释放、未结算清单
- 异常明细：失败 run、缺失价格、高危拒绝、超期预占
"""
from datetime import datetime
from typing import Any, Dict, List

from tortoise.expressions import Q

from base.common.quota.models.quota import UsageRecord
from base.common.quota.models.reservation import QuotaReservation
from base.common.quota.services.quota_service import QuotaService
from packages.agentpanel_common.gateway.budget import GatewayBudgetService
from base.plugins.harness.models.harness import HarnessAuditEvent, HarnessRun, HarnessSession
from base.plugins.harness.services.reconcile_service import HarnessReconcileService
from base.plugins.harness.services.run_service import TERMINAL_STATUSES


def _now() -> datetime:
    return datetime.now()


class HarnessDashboardService:
    @classmethod
    def _summarize(cls, records: List[Any]) -> Dict[str, Any]:
        total = {
            "records": 0,
            "amount": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "cost": 0.0,
        }
        by_source: Dict[str, Dict[str, float]] = {}
        by_kind: Dict[str, Dict[str, float]] = {}
        by_model: Dict[str, Dict[str, float]] = {}
        by_owner: Dict[str, Dict[str, float]] = {}
        by_gateway: Dict[str, Dict[str, float]] = {}

        for r in records:
            amount = float(r.amount or 0)
            cost = float(r.cost or 0)
            total["records"] += 1
            total["amount"] += amount
            total["tokens_in"] += int(r.tokens_in or 0)
            total["tokens_out"] += int(r.tokens_out or 0)
            total["cache_read_tokens"] += int(r.cache_read_tokens or 0)
            total["cache_write_tokens"] += int(r.cache_write_tokens or 0)
            total["reasoning_tokens"] += int(r.reasoning_tokens or 0)
            total["cost"] += cost

            for bucket, key in (
                (by_source, r.source or "unknown"),
                (by_kind, r.usage_kind or "normal"),
                (by_model, r.model or "unknown"),
                (by_owner, f"{r.owner_type}:{r.owner_id}"),
                (by_gateway, r.gateway_key or "unknown"),
            ):
                item = bucket.setdefault(key, {"amount": 0.0, "cost": 0.0, "records": 0})
                item["amount"] += amount
                item["cost"] += cost
                item["records"] += 1

        total["cost"] = round(total["cost"], 8)
        return {
            "total": total, "by_source": by_source, "by_kind": by_kind,
            "by_model": by_model, "by_owner": by_owner, "by_gateway": by_gateway,
        }

    @classmethod
    async def run_usage(cls, run_no: str) -> Dict[str, Any]:
        run = await HarnessRun.get_or_none(run_no=run_no)
        if run is None:
            return {"error": "run_not_found"}
        # 兼容窗口：历史 harness:{run_id}:，新 orch:{run_no}:，双读不双写
        records = await UsageRecord.filter(
            Q(idem_key__startswith=f"harness:{run.id}:")
            | Q(idem_key__startswith=f"orch:{run.run_no}:")
        ).all()
        data = cls._summarize(records)
        data["run"] = {
            "run_no": run.run_no,
            "session_no": run.session_no,
            "status": run.status,
            "reserved_tokens": run.reserved_tokens,
            "estimated_cost": float(run.estimated_cost or 0),
            "hold_id": run.hold_id,
        }
        reservation = await QuotaReservation.get_or_none(hold_id=run.hold_id) if run.hold_id else None
        data["reservation"] = {
            "hold_id": reservation.hold_id,
            "status": reservation.status,
            "items": reservation.items,
            "used_items": reservation.used_items,
        } if reservation else None
        return data

    @classmethod
    async def session_usage(cls, session_no: str) -> Dict[str, Any]:
        from base.plugins.harness.models.harness import HarnessSession

        session = await HarnessSession.get_or_none(session_no=session_no)
        if session is None:
            return {"error": "session_not_found"}
        records = await UsageRecord.filter(session_ref=session_no).all()
        data = cls._summarize(records)
        runs = await HarnessRun.filter(session_no=session_no).all()
        status_count: Dict[str, int] = {}
        for run in runs:
            status_count[run.status] = status_count.get(run.status, 0) + 1
        data["session"] = {
            "session_no": session.session_no,
            "status": session.status,
            "run_count": len(runs),
            "run_status": status_count,
            "gateway_key": session.gateway_key,
        }
        return data

    @classmethod
    async def usage_overview(
        cls,
        source=None,
        usage_kind=None,
        model=None,
        owner_type=None,
        owner_id=None,
        client_id=None,
        session_no=None,
        date_from=None,
        date_to=None,
    ) -> Dict[str, Any]:
        """全局用量看板：按 source/usage_kind/model/租户/客户端/网关 key 分组。

        不同 source 的数值只分组展示、不做跨来源合并。
        """
        query = UsageRecord.all()
        if source:
            query = query.filter(source=source)
        if usage_kind:
            query = query.filter(usage_kind=usage_kind)
        if model:
            query = query.filter(model=model)
        if owner_type:
            query = query.filter(owner_type=owner_type)
        if owner_id is not None:
            query = query.filter(owner_id=owner_id)
        if session_no:
            query = query.filter(session_ref=session_no)
        if client_id:
            session_nos = await HarnessSession.filter(client_id=client_id).values_list(
                "session_no", flat=True
            )
            query = query.filter(session_ref__in=list(session_nos))
        if date_from:
            query = query.filter(created_at__gte=date_from)
        if date_to:
            query = query.filter(created_at__lte=date_to)

        records = await query.all()
        data = cls._summarize(records)

        refs = {r.session_ref for r in records if r.session_ref}
        client_map: Dict[str, str] = {}
        if refs:
            rows = await HarnessSession.filter(session_no__in=list(refs)).values("session_no", "client_id")
            client_map = {row["session_no"]: row["client_id"] for row in rows}

        by_client: Dict[str, Dict[str, float]] = {}
        for r in records:
            key = client_map.get(r.session_ref, "unknown")
            item = by_client.setdefault(key, {"amount": 0.0, "cost": 0.0, "records": 0})
            item["amount"] += float(r.amount or 0)
            item["cost"] += float(r.cost or 0)
            item["records"] += 1
        data["by_client"] = by_client
        return data

    @classmethod
    async def reconcile(
        cls,
        release_expired: bool = True,
        release_terminal_runs: bool = True,
    ) -> Dict[str, Any]:
        now = _now()
        released: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        expired = await QuotaReservation.filter(
            status__in=["active", "partial"], expire_at__lte=now,
            source__in=["harness", "client"],
        ).all()
        for res in expired:
            if not release_expired:
                break
            ok = await QuotaService.quota_release(res.hold_id)
            target = released if ok else failed
            target.append({"hold_id": res.hold_id, "ref_id": res.ref_id, "reason": "expired"})

        terminal_runs = await HarnessRun.filter(
            status__in=list(TERMINAL_STATUSES), hold_id__isnull=False,
        ).all()
        for run in terminal_runs:
            if not run.hold_id:
                continue
            reservation = await QuotaReservation.get_or_none(hold_id=run.hold_id)
            if reservation is None or reservation.status not in ("active", "partial"):
                continue
            if not release_terminal_runs:
                continue
            ok = await QuotaService.quota_release(run.hold_id)
            target = released if ok else failed
            target.append({
                "hold_id": run.hold_id,
                "ref_id": run.run_no,
                "reason": "terminal_run_leftover",
            })

        active_count = await QuotaReservation.filter(
            status__in=["active", "partial"], source__in=["harness", "client"],
        ).count()
        return {
            "released": released,
            "failed": failed,
            "released_count": len(released),
            "failed_count": len(failed),
            "remaining_unsettled": active_count,
        }

    @classmethod
    async def anomalies(cls, limit: int = 20) -> Dict[str, Any]:
        now = _now()
        expired_reservations = await QuotaReservation.filter(
            status__in=["active", "partial"], expire_at__lte=now,
            source__in=["harness", "client"],
        ).limit(limit).all()
        failed_runs = await HarnessRun.filter(
            status__in=["failed", "timeout", "cancelled"],
        ).order_by("-created_at").limit(limit).all()
        missing_price = await UsageRecord.filter(
            price_snapshot__isnull=True, source__not="legacy",
        ).order_by("-created_at").limit(limit).all()
        denied_events = await HarnessAuditEvent.filter(
            decision="deny", risk_level__in=["high", "critical"],
        ).order_by("-created_at").limit(limit).all()

        return {
            "expired_reservations": [
                {
                    "hold_id": r.hold_id, "ref_id": r.ref_id, "items": r.items,
                    "expire_at": r.expire_at.isoformat() if r.expire_at else None,
                } for r in expired_reservations
            ],
            "failed_runs": [
                {
                    "run_no": r.run_no, "status": r.status,
                    "error_code": r.error_code, "error_message": r.error_message,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                } for r in failed_runs
            ],
            "usage_missing_price": [
                {
                    "id": r.id, "run_ref": r.session_ref, "model": r.model,
                    "source": r.source, "amount": float(r.amount or 0),
                } for r in missing_price
            ],
            "high_risk_denied": [
                {
                    "event_no": e.event_no, "action": e.action, "run_no": e.run_no,
                    "call_id": e.call_id, "policy_code": e.policy_code,
                } for e in denied_events
            ],
            "gateway_reconcile": await HarnessReconcileService.summary(limit=limit),
            "gateway_quota": await GatewayBudgetService.summary(limit=limit),
        }
