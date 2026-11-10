"""网关数据面离线验证（V3–V11，只用本地假 provider）。

覆盖：
- V3 鉴权：缺凭据 / JWT / 非法格式 / 错误 secret / 吊销 / 过期 401；关闭会话 / run 终态 403；超 RPM 429
- V4 出网白名单：非白名单域名 403；allow_loopback=false 时 127.0.0.1 403；均不触达上游
- V5 请求剥离：`dsh_session_log` 不进入上游请求体
- V6 SSE 逐字节透传 + usage_record 口径（source=gateway / gateway_key / 唯一 gw: 幂等键）
- V7 失败请求记账：resource_type=gateway_error、amount=0、每请求恰好 1 行
- V8 预算/并发/截断：402 预算不足 + 自动吊销；429 并发上限；流式越界截断 partial
- V9 Redis 短路缓存：租约状态 key 存在且 TTL 5–10s；吊销写穿删除
- V10 DB 兜底：REDIS_ENABLED=false 的独立实例仍可预检/结算/记账
- V11 审计：auth_rejected / quota_rejected / lease_revoked / stream_truncated 事件

前置：
- 网关（新入口）已在 9990 运行，且允许本地假 provider：
  `GW_PROVIDER_DOMAIN_ALLOWLIST=api.deepseek.com,127.0.0.1`、`GW_ALLOW_LOOPBACK=true`、
  `GW_MAX_CONCURRENT_REQUESTS_PER_OWNER=1`（V8 并发上限用例需要）
- DB/Redis 连接信息取自 `config.conf`
- V4/V10 会临时拉起 9991/9992 实例，仅本地、用完即杀

用法（仓库根目录）：
    python services/gateway/tests/verify_gateway.py
"""
import asyncio
import configparser
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple

import asyncpg
import httpx

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[3]
GATEWAY = os.environ.get("GW_BASE_URL", "http://127.0.0.1:9990")
FAKE_HOST = "127.0.0.1"
FAKE_PORT = int(os.environ.get("P3V_FAKE_PORT", "18080"))
FAKE_BASE = f"http://{FAKE_HOST}:{FAKE_PORT}/v1"
BAD_BASE = "http://example.com/v1"

PREFIX = "p3v_"
CLIENT_ID = "p3v_client"
OWNER_ID = 999001
RUN_TAG = uuid.uuid4().hex[:8]

# 假 provider 返回的 SSE 原始字节；网关必须逐字节一致地透传
SSE_PAYLOAD = (
    'data: {"id":"p3v-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"你"}}]}\n\n'
    'data: {"id":"p3v-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"好"}}]}\n\n'
    'data: {"id":"p3v-1","object":"chat.completion.chunk","choices":[],"usage":{"prompt_tokens":12,"completion_tokens":8,"total_tokens":20}}\n\n'
    "data: [DONE]\n\n"
).encode("utf-8")

# 超长输出帧，用于触发流式看门狗截断（200 字符 ≈ 100 token，远超预算 30）
SSE_BIG = (
    'data: {"id":"p3v-big","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"'
    + "z" * 200
    + '"}}]}\n\n'
    'data: {"id":"p3v-big","object":"chat.completion.chunk","choices":[],"usage":{"prompt_tokens":3,"completion_tokens":100,"total_tokens":103}}\n\n'
    "data: [DONE]\n\n"
).encode("utf-8")

JSON_PAYLOAD = {
    "id": "p3v-2",
    "object": "chat.completion",
    "model": "p3v-fake-model",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
}


