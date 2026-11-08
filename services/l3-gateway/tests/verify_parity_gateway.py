"""T3.10 V12：新旧网关入口等价对照（9999 旧进程 vs 9990 新入口）。

只使用本地假 provider，不调用真实 provider。
对照维度：
- 鉴权/白名单失败：状态码 + 错误 message + error code
- 非流式成功：响应 JSON 逐字段一致
- 流式成功：SSE 逐字节一致（且等于假 provider 原始字节）
- usage_record：除幂等键外逐字段一致（source / resource_type / amount / tokens / model / provider / 快照）
- RPM 超限：两侧均为 429 且错误一致

说明：
- 9999 是改动前启动的旧进程（内存中仍是旧实现），全程不重启；
- 若 9999 当前配置未允许本地假 provider（返回 403 白名单），脚本以退出码 3 报告 BLOCKED，
  不擅自重启 9999。

用法（仓库根目录）：
    python services/l3-gateway/tests/verify_parity_gateway.py
"""
import asyncio
import hashlib
import json
import os
import pathlib
import sys
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import httpx

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_gateway as V  # noqa: E402

ROOT = V.ROOT
NEW_BASE = os.environ.get("GW_NEW_BASE", "http://127.0.0.1:9990")
OLD_BASE = os.environ.get("GW_OLD_BASE", "http://127.0.0.1:9999")

CHECKS: List[Tuple[bool, str, str]] = []


def record(ok: bool, label: str, detail: str = "") -> None:
    CHECKS.append((ok, label, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" :: {detail}" if detail else ""), flush=True)


async def clone_lease(conn: asyncpg.Connection, src: str, dst: str, secret: str) -> str:
    """复制一条租约（仅换 lease_id / key_hash / prefix / fingerprint），用于两侧独立记账。"""
    row = await conn.fetchrow("SELECT * FROM harness_gateway_lease WHERE lease_id = $1", src)
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    meta = row["meta"]
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    await conn.execute(
        "INSERT INTO harness_gateway_lease (lease_id, key_hash, key_prefix, key_fingerprint,"
        " client_id, session_no, run_no, owner_type, owner_id, provider, model, status,"
        " expires_at, rpm_limit, meta) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb)",
        dst, digest, f"dgw.{dst}", digest[:12], row["client_id"], row["session_no"], row["run_no"],
        row["owner_type"], row["owner_id"], row["provider"], row["model"], row["status"],
        row["expires_at"], row["rpm_limit"], json.dumps(meta),
    )
    return f"dgw.{dst}.{secret}"


def error_of(resp: httpx.Response) -> Dict[str, Any]:
    try:
        return resp.json().get("error") or {}
    except Exception:
        return {"message": resp.text}


async def compare_failure(label: str, token: Optional[str], raw_auth: Optional[str] = None) -> None:
    body = V.base_body()
    new = await V.call_gateway(token, body, base=NEW_BASE, raw_auth=raw_auth)
    old = await V.call_gateway(token, body, base=OLD_BASE, raw_auth=raw_auth)
    new_err = error_of(new)
    old_err = error_of(old)
    ok = new.status_code == old.status_code and new_err == old_err
    record(ok, f"V12 失败分支一致 · {label}",
           f"new={new.status_code}/{new_err} old={old.status_code}/{old_err}")


async def compare_success_nonstream(token_new: str, token_old: str) -> None:
    body = V.base_body(max_tokens=32, dsh_session_log={"events": [{"type": "prompt", "text": "S"}]})
    new = await V.call_gateway(token_new, body, base=NEW_BASE)
    old = await V.call_gateway(token_old, body, base=OLD_BASE)
    same = new.status_code == old.status_code == 200
    try:
        same = same and new.json() == old.json()
    except Exception:
        same = False
    record(same, "V12 非流式成功响应逐字段一致",
           f"new={new.status_code} old={old.status_code}")


async def compare_success_stream(token_new: str, token_old: str) -> None:
    body = V.base_body(stream=True)
    new = await V.call_gateway(token_new, body, base=NEW_BASE)
    old = await V.call_gateway(token_old, body, base=OLD_BASE)
    equal = new.status_code == old.status_code == 200 \
        and new.content == old.content == V.SSE_PAYLOAD
    record(equal, "V12 流式 SSE 逐字节一致",
           f"new={len(new.content)} old={len(old.content)} upstream={len(V.SSE_PAYLOAD)}")


USAGE_FIELDS = ("source", "resource_type", "amount", "tokens_in", "tokens_out",
                "model", "provider", "usage_kind")


