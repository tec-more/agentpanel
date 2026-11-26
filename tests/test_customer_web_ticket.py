"""客户门户一次性 Web 登录票据端点回归测试。

验证边界：
- 签发只接受 cus 主体 JWT（拒绝 USR JWT 与未鉴权请求）；
- 消费是一次性的，重放被拒；
- 换发的是标准 cus JWT，与现有登录态完全一致。
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from base.common.security import get_current_actor
from base.plugins.customer.api.v1 import auth as auth_module
from base.plugins.customer.services import web_ticket_service as service_module

PREFIX = "/v1/customer"

VALID_TICKET = "a" * 43  # token_urlsafe(32) 的典型长度


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(auth_module.auth_router, prefix=PREFIX)
    with TestClient(app) as instance:
        yield instance, app
    app.dependency_overrides.clear()


def test_issue_requires_authentication(client):
    instance, _ = client
    assert instance.post(f"{PREFIX}/auth/web-ticket", json={}).status_code == 401


def test_issue_rejects_non_customer_subject(client):
    instance, app = client
    app.dependency_overrides[get_current_actor] = lambda: {"type": "usr", "id": "7"}
    response = instance.post(f"{PREFIX}/auth/web-ticket", json={})
    assert response.status_code == 403
    assert "仅客户账号" in response.json()["detail"]


def test_issue_returns_ticket_and_ttl(client):
    instance, app = client
    app.dependency_overrides[get_current_actor] = lambda: {"type": "cus", "id": "42"}
    customer = SimpleNamespace(id=42, email="a@example.com", is_active=True)
    with patch.object(service_module.WebTicketService, "issue", new=AsyncMock(return_value=(VALID_TICKET, 60))) as issue, \
         patch.object(service_module.WebTicketService, "audit", new=AsyncMock()), \
         patch("base.plugins.customer.models.customer.Customer.get_or_none", new=AsyncMock(return_value=customer)):
        response = instance.post(f"{PREFIX}/auth/web-ticket", json={"redirect_to": "/dashboard"})

    assert response.status_code == 200
    assert response.json()["data"]["ticket"] == VALID_TICKET
    assert response.json()["data"]["expires_in"] == 60
    assert issue.call_args.kwargs["customer_id"] == 42


def test_exchange_reject_replay(client):
    instance, _ = client
    record = SimpleNamespace(
        customer_id=42,
        redirect_to="/dashboard",
        token_hash="hash",
        consumed_at=None,
        expires_at=datetime.utcnow() + timedelta(seconds=30),
    )
    with patch.object(service_module.WebTicketService, "exchange", new=AsyncMock(side_effect=service_module.WebTicketError("replayed"))), \
         patch.object(service_module.WebTicketService, "audit", new=AsyncMock()):
        response = instance.post(f"{PREFIX}/auth/web-ticket/exchange", json={"ticket": VALID_TICKET})

    assert response.status_code == 400  # 统一失败响应（业务失败码），不泄漏原因
    assert response.json()["success"] is False


def test_exchange_issues_cus_jwt(client):
    instance, _ = client
    record = SimpleNamespace(customer_id=42, redirect_to="/profile", token_hash="hash")
    customer = SimpleNamespace(id=42, email="a@example.com", is_active=True, to_dict=AsyncMock(return_value={"id": 42}))
    with patch.object(service_module.WebTicketService, "exchange", new=AsyncMock(return_value=record)), \
         patch.object(service_module.WebTicketService, "audit", new=AsyncMock()), \
         patch("base.plugins.customer.models.customer.Customer.get_or_none", new=AsyncMock(return_value=customer)):
        response = instance.post(f"{PREFIX}/auth/web-ticket/exchange", json={"ticket": VALID_TICKET})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["redirect_to"] == "/profile"
    assert data["expires_in"] == 86400
    assert data["access_token"]


def test_safe_redirect_rejects_external_urls():
    assert service_module.safe_redirect("//evil.example/path") == "/dashboard"
    assert service_module.safe_redirect("https://evil.example") == "/dashboard"
    assert service_module.safe_redirect("/dashboard\\evil") == "/dashboard"
    assert service_module.safe_redirect("/profile?tab=1") == "/profile?tab=1"


def test_naive_utc_normalizes_aware_and_naive():
    """openGauss 读回的 aware 时间必须与 utcnow() 可比，且保留墙上时钟值。

    写入用 utcnow()（UTC naive），openGauss 读回会 attach 本地时区（如 +08:00），
    但数值仍是写入时的 UTC 时钟值，所以只能剥 tzinfo，不能 astimezone 转换。
    """
    # 模拟 openGauss 读回：UTC 时钟值 +08:00 时区
    wall_utc = datetime.utcnow() + timedelta(seconds=30)
    aware = wall_utc.replace(tzinfo=timezone(timedelta(hours=8)))
    normalized = service_module._naive_utc(aware)
    assert normalized.tzinfo is None
    # 关键：剥时区后仍等于原 UTC 时钟值，不因 +08:00 被减掉 8 小时
    assert normalized == wall_utc

    naive = datetime.utcnow() + timedelta(seconds=30)
    assert service_module._naive_utc(naive) is naive  # naive 原样返回


def test_exchange_accepts_aware_expires_at(client):
    """回归用户报错：消费时 awareness 混用导致 500。"""
    aware_future = (datetime.utcnow() + timedelta(seconds=30)).replace(
        tzinfo=timezone(timedelta(hours=8)))  # openGauss 读回 attach +08:00
    record = SimpleNamespace(
        id=1, customer_id=42, redirect_to="/dashboard", token_hash="hash",
        consumed_at=None, expires_at=aware_future,
    )
    with patch.object(service_module.CustomerWebTicket, "get_or_none", new=AsyncMock(return_value=record)), \
         patch.object(service_module.CustomerWebTicket, "filter") as mock_filter:
        mock_filter.return_value.update = AsyncMock(return_value=1)
        result = asyncio.run(service_module.WebTicketService.exchange("a" * 43))
    assert result is record
