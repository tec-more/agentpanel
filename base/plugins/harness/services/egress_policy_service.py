"""
L2 侧出网策略来源（策略快照下发）

定位（必须诚实表述）：
- 本模块只是「策略来源」：把业务层希望客户端遵守的出网策略整理成可版本化、
  可校验的快照，供客户端（dsh）拉取并自行应用。
- 它不是执行边界：客户端管理员、原始套接字、IPv6/QUIC、绕过客户端工具注册表的
  行为都无法被这里阻断。真正阻断要靠终端网络策略（防火墙/代理）或容器网络策略。
- 因此这里只回答「应该怎么做」，不声称「已经阻止出网」。

单一来源约定：
- provider 域名白名单不在 config.egress 里重复配置，统一读取
  harness.manifest.config.gateway.provider_domain_allowlist（经 gateway_config()），
  与网关数据面校验共用同一份配置，避免两处漂移。
- 本模块不修改网关校验语义，只读取。

版本与哈希：
- 策略版本号来自 config.egress.version；
- 内容哈希 = sha256(稳定序列化后的 policy 内容)，客户端可自行复算校验。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Dict, List, Optional

from base.plugins.harness.services.gateway_config import issuance_config, upstream_allowlist
from base.common.plugin_manager import plugin_manager
from base.plugins.harness.models.harness import HarnessAuditEvent
from base.plugins.harness.services.audit_service import HarnessAuditService

PLUGIN_NAME = "harness"

# 默认策略项；manifest.config.egress 未提供或为 null 时使用。
DEFAULT_EGRESS_CONFIG: Dict[str, Any] = {
    "version": 1,
    "min_supported_version": 1,
    # 默认禁止客户端绕过网关直连 provider
    "allow_client_non_gateway": False,
    # 至少覆盖 web_fetch / web_search 这类直连出网工具
    "tool_denylist": ["web_fetch", "web_search", "browser", "http_request"],
    "snapshot_ttl_seconds": 300,
}

HASH_ALGORITHM: Dict[str, str] = {
    "algorithm": "sha256",
    "canonicalization": "json sort_keys=True,separators=(',',':'),ensure_ascii=False",
    "prefix": "sha256:",
}

DISCLAIMER = (
    "本快照仅为策略来源，不是执行边界；客户端必须自行应用并 fail-closed。"
    "客户端管理员、原始套接字、IPv6/QUIC 等仍可能绕过，真正阻断需依赖终端网络策略或容器网络策略。"
)

_MISSING = object()

# 进程内缓存：最近一次已留痕的策略哈希，避免每次请求都查审计表。
_AUDITED_HASH: Optional[str] = None
_AUDIT_LOCK: Optional[asyncio.Lock] = None


class EgressPolicyConfigError(RuntimeError):
    """config.egress 配置非法；接口按 fail-closed 拒绝下发。"""


class EgressPolicyIncompatible(Exception):
    """客户端支持的策略版本与当前策略不兼容。"""

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        client_version: Any = None,
        policy_version: Any = None,
        min_supported_version: Any = None,
        content_hash: str = "",
    ):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.client_version = client_version
        self.policy_version = policy_version
        self.min_supported_version = min_supported_version
        self.content_hash = content_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compatible": False,
            "decision": "deny",
            "fail_closed": True,
            "reason": self.reason,
            "client_version": self.client_version,
            "policy_version": self.policy_version,
            "min_supported_version": self.min_supported_version,
            "content_hash": self.content_hash,
            "notice": "客户端必须停止继续使用出网能力并升级到受支持的策略版本",
        }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def egress_config() -> Dict[str, Any]:
    """读取 manifest.config.egress，非法配置直接抛错（fail-closed）。"""
    manifest = plugin_manager.get_manifest(PLUGIN_NAME) or {}
    raw = (manifest.get("config") or {}).get("egress") or {}
    if not isinstance(raw, dict):
        raise EgressPolicyConfigError("config.egress 必须为对象")

    cfg = dict(DEFAULT_EGRESS_CONFIG)
    cfg.update({k: v for k, v in raw.items() if v is not None and k in DEFAULT_EGRESS_CONFIG})

    try:
        version = int(cfg["version"])
        min_supported = int(cfg["min_supported_version"])
        ttl = int(cfg["snapshot_ttl_seconds"])
    except (TypeError, ValueError):
        raise EgressPolicyConfigError("config.egress 的 version/min_supported_version/snapshot_ttl_seconds 必须为整数")
    if version < 1 or min_supported < 1:
        raise EgressPolicyConfigError("config.egress 版本号必须 >= 1")
    if ttl < 30 or ttl > 86400:
        raise EgressPolicyConfigError("config.egress.snapshot_ttl_seconds 需在 30-86400 秒")

    tools = cfg.get("tool_denylist")
    if not isinstance(tools, list) or not all(isinstance(t, str) and t.strip() for t in tools):
        raise EgressPolicyConfigError("config.egress.tool_denylist 必须为非空字符串数组")

    return {
        "version": version,
        "min_supported_version": min_supported,
        "allow_client_non_gateway": _as_bool(cfg.get("allow_client_non_gateway")),
        "tool_denylist": _dedupe([t.strip() for t in tools]),
        "snapshot_ttl_seconds": ttl,
    }


def _dedupe(items: List[str]) -> List[str]:
    seen: Dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen.keys())


def provider_domain_allowlist() -> List[str]:
    """复用网关的唯一白名单来源（不在此处重复配置）。"""
    cfg = issuance_config()
    return sorted(upstream_allowlist(cfg))


def current_policy() -> Dict[str, Any]:
    """当前生效的策略内容（哈希与下发都以它为准）。"""
    cfg = egress_config()
    gw = issuance_config()
    return {
        "version": cfg["version"],
        "allow_client_non_gateway": cfg["allow_client_non_gateway"],
        "tool_denylist": list(cfg["tool_denylist"]),
        "provider_domain_allowlist": provider_domain_allowlist(),
        "gateway": {
            "deployment": gw.get("deployment"),
            "public_base_url": str(gw.get("public_base_url") or "").rstrip("/"),
            "lease_issue_endpoint": "/v1/harness/gateway/leases",
        },
        # 诚实标注：本策略只做来源，不做执行
        "enforcement": "policy_source_only",
    }


def canonical_json(policy: Dict[str, Any]) -> str:
    return json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def policy_hash(policy: Dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(policy).encode("utf-8")).hexdigest()
    return f"{HASH_ALGORITHM['prefix']}{digest}"


def snapshot(client_version: Optional[int]) -> Dict[str, Any]:
    """构建客户端快照；版本不兼容抛 EgressPolicyIncompatible。"""
    cfg = egress_config()
    policy = current_policy()
    content_hash = policy_hash(policy)
    version = cfg["version"]
    min_supported = cfg["min_supported_version"]

    if min_supported > version:
        raise EgressPolicyIncompatible(
            "server_policy_below_min_supported",
            "服务端策略版本低于其声明的最低支持版本，拒绝下发",
            client_version=client_version,
            policy_version=version,
            min_supported_version=min_supported,
            content_hash=content_hash,
        )
    if client_version is None:
        raise EgressPolicyIncompatible(
            "client_version_unknown",
            "未提供客户端支持的策略版本，按 fail-closed 拒绝下发",
            client_version=None,
            policy_version=version,
            min_supported_version=min_supported,
            content_hash=content_hash,
        )
    if client_version < min_supported:
        raise EgressPolicyIncompatible(
            "client_version_too_old",
            f"客户端策略版本 {client_version} 低于最低支持版本 {min_supported}",
            client_version=client_version,
            policy_version=version,
            min_supported_version=min_supported,
            content_hash=content_hash,
        )

    return {
        "compatible": True,
        "policy_version": version,
        "min_supported_version": min_supported,
        "content_hash": content_hash,
        "hash_algorithm": HASH_ALGORITHM,
        "cache_ttl_seconds": cfg["snapshot_ttl_seconds"],
        "policy": policy,
        "source": {
            "config": "harness.manifest.config.egress",
            "provider_domain_allowlist": "harness.manifest.config.gateway.provider_domain_allowlist",
            "note": "白名单与网关数据面校验共用同一份配置",
        },
        "disclaimer": DISCLAIMER,
    }


def _diff_policy(before: Any, after: Any) -> List[str]:
    """返回变化的字段路径（用于审计 changed_fields）。"""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ["<policy>"]

    changed: List[str] = []

    def walk(old: Dict[str, Any], new: Dict[str, Any], prefix: str) -> None:
        for key in sorted(set(old) | set(new)):
            path = f"{prefix}{key}"
            old_value = old.get(key, _MISSING)
            new_value = new.get(key, _MISSING)
            if isinstance(old_value, dict) and isinstance(new_value, dict):
                walk(old_value, new_value, f"{path}.")
            elif old_value != new_value:
                changed.append(path)

    walk(before, after, "")
    return changed


def _audit_lock() -> asyncio.Lock:
    global _AUDIT_LOCK
    if _AUDIT_LOCK is None:
        _AUDIT_LOCK = asyncio.Lock()
    return _AUDIT_LOCK


async def ensure_change_audited(policy: Optional[Dict[str, Any]] = None) -> Optional[HarnessAuditEvent]:
    """策略内容相对上次审计发生变化时留痕（谁/何时/改了什么）。

    manifest 由拥有文件系统权限的运维修改，接口侧只能记录「系统/manifest」，
    真实编辑者需通过配置管理或版本库追溯。
    """
    global _AUDITED_HASH
    target = policy or current_policy()
    target_hash = policy_hash(target)
    if _AUDITED_HASH == target_hash:
        return None

    async with _audit_lock():
        if _AUDITED_HASH == target_hash:
            return None

        previous = (
            await HarnessAuditEvent.filter(action="egress.policy.changed")
            .order_by("-id")
            .first()
        )
        previous_detail = (previous.detail or {}) if previous else {}
        previous_hash = previous_detail.get("new_hash")
        if previous_hash == target_hash:
            _AUDITED_HASH = target_hash
            return None

        before = previous_detail.get("policy_after")
        changed_fields = _diff_policy(before, target) if before else sorted(target.keys())

        event = await HarnessAuditService.record(
            "egress.policy.changed",
            actor_type="system",
            actor_id="harness.manifest",
            target_type="policy",
            target_id=str(target.get("version")),
            risk_level="medium",
            event_source="policy",
            detail={
                "change_kind": "update" if previous else "initial",
                "previous_version": previous_detail.get("new_version"),
                "previous_hash": previous_hash,
                "new_version": target.get("version"),
                "new_hash": target_hash,
                "changed_fields": changed_fields,
                "policy_before": before,
                "policy_after": target,
                "note": "manifest 配置文件变更；实际编辑者需由配置管理/版本库追溯",
            },
        )
        _AUDITED_HASH = target_hash
        return event


async def audit_snapshot(client, request, snapshot_data: Dict[str, Any], *, client_version: Any, cache_hit: bool) -> HarnessAuditEvent:
    """快照下发留痕（200 与 304 都记）。"""
    return await HarnessAuditService.record(
        "egress.policy.snapshot",
        client_id=client.client_id,
        actor_type="client",
        actor_id=client.client_id,
        target_type="policy",
        target_id=str(snapshot_data["policy_version"]),
        risk_level="low",
        decision="allow",
        event_source="policy",
        raw_type="egress_snapshot",
        detail={
            "policy_version": snapshot_data["policy_version"],
            "min_supported_version": snapshot_data["min_supported_version"],
            "content_hash": snapshot_data["content_hash"],
            "client_version": client_version,
            "cache_ttl_seconds": snapshot_data["cache_ttl_seconds"],
            "cache_hit": cache_hit,
        },
        request=request,
    )


async def audit_incompatible(client, request, exc: EgressPolicyIncompatible, *, client_version: Any) -> HarnessAuditEvent:
    """版本不兼容拒绝留痕（decision=deny）。"""
    return await HarnessAuditService.record(
        "egress.policy.incompatible",
        client_id=client.client_id,
        actor_type="client",
        actor_id=client.client_id,
        target_type="policy",
        target_id=str(exc.policy_version),
        risk_level="high",
        decision="deny",
        policy_code="egress.policy.version_incompatible",
        event_source="policy",
        raw_type="egress_incompatible",
        detail={**exc.to_dict(), "client_version": client_version},
        request=request,
    )