async def compare_usage(conn: asyncpg.Connection, id_new: str, id_old: str) -> None:
    new_rows = await V.wait_rows(conn, id_new, 2)
    old_rows = await V.wait_rows(conn, id_old, 2)
    ok = len(new_rows) == len(old_rows) == 2
    record(ok, "V12 两侧 usage 行数一致", f"new={len(new_rows)} old={len(old_rows)}")
    if not ok:
        return
    for idx, (a, b) in enumerate(zip(new_rows, old_rows)):
        values = all(a[field] == b[field] for field in USAGE_FIELDS)
        values = values and V.snapshot_of(a) == V.snapshot_of(b)
        record(values, f"V12 usage 第 {idx + 1} 行逐字段一致",
               f"new={[a[f] for f in USAGE_FIELDS]} old={[b[f] for f in USAGE_FIELDS]}")


async def compare_rpm(token_new: str, token_old: str) -> None:
    first_new = await V.call_gateway(token_new, V.base_body(), base=NEW_BASE)
    first_old = await V.call_gateway(token_old, V.base_body(), base=OLD_BASE)
    record(first_new.status_code == first_old.status_code == 200,
           "V12 RPM 首次放行一致", f"new={first_new.status_code} old={first_old.status_code}")
    second_new = await V.call_gateway(token_new, V.base_body(), base=NEW_BASE)
    second_old = await V.call_gateway(token_old, V.base_body(), base=OLD_BASE)
    ok = second_new.status_code == second_old.status_code == 429 \
        and error_of(second_new) == error_of(second_old)
    record(ok, "V12 RPM 超限一致",
           f"new={second_new.status_code}/{error_of(second_new)}"
           f" old={second_old.status_code}/{error_of(second_old)}")


def error_of(resp: httpx.Response) -> Dict[str, Any]:
    try:
        return resp.json().get("error") or {}
    except Exception:
        return {"message": resp.text}


async def main() -> int:
    for base in (NEW_BASE, OLD_BASE):
        try:
            resp = httpx.get(f"{base}/health", timeout=5.0)
            print(f"{base}/health -> {resp.status_code} {resp.text[:120]}", flush=True)
        except Exception as exc:
            print(f"❌ 网关不可用 {base}: {exc}", flush=True)
            return 2

    conn = await asyncpg.connect(
        host=V.DB["host"], port=V.DB["port"], user=V.DB["user"],
        password=V.DB["password"], database=V.DB["database"],
    )
    fake = V.FakeProvider()
    try:
        await V.cleanup_redis()
        await V.cleanup_db(conn)
        tokens = await V.insert_fixtures(conn)

        token_ok_old = await clone_lease(
            conn, "p3v_lease_ok", "p3v_lease_ok_old", "p3v_secret_ok_old"
        )
        rpm_id = tokens["rpm"].split(".")[1]
        token_rpm_old = await clone_lease(
            conn, rpm_id, "p3v_lease_rpm_old", "p3v_secret_rpm_old"
        )
        token_probe = await clone_lease(
            conn, "p3v_lease_ok", "p3v_lease_probe_old", "p3v_secret_probe_old"
        )

        fake.start()
        await asyncio.sleep(0.2)

        # 失败分支不依赖上游，始终可对照
        await compare_failure("缺凭据", None)
        await compare_failure("JWT", None, "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig")
        await compare_failure("非 dgw 格式", "plain-token")
        await compare_failure("租约不存在", "dgw.p3v_lease_absent.p3v-secret")
        await compare_failure("secret 不匹配", f"{tokens['ok'].rsplit('.', 1)[0]}.wrong-secret")
        await compare_failure("已吊销", tokens["revoked"])
        await compare_failure("已过期", tokens["expired"])
        await compare_failure("会话关闭", tokens["closed"])
        await compare_failure("运行终态", tokens["run"])
        await compare_failure("白名单拒绝", tokens["host"])

        # 成功分支需要旧入口允许本地假 provider
        probe = await V.call_gateway(token_probe, V.base_body(), base=OLD_BASE)
        blocked = probe.status_code == 403
        if blocked:
            print(f"BLOCKED：9999 不允许本地假 provider -> {error_of(probe)}", flush=True)
            print("成功路径（非流式/SSE/记账/RPM）未对照；未重启 9999。", flush=True)
        else:
            await compare_success_nonstream(tokens["ok"], token_ok_old)
            await compare_success_stream(tokens["ok"], token_ok_old)
            await compare_usage(conn, "p3v_lease_ok", "p3v_lease_ok_old")
            await compare_rpm(tokens["rpm"], token_rpm_old)
    finally:
        fake.stop()
        await V.cleanup_db(conn)
        await V.cleanup_redis()
        await conn.close()

    passed = sum(1 for ok, _, _ in CHECKS if ok)
    failed = len(CHECKS) - passed
    print(f"\n结果：{passed} 通过 / {failed} 失败（成功路径对照 { 'BLOCKED' if blocked else '已执行'}）", flush=True)
    if failed:
        for ok, label, detail in CHECKS:
            if not ok:
                print(f"  ❌ {label} :: {detail}", flush=True)
        return 1
    return 3 if blocked else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