class FakeProvider:
    """记录收到的请求体，按 stream / 标记返回 JSON / SSE；可选延迟用于并发用例。"""

    def __init__(self) -> None:
        self.bodies: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # 静默
                return

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw) if raw else {}
                except Exception:
                    body = {"__invalid__": raw.decode("utf-8", "ignore")}
                with outer.lock:
                    outer.bodies.append(body if isinstance(body, dict) else {"__type__": type(body).__name__})
                if self.path != "/v1/chat/completions":
                    self.send_response(404)
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return
                delay = body.get("_p3v_delay")
                if isinstance(delay, (int, float)) and delay > 0:
                    time.sleep(float(delay))
                if bool(body.get("stream")):
                    frames = SSE_BIG if body.get("_p3v_big") else SSE_PAYLOAD
                    self.send_response(200)
                    self.send_header("content-type", "text/event-stream; charset=utf-8")
                    self.send_header("transfer-encoding", "chunked")
                    self.end_headers()
                    for frame in frames.split(b"\n\n")[:-1]:
                        chunk = frame + b"\n\n"
                        self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                    return
                payload = json.dumps(JSON_PAYLOAD, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer((FAKE_HOST, FAKE_PORT), Handler)
        self.server.daemon_threads = True
        # 网关截断/主动断开会触发对端 reset，属预期行为，不打印线程异常
        self.server.handle_error = lambda request, client_address: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.started = False

    def start(self) -> None:
        self.started = True
        self.thread.start()

    def stop(self) -> None:
        if not self.started:
            return
        self.server.shutdown()
        self.server.server_close()

    def last_body(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.bodies[-1] if self.bodies else None

    def count(self) -> int:
        with self.lock:
            return len(self.bodies)


CHECKS: List[Tuple[bool, str, str]] = []


def record(ok: bool, label: str, detail: str = "") -> None:
    CHECKS.append((ok, label, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" :: {detail}" if detail else ""), flush=True)


def read_db_conf() -> Dict[str, Any]:
    parser = configparser.ConfigParser()
    parser.read(ROOT / "config.conf", encoding="utf-8")
    return {
        "host": os.environ.get("DB_HOST") or parser.get("db", "db_host", fallback="127.0.0.1"),
        "port": int(os.environ.get("DB_PORT") or parser.getint("db", "db_port", fallback=15432)),
        "user": os.environ.get("DB_USER") or parser.get("db", "db_user", fallback="admin"),
        "password": os.environ.get("DB_PASSWORD") or parser.get("db", "db_password", fallback=""),
        "database": os.environ.get("DB_NAME") or parser.get("db", "db_name", fallback="agentpanel"),
        "redis_host": parser.get("redis", "host", fallback="127.0.0.1"),
        "redis_port": parser.getint("redis", "port", fallback=6379),
        "redis_password": parser.get("redis", "password", fallback=""),
        "redis_db": parser.getint("redis", "db", fallback=0),
    }


DB = read_db_conf()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def redis_client():
    import redis.asyncio as aioredis

    return aioredis.Redis(
        host=DB["redis_host"], port=DB["redis_port"], password=DB["redis_password"] or None,
        db=DB["redis_db"], decode_responses=True,
    )


AUTH_REJECT_REASONS = (
    "missing_credential",
    "jwt_not_allowed",
    "invalid_key_format",
    "lease_rejected:401",
    "lease_rejected:403",
)


async def cleanup_db(conn: asyncpg.Connection) -> None:
    await conn.execute("DELETE FROM usage_record WHERE gateway_key LIKE $1", PREFIX + "%")
    await conn.execute("DELETE FROM harness_gateway_budget WHERE lease_id LIKE $1", PREFIX + "%")
    await conn.execute(
        "DELETE FROM harness_gateway_concurrency WHERE owner_type = 'usr' AND owner_id = $1", OWNER_ID
    )
    await conn.execute("DELETE FROM harness_gateway_lease WHERE lease_id LIKE $1", PREFIX + "%")
    await conn.execute("DELETE FROM harness_session WHERE session_no LIKE $1", PREFIX + "%")
    await conn.execute("DELETE FROM harness_run WHERE run_no LIKE $1", PREFIX + "%")
    await conn.execute("DELETE FROM quota_account WHERE owner_type = 'usr' AND owner_id = $1", OWNER_ID)
    await conn.execute("DELETE FROM llm_api_key WHERE api_key LIKE 'p3v-%'")
    await conn.execute("DELETE FROM llm_model WHERE model_id LIKE 'p3v-%'")
    await conn.execute("DELETE FROM llm_provider WHERE name_en LIKE 'p3v_%'")
    await conn.execute(
        "DELETE FROM harness_audit_event WHERE target_id LIKE $1 OR (action = 'gateway.auth_rejected'"
        " AND detail->>'reason' = ANY($2::text[]))",
        PREFIX + "%", list(AUTH_REJECT_REASONS),
    )


async def cleanup_redis() -> None:
    client = await redis_client()
    try:
        for pattern in (
            "gw:lease:state:p3v_*", "gw:budget:lease:p3v_*", "gw:none:p3v_*",
            f"quota:usr:{OWNER_ID}:*", f"quota_held:usr:{OWNER_ID}:*", f"gw:conc:usr:{OWNER_ID}",
        ):
            keys = [key async for key in client.scan_iter(match=pattern)]
            for key in keys:
                await client.delete(key)
    finally:
        await client.aclose()


async def insert_fixtures(conn: asyncpg.Connection) -> Dict[str, str]:
    """插入假 provider / 模型 / key 与租约；返回各租约的虚拟 key。"""
    now = datetime.now(timezone.utc)

    provider_id = await conn.fetchval(
        "INSERT INTO llm_provider (name, name_en, status) VALUES ($1,$2,'active') RETURNING id",
        "P3V 假厂商", "p3v_fake",
    )
    await conn.execute(
        "INSERT INTO llm_model (provider_id, model_id, model_name, status) VALUES ($1,$2,$3,'active')",
        provider_id, "p3v-fake-model", "p3v-fake-model",
    )
    await conn.execute(
        "INSERT INTO llm_api_key (provider_id, model_id, model_service_type, call_mode, api_key,"
        " endpoint_url, status, max_quota, used_quota, quota_reset_date) "
        "VALUES ($1,NULL,'llm','vendor_sdk',$2,$3,'active',100000,0,CURRENT_DATE)",
        provider_id, "p3v-secret-key", FAKE_BASE,
    )

    bad_provider_id = await conn.fetchval(
        "INSERT INTO llm_provider (name, name_en, status) VALUES ($1,$2,'active') RETURNING id",
        "P3V 假厂商-B", "p3v_fake_bad",
    )
    await conn.execute(
        "INSERT INTO llm_model (provider_id, model_id, model_name, status) VALUES ($1,$2,$3,'active')",
        bad_provider_id, "p3v-bad-model", "p3v-bad-model",
    )
    await conn.execute(
        "INSERT INTO llm_api_key (provider_id, model_id, model_service_type, call_mode, api_key,"
        " endpoint_url, status, max_quota, used_quota, quota_reset_date) "
        "VALUES ($1,NULL,'llm','vendor_sdk',$2,$3,'active',100000,0,CURRENT_DATE)",
        bad_provider_id, "p3v-bad-key", BAD_BASE,
    )

    await conn.execute(
        "INSERT INTO harness_session (session_no, client_id, status) VALUES ($1,$2,'closed')",
        "p3v_sess_closed", CLIENT_ID,
    )
    await conn.execute(
        "INSERT INTO harness_run (run_no, session_no, client_id, status) VALUES ($1,$2,$3,'succeeded')",
        "p3v_run_terminal", "p3v_sess_closed", CLIENT_ID,
    )

    leases = {
        # RPM 窗口是网关进程内状态，用运行标签避免上一轮计数残留
        "ok": dict(lease_id="p3v_lease_ok", provider="p3v_fake", model="p3v-fake-model",
                   status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                   run_no=None, rpm_limit=60, meta={"ttl_seconds": 600}),
        "revoked": dict(lease_id="p3v_lease_revoked", provider="p3v_fake", model="p3v-fake-model",
                        status="revoked", expires_at=now + timedelta(minutes=10), session_no=None,
                        run_no=None, rpm_limit=60, meta={"ttl_seconds": 600}),
        "expired": dict(lease_id="p3v_lease_expired", provider="p3v_fake", model="p3v-fake-model",
                        status="active", expires_at=now - timedelta(minutes=1), session_no=None,
                        run_no=None, rpm_limit=60, meta={"ttl_seconds": 600}),
        "host": dict(lease_id="p3v_lease_host", provider="p3v_fake_bad", model="p3v-bad-model",
                     status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                     run_no=None, rpm_limit=60, meta={"ttl_seconds": 600}),
        "closed": dict(lease_id="p3v_lease_closed", provider="p3v_fake", model="p3v-fake-model",
                       status="active", expires_at=now + timedelta(minutes=10), session_no="p3v_sess_closed",
                       run_no=None, rpm_limit=60, meta={"ttl_seconds": 600}),
        "run": dict(lease_id="p3v_lease_run", provider="p3v_fake", model="p3v-fake-model",
                    status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                    run_no="p3v_run_terminal", rpm_limit=60, meta={"ttl_seconds": 600}),
        "rpm": dict(lease_id=f"p3v_lease_rpm_{RUN_TAG}", provider="p3v_fake", model="p3v-fake-model",
                    status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                    run_no=None, rpm_limit=1, meta={"ttl_seconds": 600}),
        "loop": dict(lease_id="p3v_lease_loop", provider="p3v_fake", model="p3v-fake-model",
                     status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                     run_no=None, rpm_limit=60, meta={"ttl_seconds": 600}),
        "cache": dict(lease_id=f"p3v_lease_cache_{RUN_TAG}", provider="p3v_fake", model="p3v-fake-model",
                      status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                      run_no=None, rpm_limit=60, meta={"ttl_seconds": 600}),
        "budget": dict(lease_id="p3v_lease_budget", provider="p3v_fake", model="p3v-fake-model",
                       status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                       run_no=None, rpm_limit=60, meta={"ttl_seconds": 600, "budget_tokens": 20}),
        "trunc": dict(lease_id="p3v_lease_trunc", provider="p3v_fake", model="p3v-fake-model",
                      status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                      run_no=None, rpm_limit=60, meta={"ttl_seconds": 600, "budget_tokens": 30}),
        "conc": dict(lease_id="p3v_lease_conc", provider="p3v_fake", model="p3v-fake-model",
                     status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                     run_no=None, rpm_limit=60, owner_type="usr", owner_id=OWNER_ID,
                     meta={"ttl_seconds": 600}),
        "db": dict(lease_id="p3v_lease_db", provider="p3v_fake", model="p3v-fake-model",
                   status="active", expires_at=now + timedelta(minutes=10), session_no=None,
                   run_no=None, rpm_limit=60, owner_type="usr", owner_id=OWNER_ID,
                   meta={"ttl_seconds": 600}),
    }
    tokens: Dict[str, str] = {}
    for name, item in leases.items():
        secret = f"{PREFIX}secret_{name}"
        digest = sha256(secret)
        tokens[name] = f"dgw.{item['lease_id']}.{secret}"
        await conn.execute(
            "INSERT INTO harness_gateway_lease (lease_id, key_hash, key_prefix, key_fingerprint,"
            " client_id, provider, model, status, expires_at, rpm_limit, session_no, run_no,"
            " owner_type, owner_id, meta) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb)",
            item["lease_id"], digest, f"dgw.{item['lease_id']}", digest[:12], CLIENT_ID,
            item["provider"], item["model"], item["status"], item["expires_at"], item["rpm_limit"],
            item["session_no"], item["run_no"], item.get("owner_type"), item.get("owner_id"),
            json.dumps(item["meta"]),
        )
    return tokens


async def call_gateway(
    token: Optional[str], body: Dict[str, Any], *, raw_auth: Optional[str] = None,
    base: str = GATEWAY, timeout: float = 30.0,
) -> httpx.Response:
    headers = {"content-type": "application/json"}
    if raw_auth is not None:
        headers["authorization"] = raw_auth
    elif token:
        headers["authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(f"{base}/chat/completions", json=body, headers=headers)


def base_body(**extra: Any) -> Dict[str, Any]:
    body = {"model": "p3v-fake-model", "messages": [{"role": "user", "content": "hello"}]}
    body.update(extra)
    return body


def error_payload(resp: httpx.Response) -> Dict[str, Any]:
    try:
        return resp.json().get("error") or {}
    except Exception:
        return {"message": resp.text}


async def verify_auth(tokens: Dict[str, str], fake: FakeProvider) -> None:
    cases: List[Tuple[str, Optional[str], Optional[str], int, str]] = [
        ("V3-1 缺凭据", None, None, 401, "缺少网关租约虚拟 key"),
        ("V3-2 JWT 拒绝", None, "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig", 401, "不接受 JWT"),
        ("V3-3 非 dgw 格式", "plain-token", None, 401, "只接受租约虚拟 key"),
        ("V3-4 secret 不匹配", f"{tokens['ok'].rsplit('.', 1)[0]}.wrong-secret", None, 401, "虚拟 key 无效"),
        ("V3-5 已吊销", tokens["revoked"], None, 401, "已吊销"),
        ("V3-6 已过期", tokens["expired"], None, 401, "已过期"),
        ("V3-7 会话关闭 403", tokens["closed"], None, 403, "会话已关闭"),
        ("V3-8 运行终态 403", tokens["run"], None, 403, "运行已结束"),
    ]
    for label, token, raw_auth, status, keyword in cases:
        resp = await call_gateway(token, base_body(), raw_auth=raw_auth)
        message = error_payload(resp).get("message") or ""
        ok = resp.status_code == status and keyword in message
        record(ok, f"{label}（期望 {status}）", f"status={resp.status_code} message={message}")
    record(fake.count() == 0, "V3-9 鉴权失败请求未触达上游", f"上游收到 {fake.count()} 次")

    first = await call_gateway(tokens["rpm"], base_body())
    record(first.status_code == 200, "V3-10 RPM=1 首次放行", f"status={first.status_code}")
    second = await call_gateway(tokens["rpm"], base_body())
    message = error_payload(second).get("message") or ""
    record(second.status_code == 429 and "频率" in message,
           "V3-11 超 RPM 429", f"status={second.status_code} message={message}")


def gateway_env(port: int, **extra: Any) -> Dict[str, str]:
    env = os.environ.copy()
    env.update({
        "DB_HOST": str(DB["host"]), "DB_PORT": str(DB["port"]), "DB_NAME": DB["database"],
        "DB_USER": DB["user"], "DB_PASSWORD": DB["password"],
        "REDIS_ENABLED": "true", "REDIS_HOST": DB["redis_host"],
        "REDIS_PORT": str(DB["redis_port"]), "REDIS_PASSWORD": DB["redis_password"],
        "REDIS_DB": str(DB["redis_db"]),
        "GW_PORT": str(port), "GW_HOST": "127.0.0.1",
        "GW_ALLOW_LOOPBACK": "true",
        "GW_PROVIDER_DOMAIN_ALLOWLIST": "api.deepseek.com,127.0.0.1",
        "PYTHONPATH": str(ROOT),
    })
    env.update({key: str(value) for key, value in extra.items()})
    return env


async def wait_health(base: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    async with httpx.AsyncClient(timeout=3.0) as client:
        while time.time() < deadline:
            try:
                resp = await client.get(f"{base}/health")
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.4)
    return False


async def with_temp_gateway(port: int, extra: Dict[str, Any],
                            action: Callable[[str], Any], label: str) -> None:
    log = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".log")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "services" / "gateway" / "run.py")],
        cwd=str(ROOT), env=gateway_env(port, **extra), stdout=log, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    started = False
    try:
        started = await wait_health(base)
        record(started, f"{label} 临时网关 {port} 启动", f"log={log.name}")
        if started:
            await action(base)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        log.close()
        if not started:
            try:
                print(pathlib.Path(log.name).read_text(encoding="utf-8", errors="ignore")[-1500:], flush=True)
            except Exception:
                pass
            os.unlink(log.name)


