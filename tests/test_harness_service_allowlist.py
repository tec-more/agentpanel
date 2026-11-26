"""内部服务凭据鉴权的来源白名单回归测试。

核心契约：来源白名单基于「已验签的 service_id（服务名）」，不再依赖客户端 IP。
这样容器重建后 IP 漂移不影响授权，且身份由 HMAC 签名保证不可伪造。

两份实现必须行为一致：
- base.plugins.harness.services.service_auth（app 侧内部额度/触达接口）
- services.orchestration.app.auth（独立编排侧内部接口，以别名 app_orchestration 导入）
"""
import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from packages.common.security import build_signature

# 编排进程以 `app.config` / `app.auth` 为内部模块名；仓库根下的 base.* 不冲突，
# 但需把 services/orchestration 加入 path 才能让 `app` 解析到编排包。
_ORCH_DIR = Path(__file__).resolve().parents[1] / "services" / "orchestration"
if str(_ORCH_DIR) not in sys.path:
    sys.path.insert(0, str(_ORCH_DIR))

TS = 1700000000
SECRET_HASH = "a" * 64
ALLOWED = "svc_orchestration"
BODY = b""
PATH = "/internal/probe"

MODULES = [
    "base.plugins.harness.services.service_auth",
    "app.auth",  # services/orchestration 下的编排鉴权（sys.path 注入后可见）
]


def _headers(service_id, *, ts=TS, sign=True):
    sig = build_signature(SECRET_HASH, str(ts), "GET", PATH, BODY) if sign else "bad"
    return {
        "x-service-id": service_id,
        "x-service-timestamp": str(ts),
        "x-service-signature": sig,
    }


def _app_and_credential(auth_mod):
    app = FastAPI()

    async def dependency(request: Request):
        try:
            return await auth_mod.authenticate(request)
        except auth_mod.ServiceAuthError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.status_code, "msg": exc.message, "data": exc.to_dict()},
            )

    @app.get(PATH)
    async def probe(identity=Depends(dependency)):
        return {"service_id": identity["service_id"]}

    credential = {
        "service_id": ALLOWED,
        "secret_hash": SECRET_HASH,
        "scopes": ["*"],
        "status": "active",
        "expires_at": None,
    }
    return app, credential


def _run(auth_mod, credential, headers, *, client_ip, allowed):
    app, _ = _app_and_credential(auth_mod)
    with patch.object(auth_mod, "internal_allowed_services", return_value=allowed), \
         patch.object(auth_mod, "auth_timestamp_window_seconds", return_value=600), \
         patch.object(auth_mod, "_load_credential", new=AsyncMock(return_value=credential)), \
         patch.object(auth_mod, "_write_reject_audit", new=AsyncMock()), \
         patch.object(auth_mod.time, "time", return_value=TS):
        with TestClient(app, client=(client_ip, 12345)) as instance:
            return instance.get(PATH, headers=headers)


@pytest.mark.parametrize("module_path", MODULES)
def test_allowlist_uses_verified_service_id_not_ip(module_path):
    """合法 service_id 放行；客户端 IP 任意（模拟容器 IP 漂移）。"""
    auth_mod = importlib.import_module(module_path)
    credential = {
        "service_id": ALLOWED,
        "secret_hash": SECRET_HASH,
        "scopes": ["*"],
        "status": "active",
        "expires_at": None,
    }
    resp = _run(auth_mod, credential, _headers(ALLOWED), client_ip="10.99.77.66", allowed=[ALLOWED])
    assert resp.status_code == 200
    assert resp.json()["service_id"] == ALLOWED


@pytest.mark.parametrize("module_path", MODULES)
def test_service_not_in_allowlist_rejected_even_with_valid_signature(module_path):
    """未授权 service_id 即使带合法签名也 403；回环 IP 也不放行。"""
    auth_mod = importlib.import_module(module_path)
    intruder = "svc_intruder"
    credential = {
        "service_id": intruder,
        "secret_hash": SECRET_HASH,
        "scopes": ["*"],
        "status": "active",
        "expires_at": None,
    }
    resp = _run(auth_mod, credential, _headers(intruder), client_ip="127.0.0.1", allowed=[ALLOWED])
    assert resp.status_code == 403
    assert resp.json()["detail"]["data"]["error_code"] == "service_auth_service_not_allowed"


@pytest.mark.parametrize("module_path", MODULES)
def test_no_legacy_ip_error_code(module_path):
    """旧的 IP 拒绝错误码必须彻底移除。"""
    auth_mod = importlib.import_module(module_path)
    assert not hasattr(auth_mod, "ERROR_IP")
    assert hasattr(auth_mod, "ERROR_SERVICE")
    assert auth_mod.ERROR_SERVICE == "service_auth_service_not_allowed"
