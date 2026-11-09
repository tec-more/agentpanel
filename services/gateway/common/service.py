"""
内部网关数据面服务：出网白名单、请求净化、用量记账

约束：
- 不记录 prompt/response 正文；只记录用量与状态元数据；
- 真实 provider key 只在网关内存中出现，绝不回传客户端；
- usage_record 统一 source=gateway、gateway_key=租约 ID，供对账使用。
"""
import json
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .logging import gateway_logger

from .runtime import gateway_config
from packages.common.domain.pricing_service import ModelPriceService
from packages.common.models.quota import UsageRecord
from packages.common.upstream import EgressPolicy

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class GatewayProxyError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def strip_request_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """按合规要求剥离请求体字段（如 dsh_session_log），其余原样转发。"""
    fields = gateway_config().get("strip_request_fields") or []
    for name in fields:
        if name in body:
            body.pop(name, None)
    return body


def build_upstream_url(base_url: Optional[str]) -> str:
    cfg = gateway_config()
    base = str(cfg.get("upstream_base_url_override") or base_url or "").strip().rstrip("/")
    if not base:
        raise GatewayProxyError(502, "provider base_url 为空，网关拒绝转发")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def assert_egress_allowed(url: str) -> None:
    """出网按 provider 域名白名单限定（loopback 仅在显式 allow_loopback 时放行）。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise GatewayProxyError(403, "provider 地址协议不被允许")
    host = (parsed.hostname or "").lower()
    cfg = gateway_config()
    allow = {str(x).strip().lower() for x in (cfg.get("provider_domain_allowlist") or [])}
    if host in allow:
        return
    if cfg.get("allow_loopback") and host in LOOPBACK_HOSTS:
        return
    raise GatewayProxyError(403, f"provider 域名不在出网白名单: {host}")


def egress_policy() -> EgressPolicy:
    """共享客户端强制使用的出网策略（白名单为空则全部拒绝）。"""
    cfg = gateway_config()
    return EgressPolicy.from_allowlist(
        cfg.get("provider_domain_allowlist") or [],
        allow_loopback=bool(cfg.get("allow_loopback")),
    )


def extract_usage(usage: Any) -> Dict[str, int]:
    """兼容 DeepSeek/OpenAI usage 字段，返回统一口径。"""
    if not isinstance(usage, dict):
        return {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion))
    cache_read = int(
        usage.get("prompt_cache_hit_tokens")
        or usage.get("cache_read_input_tokens")
        or 0
    )
    detail = usage.get("completion_tokens_details") or {}
    reasoning = int(
        usage.get("reasoning_tokens")
        or (detail.get("reasoning_tokens") if isinstance(detail, dict) else 0)
        or 0
    )
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cache_read_tokens": min(cache_read, prompt),
        "reasoning_tokens": reasoning,
    }


async def resolve_upstream_credential(lease, body_model: Optional[str]):
    """解析真实 provider 凭据；失败即 fail-closed（不回退直连）。"""
    from packages.common.domain.credential_resolver import (
        ModelCredentialNotConfigured,
        resolve as resolve_model_credential,
    )

    try:
        return await resolve_model_credential(
            lease.provider, lease.model or body_model
        )
    except ModelCredentialNotConfigured as exc:
        raise GatewayProxyError(502, f"网关未配置可用 provider 凭据: {exc.message}")
    except Exception as exc:
        raise GatewayProxyError(502, f"网关凭据解析失败: {exc}")


async def record_gateway_usage(
    *,
    lease,
    usage: Optional[Dict[str, int]],
    model: Optional[str],
    provider: Optional[str],
    status_code: int,
    stream: bool,
    attempt: int = 1,
    error: Optional[str] = None,
    usage_kind: str = "normal",
    truncated: bool = False,
    truncation_reason: Optional[str] = None,
    estimated: bool = False,
    over_budget: bool = False,
) -> None:
    """落 usage_record（source=gateway）；失败请求也记，但金额为 0。

    额度截断记为 partial：resource_type 仍为 llm_token、金额为估算值，
    price_snapshot 明确标注 truncated/estimated/billing_status，禁止伪装成正常结束。
    """
    usage = usage or {}
    ok = status_code < 400 and error is None
    total = int(usage.get("total_tokens") or 0)
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    cache_read = int(usage.get("cache_read_tokens") or 0)
    amount = float(total) if ok else 0
    tokens_in = max(prompt - cache_read, 0)
    cost = Decimal("0")
    currency = "CNY"
    pricing: Dict[str, Any] = {}
    if ok and total > 0:
        # 计费口径见 reports/specs/l3-service-split/spec.md §14：
        # 输入（含缓存拆分）+ 输出按每 1K 计价，6 位四舍五入；缺价/归零只标记不改请求结果
        try:
            result = await ModelPriceService.estimate_cost(
                provider or lease.provider,
                model or lease.model,
                input_tokens=tokens_in,
                output_tokens=completion,
                cache_read_tokens=cache_read,
                cache_write_tokens=0,
                rounding_places=6,
            )
            cost = Decimal(str(result.get("cost") or 0))
            currency = result.get("currency") or "CNY"
            snap = result.get("price_snapshot")
            if result.get("missing_price") or not snap:
                pricing = {"missing_price": True}
            else:
                pricing = dict(snap)
                if cost == 0:
                    pricing["rounded_to_zero"] = True
                    pricing["unrounded_cost"] = result.get("unrounded_cost")
        except Exception as exc:
            # 价格解析失败同样不得影响数据面响应：按缺价记账
            gateway_logger.error(f"[gateway] 计费价格解析失败 lease={lease.lease_id}: {exc}")
            pricing = {"missing_price": True}
    idem = f"gw:{lease.lease_id}:{uuid.uuid4().hex[:20]}"
    snapshot: Dict[str, Any] = {
        "gateway_status": status_code,
        "stream": stream,
        "attempt": attempt,
        "usage_missing": ok and total <= 0,
        "error": error,
        "estimated": bool(estimated),
        "truncated": bool(truncated),
        "over_budget": bool(over_budget),
    }
    snapshot.update(pricing)
    if truncated:
        snapshot["truncation_reason"] = truncation_reason or "estimated_budget_exceeded"
        snapshot["billing_status"] = "partial"
    elif over_budget:
        snapshot["billing_status"] = "over_budget"
    try:
        await UsageRecord.create(
            owner_type=lease.owner_type or "usr",
            owner_id=lease.owner_id or 0,
            member_id=lease.member_id,
            execution_id=None,
            node_id="gateway",
            seq=0,
            resource_type="llm_token" if ok else "gateway_error",
            amount=amount,
            tokens_in=tokens_in,
            tokens_out=completion,
            cache_read_tokens=cache_read,
            cache_write_tokens=0,
            reasoning_tokens=int(usage.get("reasoning_tokens") or 0),
            cost=cost,
            currency=currency,
            source="gateway",
            gateway_key=lease.lease_id,
            usage_kind=usage_kind if ok else "normal",
            idem_key=idem,
            session_ref=lease.session_no,
            model=model or lease.model,
            provider=provider or lease.provider,
            price_snapshot=snapshot,
        )
    except Exception as exc:
        # 记账失败不得影响数据面响应，但要留日志供对账兜底
        gateway_logger.error(f"[gateway] usage_record 写入失败 lease={lease.lease_id}: {exc}")


def usage_from_sse_frame(data: bytes) -> Optional[Dict[str, int]]:
    """解析 SSE data 帧中的 usage；非 JSON/[DONE] 返回 None。"""
    text = data.strip()
    if not text or text == b"[DONE]":
        return None
    try:
        obj = json.loads(text)
    except Exception:
        return None
    if isinstance(obj, dict) and isinstance(obj.get("usage"), dict):
        return extract_usage(obj["usage"])
    return None


def output_chars_from_sse_frame(data: bytes) -> int:
    """统计增量输出字符数（content / reasoning / tool arguments），用于流式估算。"""
    text = data.strip()
    if not text or text == b"[DONE]":
        return 0
    try:
        obj = json.loads(text)
    except Exception:
        return 0
    if not isinstance(obj, dict):
        return 0
    chars = 0
    for choice in obj.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            continue
        content = delta.get("content")
        if isinstance(content, str):
            chars += len(content)
        reasoning = delta.get("reasoning_content")
        if isinstance(reasoning, str):
            chars += len(reasoning)
        for call in delta.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") or {}
            arguments = function.get("arguments") if isinstance(function, dict) else None
            if isinstance(arguments, str):
                chars += len(arguments)
    return chars
