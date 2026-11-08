"""Harness 网关记账与客户端上报对账服务

口径：
- 权威侧：usage_record(source=gateway, idem_key LIKE 'gw:%', gateway_key=<lease_id>)；
- 佐证侧：usage_record(idem_key LIKE 'harness:%')（不参与金额合并）；
- 通过租约 run_no / 客户端 idem_key 中的 run_id 对齐到 run 级；
- 对不齐的记录进入 unmatched_* 清单，不强行配对。
"""
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from tortoise.expressions import Q

from base.plugins.harness.services.gateway_config import reconciliation_config
from base.common.quota.models.quota import UsageRecord
from base.plugins.harness.models.harness import (
    HarnessGatewayLease,
    HarnessReconcileBatch,
    HarnessReconcileDiff,
    HarnessRun,
)

SAMPLE_LIMIT = 50


def _now() -> datetime:
    return datetime.now()


def _new_batch_no(now: datetime) -> str:
    return f"urc{now.strftime('%Y%m%d%H%M%S')}{random.randint(0, 9999):04d}"


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _side() -> Dict[str, Any]:
    return {
        "count": 0,
        "amount": 0.0,
        "cost": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "records": [],
    }


def _add_side(side: Dict[str, Any], record: UsageRecord) -> None:
    amount = _f(record.amount)
    side["count"] += 1
    side["amount"] += amount
    side["cost"] += _f(record.cost)
    side["tokens_in"] += int(record.tokens_in or 0)
    side["tokens_out"] += int(record.tokens_out or 0)
    if len(side["records"]) < SAMPLE_LIMIT:
        side["records"].append({
            "id": record.id,
            "idem_key": record.idem_key,
            "resource_type": record.resource_type,
            "amount": amount,
            "cost": _f(record.cost),
            "tokens_in": int(record.tokens_in or 0),
            "tokens_out": int(record.tokens_out or 0),
            "created_at": _iso(record.created_at),
        })


def _client_run_ref(record: UsageRecord) -> Tuple[Optional[int], Optional[str]]:
    """客户端上报幂等键 → (run_id, run_no)。

    兼容窗口：历史 harness:{run_id}:{node}:{seq} 与 P1.3 起的 orch:{run_no}:{node}:{seq} 双读。
    """
    idem = record.idem_key or ""
    parts = idem.split(":")
    if len(parts) < 2:
        return None, None
    if parts[0] == "harness":
        try:
            return int(parts[1]), None
        except (TypeError, ValueError):
            return None, None
    if parts[0] == "orch":
        return None, parts[1] or None
    return None, None


def _client_run_id(record: UsageRecord) -> Optional[int]:
    return _client_run_ref(record)[0]


