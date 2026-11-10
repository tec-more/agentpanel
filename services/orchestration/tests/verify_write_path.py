#!/usr/bin/env python3
"""编排写主业务链路定向回归（2026-11-10 改名后补测）。

覆盖 `api/write.py` / `api/business.py` / `api/approval.py` 三个路由的**语义正确性**，
而不只是健康检查：

- 鉴权负向：无凭据 / 只给 client_id / secret 错误 → 401
- 写主直连（编排 9100）：会话 → 运行 → 启动 → 步骤 → 事件 → 心跳 → 审批 → 结束 → 查询 → 关闭
- 代理链路（app 9998）：同一路径经 app 转发到编排写主，证明 `ORCH_APP_BASE_URL` 生效
- 取消路径：`/runs/{run_no}/cancel` 释放预占；终态再审批应 409（状态机护栏）
- 数据一致性：API 返回与 `harness_*` 表实际行一致
- 计量中立：全程 0 token，`reserved_tokens=0`、`hold_id` 为空，不产生配额预占/结算；
  结束后清理所有 fixture 行

设计约束（与 `observe_check.py` 的分工）：
    巡检只读、不写业务数据；本脚本会写业务数据，因此**必须自带清理**，且刻意走零 token
    路径，避免触碰 `used` / `held` 计量键，防止污染观察期基线。

用法（必须**在 orchestration 容器内**执行：需要 DB_* 环境与 asyncpg/httpx）：
    docker exec -i agentpanel-orchestration python - < services/orchestration/tests/verify_write_path.py

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

ORCH_BASE = os.environ.get("ORCH_BASE", "http://127.0.0.1:9100")
APP_BASE = os.environ.get("APP_BASE", "http://app:9998")
PREFIX = "e2ewrite_"

results: List[Tuple[str, str, str]] = []  # (名称, PASS/FAIL, 说明)


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, "PASS" if ok else "FAIL", detail))
    return ok


# ---------------------------------------------------------------- DB


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


async def create_fixture_client(conn: asyncpg.Connection, client_id: str, secret: str) -> None:
    await conn.execute(
        "INSERT INTO harness_client "
        "(client_id, name, secret_hash, secret_prefix, status, scopes, allowed_ips) "
        "VALUES ($1, $2, $3, $4, 'active', $5::jsonb, NULL)",
        client_id,
        "e2e 写路径回归（临时）",
        hashlib.sha256(secret.encode("utf-8")).hexdigest(),
        secret[:8],
        json.dumps([]),
    )


async def cleanup(conn: asyncpg.Connection, client_id: str) -> Dict[str, int]:
    """按子表 → 父表顺序删除，返回各表删除行数。"""
    deleted: Dict[str, int] = {}
    steps = (
        ("harness_approval_grant", "session_no IN "
         "(SELECT session_no FROM harness_session WHERE client_id=$1)"),
        ("harness_approval_request", "client_id=$1"),
        ("harness_step", "run_no IN (SELECT run_no FROM harness_run WHERE client_id=$1)"),
        ("harness_audit_event", "client_id=$1"),
        ("harness_run", "client_id=$1"),
        ("harness_session", "client_id=$1"),
        ("harness_client", "client_id=$1"),
    )
    for table, where in steps:
        try:
            tag = await conn.execute(f"DELETE FROM {table} WHERE {where}", client_id)
        except asyncpg.PostgresError as exc:  # 表不存在或列不匹配：不阻断清理
            deleted[table] = -1
            print(f"  [cleanup] {table} 跳过：{type(exc).__name__}: {exc}")
            continue
        deleted[table] = int(tag.split()[-1]) if tag else 0
    return deleted


async def rowcount(conn: asyncpg.Connection, table: str, client_id: str) -> int:
    try:
        return int(await conn.fetchval(f"SELECT count(*) FROM {table} WHERE client_id=$1", client_id))
    except asyncpg.PostgresError:
        return -1


# ---------------------------------------------------------------- HTTP


class Api:
    def __init__(self, base: str, client: httpx.AsyncClient, client_id: str, secret: str) -> None:
        self.base = base.rstrip("/")
        self.client = client
        self.headers = {"X-Harness-Client-Id": client_id, "X-Harness-Secret": secret}

    async def request(
        self, method: str, path: str, body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        resp = await self.client.request(
            method, f"{self.base}{path}", json=body, headers=headers if headers is not None else self.headers
        )
        try:
            payload = resp.json()
        except ValueError:
            payload = {"_raw": resp.text[:200]}
        return resp.status_code, payload

    async def get(self, path: str) -> Tuple[int, Dict[str, Any]]:
        return await self.request("GET", path)

    async def post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any]]:
        return await self.request("POST", path, body or {})


def data_of(payload: Dict[str, Any]) -> Any:
    return payload.get("data")


def ok_body(payload: Dict[str, Any]) -> bool:
    return payload.get("code") == 0


# ---------------------------------------------------------------- 用例


async def open_session(api: Api, label: str, client_id: str) -> str:
    status, body = await api.post("/v1/harness/sessions", {"client_id": client_id, "title": f"{PREFIX}{label}"})
    session_no = str((data_of(body) or {}).get("session_no") or "")
    check(
        f"{label} 创建会话 200",
        status == 200 and ok_body(body) and session_no.startswith("hs_"),
        f"HTTP {status} session_no={session_no or '(空)'}",
    )
    return session_no


async def open_run(api: Api, label: str, session_no: str) -> Dict[str, Any]:
    status, body = await api.post(
        f"/v1/harness/sessions/{session_no}/runs",
        {"task_type": "agent", "estimated_input_tokens": 0, "max_output_tokens": 0},
    )
    run = data_of(body) or {}
    run_no = str(run.get("run_no") or "")
    check(
        f"{label} 创建运行 200",
        status == 200 and ok_body(body) and run_no.startswith("hr_"),
        f"HTTP {status} run_no={run_no or '(空)'}",
    )
    # 计量中立：零 token 不得预占
    check(
        f"{label} 零 token 未预占",
        int(run.get("reserved_tokens") or 0) == 0 and not run.get("hold_id"),
        f"reserved={run.get('reserved_tokens')} hold_id={run.get('hold_id')!r}",
    )
    return run


async def start_run(api: Api, label: str, run_no: str) -> None:
    status, body = await api.post(f"/v1/harness/runs/{run_no}/start")
    state = (data_of(body) or {}).get("status")
    check(f"{label} 启动运行 running", status == 200 and ok_body(body) and state == "running",
          f"HTTP {status} status={state}")


async def report_progress(api: Api, label: str, run_no: str) -> None:
    status, body = await api.post(
        f"/v1/harness/runs/{run_no}/steps",
        {"node_id": f"node-{label}", "seq": 1, "step_type": "llm_call", "name": "e2e",
         "status": "completed", "tokens_in": 0, "tokens_out": 0},
    )
    check(f"{label} 上报步骤 200", status == 200 and ok_body(body), f"HTTP {status} code={body.get('code')}")

    status, body = await api.post(
        f"/v1/harness/runs/{run_no}/events",
        {"lines": [json.dumps({"type": "usage", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}), "{截断行"],
         "source": "api", "truncated_lines": 1},
    )
    counters = data_of(body) or {}
    check(
        f"{label} 事件采集容忍坏行",
        status == 200 and ok_body(body)
        and counters.get("invalid_lines") == 1 and counters.get("truncated_lines") == 1,
        f"HTTP {status} invalid={counters.get('invalid_lines')} truncated={counters.get('truncated_lines')}",
    )

    status, body = await api.post(f"/v1/harness/runs/{run_no}/heartbeat")
    check(f"{label} 心跳 200", status == 200 and ok_body(body), f"HTTP {status} code={body.get('code')}")


async def complete_run(api: Api, label: str, run_no: str) -> None:
    status, body = await api.post(f"/v1/harness/runs/{run_no}/complete", {"status": "succeeded", "usage": []})
    state = (data_of(body) or {}).get("status")
    check(f"{label} 结束运行 succeeded", status == 200 and ok_body(body) and state == "succeeded",
          f"HTTP {status} status={state}")

    status, body = await api.get(f"/v1/harness/runs/{run_no}")
    got = data_of(body) or {}
    check(
        f"{label} 查询运行与写入一致",
        status == 200 and got.get("status") == "succeeded" and int(got.get("reserved_tokens") or 0) == 0,
        f"HTTP {status} status={got.get('status')}",
    )


async def list_runs(api: Api, label: str, session_no: str, expected: int) -> None:
    status, body = await api.get(f"/v1/harness/sessions/{session_no}/runs")
    items = data_of(body)
    total = len(items) if isinstance(items, list) else (items or {}).get("total")
    check(f"{label} 会话运行列表可见", status == 200 and total == expected,
          f"HTTP {status} total={total} 期望={expected}")


async def close_session(api: Api, label: str, session_no: str) -> None:
    status, body = await api.post(f"/v1/harness/sessions/{session_no}/close")
    closed = data_of(body) or {}
    check(f"{label} 关闭会话 closed", status == 200 and ok_body(body) and closed.get("status") == "closed",
          f"HTTP {status} status={closed.get('status')}")


async def main() -> int:
    client_id = PREFIX + secrets.token_hex(8)
    secret = secrets.token_hex(16)
    conn = await connect()
    started = time.time()

    print(f"编排写路径回归  {datetime.datetime.now().astimezone():%Y-%m-%d %H:%M:%S %z}")
    print(f"fixture client_id = {client_id}\n")

    try:
        await create_fixture_client(conn, client_id, secret)

        async with httpx.AsyncClient(timeout=20.0) as http:
            orch = Api(ORCH_BASE, http, client_id, secret)
            app = Api(APP_BASE, http, client_id, secret)

            # ---- 1. 鉴权负向（编排写主）
            status, _ = await orch.request("POST", "/v1/harness/sessions", {"client_id": client_id}, headers={})
            check("负向 无凭据 → 401", status == 401, f"HTTP {status}")
            status, _ = await orch.request(
                "POST", "/v1/harness/sessions", {"client_id": client_id},
                headers={"X-Harness-Client-Id": client_id},
            )
            check("负向 缺 secret → 401", status == 401, f"HTTP {status}")
            status, _ = await orch.request(
                "POST", "/v1/harness/sessions", {"client_id": client_id},
                headers={"X-Harness-Client-Id": client_id, "X-Harness-Secret": "wrong-" + secret},
            )
            check("负向 secret 错误 → 401", status == 401, f"HTTP {status}")

            # ---- 2. 写主直连：会话 → 运行 → 启动 → 进度 → 审批 → 结束 → 关闭
            d_session = await open_session(orch, "直连", client_id)
            d_run = (await open_run(orch, "直连", d_session)).get("run_no") or ""
            await start_run(orch, "直连", d_run)
            await report_progress(orch, "直连", d_run)

            status, body = await orch.post(
                "/v1/harness/approvals/request",
                {"run_no": d_run, "action": "tool.file.read", "call_id": "call-e2e",
                 "arguments": {"path": "README.md"}},
            )
            verdict = data_of(body) or {}
            check(
                "审批 运行中三档判定返回",
                status == 200 and ok_body(body) and bool(verdict.get("decision") or verdict.get("status")),
                f"HTTP {status} decision={verdict.get('decision')} status={verdict.get('status')}",
            )
            status, body = await orch.get("/v1/harness/approvals/pending")
            pending = data_of(body) or {}
            check("审批 待审批列表可读",
                  status == 200 and ok_body(body) and isinstance(pending.get("items"), list),
                  f"HTTP {status} total={pending.get('total')}")

            await complete_run(orch, "直连", d_run)
            await list_runs(orch, "直连", d_session, 1)

            # 终态再申请审批应被状态机拒绝（409），证明护栏生效
            status, body = await orch.post(
                "/v1/harness/approvals/request",
                {"run_no": d_run, "action": "tool.file.read", "call_id": "call-e2e-2"},
            )
            check("审批 终态运行 → 409 护栏", status == 409, f"HTTP {status} msg={body.get('msg')}")

            await close_session(orch, "直连", d_session)

            # ---- 3. 代理链路（app 转发到编排写主）
            p_session = await open_session(app, "代理", client_id)
            p_run = (await open_run(app, "代理", p_session)).get("run_no") or ""
            await start_run(app, "代理", p_run)
            await report_progress(app, "代理", p_run)
            await complete_run(app, "代理", p_run)

            # ---- 4. 取消路径：同一会话新建运行，启动后取消
            p_run2 = (await open_run(app, "代理取消", p_session)).get("run_no") or ""
            await start_run(app, "代理取消", p_run2)
            status, body = await app.post(f"/v1/harness/runs/{p_run2}/cancel?reason=e2e")
            cancelled = data_of(body) or {}
            check("代理 取消运行 cancelled",
                  status == 200 and ok_body(body) and cancelled.get("status") == "cancelled",
                  f"HTTP {status} status={cancelled.get('status')}")

            await list_runs(app, "代理", p_session, 2)
            await close_session(app, "代理", p_session)

            # ---- 5. 数据一致性（DB 实际行）
            session_rows = await conn.fetch(
                "SELECT session_no, status FROM harness_session WHERE client_id=$1 ORDER BY id", client_id
            )
            run_rows = await conn.fetch(
                "SELECT run_no, status, reserved_tokens, hold_id FROM harness_run WHERE client_id=$1 ORDER BY id",
                client_id,
            )
            step_count = int(await conn.fetchval(
                "SELECT count(*) FROM harness_step WHERE run_no = ANY($1::text[])",
                [r["run_no"] for r in run_rows],
            ) or 0)
            audit_count = int(await conn.fetchval(
                "SELECT count(*) FROM harness_audit_event WHERE client_id=$1", client_id) or 0)
            approval_count = int(await conn.fetchval(
                "SELECT count(*) FROM harness_approval_request WHERE client_id=$1", client_id) or 0)

            check("DB 会话 2 行且均 closed",
                  len(session_rows) == 2 and all(r["status"] == "closed" for r in session_rows),
                  f"{[r['status'] for r in session_rows]}")
            check("DB 运行 3 行、两个 succeeded 一个 cancelled",
                  len(run_rows) == 3 and sorted(r["status"] for r in run_rows) == ["cancelled", "succeeded", "succeeded"],
                  f"{sorted(r['status'] for r in run_rows)}")
            check("DB 运行均未预占",
                  all(int(r["reserved_tokens"] or 0) == 0 and not r["hold_id"] for r in run_rows),
                  f"{[(r['reserved_tokens'], r['hold_id']) for r in run_rows]}")
            check("DB 步骤 2 行（取消的运行无步骤）", step_count == 2, f"rows={step_count}")
            check("DB 审计事件已落库", audit_count > 0, f"rows={audit_count}")
            check("DB 审批单已落库", approval_count >= 1, f"rows={approval_count}")

    finally:
        deleted = await cleanup(conn, client_id)
        print("\n清理： " + ", ".join(f"{k}={v}" for k, v in deleted.items()))
        residue = {t: await rowcount(conn, t, client_id)
                   for t in ("harness_client", "harness_session", "harness_run", "harness_audit_event",
                             "harness_approval_request")}
        check("清理后无残留", all(v == 0 for v in residue.values()), f"{residue}")
        await conn.close()

    width = max(len(name) for name, _, _ in results) + 2
    print("\n" + "-" * (width + 12 + 34))
    for name, state, detail in results:
        print(f"{name:<{width}}{state:<6}{detail}")
    print("-" * (width + 12 + 34))
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = len(results) - passed
    print(f"结论 {'PASS' if failed == 0 else 'FAIL'}  PASS={passed} FAIL={failed}  用时 {time.time() - started:.1f}s")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
