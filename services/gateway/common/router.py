"""内部网关数据面路由：兼容 DeepSeek/OpenAI Chat Completions 端点

- 客户端只持有 agentpanel 签发的短期租约虚拟 key（dgw.<lease_id>.<secret>）；
- 网关校验租约后替换成真实 provider key 再转发；
- SSE 透明透传：边读边转发，不缓冲不聚合；同时旁路解析 usage 帧；
- 不记录 prompt/response 正文，只落 usage_record。
"""
import asyncio
import json
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import service
from .audit import record_gateway_quota_event
from .auth import require_gateway_lease
from .lease_auth import renew_hint
from .budget import (
    GatewayBudgetService,
    GatewayQuotaError,
    apply_request_caps,
    estimate_completion_tokens,
)
from .runtime import gateway_config, gateway_upstream_config
from .logging import gateway_logger
from packages.common.upstream import client as upstream_client

gateway_data_router = APIRouter(tags=["Gateway-数据面"])

# 只放行这些上游响应头到客户端；content-length/content-encoding 会破坏流式语义
_PASS_HEADERS = {
    "content-type",
    "retry-after",
    "x-request-id",
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
}


def _error_response(
    status_code: int,
    message: str,
    error_type: str = "gateway_error",
    *,
    code: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    payload: Dict[str, Any] = {"message": message, "type": error_type}
    if code:
        payload["code"] = code
    if extra:
        payload.update(extra)
    return JSONResponse(status_code=status_code, content={"error": payload}, headers=headers)


def _lease_headers(lease: Any) -> Dict[str, str]:
    """数据面续期提示头（剩余 <30% TTL 时给出 renew_after 秒数）。"""
    try:
        return renew_hint(lease)
    except Exception:
        return {}


def _downstream_headers(resp: httpx.Response) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for name in _PASS_HEADERS:
        value = resp.headers.get(name)
        if value:
            headers[name] = value
    return headers


def _response_headers(resp: httpx.Response, lease: Any) -> Dict[str, str]:
    """透传白名单响应头 + 租约续期提示头。"""
    headers = _downstream_headers(resp)
    headers.update(_lease_headers(lease))
    return headers


def _scan_sse_chunk(chunk: bytes, state: Dict[str, Any]) -> None:
    """旁路解析 SSE data 帧中的 usage 与增量字符数；不改变转发字节。"""
    buf = state.get("buffer", b"") + chunk
    lines = buf.split(b"\n")
    state["buffer"] = lines.pop() if lines else b""
    if len(state["buffer"]) > (1 << 20):
        # 单行异常超长时丢弃，避免内存增长（正常 usage 帧远小于此）
        state["buffer"] = b""
    for line in lines:
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        usage = service.usage_from_sse_frame(data)
        if usage:
            state["usage"] = usage
        state["output_chars"] = int(state.get("output_chars") or 0) + service.output_chars_from_sse_frame(data)


async def _json_body(request: Request) -> Dict[str, Any]:
    raw = await request.body()
    try:
        body = json.loads(raw) if raw else {}
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")
    return body


async def _finalize_stream(
    *,
    lease,
    grant,
    state: Dict[str, Any],
    model: Optional[str],
    provider: Optional[str],
    status_code: int,
    error: Optional[str],
    response: Optional[httpx.Response],
) -> None:
    if response is not None:
        try:
            await response.aclose()
        except Exception:
            pass

    truncated = bool(state.get("truncated"))
    if truncated:
        prompt = int(grant.prompt_tokens) if grant is not None else 0
        completion = estimate_completion_tokens(int(state.get("output_chars") or 0))
        state["usage"] = {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }
        state["estimated"] = True
        error = None

    if error is not None and not truncated:
        # 未产生可计费用量：释放预占，不落 partial 记账
        await GatewayBudgetService.release(lease, grant)
    else:
        await GatewayBudgetService.settle(
            lease,
            grant,
            usage=state.get("usage"),
            estimated_completion=estimate_completion_tokens(int(state.get("output_chars") or 0)),
            truncated=truncated,
        )

    await service.record_gateway_usage(
        lease=lease,
        usage=state.get("usage"),
        model=model,
        provider=provider,
        status_code=status_code,
        stream=True,
        error=error,
        usage_kind="partial" if truncated else "normal",
        truncated=truncated,
        truncation_reason=state.get("truncation_reason"),
        estimated=bool(state.get("estimated")),
    )

    if truncated:
        GatewayBudgetService.record_truncate(state.get("truncation_reason") or "estimated_budget_exceeded")
        await record_gateway_quota_event(
            action="gateway.stream_truncated",
            lease_id=lease.lease_id,
            reason=state.get("truncation_reason") or "estimated_budget_exceeded",
            detail={
                "estimated_tokens": state.get("usage", {}).get("total_tokens"),
                "limit_tokens": getattr(grant, "limit_tokens", None),
                "budget_tokens": getattr(grant, "budget_tokens", None),
                "estimated": True,
                "partial": True,
                "upstream_aborted": True,
            },
            risk_level="high",
            decision="deny",
            client_id=lease.client_id,
            session_no=lease.session_no,
            run_no=lease.run_no,
        )


@gateway_data_router.get("/health", summary="网关健康探针（fail-closed 启动校验用）")
async def gateway_health():
    cfg = gateway_config()
    return {
        "status": "ok" if cfg.get("fail_closed") else "degraded",
        "deployment": cfg.get("deployment"),
        "fail_closed": bool(cfg.get("fail_closed")),
    }


@gateway_data_router.post("/chat/completions", summary="Chat Completions（虚拟 key 鉴权 + 透明转发）")
async def chat_completions(request: Request, lease: Any = Depends(require_gateway_lease)):
    try:
        body = await _json_body(request)
    except HTTPException as exc:
        return _error_response(
            int(exc.status_code), str(exc.detail), "invalid_request_error",
            headers=_lease_headers(lease),
        )

    body = service.strip_request_fields(body)
    stream = bool(body.get("stream"))
    body_model = body.get("model") if isinstance(body.get("model"), str) else None
    if stream and body.get("stream_options") is None:
        body["stream_options"] = {"include_usage": True}

    # 入口预检：额度/预算/并发不足直接拒绝，绝不发出上游请求
    try:
        grant = await GatewayBudgetService.grant(lease, body)
    except GatewayQuotaError as exc:
        await GatewayBudgetService.record_reject(lease, exc.code)
        if exc.code in ("quota.balance_insufficient", "quota.lease_budget_exhausted"):
            reason = (
                "lease_budget_exhausted"
                if exc.code == "quota.lease_budget_exhausted"
                else "balance_insufficient"
            )
            await GatewayBudgetService.maybe_auto_revoke(lease, reason)
        await record_gateway_quota_event(
            action="gateway.quota_rejected",
            lease_id=lease.lease_id,
            reason=exc.code,
            detail={**exc.detail, "status": exc.status_code},
            risk_level="medium",
            decision="deny",
            client_id=lease.client_id,
            session_no=lease.session_no,
            run_no=lease.run_no,
        )
        return _error_response(
            exc.status_code, exc.message, "quota_exceeded", code=exc.code,
            extra=exc.detail, headers=_lease_headers(lease),
        )
    body = apply_request_caps(body, grant)

    try:
        credential = await service.resolve_upstream_credential(lease, body_model)
        url = service.build_upstream_url(credential.base_url)
        service.assert_egress_allowed(url)
    except service.GatewayProxyError as exc:
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease,
            usage=None,
            model=body_model,
            provider=lease.provider,
            status_code=exc.status_code,
            stream=stream,
            error=exc.message,
        )
        return _error_response(
            exc.status_code, exc.message, "gateway_upstream_error",
            headers=_lease_headers(lease),
        )

    headers = {
        "authorization": f"Bearer {credential.api_key}",
        "content-type": "application/json",
        "accept": "text/event-stream" if stream else "application/json",
    }

    if not stream:
        return await _forward_non_stream(
            lease=lease,
            grant=grant,
            body=body,
            url=url,
            headers=headers,
            model=body_model,
            provider=credential.provider,
        )
    return await _forward_stream(
        lease=lease,
        grant=grant,
        body=body,
        url=url,
        headers=headers,
        model=body_model,
        provider=credential.provider,
    )


