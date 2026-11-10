"""编排 -> app 客户端活跃时间上报（异步 best-effort）

- 编排不写 `harness_client`，只调用 app 内部接口；
- 失败（未配置服务凭据/app 不可达/超时）只记日志，不影响业务请求结果；
- app 内部接口用服务凭据认证，scope=clients:touch。
"""
import hashlib
import os
import time
from urllib.parse import quote

import httpx
from loguru import logger

from app.config import orchestration_config
from app.auth import build_signature

_WARNED_MISSING_SECRET = False


def _service_credentials():
    cfg = orchestration_config()
    service_id = str(cfg.get("app_service_id") or "").strip()
    secret_env = str(cfg.get("app_service_secret_env") or "").strip()
    secret = os.getenv(secret_env, "").strip() if secret_env else ""
    return service_id, secret


async def touch_client_last_seen(client_id: str) -> None:
    global _WARNED_MISSING_SECRET

    cfg = orchestration_config()
    base_url = str(cfg.get("app_internal_base_url") or "").rstrip("/")
    service_id, secret = _service_credentials()
    if not base_url or not service_id or not secret:
        if not _WARNED_MISSING_SECRET:
            logger.warning(
                "[orchestration] 未配置 app 服务凭据（app_service_id / 环境变量），跳过 last_seen 上报"
            )
            _WARNED_MISSING_SECRET = True
        return

    path = f"/internal/v1/harness/clients/{quote(client_id, safe='')}/touch"
    timestamp = str(int(time.time()))
    key = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    signature = build_signature(key, timestamp, "POST", path, b"")
    headers = {
        "X-Service-Id": service_id,
        "X-Service-Timestamp": timestamp,
        "X-Service-Signature": signature,
    }

    timeout = min(3, max(1, float(cfg.get("internal_timeout_seconds") or 3)))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(base_url + path, headers=headers)
        if response.status_code >= 400:
            logger.warning(
                "[orchestration] last_seen 上报失败: status=%s body=%s",
                response.status_code,
                response.text[:200],
            )
    except Exception as exc:
        logger.warning("[orchestration] last_seen 上报异常（已忽略）: %s: %s", type(exc).__name__, exc)
