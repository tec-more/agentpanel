"""Harness 出网策略快照下发（L2 策略来源；不是执行边界）

客户端通过本接口拉取可版本化、可校验的出网策略快照：
- 200：快照（带 ETag / Cache-Control / 版本与哈希头），可缓存、可复算校验；
- 304：If-None-Match 命中，客户端继续使用本地缓存；
- 426：版本未知或低于最低支持版本，客户端必须 fail-closed 停止出网能力。

审计：
- 策略变更 -> egress.policy.changed（system / manifest）
- 快照下发 -> egress.policy.snapshot（client，含 304 命中）
- 版本不兼容 -> egress.policy.incompatible（client，decision=deny）
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status

from base.common.response import fail_response, success_response
from base.plugins.harness.services.client_service import require_harness_client
from base.plugins.harness.services.egress_policy_service import (
    EgressPolicyConfigError,
    EgressPolicyIncompatible,
    audit_incompatible,
    audit_snapshot,
    ensure_change_audited,
    snapshot,
)

egress_policy_router = APIRouter(prefix="/egress-policy", tags=["Harness-出网策略"])


def _normalize_etag(raw: Optional[str]) -> str:
    if not raw:
        return ""
    value = raw.strip()
    if value.startswith("W/"):
        value = value[2:]
    return value.strip().strip('"').strip()


def _cache_headers(data: Dict[str, Any]) -> Dict[str, str]:
    return {
        "ETag": f'"{data["content_hash"]}"',
        "Cache-Control": f"private, max-age={data['cache_ttl_seconds']}",
        "X-Egress-Policy-Version": str(data["policy_version"]),
        "X-Egress-Policy-Hash": data["content_hash"],
    }


@egress_policy_router.get("/snapshot", summary="拉取出网策略快照（客户端）")
async def get_egress_policy_snapshot(
    request: Request,
    client_version: Optional[str] = Query(
        None,
        description="客户端当前支持的策略版本（整数）；缺省、unknown 或无法解析时按 fail-closed 拒绝",
    ),
    client=Depends(require_harness_client),
):
    parsed_version: Optional[int]
    try:
        parsed_version = (
            None
            if client_version in (None, "", "unknown")
            else int(str(client_version).strip())
        )
    except (TypeError, ValueError):
        # 无法解析按「版本未知」处理，仍走统一的 fail-closed 拒绝路径
        parsed_version = None

    try:
        data = snapshot(parsed_version)
    except EgressPolicyConfigError as exc:
        return fail_response(
            data={"compatible": False, "fail_closed": True, "reason": "server_policy_config_invalid"},
            msg=f"出网策略配置非法，拒绝下发: {exc}",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except EgressPolicyIncompatible as exc:
        await audit_incompatible(client, request, exc, client_version=client_version)
        return fail_response(
            data=exc.to_dict(),
            msg=exc.message,
            code=status.HTTP_426_UPGRADE_REQUIRED,
            status_code=status.HTTP_426_UPGRADE_REQUIRED,
        )

    # 策略内容相对上次审计发生变化时留痕（进程内缓存哈希，避免每次请求查表）
    await ensure_change_audited()

    headers = _cache_headers(data)
    cache_hit = _normalize_etag(request.headers.get("if-none-match")) == data["content_hash"]
    await audit_snapshot(client, request, data, client_version=parsed_version, cache_hit=cache_hit)

    if cache_hit:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    response = success_response(data=data, msg="出网策略快照")
    response.headers.update(headers)
    return response
