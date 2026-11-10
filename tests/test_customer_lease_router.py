"""客户账号直签网关租约端点回归测试。

验证边界：网关数据面只接受 ``dgw.*`` 虚拟 key、业务接口只接受 JWT，
因此桌面端必须用 customer JWT 换一张绑定 ``cus`` 主体的租约，
且非客户主体不能借用该端点。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from base.common.security import get_current_actor
from base.plugins.customer.api.v1 import lease_router as lease_module

PREFIX = "/v1/customer"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(lease_module.lease_router, prefix=PREFIX)
    with TestClient(app) as instance:
        yield instance, app
    app.dependency_overrides.clear()


def test_requires_authentication(client):
    instance, _ = client
    response = instance.post(f"{PREFIX}/leases", json={})
    assert response.status_code == 401


def test_rejects_non_customer_subject(client):
    instance, app = client
    app.dependency_overrides[get_current_actor] = lambda: {"type": "usr", "id": "7"}
    response = instance.post(f"{PREFIX}/leases", json={})
    assert response.status_code == 403
    assert "仅客户账号" in response.json()["detail"]


def test_issues_lease_bound_to_customer(client):
    instance, app = client
    app.dependency_overrides[get_current_actor] = lambda: {"type": "cus", "id": "42"}
    shim = SimpleNamespace(client_id="cus:42", status="active")
    lease = {
        "lease_id": "L1",
        "virtual_key": "dgw.L1.s",
        "owner_type": "cus",
        "owner_id": 42,
    }
    with patch.object(lease_module, "_customer_client", new=AsyncMock(return_value=shim)), \
         patch.object(lease_module.GatewayLeaseService, "issue", new=AsyncMock(return_value=lease)) as issue:
        response = instance.post(f"{PREFIX}/leases", json={"ttl_seconds": 900})

    assert response.status_code == 200
    assert response.json()["data"] == lease
    assert issue.call_args.kwargs["owner_override"] == ("cus", 42)
    assert issue.call_args.args[0].client_id == "cus:42"


def test_renew_and_revoke_scope_to_the_same_customer(client):
    instance, app = client
    app.dependency_overrides[get_current_actor] = lambda: {"type": "cus", "id": "42"}
    shim = SimpleNamespace(client_id="cus:42", status="active")
    with patch.object(lease_module, "_customer_client", new=AsyncMock(return_value=shim)), \
         patch.object(lease_module.GatewayLeaseService, "renew", new=AsyncMock(return_value={"lease_id": "L1"})) as renew, \
         patch.object(lease_module.GatewayLeaseService, "revoke", new=AsyncMock(return_value={"lease_id": "L1"})) as revoke:
        renewed = instance.post(f"{PREFIX}/leases/L1/renew", json={})
        revoked = instance.delete(f"{PREFIX}/leases/L1")

    assert renewed.status_code == 200
    assert revoked.status_code == 200
    assert renew.call_args.args[1].client_id == "cus:42"
    assert revoke.call_args.args[1] == "cus:42"