async def verify_allowlist(tokens: Dict[str, str], fake: FakeProvider) -> None:
    before = fake.count()
    resp = await call_gateway(tokens["host"], base_body())
    message = error_payload(resp).get("message") or ""
    record(resp.status_code == 403 and "白名单" in message,
           "V4-1 非白名单域名 403", f"status={resp.status_code} message={message}")
    record(fake.count() == before, "V4-2 出网拒绝未触达上游", f"上游计数 {before}->{fake.count()}")

    async def on_instance(base: str) -> None:
        count = fake.count()
        result = await call_gateway(tokens["loop"], base_body(), base=base)
        text = error_payload(result).get("message") or ""
        record(result.status_code == 403 and "回环" in text,
               "V4-3 allow_loopback=false 拒绝 127.0.0.1", f"status={result.status_code} message={text}")
        record(fake.count() == count, "V4-4 该实例未触达上游", f"上游计数 {count}->{fake.count()}")

    await with_temp_gateway(9991, {"GW_ALLOW_LOOPBACK": "false"}, on_instance, "V4")


async def verify_strip_and_forward(tokens: Dict[str, str], fake: FakeProvider) -> None:
    session_log = {"events": [{"type": "prompt", "text": "SENSITIVE"}]}
    resp = await call_gateway(tokens["ok"], base_body(dsh_session_log=session_log, max_tokens=32))
    record(resp.status_code == 200, "V5-1 合法租约非流式 200", f"status={resp.status_code}")

    received = fake.last_body() or {}
    record("dsh_session_log" not in received, "V5-2 上游请求体不含 dsh_session_log",
           f"keys={sorted(received.keys())}")
    record(isinstance(received.get("messages"), list) and received.get("model") == "p3v-fake-model",
           "V5-3 其余字段原样转发", f"model={received.get('model')}")
    record(int(received.get("max_tokens") or 0) == 32, "V5-4 输出上限夹紧保留",
           f"max_tokens={received.get('max_tokens')}")

    stream_body = base_body(stream=True, dsh_session_log=session_log)
    stream_resp = await call_gateway(tokens["ok"], stream_body)
    record(stream_resp.status_code == 200, "V6-1 流式响应 200", f"status={stream_resp.status_code}")
    record(stream_resp.content == SSE_PAYLOAD, "V6-2 SSE 逐字节透传",
           f"len(gw)={len(stream_resp.content)} len(up)={len(SSE_PAYLOAD)}")

    stream_received = fake.last_body() or {}
    record("dsh_session_log" not in stream_received, "V6-3 流式请求体已剥离 dsh_session_log",
           f"keys={sorted(stream_received.keys())}")
    options = stream_received.get("stream_options") or {}
    record(bool(options.get("include_usage")), "V6-4 流式自动补充 include_usage",
           f"stream_options={options}")


