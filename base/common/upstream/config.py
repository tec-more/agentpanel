"""共享上游调用配置。

网关与 llm 插件都通过该配置描述连接池、超时、重试、TLS/代理行为，
避免两处各写一份且逐渐漂移。
"""
from dataclasses import dataclass
from typing import Optional, Tuple

import httpx

DEFAULT_RETRY_STATUSES: Tuple[int, ...] = (429, 500, 502, 503, 504)


@dataclass(frozen=True)
class UpstreamConfig:
    """一次上游调用的传输层参数。"""

    # 超时：区分连接 / 读 / 单次尝试总时长（<=0 表示关闭总时长限制）
    connect_timeout: float = 10.0
    read_timeout: float = 300.0
    total_timeout: float = 0.0

    # 连接池
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0

    # TLS / 代理
    verify_tls: bool = True
    proxy_url: str = ""
    trust_env: bool = False
    follow_redirects: bool = False
    http2: bool = False

    # 重试：retry_attempts 为总尝试次数（1 表示不重试）
    retry_attempts: int = 1
    retry_backoff: float = 0.5
    retry_max_backoff: float = 4.0
    retry_statuses: Tuple[int, ...] = DEFAULT_RETRY_STATUSES

    def max_attempts(self) -> int:
        return max(1, int(self.retry_attempts))

    def signature(self) -> str:
        """连接池缓存键：配置变化即换池。"""
        return repr(
            (
                self.connect_timeout,
                self.read_timeout,
                self.total_timeout,
                self.max_connections,
                self.max_keepalive_connections,
                self.keepalive_expiry,
                self.verify_tls,
                self.proxy_url,
                self.trust_env,
                self.follow_redirects,
                self.http2,
            )
        )

    def httpx_timeout(
        self,
        read_timeout: Optional[float] = None,
        total_timeout: Optional[float] = None,
    ) -> httpx.Timeout:
        read = float(self.read_timeout if read_timeout is None else read_timeout)
        connect = float(self.connect_timeout)
        return httpx.Timeout(connect=connect, read=read, write=connect, pool=connect)

    def client_kwargs(self) -> dict:
        kwargs = {
            "timeout": self.httpx_timeout(),
            "limits": httpx.Limits(
                max_connections=int(self.max_connections),
                max_keepalive_connections=int(self.max_keepalive_connections),
                keepalive_expiry=float(self.keepalive_expiry),
            ),
            "verify": bool(self.verify_tls),
            "follow_redirects": bool(self.follow_redirects),
            "trust_env": bool(self.trust_env),
        }
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        if self.http2:
            kwargs["http2"] = True
        return kwargs
