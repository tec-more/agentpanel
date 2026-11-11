#!/usr/bin/env python3
"""编排额度中立回归（2026-11-11 计量契约调整后）。

计量契约：真实模型用量与额度扣减**只由网关**完成；编排不再做
reserve / settle / release，也不写 usage_record。

本脚本验证：
- 建运行即使带 estimated_input_tokens / max_output_tokens，也不产生 quota_reservation 与 Redis 预占键；
- complete 带 usage 不产生 usage_record、不推进 Redis used / quota_account；
- events 里的 usage 只落 harness_step 明细，不记账；
- cancel 无预占可释放，仍保持幂等；
- 清理后 DB / Redis 无残留。

fixture 隔离（仿 `services/gateway/tests/plan_golden.py`）：
临时 plan + role + binding + user + harness_client，全部 `eq_` 前缀
（`user.username` 只有 varchar(20)，名字必须短）；`finally` 里删 DB 行与 Redis 键，
并断言残留为 0。跑完请复核 `observe_check.py` 仍是 `used 基线一致 / held 全 0`。

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
RESERVE_A = (1000, 500)   # 运行 A 上报的预估输入 + 最大输出（旧实现会预占 1500）
SETTLE_A = (100, 50)      # 运行 A 上报的真实用量（旧实现会写 150）

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
        fx["client_id"], "e2e 额度中立回归（临时）",
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
        ("harness_run", "client_id", cid),
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


def period() -> str:
    return datetime.datetime.now().strftime("%Y-%m")


async def quota_keys(rds: Optional[aioredis.Redis], uid: int) -> Tuple[Optional[float], Optional[float]]:
    if rds is None:
        return None, None
    used = await rds.get(f"quota:usr:{uid}:token:{period()}")
    held = await rds.get(f"quota_held:usr:{uid}:token:{period()}")
    return float(used or 0), float(held or 0)


# ---------------------------------------------------------------- 主流程


async def main() -> int:
    tag = secrets.token_hex(4)
    secret = secrets.token_hex(16)
    conn = await connect()
    rds = redis_client()
    started = time.time()
    fx: Dict[str, Any] = {"user_id": 0, "client_id": PREFIX + "c_" + tag, "role_id": 0,
                          "binding_id": 0, "plan_id": 0}

    print(f"编排额度中立回归  {datetime.datetime.now().astimezone():%Y-%m-%d %H:%M:%S %z}")
    print(f"fixture tag = {tag}\n")

    try:
        fx = await build_fixture(conn, tag, secret)
        uid = fx["user_id"]

        async with httpx.AsyncClient(timeout=25.0) as http:
            api = Api(ORCH_BASE, http, fx["client_id"], secret)

            # ---- 会话（owner=usr/uid；即使挂了 10000 token 套餐也不应预占）
            status, body = await api.post("/v1/harness/sessions",
                                          {"client_id": fx["client_id"], "user_id": uid})
            session_no = str((data_of(body) or {}).get("session_no") or "")
            sess_row = await conn.fetchrow(
                "SELECT owner_type, owner_id FROM harness_session WHERE session_no=$1", session_no)
            check("会话创建且归属 usr",
                  status == 200 and sess_row is not None
                  and sess_row["owner_type"] == "usr" and int(sess_row["owner_id"]) == uid,
                  f"HTTP {status} owner={sess_row['owner_type'] if sess_row else None}/"
                  f"{sess_row['owner_id'] if sess_row else None} 期望 usr/{uid}")

            # ---- A. 建运行：带预估输入/输出，但不应预占
            status, body = await api.post(
                f"/v1/harness/sessions/{session_no}/runs",
                {"estimated_input_tokens": RESERVE_A[0], "max_output_tokens": RESERVE_A[1],
                 "model": "deepseek-chat", "provider": "deepseek"},
            )
            run_a = data_of(body) or {}
            run_a_no = str(run_a.get("run_no") or "")
            check("A 建运行 200", status == 200 and bool(run_a_no), f"HTTP {status} run={run_a_no}")
            check("A reserved_tokens=0", int(run_a.get("reserved_tokens") or 0) == 0,
                  f"reserved={run_a.get('reserved_tokens')}")
            check("A hold_id 为空", not run_a.get("hold_id"), f"hold_id={run_a.get('hold_id')!r}")
            reservations = int(await conn.fetchval(
                "SELECT count(*) FROM quota_reservation WHERE owner_type='usr' AND owner_id=$1", uid) or 0)
            check("A 未落 quota_reservation", reservations == 0, f"rows={reservations}")
            used, held = await quota_keys(rds, uid)
            check("A Redis 无 used/held", used in (None, 0.0) and held in (None, 0.0),
                  f"used={used} held={held}")

            # ---- A. 启动 + 完成（带 usage）：不写 usage_record、不动账户
            status, _ = await api.post(f"/v1/harness/runs/{run_a_no}/start")
            check("A 启动运行 running", status == 200, f"HTTP {status}")
            status, body = await api.post(
                f"/v1/harness/runs/{run_a_no}/complete",
                {"status": "succeeded",
                 "usage": [{"node_id": "assistant:1", "seq": 1,
                            "tokens_in": SETTLE_A[0], "tokens_out": SETTLE_A[1],
                            "source": "provider"}]},
            )
            done_a = data_of(body) or {}
            check("A 结束运行 succeeded",
                  status == 200 and done_a.get("status") == "succeeded",
                  f"HTTP {status} status={done_a.get('status')}")
            usage_rows = int(await conn.fetchval(
                "SELECT count(*) FROM usage_record WHERE owner_type='usr' AND owner_id=$1", uid) or 0)
            check("A complete 不写 usage_record", usage_rows == 0, f"rows={usage_rows}")
            orch_rows = int(await conn.fetchval(
                "SELECT count(*) FROM usage_record WHERE idem_key LIKE $1", f"orch:{run_a_no}:%") or 0)
            check("A 无 orch: 幂等流水", orch_rows == 0, f"rows={orch_rows}")
            used, held = await quota_keys(rds, uid)
            check("A 结算后 Redis 仍无 used/held", used in (None, 0.0) and held in (None, 0.0),
                  f"used={used} held={held}")
            accounts = int(await conn.fetchval(
                "SELECT count(*) FROM quota_account WHERE owner_type='usr' AND owner_id=$1", uid) or 0)
            check("A 未创建 quota_account", accounts == 0, f"rows={accounts}")

            # ---- B. 事件里的 usage：只落 step，不记账
            status, body = await api.post(
                f"/v1/harness/sessions/{session_no}/runs",
                {"estimated_input_tokens": 200, "max_output_tokens": 100,
                 "model": "deepseek-chat", "provider": "deepseek"},
            )
            run_b_no = str((data_of(body) or {}).get("run_no") or "")
            await api.post(f"/v1/harness/runs/{run_b_no}/start")
            status, body = await api.post(
                f"/v1/harness/runs/{run_b_no}/events",
                {"source": "jsonl", "default_source": "provider",
                 "events": [{"type": "assistant/message", "seq": 1,
                             "usage": {"inputTokens": 10, "outputTokens": 5}}]},
            )
            counters = data_of(body) or {}
            check("B 事件采集 200 且 usage_events=1",
                  status == 200 and int(counters.get("usage_events") or 0) == 1,
                  f"HTTP {status} counters={counters}")
            check("B usage_records 计数为 0", int(counters.get("usage_records") or 0) == 0,
                  f"usage_records={counters.get('usage_records')}")
            steps = int(await conn.fetchval(
                "SELECT count(*) FROM harness_step WHERE run_no=$1 AND step_type='llm_call'",
                run_b_no) or 0)
            check("B 用量事件落为 llm_call 步骤", steps == 1, f"steps={steps}")
            usage_rows = int(await conn.fetchval(
                "SELECT count(*) FROM usage_record WHERE owner_type='usr' AND owner_id=$1", uid) or 0)
            check("B 仍无 usage_record", usage_rows == 0, f"rows={usage_rows}")

            # ---- C. 取消运行：无预占可释放，仍幂等
            status, body = await api.post(
                f"/v1/harness/sessions/{session_no}/runs",
                {"estimated_input_tokens": 300, "max_output_tokens": 200},
            )
            run_c_no = str((data_of(body) or {}).get("run_no") or "")
            await api.post(f"/v1/harness/runs/{run_c_no}/start")
            status, body = await api.post(f"/v1/harness/runs/{run_c_no}/cancel")
            cancelled = data_of(body) or {}
            check("C 取消运行 cancelled",
                  status == 200 and cancelled.get("status") == "cancelled",
                  f"HTTP {status} status={cancelled.get('status')}")
            used, held = await quota_keys(rds, uid)
            check("C 取消后 Redis 仍无 used/held", used in (None, 0.0) and held in (None, 0.0),
                  f"used={used} held={held}")
            reservations = int(await conn.fetchval(
                "SELECT count(*) FROM quota_reservation WHERE owner_type='usr' AND owner_id=$1", uid) or 0)
            check("C 全程无 quota_reservation", reservations == 0, f"rows={reservations}")

    finally:
        try:
            deleted = await cleanup(conn, fx)
            print("\n清理：", ", ".join(f"{k}={v}" for k, v in deleted.items()))
            left = await residue(conn, fx)
            check("清理后 DB 无残留", all(v == 0 for v in left.values()), str(left))
            if rds is not None:
                keys = await rds.keys(f"*:usr:{fx['user_id']}:*")
                check("清理后 Redis 无残留", not keys, str(keys))
        finally:
            if rds is not None:
                await rds.aclose()
            await conn.close()

    passed = sum(1 for _, st, _ in results if st == "PASS")
    failed = len(results) - passed
    print("\n" + "-" * 83)
    for name, st, detail in results:
        print(f"{name:<34} {st:<5} {detail}")
    print("-" * 83)
    print(f"结论 {'PASS' if not failed else 'FAIL'}  PASS={passed} FAIL={failed}  "
          f"用时 {time.time() - started:.1f}s")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