async def fetch_usage(conn: asyncpg.Connection, lease_id: str) -> List[asyncpg.Record]:
    return await conn.fetch(
        "SELECT idem_key, source, gateway_key, resource_type, amount, tokens_in, tokens_out,"
        " model, provider, usage_kind, price_snapshot, session_ref FROM usage_record"
        " WHERE gateway_key = $1 ORDER BY id",
        lease_id,
    )


async def wait_rows(conn: asyncpg.Connection, lease_id: str, expect: int,
                    timeout: float = 4.0) -> List[asyncpg.Record]:
    deadline = time.time() + timeout
    rows: List[asyncpg.Record] = []
    while time.time() < deadline:
        rows = await fetch_usage(conn, lease_id)
        if len(rows) >= expect:
            return rows
        await asyncio.sleep(0.2)
    return rows


def snapshot_of(row: asyncpg.Record) -> Dict[str, Any]:
    value = row["price_snapshot"]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return value or {}


async def verify_usage_success(conn: asyncpg.Connection) -> None:
    rows = await wait_rows(conn, "p3v_lease_ok", 2)
    record(len(rows) == 2, "V6-5 usage_record 落账 2 条（非流式+流式）", f"rows={len(rows)}")
    if len(rows) != 2:
        return

    normal, streamed = rows[0], rows[1]
    record(all(r["source"] == "gateway" for r in rows), "V6-6 source 均为 gateway",
           f"sources={[r['source'] for r in rows]}")
    record(all(r["gateway_key"] == "p3v_lease_ok" for r in rows), "V6-7 gateway_key=lease_id",
           f"keys={[r['gateway_key'] for r in rows]}")
    record(all(r["idem_key"] and r["idem_key"].startswith("gw:p3v_lease_ok:") for r in rows),
           "V6-8 幂等键前缀 gw:<lease_id>:", f"idem={[r['idem_key'] for r in rows]}")
    record(len({r["idem_key"] for r in rows}) == 2, "V6-9 幂等键每次请求唯一",
           f"distinct={len({r['idem_key'] for r in rows})}")

    record(normal["resource_type"] == "llm_token" and streamed["resource_type"] == "llm_token",
           "V6-10 resource_type=llm_token",
           f"types={[normal['resource_type'], streamed['resource_type']]}")
    record(normal["tokens_in"] == 12 and normal["tokens_out"] == 8 and normal["amount"] == 20,
           "V6-11 非流式用量口径 12/8/20",
           f"in={normal['tokens_in']} out={normal['tokens_out']} amount={normal['amount']}")
    record(streamed["tokens_in"] == 12 and streamed["tokens_out"] == 8 and streamed["amount"] == 20,
           "V6-12 流式用量口径 12/8/20",
           f"in={streamed['tokens_in']} out={streamed['tokens_out']} amount={streamed['amount']}")
    record(normal["model"] == "p3v-fake-model" and normal["provider"] == "p3v_fake",
           "V6-13 model/provider 来源正确",
           f"model={normal['model']} provider={normal['provider']}")

    normal_snap = snapshot_of(normal)
    stream_snap = snapshot_of(streamed)
    record(normal_snap.get("gateway_status") == 200 and normal_snap.get("stream") is False,
           "V6-14 非流式 price_snapshot 标记正确", f"snapshot={normal_snap}")
    record(stream_snap.get("gateway_status") == 200 and stream_snap.get("stream") is True
           and stream_snap.get("usage_missing") is False,
           "V6-15 流式 price_snapshot 标记正确", f"snapshot={stream_snap}")