def _payload_output_chars(payload: Any) -> int:
    chars = 0
    if not isinstance(payload, dict):
        return chars
    for choice in payload.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                chars += len(content)
            for call in message.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                function = call.get("function") or {}
                arguments = function.get("arguments") if isinstance(function, dict) else None
                if isinstance(arguments, str):
                    chars += len(arguments)
    return chars


async def _forward_non_stream(
    *,
    lease,
    grant,
    body: Dict[str, Any],
    url: str,
    headers: Dict[str, str],
    model: Optional[str],
    provider: Optional[str],
):
    try:
        upstream = await upstream_client.post_json(
            url,
            json=body,
            headers=headers,
            cfg=gateway_upstream_config(),
            policy=service.egress_policy(),
            # 非流式可安全重放：配置的 429/5xx 重试由共享客户端负责
            replay=True,
        )
    except upstream_client.UpstreamEgressError as exc:
        gateway_logger.warning(f"[gateway] 出网校验拒绝 lease={lease.lease_id}: {exc.message}")
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease, usage=None, model=model, provider=provider,
            status_code=403, stream=False, error=f"upstream_egress_denied:{exc.message}",
        )
        return _error_response(
            403, exc.message, "gateway_upstream_error", headers=_lease_headers(lease)
        )
    except upstream_client.UpstreamTimeout as exc:
        gateway_logger.warning(
            f"[gateway] 上游超时 lease={lease.lease_id}: {exc.timeout_kind}"
        )
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease, usage=None, model=model, provider=provider,
            status_code=504, stream=False, error=f"upstream_timeout:{exc.timeout_kind}",
        )
        return _error_response(
            504, "上游模型服务超时", "upstream_timeout", headers=_lease_headers(lease)
        )
    except upstream_client.UpstreamError as exc:
        gateway_logger.warning(
            f"[gateway] 上游连接失败 lease={lease.lease_id}: {type(exc).__name__}"
        )
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease, usage=None, model=model, provider=provider,
            status_code=502, stream=False, error=f"upstream_unreachable:{type(exc).__name__}",
        )
        return _error_response(
            502, "上游模型服务不可达", "upstream_unreachable", headers=_lease_headers(lease)
        )

    usage: Optional[Dict[str, int]] = None
    payload: Any = None
    if upstream.status_code < 400:
        try:
            payload = upstream.json()
            if isinstance(payload, dict) and isinstance(payload.get("usage"), dict):
                usage = service.extract_usage(payload["usage"])
        except Exception:
            payload = None

    if upstream.status_code >= 400:
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease,
            usage=None,
            model=model,
            provider=provider,
            status_code=upstream.status_code,
            stream=False,
            error=f"upstream_status:{upstream.status_code}",
        )
    else:
        estimated_completion = 0 if usage else estimate_completion_tokens(
            _payload_output_chars(payload)
        )
        over_budget = bool(
            usage and grant.limit_tokens > 0
            and int(usage.get("total_tokens") or 0) > grant.limit_tokens
        )
        await GatewayBudgetService.settle(
            lease,
            grant,
            usage=usage,
            estimated_completion=estimated_completion,
            over_budget=over_budget,
        )
        await service.record_gateway_usage(
            lease=lease,
            usage=usage,
            model=model,
            provider=provider,
            status_code=upstream.status_code,
            stream=False,
            error=None,
            estimated=usage is None,
            over_budget=over_budget,
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_response_headers(upstream, lease),
    )


