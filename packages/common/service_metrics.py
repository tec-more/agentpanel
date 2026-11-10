"""独立服务（网关 / 编排）观测指标，复用共享 registry。

T7.4：为物理拆分后的两个容器补齐 health、5xx、预占失败、租约缓存命中指标。
（2026-11-10 更名：模块由 `l3_metrics` 更名为 `service_metrics`，指标名去掉 `l3_` 前缀，
类 `L3HttpMetricsMiddleware` 更名为 `HttpMetricsMiddleware`。）

设计约束：
- 复用 `prometheus.py` 的 registry 与 HTTP 指标名，使 app / gateway / orchestration 告警表达式可跨 job 复用；
- HTTP 采集使用**纯 ASGI 中间件**而非 `PrometheusMiddleware`（BaseHTTPMiddleware），
  避免包装 StreamingResponse 破坏网关 `/chat/completions` 的 SSE 原样透传；
- `endpoint` 标签做路径归一化，防止 `run_no` / `hold_id` 等高基数段撑爆序列；
- 所有埋点为观测旁路，失败一律吞掉，不改变任何业务分支与返回码。
"""
import asyncio
import re
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from packages.common.prometheus import (
    active_requests,
    registry,
    request_counter,
    request_duration,
    response_size,
    update_system_metrics,
)

# 单段路径若形似 id（纯数字 / 长十六进制 / 长标识串）统一折叠，控制标签基数。
_ID_SEGMENT = re.compile(r"^(?:\d+|[0-9a-fA-F]{8,}|[A-Za-z0-9_-]{16,})$")


def normalize_path(path: str) -> str:
    """兜底：把形似 id 的路径段折叠成 `:id`（用于未匹配路由/404）。"""
    if not path:
        return "/"
    return "/".join(":id" if seg and _ID_SEGMENT.match(seg) else seg for seg in path.split("/")) or "/"


def endpoint_from_scope(scope: Dict[str, Any]) -> str:
    """从路由匹配后的 `path_params` 精确折叠动态段，得到路由模板式标签。

    `nope`、`other_1234` 这类短 run_no 不像 id，单靠正则会漏，
    因此优先用 Starlette 写入 scope 的动态参数值按段精确替换。
    """
    path = str(scope.get("path") or "/")
    params = scope.get("path_params") or {}
    dynamic = {str(v) for v in params.values() if v is not None}
    if dynamic:
        path = "/".join(":id" if seg in dynamic else seg for seg in path.split("/"))
    return normalize_path(path)


# ---------------------------------------------------------------------------
# 独立服务专属业务指标
# ---------------------------------------------------------------------------

lease_cache_lookups = Counter(
    "lease_cache_lookups_total",
    "Gateway lease cache lookups by result",
    ["result"],  # hit | miss | unavailable | error
    registry=registry,
)

quota_operations = Counter(
    "quota_operations_total",
    "Orchestration -> L2 quota API operations",
    ["action", "result", "reason"],  # reserve|settle|release / ok|failed / 异常类名
    registry=registry,
)

health_check_status = Gauge(
    "health_check_status",
    "Last health probe result (1=healthy/skipped, 0=unhealthy/unknown)",
    ["service", "check"],
    registry=registry,
)

health_check_last_success = Gauge(
    "health_check_last_success_timestamp_seconds",
    "Unix timestamp of the last successful full health probe",
    ["service"],
    registry=registry,
)

service_info = Gauge(
    "service_info",
    "Static service identity (always 1 while the process is alive)",
    ["service", "version"],
    registry=registry,
)


# 预注册零值序列：无业务流量时 /metrics 也能看到完整口径，
# 便于 Grafana 建面板与告警表达式求值（失败序列的 reason 按需创建）。
for _result in ("hit", "miss", "unavailable", "error"):
    lease_cache_lookups.labels(result=_result)
for _action in ("reserve", "settle", "release"):
    quota_operations.labels(action=_action, result="ok", reason="none")


