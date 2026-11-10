"""app -> 编排代理（兼容期只代理、不双写）

- 仅 orchestration.mode=proxy 时启用，且只作用于 P1.2 已迁移的路径；
- 转发原始客户端凭据与查询参数，由 独立服务做业务鉴权；
- 下游不可达/超时统一 503 fail-closed，不回落到本进程查询、不返回空数据。
"""
from fastapi import Request
from fastapi.responses import JSONResponse

import httpx

from base.common.response import fail_response
from base.plugins.harness.services.orchestration_config import orchestration_config

DOWNSTREAM_UNAVAILABLE = "orchestration_downstream_unavailable"

_FORWARD_HEADERS = (
    "authorization",
    "x-harness-client-id",
    "x-harness-secret",
    "accept",
    "content-type",
    "user-agent",
    "x-request-id",
    "x-trace-id",
    "x-forwarded-for",
)


def proxy_mode_enabled() -> bool:
    return str(orchestration_config().get("mode") or "") == "proxy"


async def require_client_or_proxy(request: Request):
    """proxy 模式下跳过 app 本地鉴权/触达，交由编排处理；否则维持原逻辑。"""
    if proxy_mode_enabled():
        return None
    from base.plugins.harness.services.client_service import require_harness_client

    return await require_harness_client(request)


def _forward_headers(request: Request) -> dict:
    headers = {}
    for name in _FORWARD_HEADERS:
        value = request.headers.get(name)
        if value:
            headers[name] = value
    # 与 app 本地模式保持一致的客户端 IP 口径：
    # 有原始 X-Forwarded-For 则透传，否则用直连地址填充。
    if "x-forwarded-for" not in headers:
        headers["x-forwarded-for"] = request.client.host if request.client else ""
    return headers


async def proxy_to_orchestration(request: Request) -> JSONResponse:
    cfg = orchestration_config()
    base_url = str(cfg.get("public_base_url") or "").rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        return fail_response(
            data={
                "error_code": DOWNSTREAM_UNAVAILABLE,
                "downstream": "orchestration",
                "reason": "orchestration.public_base_url 未配置",
            },
            msg="编排服务不可用（未配置下游地址）",
            code=503,
            status_code=503,
        )

    path = request.url.path
    query = request.url.query
    url = f"{base_url}{path}" + (f"?{query}" if query else "")
    timeout = float(cfg.get("internal_timeout_seconds") or 5)
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                request.method,
                url,
                headers=_forward_headers(request),
                content=body if body else None,
            )
    except Exception as exc:
        return fail_response(
            data={
                "error_code": DOWNSTREAM_UNAVAILABLE,
                "downstream": "orchestration",
                "upstream": url,
                "reason": f"{type(exc).__name__}: {exc}",
            },
            msg="编排服务不可用（下游不可达或超时）",
            code=503,
            status_code=503,
        )

    try:
        content = response.json()
    except ValueError:
        content = {"code": response.status_code, "msg": response.text, "data": None}
    return JSONResponse(status_code=response.status_code, content=content)