def _watchdog_exceeded(grant, state: Dict[str, Any]) -> bool:
    if grant is None or int(grant.limit_tokens or 0) <= 0:
        return False
    estimated_completion = estimate_completion_tokens(int(state.get("output_chars") or 0))
    return int(grant.prompt_tokens or 0) + estimated_completion > int(grant.limit_tokens)


def _truncation_frames(grant) -> bytes:
    if grant is not None and grant.budget_tokens <= 0 and grant.owner_limit > 0:
        code = "quota.balance_insufficient"
    else:
        code = "quota.lease_budget_exhausted"
    payload = {
        "error": {
            "message": "额度预算耗尽，流式输出被截断（估算触发）",
            "type": "quota_exceeded",
            "code": code,
            "partial": True,
            "estimated": True,
            "truncated": True,
        }
    }
    return (
        "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
        "data: [DONE]\n\n"
    ).encode("utf-8")


async def _forward_stream(
    *,
    lease,
    grant,
    body: Dict[str, Any],
    url: str,
    headers: Dict[str, str],
    model: Optional[str],
    provider: Optional[str],
):
    try:
        upstream = await upstream_client.send_stream(
            url,
            json=body,
            headers=headers,
            cfg=gateway_upstream_config(),
            policy=service.egress_policy(),
        )
    except upstream_client.UpstreamEgressError as exc:
        gateway_logger.warning(f"[gateway] 出网校验拒绝(stream) lease={lease.lease_id}: {exc.message}")
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease, usage=None, model=model, provider=provider,
            status_code=403, stream=True, error=f"upstream_egress_denied:{exc.message}",
        )
        return _error_response(
            403, exc.message, "gateway_upstream_error", headers=_lease_headers(lease)
        )
    except upstream_client.UpstreamTimeout as exc:
        gateway_logger.warning(
            f"[gateway] 上游超时(stream) lease={lease.lease_id}: {exc.timeout_kind}"
        )
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease, usage=None, model=model, provider=provider,
            status_code=504, stream=True, error=f"upstream_timeout:{exc.timeout_kind}",
        )
        return _error_response(
            504, "上游模型服务超时", "upstream_timeout", headers=_lease_headers(lease)
        )
    except upstream_client.UpstreamError as exc:
        gateway_logger.warning(
            f"[gateway] 上游连接失败(stream) lease={lease.lease_id}: {type(exc).__name__}"
        )
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease, usage=None, model=model, provider=provider,
            status_code=502, stream=True, error=f"upstream_unreachable:{type(exc).__name__}",
        )
        return _error_response(
            502, "上游模型服务不可达", "upstream_unreachable", headers=_lease_headers(lease)
        )

    if upstream.status_code >= 400:
        raw = await upstream.aread()
        await upstream.aclose()
        await GatewayBudgetService.release(lease, grant)
        await service.record_gateway_usage(
            lease=lease, usage=None, model=model, provider=provider,
            status_code=upstream.status_code, stream=True,
            error=f"upstream_status:{upstream.status_code}",
        )
        return Response(
            content=raw,
            status_code=upstream.status_code,
            headers=_response_headers(upstream, lease),
        )

    state: Dict[str, Any] = {
        "usage": None,
        "buffer": b"",
        "output_chars": 0,
        "truncated": False,
        "truncation_reason": None,
    }

    async def relay():
        error: Optional[str] = None
        try:
            async for chunk in upstream.aiter_bytes():
                if not chunk:
                    continue
                _scan_sse_chunk(chunk, state)
                if _watchdog_exceeded(grant, state):
                    # 越过预算：停止读取并主动断开上游，绝不伪装成正常结束
                    state["truncated"] = True
                    state["truncation_reason"] = "estimated_budget_exceeded"
                    gateway_logger.warning(
                        f"[gateway] 额度估算越界，截断流 lease={lease.lease_id} "
                        f"limit={grant.limit_tokens} output_chars={state.get('output_chars')}"
                    )
                    break
                yield chunk
        except asyncio.CancelledError:
            error = "client_disconnect"
            raise
        except httpx.HTTPError as exc:
            error = f"upstream_stream_error:{type(exc).__name__}"
            gateway_logger.warning(f"[gateway] 上游流中断 lease={lease.lease_id}: {type(exc).__name__}")
            raise
        finally:
            # 生成器可能在取消上下文退出，不在 finally 中 await，改为调度后台收尾
            asyncio.create_task(
                _finalize_stream(
                    lease=lease,
                    grant=grant,
                    state=state,
                    model=model,
                    provider=provider,
                    status_code=upstream.status_code,
                    error=error,
                    response=upstream,
                )
            )

        if state.get("truncated"):
            try:
                await upstream.aclose()
            except Exception:
                pass
            yield _truncation_frames(grant)

    return StreamingResponse(
        relay(),
        status_code=upstream.status_code,
        headers=_response_headers(upstream, lease),
        media_type="text/event-stream",
    )