def inc_lease_cache(result: str) -> None:
    try:
        lease_cache_lookups.labels(result=result).inc()
    except Exception:
        pass


def inc_quota_operation(action: str, result: str, reason: str = "") -> None:
    try:
        quota_operations.labels(action=action, result=result, reason=reason or "none").inc()
    except Exception:
        pass


def mark_service(service: str, version: str) -> None:
    try:
        service_info.labels(service=service, version=version).set(1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 纯 ASGI HTTP 指标中间件
# ---------------------------------------------------------------------------

class HttpMetricsMiddleware:
    """统计 method/endpoint/status_code、耗时、响应体大小与在途请求数。

    不包装响应对象、不消费 body，SSE 流式响应保持逐帧原样透传。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "GET")
        started = time.perf_counter()
        status_code = 500
        body_bytes = 0
        recorded = False
        active_requests.inc()

        def _record() -> None:
            nonlocal recorded
            if recorded:
                return
            recorded = True
            elapsed = time.perf_counter() - started
            # 响应发出时路由已匹配，scope["path_params"] 可用，标签取模板式路径。
            endpoint = endpoint_from_scope(scope)
            try:
                request_counter.labels(
                    method=method, endpoint=endpoint, status_code=str(status_code)
                ).inc()
                request_duration.labels(method=method, endpoint=endpoint).observe(elapsed)
                response_size.labels(method=method, endpoint=endpoint).observe(body_bytes)
            except Exception:
                pass
            finally:
                active_requests.dec()

        async def _send(message: Dict[str, Any]) -> None:
            nonlocal status_code, body_bytes
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 0)
            elif message.get("type") == "http.response.body":
                body_bytes += len(message.get("body") or b"")
                if not message.get("more_body"):
                    _record()
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            status_code = 500
            raise
        finally:
            # 客户端提前断开 / 抛异常时没有 response.body，此处兜底只记一次。
            _record()


# ---------------------------------------------------------------------------
# /metrics 端点：健康检查随抓取刷新（10s 缓存，避免每次抓取都打 DB/Redis）
# ---------------------------------------------------------------------------

ProbeFn = Callable[[], Awaitable[Dict[str, Any]]]

_probe_cache: Dict[str, float] = {}
_PROBE_TTL_SECONDS = 10.0


def make_metrics_endpoint(
    service: str,
    probes: Optional[Dict[str, ProbeFn]] = None,
) -> Callable[[Request], Awaitable[Response]]:
    """返回不依赖 L2 settings 的 /metrics 端点（L2 端点受 PROMETHEUS_ENABLED 控制）。

    每次抓取最多做一次 DB/Redis 探测（10s 内复用），把结果写入 Gauge，
    从而使 `health_check_status` 与 `up` 一起覆盖灰度方案 R1。
    """

    async def _endpoint(request: Request) -> Response:
        if probes:
            now = time.monotonic()
            if now - _probe_cache.get(service, 0.0) >= _PROBE_TTL_SECONDS:
                _probe_cache[service] = now
                names = list(probes)
                try:
                    results = await asyncio.gather(
                        *(probes[name]() for name in names), return_exceptions=True
                    )
                except Exception:
                    results = [RuntimeError("probe failed")] * len(names)
                all_ok = True
                for name, result in zip(names, results):
                    status = (
                        str(result.get("status") or "unknown")
                        if isinstance(result, dict)
                        else "unhealthy"
                    )
                    ok = status in ("healthy", "skipped")
                    all_ok = all_ok and ok
                    health_check_status.labels(service=service, check=name).set(1 if ok else 0)
                if all_ok:
                    health_check_last_success.labels(service=service).set(time.time())

        try:
            update_system_metrics()
        except Exception:
            pass
        return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return _endpoint


__all__ = [
    "HttpMetricsMiddleware",
    "make_metrics_endpoint",
    "normalize_path",
    "endpoint_from_scope",
    "inc_lease_cache",
    "inc_quota_operation",
    "mark_service",
]
