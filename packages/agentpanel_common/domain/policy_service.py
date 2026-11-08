"""
三档审批策略评估（fail-closed）

默认行为：
1. 一档（tier=1）：沙箱内 / workspace 内的普通只读操作直接放行，只留审计；
2. 二档（tier=2）：规则表自动判定——黑名单直接 deny、白名单自动 allow、其余转人工；
3. 三档（tier=3）：风险升级、跨 workspace 写、出网、提权进入人工审批。

判定顺序（固定，绝不 default allow）：
黑名单 deny → 旧策略显式覆盖 → 三档风险信号 ask → 显式 ask 规则
→ 白名单/一档 allow → 未命中默认 ask。

规则可配置、可版本化：命中规则的 rule_code 即审计 policy_code，
规则单条 version 与 manifest.config.approval.ruleset_version 一并落审计。
"""
import fnmatch
from typing import Any, Callable, Dict, List, Optional

from packages.agentpanel_common.models.harness import HarnessActionPolicy
from packages.agentpanel_common.domain.policy_rule_service import (
    DEFAULT_RULESET_VERSION,
    HarnessPolicyRuleService,
    classify_signals,
    extract_command,
)

PLUGIN_NAME = "harness"

# 审批配置/通道由入口在启动时显式注入（C4）：L2 注入 manifest 读取器，L3 用同值默认。
_approval_config_provider: Optional[Callable[[], Optional[Dict[str, Any]]]] = None
_approval_channel_provider: Optional[Callable[[], bool]] = None


def configure_approval(
    config_provider: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
    channel_provider: Optional[Callable[[], bool]] = None,
) -> None:
    """显式注入审批配置来源；不注入时使用下方默认值。"""
    global _approval_config_provider, _approval_channel_provider
    _approval_config_provider = config_provider
    _approval_channel_provider = channel_provider


# 三档风险信号 → 审计 policy_code（无对应规则时使用）
SIGNAL_POLICY_CODES = (
    ("escalation", "signal_risk_escalation"),
    ("outside_workspace", "signal_outside_workspace"),
    ("network", "signal_network"),
    ("privilege", "signal_privilege"),
    ("system_path", "signal_system_path"),
)


def approval_config() -> Dict[str, Any]:
    """审批默认配置（L2 来自 manifest.config.approval；L3 为同值默认）。"""
    raw = _approval_config_provider() if _approval_config_provider else {}
    raw = raw or {}
    return {
        "timeout_seconds": int(raw.get("timeout_seconds") or 300),
        "default_scope": raw.get("default_scope") or "once",
        "allowed_scopes": raw.get("allowed_scopes") or ["once", "session_pattern"],
        "admin_fallback_risk": raw.get("admin_fallback_risk") or ["high", "critical"],
        "ruleset_version": int(raw.get("ruleset_version") or DEFAULT_RULESET_VERSION),
        "interception": raw.get("interception") or "backend_api",
        "fail_closed": bool(raw.get("fail_closed", True)),
    }


def _approval_available() -> bool:
    """审批通道是否可用：默认后端侧挡（backend_api）视为可用。

    若入口显式注入通道探测（L2 检查 approval 插件安装/启用状态），以注入结果为准；
    未注入视为可用（L3 独立进程固定 backend_api 后端侧挡）。
    """
    cfg = approval_config()
    channel = (cfg.get("interception") or "backend_api").lower()
    if channel == "backend_api":
        return True
    if _approval_channel_provider is None:
        return True
    return bool(_approval_channel_provider())


def _conditions_match(conditions: Optional[Dict[str, Any]], context: Optional[Dict[str, Any]]) -> bool:
    if not conditions:
        return True
    ctx = context or {}
    for key, expected in conditions.items():
        actual = ctx.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _result(
    decision: str,
    reason: str,
    action: str,
    *,
    policy_code: Optional[str] = None,
    risk_level: str = "medium",
    tier: int = 2,
    category: str = "general",
    command: Optional[str] = None,
    command_pattern: Optional[str] = None,
    rule_version: Optional[int] = None,
    ruleset_version: Optional[int] = None,
    signals: Optional[Dict[str, Any]] = None,
    rule: Any = None,
) -> Dict[str, Any]:
    cfg = approval_config()
    return {
        "decision": decision,
        "reason": reason,
        "action": action,
        "policy_code": policy_code,
        "risk_level": risk_level,
        "tier": tier,
        "category": category,
        "command": command,
        "command_pattern": command_pattern,
        "rule_version": rule_version,
        "ruleset_version": ruleset_version if ruleset_version is not None else cfg["ruleset_version"],
        "signals": signals or {},
        "approval_required": decision == "ask",
        "interception": cfg["interception"],
    }


