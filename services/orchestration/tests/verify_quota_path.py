#!/usr/bin/env python3
"""编排→app 配额链路定向回归（2026-11-10 改名后补测，第二项）。

`verify_write_path.py` 刻意走 0 token 绕开了预占/结算；本脚本专门补这一段：
经真实业务入口（建运行）触发 `app_quota_client` → app 内部额度 API 的
reserve / settle / release，验证 hold、用量流水、账户计数与 Redis 键。

覆盖：
- 预占：`reserved_tokens>0` 建运行 → `quota_reservation` 落行、Redis `quota_held` 增加
- 结算：complete 带 usage → `usage_record` 落行（amount/idem_key/source 口径）、
  账户 `used` 推进、hold 归零
- 释放：start 后 cancel → 预占行置 released、不产生用量流水、hold 归零
- 超限：申请额度远超套餐 → 429 `quota_exceeded`，且不落 run / 不落预占

fixture 隔离（仿 `services/gateway/tests/plan_golden.py`）：
临时 plan + role + binding + user + harness_client，全部 `eq_` 前缀（`user.username` 只有
varchar(20)，名字必须短）；`finally` 里删 DB 行与 Redis 键，并断言残留为 0。跑完请复核
`observe_check.py` 仍是 `used 3 键基线一致 / held 全 0`。

用法（必须**在 orchestration 容器内**执行）：
    docker exec -i agentpanel-orchestration python - < services/orchestration/tests/verify_quota_path.py

退出码：存在 FAIL 返回 1，否则 0。
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import httpx
import redis.asyncio as aioredis

ORCH_BASE = os.environ.get("ORCH_BASE", "http://127.0.0.1:9100")
PREFIX = "eq_"
PLAN_TOKENS = 10000
RESERVE_A = (1000, 500)   # → 1500
SETTLE_A = (100, 50)      # → amount 150
RESERVE_B = (1200, 800)   # → 2000

results: List[Tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, "PASS" if ok else "FAIL", detail))
    return ok


# ---------------------------------------------------------------- 连接


def _secret(name: str) -> str:
    path = os.environ.get(f"{name}_FILE")
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    return os.environ.get(name, "")


async def connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=_secret("DB_PASSWORD"),
        database=os.environ["DB_NAME"],
    )


def redis_client() -> Optional[aioredis.Redis]:
    if str(os.environ.get("REDIS_ENABLED", "true")).lower() in ("0", "false", "no"):
        return None
    return aioredis.Redis(
        host=os.environ.get("REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=_secret("REDIS_PASSWORD") or None,
        db=int(os.environ.get("REDIS_DB", 0)),
        decode_responses=True,
    )


# ---------------------------------------------------------------- fixture


async def build_fixture(conn: asyncpg.Connection, tag: str, secret: str) -> Dict[str, Any]:
    fx: Dict[str, Any] = {"client_id": PREFIX + "c_" + tag}
    fx["plan_id"] = await conn.fetchval(
        "INSERT INTO quota_plan (code,name,scope,quota_items,status) "
        "VALUES ($1,$2,'usr',$3::jsonb,'active') RETURNING id",
        PREFIX + "plan_" + tag, PREFIX + "plan_" + tag, json.dumps({"token": PLAN_TOKENS}),
    )
    fx["role_code"] = PREFIX + "role_" + tag
    fx["binding_id"] = await conn.fetchval(
        "INSERT INTO quota_plan_binding (bind_type,bind_key,priority,plan_id) "
        "VALUES ('role',$1,1,$2) RETURNING id",
        fx["role_code"], fx["plan_id"],
    )
    fx["role_id"] = await conn.fetchval(
        "INSERT INTO role (name,code,is_active) VALUES ($1,$1,true) RETURNING id",
        fx["role_code"],
    )
    fx["user_id"] = await conn.fetchval(
        'INSERT INTO "user" (username,email,is_active) VALUES ($1,$2,true) RETURNING id',
        PREFIX + "user_" + tag, PREFIX + "user_" + tag + "@example.local",
    )
    await conn.execute("INSERT INTO user_role (user_id,role_id) VALUES ($1,$2)",
                       fx["user_id"], fx["role_id"])
    await conn.execute(
        "INSERT INTO harness_client "
        "(client_id,name,secret_hash,secret_prefix,status,scopes,allowed_ips) "
        "VALUES ($1,$2,$3,$4,'active',$5::jsonb,NULL)",
        fx["client_id"], "e2e 配额链路回归（临时）",
        hashlib.sha256(secret.encode("utf-8")).hexdigest(), secret[:8], json.dumps([]),
    )
    return fx


async def cleanup(conn: asyncpg.Connection, fx: Dict[str, Any]) -> Dict[str, int]:
    uid, cid = fx["user_id"], fx["client_id"]
    deleted: Dict[str, int] = {}
    steps: Tuple[Tuple[str, str, Tuple[Any, ...]], ...] = (
        ("usage_record", "owner_type='usr' AND owner_id=$1", (uid,)),
        ("quota_reservation", "owner_type='usr' AND owner_id=$1", (uid,)),
        ("quota_account", "owner_type='usr' AND owner_id=$1", (uid,)),
        ("harness_approval_request", "client_id=$1", (cid,)),
        ("harness_step", "run_no IN (SELECT run_no FROM harness_run WHERE client_id=$1)", (cid,)),
        ("harness_audit_event", "client_id=$1", (cid,)),
        ("harness_run", "client_id=$1", (cid,)),
        ("harness_session", "client_id=$1", (cid,)),
        ("harness_client", "client_id=$1", (cid,)),
        ("user_role", "user_id=$1", (uid,)),
        ("role", "id=$1", (fx["role_id"],)),
        ("quota_plan_binding", "id=$1", (fx["binding_id"],)),
        ("quota_plan", "id=$1", (fx["plan_id"],)),
        ('"user"', "id=$1", (uid,)),
    )
    for table, where, params in steps:
        try:
            tag = await conn.execute(f"DELETE FROM {table} WHERE {where}", *params)
            deleted[table] = int(tag.split()[-1]) if tag else 0
        except asyncpg.PostgresError as exc:
            deleted[table] = -1
            print(f"  [cleanup] {table} 跳过：{type(exc).__name__}: {exc}")
    return deleted


async def residue(conn: asyncpg.Connection, fx: Dict[str, Any]) -> Dict[str, int]:
    uid, cid = fx["user_id"], fx["client_id"]
    counts = {}
    for table, col, val in (
        ("usage_record", "owner_id", uid),
        ("quota_reservation", "owner_id", uid),
        ("quota_account", "owner_id", uid),
        ("harness_client", "client_id", cid),
    ):
        counts[table] = int(await conn.fetchval(
            f"SELECT count(*) FROM {table} WHERE {col}=$1", val) or 0)
    return counts


# ---------------------------------------------------------------- HTTP


class Api:
    def __init__(self, base: str, client: httpx.AsyncClient, cid: str, secret: str) -> None:
        self.base = base.rstrip("/")
        self.client = client
        self.headers = {"X-Harness-Client-Id": cid, "X-Harness-Secret": secret}

    async def get(self, path: str) -> Tuple[int, Dict[str, Any]]:
        r = await self.client.get(f"{self.base}{path}", headers=self.headers)
        return r.status_code, self._json(r)

    async def post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any]]:
        r = await self.client.post(f"{self.base}{path}", json=body or {}, headers=self.headers)
        return r.status_code, self._json(r)

    @staticmethod
    def _json(r: httpx.Response) -> Dict[str, Any]:
        try:
            return r.json()
        except ValueError:
            return {"_raw": r.text[:200]}


def data_of(p: Dict[str, Any]) -> Any:
    return p.get("data")


async def held_of(rds: Optional[aioredis.Redis], uid: int, period: str) -> Optional[float]:
    if rds is None:
        return None
    val = await rds.get(f"quota_held:usr:{uid}:token:{period}")
    return float(val or 0)


# ---------------------------------------------------------------- 主流程


async def main() -> int:
    tag = secrets.token_hex(4)
    secret = secrets.token_hex(16)
    conn = await connect()
    rds = redis_client()
    started = time.time()
    fx: Dict[str, Any] = {"user_id": 0, "client_id": PREFIX + "c_" + tag, "role_id": 0,
                          "binding_id": 0, "plan_id": 0}

    print(f"配额链路回归  {datetime.datetime.now().astimezone():%Y-%m-%d %H:%M:%S %z}")
    print(f"fixture tag = {tag}\n")

    try:
        fx = await build_fixture(conn, tag, secret)
        uid = fx["user_id"]

        async with httpx.AsyncClient(timeout=25.0) as http:
            api = Api(ORCH_BASE, http, fx["client_id"], secret)

            # ---- 会话（owner=usr/uid，保证预占走用户账）
            status, body = await api.post("/v1/harness/sessions",
                                          {"client_id": fx["client_id"], "user_id": uid})
            session = data_of(body) or {}
            session_no = str(session.get("session_no") or "")
            # 响应体不含 owner 字段（session_to_dict 未序列化），归属以库为准
            sess_row = await conn.fetchrow(
                "SELECT owner_type, owner_id FROM harness_session WHERE session_no=$1", session_no)
            check("会话创建且归属 usr",
                  status == 200 and sess_row is not None
                  and sess_row["owner_type"] == "usr" and int(sess_row["owner_id"]) == uid,
                  f"HTTP {status} owner={sess_row['owner_type'] if sess_row else None}/"
                  f"{sess_row['owner_id'] if sess_row else None} 期望 usr/{uid}")

            # ---- A. 预占
            status, body = await api.post(
                f"/v1/harness/sessions/{session_no}/runs",
                {"task_type": "agent", "estimated_input_tokens": RESERVE_A[0],
                 "max_output_tokens": RESERVE_A[1]},
            )
            run_a = data_of(body) or {}
            run_a_no = str(run_a.get("run_no") or "")
            hold_a = str(run_a.get("hold_id") or "")
            check("A 建运行触发预占 200", status == 200, f"HTTP {status} msg={body.get('msg')}")
            check("A reserved_tokens=1500", int(run_a.get("reserved_tokens") or 0) == 1500,
                  f"reserved={run_a.get('reserved_tokens')}")
            check("A hold_id 形如 orch:hr_", hold_a.startswith("orch:hr_"), hold_a or "(空)")

            res_a = await conn.fetchrow(
                "SELECT status, items, original_items, owner_type, owner_id, period "
                "FROM quota_reservation WHERE hold_id=$1", hold_a)
            check("A 预占行落库且 owner 正确",
                  res_a is not None and res_a["owner_type"] == "usr" and int(res_a["owner_id"]) == uid,
                  f"status={res_a['status'] if res_a else None}")
            items_a = json.loads(res_a["items"]) if res_a and isinstance(res_a["items"], str) else (
                res_a["items"] if res_a else {})
            check("A 预占额度 1500 token", float((items_a or {}).get("token") or 0) == 1500,
                  f"items={items_a}")
            period = (res_a["period"] if res_a else "") or datetime.datetime.now().strftime("%Y-%m")

            held_a = await held_of(rds, uid, period)
            check("A Redis quota_held 增加 1500",
                  held_a is None or held_a == 1500, f"held={held_a}（None=Redis 未启用，跳过）")
            used_before = int(await conn.fetchval(
                "SELECT count(*) FROM usage_record WHERE owner_type='usr' AND owner_id=$1", uid) or 0)
            check("A 预占阶段无用量流水", used_before == 0, f"rows={used_before}")

            # ---- 结算
            status, body = await api.post(f"/v1/harness/runs/{run_a_no}/start")
            check("A 启动运行 running", status == 200 and
                  (data_of(body) or {}).get("status") == "running", f"HTTP {status}")
            status, body = await api.post(
                f"/v1/harness/runs/{run_a_no}/complete",
                {"status": "succeeded", "usage": [{
                    "node_id": "n1", "seq": 1,
                    "tokens_in": SETTLE_A[0], "tokens_out": SETTLE_A[1],
                }]},
            )
            check("A 结束运行 succeeded", status == 200 and
                  (data_of(body) or {}).get("status") == "succeeded", f"HTTP {status}")

            usage = await conn.fetchrow(
                "SELECT amount, resource_type, idem_key, source, tokens_in, tokens_out "
                "FROM usage_record WHERE owner_type='usr' AND owner_id=$1 ORDER BY id DESC LIMIT 1", uid)
            check("A 用量流水 amount=150 token",
                  usage is not None and float(usage["amount"]) == 150.0
                  and usage["resource_type"] == "token",
                  f"amount={usage['amount'] if usage else None} type={usage['resource_type'] if usage else None}")
            check("A 流水幂等键 orch: 前缀且来源 client",
                  usage is not None and str(usage["idem_key"]).startswith("orch:") and usage["source"] == "client",
                  f"idem={usage['idem_key'] if usage else None} source={usage['source'] if usage else None}")

            # 结算语义：预占 1500、实际 150 → 先 partial 结算，再由 complete 释放剩余 → released
            res_a2 = await conn.fetchrow(
                "SELECT status, settled_at, released_at, used_items FROM quota_reservation WHERE hold_id=$1",
                hold_a)
            used_items = res_a2["used_items"] if res_a2 else {}
            if isinstance(used_items, str):
                used_items = json.loads(used_items or "{}")
            check("A 预占行结算后释放（partial→released）",
                  res_a2 is not None and res_a2["status"] == "released"
                  and res_a2["released_at"] is not None,
                  f"status={res_a2['status'] if res_a2 else None} "
                  f"settled_at={res_a2['settled_at'] if res_a2 else None}"
                  f"（partial 结算按现有实现不写 settled_at，只写 released_at）")
            check("A 预占行记账 used_items=150",
                  float((used_items or {}).get("token") or 0) == 150.0, f"used_items={used_items}")

            # redis 模式下实时计数在 Redis，DB quota_account.used 由对账周期回填
            acc = await conn.fetchrow(
                "SELECT used FROM quota_account WHERE owner_type='usr' AND owner_id=$1", uid)
            check("A 账户行已建立", acc is not None, f"used={acc['used'] if acc else None}")
            if rds is not None:
                used_redis = await rds.get(f"quota:usr:{uid}:token:{period}")
                check("A Redis used 推进到 150", float(used_redis or 0) == 150.0,
                      f"used={used_redis}")

            held_after = await held_of(rds, uid, period)
            check("A 结算后 held 归零", held_after is None or held_after == 0, f"held={held_after}")

            # ---- B. 预占 → 取消释放
            status, body = await api.post(
                f"/v1/harness/sessions/{session_no}/runs",
                {"task_type": "agent", "estimated_input_tokens": RESERVE_B[0],
                 "max_output_tokens": RESERVE_B[1]},
            )
            run_b = data_of(body) or {}
            run_b_no = str(run_b.get("run_no") or "")
            hold_b = str(run_b.get("hold_id") or "")
            check("B 第二次预占 2000", status == 200 and int(run_b.get("reserved_tokens") or 0) == 2000,
                  f"HTTP {status} reserved={run_b.get('reserved_tokens')}")
            held_b = await held_of(rds, uid, period)
            check("B Redis held 增至 2000", held_b is None or held_b == 2000, f"held={held_b}")

            await api.post(f"/v1/harness/runs/{run_b_no}/start")
            status, body = await api.post(f"/v1/harness/runs/{run_b_no}/cancel?reason=e2e")
            check("B 取消运行 cancelled", status == 200 and
                  (data_of(body) or {}).get("status") == "cancelled", f"HTTP {status}")

            res_b = await conn.fetchrow("SELECT status, released_at FROM quota_reservation WHERE hold_id=$1", hold_b)
            check("B 预占行转 released", res_b is not None and res_b["status"] == "released"
                  and res_b["released_at"] is not None,
                  f"status={res_b['status'] if res_b else None}")
            usage_b = int(await conn.fetchval(
                "SELECT count(*) FROM usage_record WHERE session_ref=$1", session_no) or 0)
            check("B 取消的运行无用量流水", usage_b == 1, f"会话流水 {usage_b} 行（应为 A 的 1 行）")
            held_b2 = await held_of(rds, uid, period)
            check("B 释放后 held 归零", held_b2 is None or held_b2 == 0, f"held={held_b2}")

            # ---- C. 超限
            runs_before = int(await conn.fetchval(
                "SELECT count(*) FROM harness_run WHERE client_id=$1", fx["client_id"]) or 0)
            status, body = await api.post(
                f"/v1/harness/sessions/{session_no}/runs",
                {"task_type": "agent", "estimated_input_tokens": 10 ** 9, "max_output_tokens": 0},
            )
            err = data_of(body) or {}
            check("C 超额申请 → 429 quota_exceeded",
                  status == 429 and err.get("error_code") == "quota_exceeded",
                  f"HTTP {status} code={err.get('error_code')} remaining={err.get('remaining')}")
            runs_after = int(await conn.fetchval(
                "SELECT count(*) FROM harness_run WHERE client_id=$1", fx["client_id"]) or 0)
            check("C 超限不落 run", runs_after == runs_before, f"{runs_before} → {runs_after}")
            holds_total = int(await conn.fetchval(
                "SELECT count(*) FROM quota_reservation WHERE owner_type='usr' AND owner_id=$1", uid) or 0)
            check("C 超限不落预占", holds_total == 2, f"reservation 行数={holds_total}")

    finally:
        if fx.get("user_id"):
            deleted = await cleanup(conn, fx)
            print("\n清理： " + ", ".join(f"{k}={v}" for k, v in deleted.items()))
            left = await residue(conn, fx)
            check("清理后 DB 无残留", all(v == 0 for v in left.values()), f"{left}")
            if rds is not None:
                keys = []
                async for k in rds.scan_iter(match=f"*:usr:{fx['user_id']}:*"):
                    keys.append(k)
                if keys:
                    await rds.delete(*keys)
                rest = [k async for k in rds.scan_iter(match=f"*:usr:{fx['user_id']}:*")]
                check("清理后 Redis 无残留", not rest, f"{rest}")
        await conn.close()
        if rds is not None:
            await rds.aclose()

    width = max(len(n) for n, _, _ in results) + 2
    print("\n" + "-" * (width + 12 + 36))
    for name, state, detail in results:
        print(f"{name:<{width}}{state:<6}{detail}")
    print("-" * (width + 12 + 36))
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = len(results) - passed
    print(f"结论 {'PASS' if failed == 0 else 'FAIL'}  PASS={passed} FAIL={failed}  用时 {time.time() - started:.1f}s")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
