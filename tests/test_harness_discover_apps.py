"""发现应用目录（harness 插件）：后台 CRUD 与 CUS 只读下发的边界回归。

2026-11-26 从 customer 插件迁入 harness：路由前缀 /v1/harness，CUS 守卫取自
底座 base.common.authz（customer.services.cus_guard 保留为兼容再导出）。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from base.common.security import get_current_user_id
from base.plugins.harness.api.v1 import discover_app_router as router_module
from base.common.authz import require_customer

CUS = "/v1/harness/discover-apps"
ADMIN = "/v1/harness/admin/discover-apps"


def app_item(app_id=1, name="AgentPanel", **overrides):
    values = dict(
        id=app_id, name=name, description="后台管理", icon_text="AP", icon_color="#3366ff",
        open_mode="portal", target="/dashboard", sort=1, is_active=True,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def env():
    app = FastAPI()
    # 插件装配器只取文件的首个 router 变量，测试也只挂这一个聚合入口。
    app.include_router(router_module.discover_app_router, prefix="/v1/harness")
    with TestClient(app) as instance:
        yield instance, app
    app.dependency_overrides.clear()


def as_admin(app):
    app.dependency_overrides[get_current_user_id] = lambda: 7


def test_single_router_variable_aggregates_both_surfaces():
    assert len(router_module.discover_app_router.routes) == 2  # 两条子路由被首个 router 聚合
    paths = ({route.path for route in router_module.catalog_router.routes}
             | {route.path for route in router_module.admin_discover_app_router.routes})
    assert "/discover-apps" in paths
    assert "/admin/discover-apps" in paths
    assert "/admin/discover-apps/{app_id}/status" in paths


def test_cus_list_requires_authentication(env):
    instance, _ = env
    assert instance.get(CUS).status_code == 401


def test_cus_list_rejects_usr(env):
    instance, app = env
    from base.common.authz.context import require_owner
    app.dependency_overrides[require_owner] = lambda: SimpleNamespace(is_customer=False)
    assert instance.get(CUS).status_code == 403


def test_cus_list_returns_only_active_sorted_items(env):
    instance, app = env
    app.dependency_overrides[require_customer] = lambda: SimpleNamespace(is_customer=True)
    visible = [app_item(2, "B", sort=2), app_item(1, "A", sort=1)]
    chain = SimpleNamespace(order_by=lambda *args: SimpleNamespace(all=AsyncMock(return_value=visible)))
    with patch.object(router_module.CustomerDiscoverApp, "filter", new=lambda **kw: chain):
        response = instance.get(CUS)

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]["items"]] == ["B", "A"]
    assert set(response.json()["data"]["items"][0]) == {
        "id", "name", "description", "icon_text", "icon_color", "open_mode", "target", "sort", "is_active",
    }


def test_admin_requires_superuser(env):
    instance, app = env
    as_admin(app)
    with patch("base.core.users.services.user_service.UserService.get_by_id", new=AsyncMock(return_value=SimpleNamespace(is_superuser=False))):
        assert instance.get(ADMIN).status_code == 403


def test_admin_crud_and_validation(env):
    instance, app = env
    as_admin(app)
    user = SimpleNamespace(is_superuser=True)
    with patch("base.core.users.services.user_service.UserService.get_by_id", new=AsyncMock(return_value=user)):
        created = app_item()
        with patch.object(router_module.CustomerDiscoverApp, "create", new=AsyncMock(return_value=created)):
            response = instance.post(ADMIN, json={
                "name": "AgentPanel", "description": "后台管理", "icon_text": "AP",
                "open_mode": "portal", "target": "/dashboard", "sort": 1,
            })
        assert response.status_code == 200
        assert response.json()["data"]["id"] == 1

        # 外链协议白名单：普通 http 不允许（非回环）
        response = instance.post(ADMIN, json={"name": "Bad", "open_mode": "link", "target": "http://example.com"})
        assert response.status_code == 422

        # 站内路径不能是协议相对地址
        response = instance.post(ADMIN, json={"name": "Bad", "open_mode": "portal", "target": "//evil.com"})
        assert response.status_code == 422

        # 更新合并后完整校验：改成非法 link 必须被拒
        with patch.object(router_module.CustomerDiscoverApp, "get_or_none", new=AsyncMock(return_value=created)):
            response = instance.put(f"{ADMIN}/1", json={"open_mode": "link", "target": "ftp://x/y"})
            assert response.status_code == 422

        # 启停
        created.save = AsyncMock()
        with patch.object(router_module.CustomerDiscoverApp, "get_or_none", new=AsyncMock(return_value=created)):
            response = instance.patch(f"{ADMIN}/1/status", json={"is_active": False})
            assert response.status_code == 200
            assert response.json()["data"]["is_active"] is False