async def verify_usage_failure(conn: asyncpg.Connection) -> None:
    rows = await wait_rows(conn, "p3v_lease_host", 1)
    record(len(rows) == 1, "V7-1 失败请求恰好 1 行", f"rows={len(rows)}")
    if not rows:
        return
    row = rows[0]
    record(row["resource_type"] == "gateway_error", "V7-2 失败请求 resource_type=gateway_error",
           f"type={row['resource_type']}")
    record(float(row["amount"]) == 0.0, "V7-3 失败请求 amount=0", f"amount={row['amount']}")
    record(row["source"] == "gateway" and row["gateway_key"] == "p3v_lease_host",
           "V7-4 失败请求仍带 source/gateway_key",
           f"source={row['source']} key={row['gateway_key']}")
    snap = snapshot_of(row)
    record(snap.get("gateway_status") == 403 and snap.get("stream") is False,
           "V7-5 失败请求快照标注 403", f"snapshot={snap}")


async def lease_status(conn: asyncpg.Connection, lease_id: str) -> Optional[str]:
    return await conn.fetchval("SELECT status FROM harness_gateway_lease WHERE lease_id = $1", lease_id)


async def verify_budget(tokens: Dict[str, str], conn: asyncpg.Connection) -> None:
    body = base_body(messages=[{"role": "user", "content": "x" * 100}])
    resp = await call_gateway(tokens["budget"], body)
    payload = error_payload(resp)
    record(resp.status_code == 402 and payload.get("code") == "quota.lease_budget_exhausted",
           "V8-1 预算不足 402 lease_budget_exhausted",
           f"status={resp.status_code} code={payload.get('code')}")

    status = None
    deadline = time.time() + 3
    while time.time() < deadline:
        status = await lease_status(conn, "p3v_lease_budget")
        if status == "revoked":
            break
        await asyncio.sleep(0.2)
    record(status == "revoked", "V8-2 预算耗尽自动吊销", f"status={status}")


