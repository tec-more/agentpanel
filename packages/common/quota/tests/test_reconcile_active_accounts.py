"""活跃账户配额对账：逐条容错与异常清单测试。"""
import pytest

from packages.common.quota.services.quota_service import QuotaService


class _FakeAccount:
    def __init__(self):
        self.used = {}

    async def save(self):
        return None


class _FakeRedis:
    def __init__(self, owners, counters):
        self._owners = owners
        self._counters = counters

    async def smembers(self, key):
        return list(self._owners)

    async def scan_iter(self, match):
        for key in self._counters:
            yield key

    async def get(self, key):
        return self._counters.get(key, 0)


@pytest.mark.asyncio
async def test_reconcile_skips_bad_ident_and_continues(monkeypatch):
    owners = [
        "usr:4",
        "none:p3v_lease_ok_old",
        "usr:5",
        "bad-format",
        "org:",
    ]
    counters = {"quota:usr:4:token:2026-11": "100"}
    redis = _FakeRedis(owners, counters)
    account = _FakeAccount()
    ensured = []

    async def _fake_redis():
        return redis

    async def _fake_ensure(cls, ot, oid):
        ensured.append(f"{ot}:{oid}")
        if oid == 5:
            raise RuntimeError("db write failed")
        return account

    monkeypatch.setattr(QuotaService, "_redis", staticmethod(_fake_redis))
    monkeypatch.setattr(QuotaService, "ensure_account", classmethod(_fake_ensure))

    result = await QuotaService.reconcile_active_accounts()

    assert result["total"] == 5
    assert result["processed"] == 1
    assert result["skipped"] == 4
    assert ensured == ["usr:4", "usr:5"]
    assert account.used == {"token": 100.0}

    batch_no = result["batch_no"]
    assert batch_no.startswith("qrc")
    hold_ids = [item["hold_id"] for item in result["anomalies"]]
    assert hold_ids == ["none:p3v_lease_ok_old", "usr:5", "bad-format", "org:"]
    assert all(item["batch_no"] == batch_no for item in result["anomalies"])
    reasons = {item["hold_id"]: item["reason"] for item in result["anomalies"]}
    assert "owner_id 无法解析为整数" in reasons["none:p3v_lease_ok_old"]
    assert reasons["usr:5"] == "对账落盘失败"
    assert "标识格式不符" in reasons["bad-format"]
    assert "标识格式不符" in reasons["org:"]