class HarnessPolicyService:
    @classmethod
    async def evaluate(
        cls,
        action: str,
        context: Optional[Dict[str, Any]] = None,
        arguments: Any = None,
    ) -> Dict[str, Any]:
        ctx = dict(context or {})
        command = extract_command(arguments)
        signals = classify_signals(action, command, ctx, arguments)

        try:
            rules = await HarnessPolicyRuleService.active_rules()
        except Exception:
            return _result(
                "deny", "policy_backend_unavailable", action,
                risk_level="high", tier=3, command=command,
                command_pattern=signals.get("command_pattern"), signals=signals,
            )

        # 1) 黑名单：直接 deny（优先级最高，白名单/一档不可覆盖）
        deny_rule = cls._match_rule(rules, action, command, "deny")
        if deny_rule is not None:
            return _result(
                "deny", "policy_deny_blocklist", action,
                policy_code=deny_rule.rule_code, risk_level=deny_rule.risk_level or "critical",
                tier=deny_rule.tier or 2, category=deny_rule.category,
                command=command, command_pattern=signals.get("command_pattern"),
                rule_version=deny_rule.version, signals=signals, rule=deny_rule,
            )

        # 2) 旧策略表显式覆盖（deny/approve/allow），兼容既有管理数据
        legacy = await cls._match_legacy(action, ctx)
        if legacy is not None:
            effect = (legacy.effect or "deny").lower()
            if effect == "deny":
                return _result(
                    "deny", "policy_deny_legacy", action,
                    policy_code=legacy.code, risk_level=legacy.risk_level or "high",
                    tier=2, command=command, command_pattern=signals.get("command_pattern"),
                    signals=signals,
                )
            if effect == "approve":
                if not _approval_available():
                    return _result(
                        "deny", "approval_unavailable", action,
                        policy_code=legacy.code, risk_level=legacy.risk_level or "high",
                        tier=3, command=command, command_pattern=signals.get("command_pattern"),
                        signals=signals,
                    )
                return _result(
                    "ask", "policy_ask_legacy", action,
                    policy_code=legacy.code, risk_level=legacy.risk_level or "high",
                    tier=3, command=command, command_pattern=signals.get("command_pattern"),
                    signals=signals,
                )
            return _result(
                "allow", "policy_allow_legacy", action,
                policy_code=legacy.code, risk_level=legacy.risk_level or "low",
                tier=1, command=command, command_pattern=signals.get("command_pattern"),
                signals=signals,
            )

        # 3) 三档风险信号：风险升级 / 跨 workspace 写 / 出网 / 提权 → 人工审批
        if signals.get("tier3"):
            signal_code = next(
                (code for key, code in SIGNAL_POLICY_CODES if signals.get(key)),
                "signal_risk_escalation",
            )
            if not _approval_available():
                return _result(
                    "deny", "approval_unavailable", action,
                    policy_code=signal_code, risk_level=signals.get("risk_level") or "high",
                    tier=3, category="risk_signal", command=command,
                    command_pattern=signals.get("command_pattern"), signals=signals,
                )
            return _result(
                "ask", "policy_ask_signal", action,
                policy_code=signal_code, risk_level=signals.get("risk_level") or "high",
                tier=3, category="risk_signal", command=command,
                command_pattern=signals.get("command_pattern"), signals=signals,
            )

        # 4) 规则表显式 ask
        ask_rule = cls._match_rule(rules, action, command, "ask")
        if ask_rule is not None:
            if not _approval_available():
                return _result(
                    "deny", "approval_unavailable", action,
                    policy_code=ask_rule.rule_code, risk_level=ask_rule.risk_level or "high",
                    tier=3, category=ask_rule.category, command=command,
                    command_pattern=signals.get("command_pattern"),
                    rule_version=ask_rule.version, signals=signals, rule=ask_rule,
                )
            return _result(
                "ask", "policy_ask_explicit", action,
                policy_code=ask_rule.rule_code, risk_level=ask_rule.risk_level or "high",
                tier=3, category=ask_rule.category, command=command,
                command_pattern=signals.get("command_pattern"),
                rule_version=ask_rule.version, signals=signals, rule=ask_rule,
            )

        # 5) 白名单 / 一档 allow（只读、测试、构建等安全命令）
        allow_rule = cls._match_rule(rules, action, command, "allow")
        if allow_rule is not None:
            tier = allow_rule.tier or 2
            reason = "policy_allow_readonly" if tier == 1 else "policy_allow_whitelist"
            return _result(
                "allow", reason, action,
                policy_code=allow_rule.rule_code, risk_level=allow_rule.risk_level or "low",
                tier=tier, category=allow_rule.category, command=command,
                command_pattern=signals.get("command_pattern"),
                rule_version=allow_rule.version, signals=signals, rule=allow_rule,
            )

        # 6) 规则表未命中 → 转人工（二档其余转人工 / 三档兜底）
        if not _approval_available():
            return _result(
                "deny", "approval_unavailable", action,
                policy_code=None, risk_level=signals.get("risk_level") or "medium",
                tier=3, command=command, command_pattern=signals.get("command_pattern"),
                signals=signals,
            )
        return _result(
            "ask", "policy_ask_default", action,
            policy_code=None, risk_level=signals.get("risk_level") or "medium",
            tier=3, command=command, command_pattern=signals.get("command_pattern"),
            signals=signals,
        )

    @staticmethod
    def _match_rule(rules: List[Any], action: str, command: Optional[str], effect: str) -> Optional[Any]:
        for rule in rules:
            if (rule.effect or "").lower() != effect:
                continue
            if HarnessPolicyRuleService._match(rule, action, command):
                return rule
        return None

    @staticmethod
    async def _match_legacy(action: str, context: Dict[str, Any]) -> Optional[HarnessActionPolicy]:
        try:
            policies = await HarnessActionPolicy.filter(status="active").order_by("-priority", "code").all()
        except Exception:
            return None
        for policy in policies:
            if not fnmatch.fnmatchcase(action, policy.action_pattern or ""):
                continue
            if not _conditions_match(policy.conditions or {}, context):
                continue
            return policy
        return None