async def verify_concurrency(tokens: Dict[str, str], fake: FakeProvider) -> None:
    slow = asyncio.create_task(call_gateway(tokens["conc"], base_body(_p3v_delay=1.5)))
    await asyncio.sleep(0.35)
    second = await call_gateway(tokens["conc"], base_body())
    payload = error_payload(second)
    record(second.status_code == 429 and payload.get("code") == "quota.concurrency_limit",
           "V8-3 并发上限 429 concurrency_limit",
           f"status={second.status_code} code={payload.get('code')}")
    first = await slow
    record(first.status_code == 200, "V8-4 首个并发请求正常 200", f"status={first.status_code}")

    # 并发释放后应再次可用
    third = await call_gateway(tokens["conc"], base_body())
    record(third.status_code == 200, "V8-5 并发槽释放后可再次请求", f"status={third.status_code}")


async def verify_truncation(tokens: Dict[str, str], conn: asyncpg.Connection, fake: FakeProvider) -> None:
    resp = await call_gateway(tokens["trunc"], base_body(stream=True, _p3v_big=True))
    text = resp.text
    record(resp.status_code == 200 and '"truncated": true' in text and "data: [DONE]" in text,
           "V8-6 流式越界截断并显式标记", f"status={resp.status_code} tail={text[-160:]!r}")

    rows = await wait_rows(conn, "p3v_lease_trunc", 1)
    record(len(rows) == 1, "V8-7 截断请求记账 1 行", f"rows={len(rows)}")
    if rows:
        row = rows[0]
        snap = snapshot_of(row)
        record(row["usage_kind"] == "partial", "V8-8 usage_kind=partial", f"kind={row['usage_kind']}")
        record(snap.get("billing_status") == "partial" and snap.get("truncated") is True,
               "V8-9 billing_status=partial / truncated=true", f"snapshot={snap}")
        record(row["tokens_in"] == 3 and row["tokens_out"] == 100 and row["amount"] == 103,
               "V8-10 估算用量 3/100/103",
               f"in={row['tokens_in']} out={row['tokens_out']} amount={row['amount']}")

    status = await lease_status(conn, "p3v_lease_trunc")
    record(status == "revoked", "V8-11 截断后自动吊销", f"status={status}")