def _chunks(values: List[str], size: int = 500) -> List[List[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def _run_meta(run: Optional[HarnessRun], lease: Optional[HarnessGatewayLease] = None) -> Dict[str, Any]:
    return {
        "run_no": run.run_no if run else None,
        "session_no": (run.session_no if run else None) or (lease.session_no if lease else None),
        "client_id": (run.client_id if run else None) or (lease.client_id if lease else None),
        "owner_type": (run.owner_type if run else None) or (lease.owner_type if lease else None),
        "owner_id": (run.owner_id if run else None) or (lease.owner_id if lease else None),
    }


def _serialize(diff: HarnessReconcileDiff) -> Dict[str, Any]:
    return {
        "id": diff.id,
        "fingerprint": diff.fingerprint,
        "batch_no": diff.batch_no,
        "run_no": diff.run_no,
        "session_no": diff.session_no,
        "client_id": diff.client_id,
        "owner_type": diff.owner_type,
        "owner_id": diff.owner_id,
        "gateway_key": diff.gateway_key,
        "category": diff.category,
        "severity": diff.severity,
        "gateway_amount": _f(diff.gateway_amount),
        "client_amount": _f(diff.client_amount),
        "diff_amount": _f(diff.diff_amount),
        "diff_rate": _f(diff.diff_rate),
        "gateway_cost": _f(diff.gateway_cost),
        "client_cost": _f(diff.client_cost),
        "gateway_count": int(diff.gateway_count or 0),
        "client_count": int(diff.client_count or 0),
        "detail": diff.detail,
        "status": diff.status,
        "resolved_by": diff.resolved_by,
        "resolved_at": _iso(diff.resolved_at),
        "resolve_note": diff.resolve_note,
        "last_seen_at": _iso(diff.last_seen_at),
        "occurrence_count": int(diff.occurrence_count or 0),
        "created_at": _iso(diff.created_at),
        "updated_at": _iso(diff.updated_at),
    }


def _serialize_batch(batch: HarnessReconcileBatch) -> Dict[str, Any]:
    return {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "trigger": batch.trigger,
        "window_start": _iso(batch.window_start),
        "window_end": _iso(batch.window_end),
        "status": batch.status,
        "stats": batch.stats,
        "operator_id": batch.operator_id,
        "duration_ms": int(batch.duration_ms or 0),
        "error_message": batch.error_message,
        "created_at": _iso(batch.created_at),
    }


class HarnessReconcileService:
    # ---------------- 执行对账 ----------------
    @classmethod
    async def execute(
        cls,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        trigger: str = "manual",
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        cfg = reconciliation_config()
        now = _now()
        end = window_end or now
        start = window_start or (end - timedelta(hours=float(cfg["window_hours"])))
        if start > end:
            start, end = end, start
        max_window = timedelta(hours=float(cfg["max_window_hours"]))
        if end - start > max_window:
            start = end - max_window

        batch = await HarnessReconcileBatch.create(
            batch_no=_new_batch_no(now),
            trigger=trigger,
            window_start=start,
            window_end=end,
            status="running",
            operator_id=operator_id,
        )
        started = time.monotonic()

        try:
            result = await cls._run_window(start, end, cfg, batch.batch_no)
            result["batch_no"] = batch.batch_no
            batch.status = "completed"
            batch.stats = result["stats"]
            batch.duration_ms = int((time.monotonic() - started) * 1000)
            await batch.save(update_fields=["status", "stats", "duration_ms"])
            result["window_start"] = _iso(start)
            result["window_end"] = _iso(end)
            result["trigger"] = trigger
            return result
        except Exception as exc:
            batch.status = "failed"
            batch.error_message = str(exc)
            batch.duration_ms = int((time.monotonic() - started) * 1000)
            await batch.save(update_fields=["status", "error_message", "duration_ms"])
            raise

    @classmethod
    async def _run_window(
        cls, start: datetime, end: datetime, cfg: Dict[str, Any], batch_no: str,
    ) -> Dict[str, Any]:
        gateway_records = await UsageRecord.filter(
            source="gateway",
            idem_key__startswith="gw:",
            created_at__gte=start,
            created_at__lt=end,
        ).all()
        client_records = await UsageRecord.filter(
            Q(idem_key__startswith="harness:") | Q(idem_key__startswith="orch:"),
            created_at__gte=start,
            created_at__lt=end,
        ).all()

        lease_map = await cls._load_leases(gateway_records)
        runs_by_id, runs_by_no = await cls._load_runs(gateway_records, client_records, lease_map)

        run_stats: Dict[str, Dict[str, Any]] = {}
        unmatched: List[Dict[str, Any]] = []

        def ensure_run(run: HarnessRun, lease: Optional[HarnessGatewayLease] = None) -> Dict[str, Any]:
            item = run_stats.get(run.run_no)
            if item is None:
                meta = _run_meta(run, lease)
                item = {
                    **meta,
                    "leases": set(),
                    "gateway": _side(),
                    "client": _side(),
                    "failures": {"count": 0, "errors": []},
                }
                run_stats[run.run_no] = item
            if lease is not None:
                item["leases"].add(lease.lease_id)
            return item

        for record in gateway_records:
            lease = lease_map.get(record.gateway_key) if record.gateway_key else None
            if lease is None or not lease.run_no:
                unmatched.append({
                    "kind": "unmatched_gateway",
                    "fingerprint": f"gwrec:{record.id}",
                    "gateway_key": record.gateway_key,
                    "session_no": record.session_ref,
                    "client_id": lease.client_id if lease else None,
                    "owner_type": lease.owner_type if lease else None,
                    "owner_id": lease.owner_id if lease else None,
                    "reason": "gateway_lease_missing" if lease is None else "gateway_lease_without_run",
                    "record": {
                        "id": record.id,
                        "idem_key": record.idem_key,
                        "resource_type": record.resource_type,
                        "amount": _f(record.amount),
                        "cost": _f(record.cost),
                        "created_at": _iso(record.created_at),
                    },
                })
                continue
            run = runs_by_no.get(lease.run_no)
            if run is None:
                unmatched.append({
                    "kind": "unmatched_gateway",
                    "fingerprint": f"gwrec:{record.id}",
                    "gateway_key": lease.lease_id,
                    "session_no": lease.session_no,
                    "client_id": lease.client_id,
                    "owner_type": lease.owner_type,
                    "owner_id": lease.owner_id,
                    "reason": "gateway_run_not_found",
                    "record": {
                        "id": record.id,
                        "idem_key": record.idem_key,
                        "resource_type": record.resource_type,
                        "amount": _f(record.amount),
                        "cost": _f(record.cost),
                        "created_at": _iso(record.created_at),
                    },
                })
                continue

            item = ensure_run(run, lease)
            if record.resource_type == "gateway_error":
                item["failures"]["count"] += 1
                snapshot = record.price_snapshot or {}
                if len(item["failures"]["errors"]) < SAMPLE_LIMIT:
                    item["failures"]["errors"].append({
                        "id": record.id,
                        "idem_key": record.idem_key,
                        "status": snapshot.get("gateway_status"),
                        "stream": snapshot.get("stream"),
                        "error": snapshot.get("error"),
                        "created_at": _iso(record.created_at),
                    })
            else:
                _add_side(item["gateway"], record)

        for record in client_records:
            run_id, run_no_ref = _client_run_ref(record)
            run = runs_by_id.get(run_id) if run_id is not None else None
            if run is None and run_no_ref:
                run = runs_by_no.get(run_no_ref)
            if run is None:
                unmatched.append({
                    "kind": "unmatched_client",
                    "fingerprint": f"client:{record.idem_key or record.id}",
                    "run_no": None,
                    "session_no": record.session_ref,
                    "client_id": None,
                    "owner_type": record.owner_type,
                    "owner_id": record.owner_id,
                    "reason": "client_run_not_found",
                    "record": {
                        "id": record.id,
                        "idem_key": record.idem_key,
                        "resource_type": record.resource_type,
                        "source": record.source,
                        "amount": _f(record.amount),
                        "cost": _f(record.cost),
                        "created_at": _iso(record.created_at),
                    },
                })
                continue
            item = ensure_run(run)
            _add_side(item["client"], record)

        diffs = cls._classify(run_stats, cfg)
        diffs.extend(cls._unmatched_diffs(unmatched))
        for item in diffs:
            item["batch_no"] = batch_no

        created, updated = await cls._persist(diffs, cfg)
        stats = cls._stats(diffs, created, updated, run_stats, unmatched)

        return {
            "stats": stats,
            "diffs": diffs,
            "unmatched": unmatched,
        }

    @classmethod
    async def _load_leases(cls, records: List[UsageRecord]) -> Dict[str, HarnessGatewayLease]:
        lease_ids = sorted({r.gateway_key for r in records if r.gateway_key})
        result: Dict[str, HarnessGatewayLease] = {}
        for chunk in _chunks(lease_ids):
            rows = await HarnessGatewayLease.filter(lease_id__in=chunk).all()
            result.update({row.lease_id: row for row in rows})
        return result

    @classmethod
    async def _load_runs(
        cls,
        gateway_records: List[UsageRecord],
        client_records: List[UsageRecord],
        lease_map: Dict[str, HarnessGatewayLease],
    ) -> Tuple[Dict[int, HarnessRun], Dict[str, HarnessRun]]:
        refs = [_client_run_ref(r) for r in client_records]
        run_ids = sorted({rid for rid, _ in refs if rid is not None})
        run_nos = sorted(
            {lease.run_no for lease in lease_map.values() if lease.run_no}
            | {rno for _, rno in refs if rno}
        )

        runs: List[HarnessRun] = []
        for chunk in _chunks([str(i) for i in run_ids]):
            rows = await HarnessRun.filter(id__in=[int(i) for i in chunk]).all()
            runs.extend(rows)
        for chunk in _chunks(run_nos):
            rows = await HarnessRun.filter(run_no__in=chunk).all()
            runs.extend(rows)

        by_id: Dict[int, HarnessRun] = {}
        by_no: Dict[str, HarnessRun] = {}
        for run in runs:
            by_id[run.id] = run
            by_no[run.run_no] = run
        return by_id, by_no

    @classmethod
    def _classify(
        cls, run_stats: Dict[str, Dict[str, Any]], cfg: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        diffs: List[Dict[str, Any]] = []
        ratio_high = float(cfg["duplicate_ratio_high"])
        amount_high = float(cfg["diff_amount_high"])
        rate_high = float(cfg["diff_rate_high"])
        cost_high = float(cfg["diff_cost_high"])
        missing_high = float(cfg["missing_amount_high"])

        for run_no, item in run_stats.items():
            base = {
                "run_no": run_no,
                "session_no": item.get("session_no"),
                "client_id": item.get("client_id"),
                "owner_type": item.get("owner_type"),
                "owner_id": item.get("owner_id"),
                "gateway_key": sorted(item["leases"])[0] if item["leases"] else None,
            }
            gateway = item["gateway"]
            client = item["client"]
            failures = item["failures"]

            if failures["count"] > 0:
                diffs.append({
                    **base,
                    "fingerprint": f"run:{run_no}:failure_timeout",
                    "category": "failure_timeout",
                    "severity": "low",
                    "gateway_amount": 0.0,
                    "client_amount": 0.0,
                    "diff_amount": 0.0,
                    "diff_rate": 0.0,
                    "gateway_cost": 0.0,
                    "client_cost": 0.0,
                    "gateway_count": 0,
                    "client_count": 0,
                    "detail": {
                        "failures": failures["count"],
                        "errors": failures["errors"],
                        "leases": sorted(item["leases"]),
                    },
                })

            gw_count = gateway["count"]
            cl_count = client["count"]
            gw_amount = gateway["amount"]
            cl_amount = client["amount"]
            diff_amount = cl_amount - gw_amount
            diff_rate = diff_amount / max(gw_amount, 1.0)
            cost_diff = client["cost"] - gateway["cost"]
            has_both_cost = gateway["cost"] > 0 and client["cost"] > 0

            if gw_count > 0 and cl_count == 0:
                diffs.append({
                    **base,
                    "fingerprint": f"run:{run_no}:only_gateway",
                    "category": "only_gateway",
                    "severity": "high" if gw_amount >= missing_high else "low",
                    "gateway_amount": gw_amount,
                    "client_amount": 0.0,
                    "diff_amount": -gw_amount,
                    "diff_rate": -1.0,
                    "gateway_cost": gateway["cost"],
                    "client_cost": 0.0,
                    "gateway_count": gw_count,
                    "client_count": 0,
                    "detail": {"gateway": gateway, "client": client, "leases": sorted(item["leases"])},
                })
                continue

            if gw_count == 0 and cl_count > 0:
                diffs.append({
                    **base,
                    "fingerprint": f"run:{run_no}:only_client",
                    "category": "only_client",
                    "severity": "high",
                    "gateway_amount": 0.0,
                    "client_amount": cl_amount,
                    "diff_amount": cl_amount,
                    "diff_rate": cl_amount,
                    "gateway_cost": 0.0,
                    "client_cost": client["cost"],
                    "gateway_count": 0,
                    "client_count": cl_count,
                    "detail": {"gateway": gateway, "client": client},
                })
                continue

            if gw_count > 0 and cl_count > 0:
                if cl_count > gw_count:
                    diffs.append({
                        **base,
                        "fingerprint": f"run:{run_no}:duplicate_count",
                        "category": "duplicate_count",
                        "severity": "high" if cl_count >= gw_count * ratio_high else "low",
                        "gateway_amount": gw_amount,
                        "client_amount": cl_amount,
                        "diff_amount": diff_amount,
                        "diff_rate": diff_rate,
                        "gateway_cost": gateway["cost"],
                        "client_cost": client["cost"],
                        "gateway_count": gw_count,
                        "client_count": cl_count,
                        "detail": {
                            "gateway": gateway, "client": client,
                            "leases": sorted(item["leases"]),
                        },
                    })
                elif cl_count != gw_count or abs(diff_amount) > 0 or (has_both_cost and abs(cost_diff) > 0):
                    high = (
                        abs(diff_amount) >= amount_high
                        or abs(diff_rate) >= rate_high
                        or (has_both_cost and abs(cost_diff) >= cost_high)
                    )
                    diffs.append({
                        **base,
                        "fingerprint": f"run:{run_no}:value_mismatch",
                        "category": "value_mismatch",
                        "severity": "high" if high else "low",
                        "gateway_amount": gw_amount,
                        "client_amount": cl_amount,
                        "diff_amount": diff_amount,
                        "diff_rate": diff_rate,
                        "gateway_cost": gateway["cost"],
                        "client_cost": client["cost"],
                        "gateway_count": gw_count,
                        "client_count": cl_count,
                        "detail": {
                            "gateway": gateway, "client": client,
                            "leases": sorted(item["leases"]),
                        },
                    })
        return diffs

    @classmethod
    def _unmatched_diffs(cls, unmatched: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        diffs: List[Dict[str, Any]] = []
        for item in unmatched:
            diffs.append({
                "fingerprint": item["fingerprint"],
                "run_no": item.get("run_no"),
                "session_no": item.get("session_no"),
                "client_id": item.get("client_id"),
                "owner_type": item.get("owner_type"),
                "owner_id": item.get("owner_id"),
                "gateway_key": item.get("gateway_key"),
                "category": item["kind"],
                "severity": "low",
                "gateway_amount": _f(item["record"].get("amount")) if item["kind"] == "unmatched_gateway" else 0.0,
                "client_amount": _f(item["record"].get("amount")) if item["kind"] == "unmatched_client" else 0.0,
                "diff_amount": 0.0,
                "diff_rate": 0.0,
                "gateway_cost": _f(item["record"].get("cost")) if item["kind"] == "unmatched_gateway" else 0.0,
                "client_cost": _f(item["record"].get("cost")) if item["kind"] == "unmatched_client" else 0.0,
                "gateway_count": 1 if item["kind"] == "unmatched_gateway" else 0,
                "client_count": 1 if item["kind"] == "unmatched_client" else 0,
                "detail": {"reason": item["reason"], "record": item["record"]},
            })
        return diffs

    @classmethod
    async def _persist(
        cls, diffs: List[Dict[str, Any]], cfg: Dict[str, Any],
    ) -> Tuple[int, int]:
        created = 0
        updated = 0
        now = _now()
        for item in diffs:
            payload = {
                "run_no": item.get("run_no"),
                "session_no": item.get("session_no"),
                "client_id": item.get("client_id"),
                "owner_type": item.get("owner_type"),
                "owner_id": item.get("owner_id"),
                "gateway_key": item.get("gateway_key"),
                "category": item.get("category"),
                "severity": item.get("severity"),
                "gateway_amount": _f(item.get("gateway_amount")),
                "client_amount": _f(item.get("client_amount")),
                "diff_amount": _f(item.get("diff_amount")),
                "diff_rate": _f(item.get("diff_rate")),
                "gateway_cost": _f(item.get("gateway_cost")),
                "client_cost": _f(item.get("client_cost")),
                "gateway_count": int(item.get("gateway_count") or 0),
                "client_count": int(item.get("client_count") or 0),
                "detail": item.get("detail"),
            }
            existing = await HarnessReconcileDiff.get_or_none(fingerprint=item["fingerprint"])
            if existing is None:
                try:
                    await HarnessReconcileDiff.create(
                        fingerprint=item["fingerprint"],
                        batch_no=item.get("batch_no"),
                        status="open",
                        last_seen_at=now,
                        occurrence_count=1,
                        **payload,
                    )
                    created += 1
                    continue
                except Exception:
                    # 并发执行时唯一键冲突：转为更新已有行
                    existing = await HarnessReconcileDiff.get_or_none(fingerprint=item["fingerprint"])
                    if existing is None:
                        raise
            existing.batch_no = item.get("batch_no")
            existing.run_no = payload["run_no"] or existing.run_no
            existing.session_no = payload["session_no"] or existing.session_no
            existing.client_id = payload["client_id"] or existing.client_id
            existing.owner_type = payload["owner_type"] or existing.owner_type
            existing.owner_id = payload["owner_id"] or existing.owner_id
            existing.gateway_key = payload["gateway_key"] or existing.gateway_key
            existing.category = payload["category"]
            existing.severity = payload["severity"]
            existing.gateway_amount = payload["gateway_amount"]
            existing.client_amount = payload["client_amount"]
            existing.diff_amount = payload["diff_amount"]
            existing.diff_rate = payload["diff_rate"]
            existing.gateway_cost = payload["gateway_cost"]
            existing.client_cost = payload["client_cost"]
            existing.gateway_count = payload["gateway_count"]
            existing.client_count = payload["client_count"]
            existing.detail = payload["detail"]
            existing.last_seen_at = now
            existing.occurrence_count = int(existing.occurrence_count or 0) + 1
            await existing.save()
            updated += 1
        return created, updated

    @classmethod
    def _stats(
        cls,
        diffs: List[Dict[str, Any]],
        created: int,
        updated: int,
        run_stats: Dict[str, Dict[str, Any]],
        unmatched: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for item in diffs:
            by_category[item["category"]] = by_category.get(item["category"], 0) + 1
            by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1

        consistent_runs = 0
        for item in run_stats.values():
            gw = item["gateway"]
            cl = item["client"]
            if gw["count"] > 0 and gw["count"] == cl["count"] and gw["amount"] == cl["amount"]:
                consistent_runs += 1

        return {
            "diffs": len(diffs),
            "created": created,
            "updated": updated,
            "consistent_runs": consistent_runs,
            "matched_runs": len(run_stats),
            "unmatched": len(unmatched),
            "by_category": by_category,
            "by_severity": by_severity,
        }

    # ---------------- 查询 ----------------
    @classmethod
    async def list_diffs(
        cls,
        *,
        run_no: Optional[str] = None,
        session_no: Optional[str] = None,
        client_id: Optional[str] = None,
        owner_type: Optional[str] = None,
        owner_id: Optional[int] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        query = HarnessReconcileDiff.all()
        if run_no:
            query = query.filter(run_no=run_no)
        if session_no:
            query = query.filter(session_no=session_no)
        if client_id:
            query = query.filter(client_id=client_id)
        if owner_type:
            query = query.filter(owner_type=owner_type)
        if owner_id is not None:
            query = query.filter(owner_id=owner_id)
        if severity:
            query = query.filter(severity=severity)
        if category:
            query = query.filter(category=category)
        if status:
            query = query.filter(status=status)
        if date_from:
            query = query.filter(created_at__gte=date_from)
        if date_to:
            query = query.filter(created_at__lte=date_to)

        total = await query.count()
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 20), 1), 200)
        items = await query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize(item) for item in items],
        }

    @classmethod
    async def diff_detail(cls, diff_id: int) -> Dict[str, Any]:
        diff = await HarnessReconcileDiff.get_or_none(id=diff_id)
        if diff is None:
            return {"error": "diff_not_found"}
        return _serialize(diff)

    @classmethod
    async def mark_diff(
        cls,
        diff_id: int,
        status: str,
        note: Optional[str] = None,
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if status not in ("open", "resolved", "ignored"):
            return {"error": "invalid_status"}
        diff = await HarnessReconcileDiff.get_or_none(id=diff_id)
        if diff is None:
            return {"error": "diff_not_found"}
        diff.status = status
        if status == "open":
            diff.resolved_by = None
            diff.resolved_at = None
            diff.resolve_note = None
        else:
            diff.resolved_by = operator_id
            diff.resolved_at = _now()
            diff.resolve_note = note
        await diff.save(update_fields=[
            "status", "resolved_by", "resolved_at", "resolve_note",
        ])
        return _serialize(diff)

    @classmethod
    async def list_batches(cls, limit: int = 20) -> List[Dict[str, Any]]:
        limit = min(max(int(limit or 20), 1), 200)
        batches = await HarnessReconcileBatch.all().order_by("-id").limit(limit).all()
        return [_serialize_batch(batch) for batch in batches]

    @classmethod
    async def summary(cls, limit: int = 20) -> Dict[str, Any]:
        limit = min(max(int(limit or 20), 1), 200)
        open_count = await HarnessReconcileDiff.filter(status="open").count()
        high_open = await HarnessReconcileDiff.filter(status="open", severity="high").count()

        rows = await HarnessReconcileDiff.filter(status="open").values("category", "severity")
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for row in rows:
            by_category[row["category"]] = by_category.get(row["category"], 0) + 1
            by_severity[row["severity"]] = by_severity.get(row["severity"], 0) + 1

        latest = await HarnessReconcileBatch.all().order_by("-id").first()
        high_rows = await HarnessReconcileDiff.filter(
            status="open", severity="high",
        ).order_by("-last_seen_at", "-id").limit(limit).all()
        remaining = limit - len(high_rows)
        low_rows = []
        if remaining > 0:
            low_rows = await HarnessReconcileDiff.filter(
                status="open", severity="low",
            ).order_by("-last_seen_at", "-id").limit(remaining).all()

        return {
            "open": open_count,
            "high_open": high_open,
            "by_category": by_category,
            "by_severity": by_severity,
            "latest_batch": _serialize_batch(latest) if latest else None,
            "top_diffs": [_serialize(item) for item in (high_rows + low_rows)],
        }
