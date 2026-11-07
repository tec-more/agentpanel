"""L3 编排业务路由的 Harness 客户端凭据校验（只读）

- 与 L2 `require_harness_client` 行为对齐：同样的请求头、Bearer 解析、401/403 文案与 IP 白名单；
- 区别：L3 只读 `harness_client`，不得写 `last_used_at`；
- `last_used_at` 由 L3 异步调用 L2 内部接口更新（best-effort，失败只记日志）。
"""
import asyncio
import hmac
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status

from base.plugins.harness.services.client_service import _client_ip, hash_secret
from base.plugins.harness.services.readonly_db import get_readonly_db


def _json_list(raw: Any) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        import json

        try:
            parsed = json.loads(raw)
        except ValueError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


async def _load_client(client_id: str) -> Optional[Dict[str, Any]]:
    row = await get_readonly_db().fetchrow(
        "SELECT client_id, secret_hash, status, allowed_ips, expires_at "
        "FROM harness_client WHERE client_id = $1",
        client_id,
    )
    if row is None:
        return None
    return {
        "client_id": row["client_id"],
        "secret_hash": row["secret_hash"],
        "status": row["status"],
        "allowed_ips": _json_list(row["allowed_ips"]),
        "expires_at": row["expires_at"],
    }


def _expired(row: Dict[str, Any]) -> bool:
    expires_at = row.get("expires_at")
    if expires_at is None:
        return False
    try:
        expires = expires_at.replace(tzinfo=None)
    except AttributeError:
        return True
    return expires <= datetime.now()


def _schedule_touch(client_id: str) -> None:
    from base.plugins.harness.services.l3_touch import touch_client_last_seen

    try:
        task = asyncio.create_task(touch_client_last_seen(client_id))
    except RuntimeError:
        return

    def _done(t: asyncio.Task) -> None:
        try:
            t.result()
        except Exception:
            pass

    task.add_done_callback(_done)


async def require_harness_client_readonly(request: Request) -> Dict[str, Any]:
    """L3 业务路由依赖：校验客户端凭据，不写 harness_client。"""
    header_id = request.headers.get("X-Harness-Client-Id")
    header_secret = request.headers.get("X-Harness-Secret")
    if header_id and header_secret:
        client_id, secret = header_id, header_secret
    else:
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if token and "." in token:
            client_id, secret = token.split(".", 1)
        else:
            client_id, secret = "", ""

    client = await _load_client(client_id) if client_id else None
    if client is None or client.get("status") != "active" or _expired(client):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Harness 客户端凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not hmac.compare_digest(client.get("secret_hash") or "", hash_secret(secret or "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Harness 客户端凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    allowed_ips = client.get("allowed_ips") or []
    if allowed_ips and _client_ip(request) not in allowed_ips:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="来源 IP 不在白名单")

    _schedule_touch(client["client_id"])
    request.state.harness_client = client
    request.state.harness_client_id = client["client_id"]
    return client