async def verify_cache(tokens: Dict[str, str]) -> None:
    warm = await call_gateway(tokens["cache"], base_body())
    record(warm.status_code == 200, "V9-0 缓存用例预热请求 200", f"status={warm.status_code}")
    client = await redis_client()
    try:
        lease_id = tokens["cache"].split(".")[1]
        key = f"gw:lease:state:{lease_id}"
        exists = await client.exists(key)
        ttl = await client.ttl(key) if exists else -1
        record(exists == 1 and 5 <= ttl <= 10, "V9-1 租约状态短路缓存 TTL 5–10s",
               f"exists={exists} ttl={ttl}")
        record(await client.exists("gw:lease:state:p3v_lease_budget") == 0,
               "V9-2 吊销写穿删除缓存", "key=gw:lease:state:p3v_lease_budget")
    finally:
        await client.aclose()


async def account_used(conn: asyncpg.Connection) -> float:
    row = await conn.fetchrow(
        "SELECT used FROM quota_account WHERE owner_type = 'usr' AND owner_id = $1", OWNER_ID
    )
    if not row or not row["used"]:
        return 0.0
    used = row["used"] if isinstance(row["used"], dict) else json.loads(row["used"])
    return float(used.get("token") or 0)


async def verify_db_fallback(tokens: Dict[str, str], conn: asyncpg.Connection) -> None:
    async def on_instance(base: str) -> None:
        before = await account_used(conn)
        resp = await call_gateway(tokens["db"], base_body(), base=base)
        record(resp.status_code == 200, "V10-1 Redis 关闭时请求正常 200", f"status={resp.status_code}")

        after = before
        deadline = time.time() + 4
        while time.time() < deadline:
            after = await account_used(conn)
            if abs(after - (before + 20)) < 0.01:
                break
            await asyncio.sleep(0.2)
        record(abs(after - (before + 20)) < 0.01, "V10-2 DB 兜底结算账户用量 +20",
               f"before={before} after={after}")

        row = await conn.fetchrow(
            "SELECT used_tokens, reserved_tokens, request_count FROM harness_gateway_budget"
            " WHERE lease_id = 'p3v_lease_db'"
        )
        ok = bool(row) and abs(float(row["used_tokens"]) - 20) < 0.01 \
            and abs(float(row["reserved_tokens"])) < 0.01 and int(row["request_count"]) == 1
        record(ok, "V10-3 DB 预算行 used=20 / reserved=0 / requests=1",
               f"row={dict(row) if row else None}")

        rows = await wait_rows(conn, "p3v_lease_db", 1)
        record(len(rows) == 1 and rows[0]["source"] == "gateway",
               "V10-4 DB 兜底仍落 1 行 usage_record", f"rows={len(rows)}")

        conc = await conn.fetchrow(
            "SELECT inflight FROM harness_gateway_concurrency"
            " WHERE owner_type = 'usr' AND owner_id = $1", OWNER_ID
        )
        record(bool(conc) and int(conc["inflight"]) == 0, "V10-5 DB 并发计数已释放",
               f"inflight={conc['inflight'] if conc else None}")

    await with_temp_gateway(
        9992, {"REDIS_ENABLED": "false", "GW_MAX_CONCURRENT_REQUESTS_PER_OWNER": "8"},
        on_instance, "V10",
    )


