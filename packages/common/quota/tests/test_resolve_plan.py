"""套餐解析：绑定优先、账户 plan_id 回落的四种组合。"""
import pytest

import packages.common.quota.services.plan_service as plan_service


class _FakePlan:
    def __init__(self, pid: int, status: str = "active"):
        self.id = pid
        self.status = status


class _FakeRow:
    def __init__(self, plan):
        self.plan = plan


class _Chain:
    """模拟 Tortoise 查询链：order_by/prefetch_related 可链式，可 await，可 first。"""

    def __init__(self, rows):
        self._rows = rows

    def order_by(self, *args):
        return self

    def prefetch_related(self, *args):
        return self

    def __await__(self):
        async def _rows():
            return self._rows

        return _rows().__await__()

    async def first(self):
        return self._rows[0] if self._rows else None


class _BindingStub:
    BIND_TYPE_MEMBERSHIP_LEVEL = "membership_level"
    BIND_TYPE_ROLE = "role"
    BIND_TYPE_ORGANIZATION = "organization"

    def __init__(self, rows):
        self.rows = rows

    def filter(self, **kwargs):
        return _Chain(self.rows)


class _AccountStub:
    def __init__(self, account):
        self.account = account

    def filter(self, **kwargs):
        return _Chain([self.account] if self.account else [])


def _patch(monkeypatch, bindings, account):
    monkeypatch.setattr(plan_service, "QuotaPlanBinding", _BindingStub(bindings))
    monkeypatch.setattr(plan_service, "QuotaAccount", _AccountStub(account))


@pytest.mark.asyncio
async def test_account_plan_only(monkeypatch):
    plan_a = _FakePlan(101)
    _patch(monkeypatch, [], _FakeRow(plan_a))
    result = await plan_service.PlanService.resolve_plan("org", 14)
    assert result is plan_a


@pytest.mark.asyncio
async def test_binding_only(monkeypatch):
    plan_b = _FakePlan(202)
    _patch(monkeypatch, [_FakeRow(plan_b)], None)
    result = await plan_service.PlanService.resolve_plan("org", 14)
    assert result is plan_b


@pytest.mark.asyncio
async def test_binding_wins_when_both_differ(monkeypatch):
    plan_a = _FakePlan(101)
    plan_b = _FakePlan(202)
    _patch(monkeypatch, [_FakeRow(plan_b)], _FakeRow(plan_a))
    result = await plan_service.PlanService.resolve_plan("org", 14)
    assert result is plan_b


@pytest.mark.asyncio
async def test_none_when_neither_source(monkeypatch):
    _patch(monkeypatch, [], None)
    result = await plan_service.PlanService.resolve_plan("org", 14)
    assert result is None
