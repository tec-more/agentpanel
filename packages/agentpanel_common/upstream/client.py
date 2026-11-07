"""共享上游 HTTP 客户端。

安全语义（不可绕过）：
- 出网校验在每次发送前强制执行（EgressPolicy 为必填参数），不提供关闭开关；
- 只有“请求尚未发出”的连接类失败可重试；响应体已消费、流式响应头已返回、
  或调用方声明有副作用（replay=False）时一律不重放；
- 流式请求一旦拿到响应头就不再重试，满足“开始向客户端输出后不得重试”。

网关与 llm 只负责业务语义，传输层统一由本模块承担。
"""
import asyncio
from typing import AsyncIterator, Dict, Optional, Tuple

import httpx

from packages.agentpanel_common.upstream.config import UpstreamConfig
from packages.agentpanel_common.upstream.egress import EgressPolicy, UpstreamEgressError


class UpstreamError(Exception):
    """上游调用失败的统一基类。"""

    kind = "upstream"

    def __init__(self, message: str, *, original: Optional[BaseException] = None):
        super().__init__(message)
        self.message = message
        self.original = original


class UpstreamTimeout(UpstreamError):
    """上游超时；timeout_kind ∈ connect|read|write|pool|total。"""

    kind = "timeout"

    def __init__(self, timeout_kind: str, *, original: Optional[BaseException] = None):
        super().__init__(f"上游超时({timeout_kind})", original=original)
        self.timeout_kind = timeout_kind

    @property
    def retryable(self) -> bool:
        # 连接阶段（含连接超时/池等待）请求未发出，可安全重试
        return self.timeout_kind in ("connect", "pool")


class UpstreamConnectError(UpstreamError):
    """连接失败：请求未发出，可安全重试。"""

    kind = "connect"


class UpstreamReadError(UpstreamError):
    """读取响应失败：请求可能已发出/已消费，不重试。"""

    kind = "read"


class UpstreamStatusError(UpstreamError):
    """上游返回 >=400 状态码。"""

    kind = "status"

    def __init__(
        self,
        status_code: int,
        body: bytes,
        response: Optional[httpx.Response] = None,
        *,
        label: str = "上游请求",
    ):
        self.status_code = status_code
        self.body = body or b""
        self.response = response
        self.label = label
        super().__init__(self.body_text)

    @property
    def body_text(self) -> str:
        if isinstance(self.body, (bytes, bytearray)):
            return bytes(self.body).decode("utf-8", "ignore")
        return str(self.body)


_clients: Dict[str, httpx.AsyncClient] = {}
_clients_lock: Optional[asyncio.Lock] = None


def _lock() -> asyncio.Lock:
    global _clients_lock
    if _clients_lock is None:
        _clients_lock = asyncio.Lock()
    return _clients_lock


async def get_client(cfg: UpstreamConfig) -> httpx.AsyncClient:
    """按配置签名复用连接池；client 不随单请求关闭。"""
    signature = cfg.signature()
    async with _lock():
        client = _clients.get(signature)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(**cfg.client_kwargs())
            _clients[signature] = client
        return client


async def close_upstream_clients() -> None:
    async with _lock():
        clients = list(_clients.values())
        _clients.clear()
    for client in clients:
        try:
            await client.aclose()
        except Exception:
            pass


def _map_exception(exc: BaseException) -> UpstreamError:
    if isinstance(exc, UpstreamError):
        return exc
    if isinstance(exc, httpx.ConnectTimeout):
        return UpstreamTimeout("connect", original=exc)
    if isinstance(exc, httpx.PoolTimeout):
        return UpstreamTimeout("pool", original=exc)
    if isinstance(exc, httpx.ConnectError):
        return UpstreamConnectError(str(exc), original=exc)
    if isinstance(exc, httpx.ReadTimeout):
        return UpstreamTimeout("read", original=exc)
    if isinstance(exc, httpx.WriteTimeout):
        return UpstreamTimeout("write", original=exc)
    if isinstance(exc, (httpx.ReadError, httpx.RemoteProtocolError, httpx.WriteError)):
        return UpstreamReadError(str(exc), original=exc)
    if isinstance(exc, asyncio.TimeoutError):
        return UpstreamTimeout("total", original=exc)
    if isinstance(exc, httpx.HTTPError):
        return UpstreamError(str(exc), original=exc)
    return UpstreamError(str(exc), original=exc)


def _retryable(exc: UpstreamError) -> bool:
    if isinstance(exc, UpstreamConnectError):
        return True
    if isinstance(exc, UpstreamTimeout):
        return exc.retryable
    return False


async def _with_total(coro, total_timeout: Optional[float]):
    if not total_timeout or float(total_timeout) <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=float(total_timeout))
    except asyncio.TimeoutError as exc:
        raise UpstreamTimeout("total", original=exc) from exc


def _retry_after_seconds(response: httpx.Response) -> Optional[float]:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


async def _sleep_backoff(
    cfg: UpstreamConfig, attempt: int, retry_after: Optional[float]
) -> None:
    delay = min(
        float(cfg.retry_backoff) * (2 ** max(0, attempt - 1)),
        float(cfg.retry_max_backoff),
    )
    if retry_after is not None:
        delay = min(max(delay, retry_after), float(cfg.retry_max_backoff))
    if delay > 0:
        await asyncio.sleep(delay)


def _require_policy(policy: EgressPolicy) -> EgressPolicy:
    if not isinstance(policy, EgressPolicy):
        # 编程错误也按 fail-closed 处理，避免漏校验
        raise UpstreamEgressError("缺少出网策略，拒绝上游请求")
    return policy