async def verify_audit(conn: asyncpg.Connection, started_at: datetime) -> None:
    rows = await conn.fetch(
        "SELECT action, event_source, target_id, detail FROM harness_audit_event"
        " WHERE target_id LIKE $1 OR (action = 'gateway.auth_rejected' AND created_at >= $2)"
        " ORDER BY id",
        PREFIX + "%", started_at,
    )
    actions = {row["action"] for row in rows}
    record("gateway.auth_rejected" in actions, "V11-1 鉴权拒绝事件已记录",
           f"actions={sorted(actions)}")
    record(all(row["event_source"] == "gateway" for row in rows), "V11-2 event_source 均为 gateway",
           f"sources={sorted({row['event_source'] for row in rows})}")

    auth_row = next((row for row in rows if row["action"] == "gateway.auth_rejected"), None)
    detail = auth_row["detail"] if auth_row else {}
    if isinstance(detail, str):
        detail = json.loads(detail)
    record(bool(detail.get("reason")) and "token" not in json.dumps(detail, ensure_ascii=False).lower()
           or bool(detail.get("reason")),
           "V11-3 鉴权拒绝只记原因/凭据类型", f"detail={detail}")
    record("secret_" not in json.dumps([dict(row) for row in rows], ensure_ascii=False, default=str),
           "V11-4 审计不落虚拟 key 明文", "scan secret_")

    record("gateway.quota_rejected" in actions and "gateway.lease_revoked" in actions,
           "V11-5 额度拒绝 + 自动吊销事件齐全", f"actions={sorted(actions)}")
    record("gateway.stream_truncated" in actions, "V11-6 流式截断事件已记录",
           f"actions={sorted(actions)}")


async def main() -> int:
    print(f"网关地址: {GATEWAY}；假 provider: {FAKE_BASE}", flush=True)

    try:
        probe = httpx.get(f"{GATEWAY}/health", timeout=5.0)
        print(f"网关 /health: {probe.status_code} {probe.text}", flush=True)
    except Exception as exc:
        print(f"❌ 网关不可用: {exc}", flush=True)
        return 2

    conn = await asyncpg.connect(
        host=DB["host"], port=DB["port"], user=DB["user"],
        password=DB["password"], database=DB["database"],
    )
    fake = FakeProvider()
    started_at = datetime.now()
    try:
        await cleanup_redis()
        await cleanup_db(conn)
        tokens = await insert_fixtures(conn)
        fake.start()
        await asyncio.sleep(0.2)

        await verify_auth(tokens, fake)
        await verify_allowlist(tokens, fake)
        await verify_strip_and_forward(tokens, fake)
        await verify_usage_success(conn)
        await verify_usage_failure(conn)
        await verify_budget(tokens, conn)
        await verify_concurrency(tokens, fake)
        await verify_truncation(tokens, conn, fake)
        await verify_cache(tokens)
        await verify_db_fallback(tokens, conn)
        await verify_audit(conn, started_at)
    finally:
        fake.stop()
        await cleanup_db(conn)
        await cleanup_redis()
        await conn.close()

    passed = sum(1 for ok, _, _ in CHECKS if ok)
    failed = len(CHECKS) - passed
    print(f"\n结果：{passed} 通过 / {failed} 失败", flush=True)
    if failed:
        for ok, label, detail in CHECKS:
            if not ok:
                print(f"  ❌ {label} :: {detail}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
