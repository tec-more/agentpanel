"""
http 节点运行时防护（R-10 / 05-§2.5 SSRF）

规则：
- 域名白名单（管理员维护；环境变量 HTTP_NODE_DOMAIN_WHITELIST，逗号分隔，支持 *.example.com 通配）
- 内网阻断：禁 10/8、172.16/12、192.168/16、127/8、169.254/16、::1、fc00::/7
- DNS 解析后二次校验（防 DNS rebinding）：先校验域名在白名单，再解析全部 IP 逐一判定
- 仅 GET/POST；超时 ≤ 30s；响应 ≤ 5MB
"""
import asyncio
import ipaddress
import os
import socket
from typing import List, Optional, Set
from urllib.parse import urlparse

from base.plugins.agent.services.engine.errors import NodeCapabilityDenied

ALLOWED_METHODS = {"GET", "POST"}
MAX_TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def load_domain_whitelist() -> Set[str]:
    """域名白名单（管理员维护，环境变量注入；小写归一）"""
    raw = os.getenv("HTTP_NODE_DOMAIN_WHITELIST", "")
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def is_private_ip(ip: str) -> bool:
    """内网/保留地址判定（SSRF 阻断清单）"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # 无法解析按内网处理（安全侧）
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved:
        return True
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _domain_matches(host: str, whitelist: Set[str]) -> bool:
    host = host.lower()
    for item in whitelist:
        if item.startswith("*."):
            if host == item[2:] or host.endswith("." + item[2:]):
                return True
        elif host == item:
            return True
    return False


async def assert_url_allowed(url: str, whitelist: Optional[Set[str]] = None) -> str:
    """
    运行时 URL 校验：白名单 → DNS 解析 → 全部 IP 内网二次校验

    Returns:
        归一化后的 URL

    Raises:
        NodeCapabilityDenied: 未过校验（不可重试，直接失败）
    """
    whitelist = whitelist if whitelist is not None else load_domain_whitelist()
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise NodeCapabilityDenied(f"http 节点 URL 非法: {url!r}")
    host = parsed.hostname.lower()

    if not whitelist:
        raise NodeCapabilityDenied("http 节点域名白名单为空，拒绝所有出站请求")
    if not _domain_matches(host, whitelist):
        raise NodeCapabilityDenied(f"http 节点域名未在白名单: {host}")

    # DNS 解析（异步，R-08）后二次校验全部解析 IP（防 DNS rebinding）
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = await asyncio.get_event_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise NodeCapabilityDenied(f"http 节点域名解析失败: {host} ({e})")
    ips: List[str] = sorted({info[4][0] for info in infos})
    if not ips:
        raise NodeCapabilityDenied(f"http 节点域名无解析结果: {host}")
    for ip in ips:
        if is_private_ip(ip):
            raise NodeCapabilityDenied(f"http 节点目标解析到内网地址，已阻断: {host} -> {ip}")
    return url


def assert_method_allowed(method: str) -> str:
    m = (method or "GET").upper()
    if m not in ALLOWED_METHODS:
        raise NodeCapabilityDenied(f"http 节点仅支持 GET/POST，当前: {m}")
    return m
