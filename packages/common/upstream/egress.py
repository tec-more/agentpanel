"""出网校验：共享上游客户端强制执行的策略。

背景：Linux 容器实测确认 dsh 自身的 web_fetch 没有域名白名单，
出网管控只能由后端/网关承担。因此共享客户端在每次发送前无条件校验，
不存在 skip_egress / egress_enabled 一类可绕过的配置开关。

注意：web_fetch/web_search 属于 dsh 工具侧的直接出网通道，不经过本模块，
必须由 dsh 工具禁用或容器网络策略兜底；审批通道不作为放行前提。
"""
import ipaddress
from dataclasses import dataclass, field
from typing import FrozenSet, Iterable

from urllib.parse import urlparse

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(x)
    for x in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "100.64.0.0/10",
        "fc00::/7",
        "fe80::/10",
    )
)


class UpstreamEgressError(Exception):
    """出网校验失败（403），fail-closed。"""

    status_code = 403

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class EgressPolicy:
    """强制出网策略；策略本身没有“关闭”开关。"""

    allowed_hosts: FrozenSet[str] = frozenset()
    allow_loopback: bool = False
    allow_private: bool = False
    require_https: bool = False
    enforce_allowlist: bool = True

    @classmethod
    def from_allowlist(
        cls, hosts: Iterable[str], *, allow_loopback: bool = False
    ) -> "EgressPolicy":
        cleaned = frozenset(
            str(host).strip().lower() for host in hosts if str(host).strip()
        )
        return cls(allowed_hosts=cleaned, allow_loopback=allow_loopback)

    @classmethod
    def for_provider(cls, kind: str, endpoint_url: str = "") -> "EgressPolicy":
        """llm provider 策略：仅本地 provider 允许回环/私网。"""
        normalized = str(kind or "").strip().lower()
        local = normalized in {"local", "localai", "localhost"}
        # 公共 provider 只做协议与私网拦截，不强制 https，避免破坏既有 http 端点
        policy = cls(
            allowed_hosts=frozenset(),
            allow_loopback=local,
            allow_private=local,
            require_https=False,
            enforce_allowlist=False,
        )
        # endpoint_url 仅用于将来按 host 白名单收紧，当前保持行为兼容
        return policy

    def check(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise UpstreamEgressError("provider 地址协议不被允许")
        if parsed.username or parsed.password:
            raise UpstreamEgressError("provider 地址不得包含用户凭据")
        host = (parsed.hostname or "").strip().lower()
        if not host:
            raise UpstreamEgressError("provider 地址缺少主机名")

        if self.enforce_allowlist:
            if not self.allowed_hosts:
                raise UpstreamEgressError("出网白名单为空，拒绝所有上游请求")
            if host not in self.allowed_hosts:
                raise UpstreamEgressError(f"provider 域名不在出网白名单: {host}")

        if self.require_https and parsed.scheme != "https":
            raise UpstreamEgressError("provider 地址必须使用 https")

        self._check_private(host)

    def _check_private(self, host: str) -> None:
        if host in LOOPBACK_HOSTS or host.startswith("127."):
            if not self.allow_loopback:
                raise UpstreamEgressError(f"provider 地址指向回环地址，已拒绝: {host}")
            return
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        if not self.allow_private:
            if (
                address.is_loopback
                or address.is_link_local
                or address.is_private
                or any(address in network for network in _PRIVATE_NETWORKS)
            ):
                raise UpstreamEgressError(f"provider 地址指向私网地址，已拒绝: {host}")
