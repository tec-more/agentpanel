"""
Harness 事件映射服务：会话 JSONL / notification → step / audit_event / usage_record

容错约定：
- 截断行、非法 JSON、未知事件类型、缺失 usage 都不阻断整批采集，只计入统计并留审计缺口事件；
- usage 必须携带 source（provider/gateway/estimated），不同 source 各自落 usage_record，不合并；
- 计费输入 = inputTokens + cacheReadTokens + cacheWriteTokens；outputTokens 单独计；
- compaction/summary 的 usage 是额外一次模型调用，使用独立 node_id（compaction:{seq}），不混入普通回合；
- approval/asked 不带参数，按 callId 回查 tool/call 的参数。
"""
import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from packages.common.domain import quota_backend
from packages.common.domain.quota_backend import QuotaUnavailable
from packages.common.models.harness import (
    HarnessApprovalRequest,
    HarnessRun,
    HarnessSession,
    HarnessStep,
)
from packages.common.domain.audit_service import HarnessAuditService
from packages.common.domain.policy_service import HarnessPolicyService
from packages.common.domain.pricing_service import ModelPriceService
from packages.common.domain.run_service import TERMINAL_STATUSES

ALLOWED_SOURCES = {"provider", "gateway", "estimated"}
USAGE_EVENT_TYPES = {"assistant/message", "compaction/summary"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _event_type(event: Dict[str, Any]) -> str:
    t = event.get("type") or event.get("event_type")
    if not t and isinstance(event.get("event"), dict):
        t = event["event"].get("type")
    return str(t or "")


def _event_data(event: Dict[str, Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    inner = event.get("event")
    if isinstance(inner, dict):
        data.update(inner)
    for key in ("data", "payload"):
        value = event.get(key)
        if isinstance(value, dict):
            data.update(value)
        elif value is not None:
            data.setdefault(key, value)
    # 兼容字段平铺在事件顶层
    for key, value in event.items():
        if key in ("type", "event_type", "event", "data", "payload", "seq", "__line_no"):
            continue
        data.setdefault(key, value)
    return data


def _usage_of(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    usage = data.get("usage")
    if isinstance(usage, dict):
        return usage
    message = data.get("message")
    if isinstance(message, dict):
        usage = message.get("usage")
        if isinstance(usage, dict):
            return usage
    return None


def _pick(usage: Dict[str, Any], *names: str) -> int:
    for name in names:
        if name in usage and usage[name] is not None:
            return _as_int(usage[name])
    return 0


def _normalize_source(raw: Optional[str]) -> str:
    value = (raw or "provider").lower()
    return value if value in ALLOWED_SOURCES else "provider"


class HarnessEventService:
    @classmethod
    async def _get_run(cls, run_no: str, client_id: str) -> HarnessRun:
        run = await HarnessRun.get_or_none(run_no=run_no)
        if run is None or run.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行不存在")
        if run.status in TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="运行已结束")
        return run

    @classmethod
    async def ingest(cls, run_no: str, client_id: str, batch: Any) -> Dict[str, Any]:
        run = await cls._get_run(run_no, client_id)
        run._event_source = batch.source
        session = await HarnessSession.get_or_none(session_no=run.session_no)

        counters: Dict[str, int] = {
            "processed": 0,
            "tool_calls": 0,
            "tool_results": 0,
            "approvals": 0,
            "policy_events": 0,
            "usage_events": 0,
            "usage_records": 0,
            "unknown": 0,
            "invalid_lines": 0,
            "missing_usage": 0,
            "truncated_lines": int(batch.truncated_lines or 0),
        }
        unknown_types: Dict[str, int] = {}

        events: List[Dict[str, Any]] = []
        for item in batch.events or []:
            if isinstance(item, dict):
                events.append(item)
            else:
                counters["invalid_lines"] += 1
        for idx, line in enumerate(batch.lines or []):
            if not isinstance(line, str) or not line.strip():
                counters["invalid_lines"] += 1
                continue
            try:
                parsed = json.loads(line)
            except Exception:
                counters["invalid_lines"] += 1
                continue
            if not isinstance(parsed, dict):
                counters["invalid_lines"] += 1
                continue
            parsed["__line_no"] = idx + 1
            events.append(parsed)

        for idx, event in enumerate(events):
            ev_type = _event_type(event)
            seq = _as_int(event.get("seq"), _as_int(event.get("__line_no"), idx + 1))
            data = _event_data(event)
            # approval/request 是内部 hook，不是 JSONL 事件类型；真实审批链以 asked/decided 为准
            if ev_type == "approval/request":
                continue
            counters["processed"] += 1

            if ev_type == "tool/call":
                await cls._tool_call(run, seq, data, event, counters)
            elif ev_type == "tool/result":
                await cls._tool_result(run, seq, data, counters)
            elif ev_type == "approval/asked":
                await cls._approval_asked(run, seq, data, counters)
            elif ev_type == "approval/decided":
                await cls._approval_decided(run, seq, data, counters)
            elif ev_type in ("permission/preset", "sandbox/mode", "approval/policy"):
                await cls._policy_state(run, seq, ev_type, data, counters)
            elif ev_type in USAGE_EVENT_TYPES:
                await cls._usage(run, session, seq, ev_type, data, event, batch, counters)
            else:
                counters["unknown"] += 1
                key = ev_type or "<empty>"
                unknown_types[key] = unknown_types.get(key, 0) + 1

        if counters["invalid_lines"] or counters["truncated_lines"]:
            await HarnessAuditService.record(
                "event.collection_gap",
                client_id=client_id,
                session_no=run.session_no,
                run_no=run.run_no,
                risk_level="medium",
                event_source=batch.source,
                detail={
                    "invalid_lines": counters["invalid_lines"],
                    "truncated_lines": counters["truncated_lines"],
                },
            )
        for raw_type, count in unknown_types.items():
            await HarnessAuditService.record(
                "event.unknown",
                client_id=client_id,
                session_no=run.session_no,
                run_no=run.run_no,
                risk_level="low",
                raw_type=raw_type[:100],
                event_source=batch.source,
                detail={"count": count},
            )

        run.last_heartbeat_at = run.last_heartbeat_at
        if counters["processed"]:
            from datetime import datetime
            run.last_heartbeat_at = datetime.now()
            await run.save()
            if session is not None:
                session.last_activity_at = datetime.now()
                await session.save()

        return counters

    # ---------------- 单事件处理 ----------------
    @classmethod
    async def _upsert_step(cls, run: HarnessRun, node_id: str, seq: int, **fields):
        node_id = node_id[:100]
        step = await HarnessStep.get_or_none(run_id=run.id, node_id=node_id, seq=seq)
        base = dict(
            run_id=run.id, run_no=run.run_no, session_no=run.session_no,
            node_id=node_id, seq=seq,
        )
        base.update(fields)
        if step is None:
            return await HarnessStep.create(**base)
        for key, value in base.items():
            setattr(step, key, value)
        await step.save()
        return step

    @classmethod
    async def _tool_call(cls, run, seq, data, event, counters):
        call_id = data.get("callId") or data.get("call_id")
        name = data.get("name") or data.get("tool") or "<unknown>"
        arguments = data.get("arguments", data.get("args"))
        await cls._upsert_step(
            run, call_id or f"tool:{seq}", seq,
            step_type="tool_call", name=str(name)[:200],
            call_id=str(call_id)[:100] if call_id else None,
            input=arguments, status="completed", raw_seq=seq,
        )
        verdict = await HarnessPolicyService.evaluate(
            str(name), {"run_no": run.run_no, "session_no": run.session_no}, arguments,
        )
        await HarnessAuditService.record(
            "tool.call",
            client_id=run.client_id,
            session_no=run.session_no,
            run_no=run.run_no,
            call_id=str(call_id)[:100] if call_id else None,
            raw_seq=seq,
            event_source=getattr(run, "_event_source", "jsonl"),
            raw_type="tool/call",
            target_type="tool",
            target_id=str(name),
            risk_level=verdict.get("risk_level") or "medium",
            decision=verdict.get("decision"),
            policy_code=verdict.get("policy_code"),
            detail={"name": name, "arguments": arguments},
        )
        counters["tool_calls"] += 1

    @classmethod
    async def _tool_result(cls, run, seq, data, counters):
        message = data.get("message") if isinstance(data.get("message"), dict) else {}
        source = message.get("source") if isinstance(message.get("source"), dict) else {}
        call_id = (
            data.get("callId") or data.get("call_id")
            or source.get("callId") or source.get("call_id")
        )
        result_block = {}
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool-result":
                result_block = block
                break
        if not call_id:
            call_id = result_block.get("toolCallId") or result_block.get("tool_call_id")
        is_error = data.get("isError", data.get("is_error"))
        if is_error is None:
            is_error = result_block.get("isError", result_block.get("is_error"))
        text = None
        content = result_block.get("content")
        if isinstance(content, list):
            text = "".join(
                str(item.get("text") or "") for item in content if isinstance(item, dict)
            )
        elif isinstance(content, str):
            text = content
        output = {
            "content": text if text is not None else data.get("content"),
            "isError": is_error,
            "error": data.get("error"),
        }
        node_id = f"{call_id}:result" if call_id else f"tool-result:{seq}"
        await cls._upsert_step(
            run, node_id, seq,
            step_type="tool_result",
            call_id=str(call_id)[:100] if call_id else None,
            output=output, status="failed" if output["isError"] else "completed",
            raw_seq=seq,
        )
        await HarnessAuditService.record(
            "tool.result",
            client_id=run.client_id,
            session_no=run.session_no,
            run_no=run.run_no,
            call_id=str(call_id)[:100] if call_id else None,
            raw_seq=seq,
            event_source=getattr(run, "_event_source", "jsonl"),
            raw_type="tool/result",
            target_type="tool",
            risk_level="medium" if output["isError"] else "low",
            detail={
                "is_error": bool(output["isError"]),
                "error": output["error"],
                "output": (text or "")[:500] if text else None,
            },
        )
        counters["tool_results"] += 1

    @classmethod
    async def _find_call_arguments(cls, run, call_id: Optional[str]):
        if not call_id:
            return None
        step = await HarnessStep.filter(
            run_id=run.id, call_id=call_id, step_type="tool_call",
        ).order_by("seq").first()
        return step.input if step else None

    @classmethod
    async def _approval_asked(cls, run, seq, data, counters):
        call_id = data.get("callId") or data.get("call_id")
        arguments = await cls._find_call_arguments(run, call_id)
        approval = None
        if call_id:
            approval = await HarnessApprovalRequest.filter(
                run_no=run.run_no, call_id=str(call_id)[:100], status="pending",
            ).order_by("-id").first()
        detail = {
            "request_id": data.get("id") or data.get("requestId") or data.get("request_id"),
            "tool_name": data.get("toolName") or data.get("tool_name"),
            "reason": data.get("reason"),
            "tool_arguments": arguments,
            "note": "approval/asked 不带参数，已按 callId 关联 tool/call",
        }
        if approval is not None:
            detail.update({
                "approval_no": approval.approval_no,
                "command_text": approval.command_text,
                "initiator_user_id": approval.initiator_user_id,
                "approver_user_id": approval.approver_user_id,
                "approver_role": approval.approver_role,
                "timeout_seconds": approval.timeout_seconds,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                "policy_code": approval.policy_code,
                "scope": approval.scope,
            })
        await HarnessAuditService.record(
            "approval.asked",
            client_id=run.client_id,
            session_no=run.session_no,
            run_no=run.run_no,
            call_id=str(call_id)[:100] if call_id else None,
            raw_seq=seq,
            event_source=getattr(run, "_event_source", "jsonl"),
            raw_type="approval/asked",
            target_type="approval",
            target_id=str(
                (approval.approval_no if approval else None)
                or data.get("id") or data.get("requestId") or data.get("request_id") or call_id or ""
            ),
            risk_level=approval.risk_level if approval else "high",
            policy_code=approval.policy_code if approval else None,
            detail=detail,
        )
        counters["approvals"] += 1

    @classmethod
    async def _approval_decided(cls, run, seq, data, counters):
        call_id = data.get("callId") or data.get("call_id")
        raw_decision = str(
            data.get("decision") or data.get("outcome") or data.get("approved") or ""
        ).lower()
        if raw_decision in (
            "true", "approved", "allow", "allowed", "allow-once", "allowed-once", "allowed_once",
        ):
            decision = "allow"
        elif raw_decision in (
            "false", "denied", "deny", "rejected", "cancelled", "canceled", "unavailable",
        ):
            decision = "deny"
        else:
            decision = raw_decision or "unknown"
        await HarnessAuditService.record(
            "approval.decided",
            client_id=run.client_id,
            session_no=run.session_no,
            run_no=run.run_no,
            call_id=str(call_id)[:100] if call_id else None,
            raw_seq=seq,
            event_source=getattr(run, "_event_source", "jsonl"),
            raw_type="approval/decided",
            target_type="approval",
            target_id=str(
                data.get("id") or data.get("requestId") or data.get("request_id") or call_id or ""
            ),
            risk_level="high",
            decision=decision,
            detail={
                "comment": data.get("comment"),
                "decision_raw": raw_decision,
                "outcome": data.get("outcome") or data.get("decision"),
            },
        )
        counters["approvals"] += 1

    @classmethod
    async def _policy_state(cls, run, seq, ev_type, data, counters):
        await HarnessAuditService.record(
            ev_type.replace("/", "."),
            client_id=run.client_id,
            session_no=run.session_no,
            run_no=run.run_no,
            raw_seq=seq,
            event_source=getattr(run, "_event_source", "jsonl"),
            raw_type=ev_type,
            target_type="policy",
            risk_level="medium",
            detail=data,
        )
        counters["policy_events"] += 1

    @classmethod
    async def _usage(cls, run, session, seq, ev_type, data, event, batch, counters):
        usage = _usage_of(data)
        if not usage:
            counters["missing_usage"] += 1
            return

        kind = "compaction" if ev_type == "compaction/summary" else "normal"
        tokens_in = _pick(usage, "inputTokens", "input_tokens", "input")
        cache_read = _pick(usage, "cacheReadTokens", "cache_read_tokens", "cacheRead")
        cache_write = _pick(usage, "cacheWriteTokens", "cache_write_tokens", "cacheWrite")
        tokens_out = _pick(usage, "outputTokens", "output_tokens", "output")
        reasoning = _pick(usage, "reasoningTokens", "reasoning_tokens", "reasoning")
        total = _pick(usage, "totalTokens", "total_tokens", "total")
        model = data.get("model") or event.get("model") or batch.model or run.model
        provider = data.get("provider") or event.get("provider") or batch.provider or run.provider
        source = _normalize_source(
            data.get("source") or event.get("source") or batch.default_source
        )
        gateway_key = batch.gateway_key or (session.gateway_key if session else None)

        billed_input = tokens_in + cache_read + cache_write
        amount = billed_input + tokens_out
        if amount <= 0:
            counters["missing_usage"] += 1
            return

        price = await ModelPriceService.estimate_cost(
            provider, model, tokens_in, tokens_out, cache_read, cache_write,
        )
        cost = data.get("cost") if data.get("cost") is not None else price["cost"]
        node_id = f"{'compaction' if kind == 'compaction' else 'assistant'}:{seq}"
        # 来源隔离：编排侧实际值写 client（provider/harness 归一），估算值保持 estimated
        billed_source = "client" if source in ("provider", "harness") else source

        entry = {
            "run_id": run.id,
            "execution_id": None,
            "node_id": node_id,
            "seq": seq,
            "session_ref": run.session_no,
            "resource_type": "token",
            "amount": amount,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "reasoning_tokens": reasoning,
            "source": billed_source,
            "idem_key": f"orch:{run.run_no}:{node_id}:{seq}",
            "gateway_key": gateway_key,
            "usage_kind": kind,
            "model": model,
            "provider": provider,
            "cost": cost,
            "currency": price["currency"],
            "price_snapshot": price["price_snapshot"],
            "raw_seq": seq,
            "member_id": (run.metrics or {}).get("quota_member_id"),
        }
        try:
            result = await quota_backend.settle(
                run.hold_id or "", [entry],
                owner=(run.owner_type, run.owner_id) if run.owner_id else None,
            )
        except QuotaUnavailable as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": 503, "msg": "额度服务不可用，事件批次未确认",
                        "data": {"error_code": "orchestration_dependency_unavailable",
                                 "message": str(e), "downstream": "l2_quota"}},
            )
        counters["usage_records"] += int(result.get("settled", 0))

        await cls._upsert_step(
            run, node_id, seq,
            step_type="llm_call" if kind == "normal" else "compaction",
            name=model, status="completed",
            tokens_in=tokens_in, tokens_out=tokens_out,
            cache_read_tokens=cache_read, cache_write_tokens=cache_write,
            reasoning_tokens=reasoning, total_tokens=total or amount,
            model=model, provider=provider, source=source,
            cost=cost, price_snapshot=price["price_snapshot"], raw_seq=seq,
        )
        counters["usage_events"] += 1