async def request_json(
    method: str,
    url: str,
    *,
    json=None,
    content=None,
    headers: Optional[Dict[str, str]] = None,
    cfg: UpstreamConfig,
    policy: EgressPolicy,
    read_timeout: Optional[float] = None,
    total_timeout: Optional[float] = None,
    replay: bool = False,
) -> httpx.Response:
    """非流式请求（响应体已完整读取）。

    replay=False 时仅重试“请求未发出”的连接类故障；replay=True 额外允许
    配置的可重试状态码（429/5xx）重放，供无副作用或可安全重放的调用使用。
    """
    _require_policy(policy).check(url)
    timeout = cfg.httpx_timeout(read_timeout=read_timeout, total_timeout=total_timeout)
    attempts = cfg.max_attempts()
    effective_total = cfg.total_timeout if total_timeout is None else total_timeout
    last_error: Optional[UpstreamError] = None

    for attempt in range(1, attempts + 1):
        client = await get_client(cfg)
        try:
            response = await _with_total(
                client.request(
                    method,
                    url,
                    json=json,
                    content=content,
                    headers=headers,
                    timeout=timeout,
                ),
                effective_total,
            )
        except Exception as exc:
            mapped = _map_exception(exc)
            last_error = mapped
            if attempt < attempts and _retryable(mapped):
                await _sleep_backoff(cfg, attempt, None)
                continue
            raise mapped from exc

        if (
            replay
            and response.status_code in cfg.retry_statuses
            and attempt < attempts
        ):
            retry_after = _retry_after_seconds(response)
            try:
                await response.aclose()
            except Exception:
                pass
            await _sleep_backoff(cfg, attempt, retry_after)
            continue
        return response

    raise last_error or UpstreamError("上游请求失败")


async def post_json(
    url: str,
    *,
    json=None,
    content=None,
    headers: Optional[Dict[str, str]] = None,
    cfg: UpstreamConfig,
    policy: EgressPolicy,
    read_timeout: Optional[float] = None,
    total_timeout: Optional[float] = None,
    replay: bool = False,
) -> httpx.Response:
    return await request_json(
        "POST",
        url,
        json=json,
        content=content,
        headers=headers,
        cfg=cfg,
        policy=policy,
        read_timeout=read_timeout,
        total_timeout=total_timeout,
        replay=replay,
    )


async def get_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    cfg: UpstreamConfig,
    policy: EgressPolicy,
    read_timeout: Optional[float] = None,
    total_timeout: Optional[float] = None,
) -> httpx.Response:
    return await request_json(
        "GET",
        url,
        headers=headers,
        cfg=cfg,
        policy=policy,
        read_timeout=read_timeout,
        total_timeout=total_timeout,
    )


async def send_stream(
    url: str,
    *,
    json=None,
    headers: Optional[Dict[str, str]] = None,
    cfg: UpstreamConfig,
    policy: EgressPolicy,
    read_timeout: Optional[float] = None,
    total_timeout: Optional[float] = None,
) -> httpx.Response:
    """发起流式请求并返回已拿到响应头的 Response。

    只可能在“尚未拿到响应”时重试连接失败；拿到响应后永不重试（即使状态码
    在可重试集合）。total_timeout 仅约束到响应头，不覆盖响应体读取。
    调用方负责 aclose()。
    """
    _require_policy(policy).check(url)
    timeout = cfg.httpx_timeout(read_timeout=read_timeout, total_timeout=total_timeout)
    attempts = cfg.max_attempts()
    effective_total = cfg.total_timeout if total_timeout is None else total_timeout
    last_error: Optional[UpstreamError] = None

    for attempt in range(1, attempts + 1):
        client = await get_client(cfg)
        request = client.build_request("POST", url, json=json, headers=headers)
        try:
            response = await _with_total(
                client.send(request, stream=True), effective_total
            )
        except Exception as exc:
            mapped = _map_exception(exc)
            last_error = mapped
            if attempt < attempts and _retryable(mapped):
                await _sleep_backoff(cfg, attempt, None)
                continue
            raise mapped from exc
        # 响应头已到：之后绝不再重试
        return response

    raise last_error or UpstreamError("上游流式请求失败")


async def ensure_success(response: httpx.Response, *, label: str = "上游请求") -> None:
    if response.status_code >= 400:
        try:
            body = await response.aread()
        except Exception:
            body = b""
        raise UpstreamStatusError(
            response.status_code, body, response, label=label
        )


async def iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
    """逐条产出 SSE `data:` 内容；跳过注释/空行，遇 [DONE] 结束。"""
    async for line in response.aiter_lines():
        if not line:
            continue
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        data = stripped[5:]
        if data.startswith(" "):
            data = data[1:]
        data = data.strip()
        if data == "[DONE]":
            break
        if not data:
            continue
        yield data


def is_timeout_error(exc: BaseException) -> bool:
    return isinstance(exc, UpstreamTimeout)


def is_connect_error(exc: BaseException) -> bool:
    return isinstance(exc, UpstreamConnectError)


__all__: Tuple[str, ...] = (
    "EgressPolicy",
    "UpstreamEgressError",
    "UpstreamError",
    "UpstreamTimeout",
    "UpstreamConnectError",
    "UpstreamReadError",
    "UpstreamStatusError",
    "UpstreamConfig",
    "get_client",
    "close_upstream_clients",
    "request_json",
    "post_json",
    "get_json",
    "send_stream",
    "ensure_success",
    "iter_sse_data",
    "is_timeout_error",
    "is_connect_error",
)
