"""
三档审批策略规则服务

落地口径（默认行为）：
- 一档（tier=1）：沙箱内 / workspace 内的普通只读操作，直接放行，只留审计；
- 二档（tier=2）：规则表自动判定——白名单 allow、黑名单 deny、其余转人工；
- 三档（tier=3）：风险升级、跨 workspace 写、出网、提权，进入人工审批。

规则可配置、可版本化：HarnessPolicyRule.rule_code 即审计 policy_code，
version 为单条规则版本，manifest.config.approval.ruleset_version 为规则集版本。
"""
import fnmatch
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from base.plugins.harness.models.harness import HarnessPolicyRule

# 默认规则集版本（与 manifest.config.approval.ruleset_version 对齐）
DEFAULT_RULESET_VERSION = 1


def _default_rules() -> List[Dict[str, Any]]:
    """系统默认规则（首次启动自动落库；后续可通过管理接口调整）。"""
    read_actions = [
        ("allow_tool_read", "tool.read"), ("allow_tool_glob", "tool.glob"),
        ("allow_tool_grep", "tool.grep"), ("allow_tool_ls", "tool.ls"),
        ("allow_tool_list", "tool.list"), ("allow_tool_stat", "tool.stat"),
    ]
    rules: List[Dict[str, Any]] = []
    for code, action in read_actions:
        rules.append({
            "rule_code": code, "name": f"只读工具放行 {action}", "version": 1, "tier": 1,
            "effect": "allow", "category": "safe_read", "action_pattern": action,
            "command_pattern": None, "risk_level": "low", "priority": 300,
            "status": "active", "description": "workspace 内只读操作默认放行，仅留审计",
        })

    # ---- 白名单：安全命令自动 allow ----
    allow_commands = [
        ("safe_echo", "echo/Write-Output", r"^(echo|write-output)\b", "safe_read", "low", 260),
        ("safe_list", "目录列举", r"^(ls|dir|get-childitem|pwd|get-location)\b", "safe_read", "low", 260),
        ("safe_read", "只读文本查看", r"^(cat|type|get-content|head|tail|more)\b", "safe_read", "low", 250),
        ("safe_git_read", "git 只读查询", r"^git\s+(status|diff|log|show|branch|remote\s+-v|rev-parse)\b", "safe_read", "low", 250),
        ("safe_search", "文本搜索", r"^(grep|findstr|select-string|rg)\b", "safe_read", "low", 240),
        ("safe_test", "测试命令", r"^(pytest|python\s+-m\s+pytest|npm\s+(test|run\s+test)|pnpm\s+(test|run\s+test)|yarn\s+test|go\s+test|cargo\s+test|dotnet\s+test)\b", "test_build", "medium", 220),
        ("safe_build", "构建命令", r"^(npm\s+run\s+build|pnpm\s+build|yarn\s+build|go\s+build|cargo\s+build|dotnet\s+build|mvn\b|gradle\b)", "test_build", "medium", 220),
        ("safe_lint", "静态检查", r"^(ruff|flake8|eslint|pylint|tsc\s+--noemit)\b", "test_build", "medium", 210),
    ]
    for code, name, pattern, category, risk, priority in allow_commands:
        rules.append({
            "rule_code": code, "name": f"白名单: {name}", "version": 1, "tier": 2,
            "effect": "allow", "category": category, "action_pattern": "*",
            "command_pattern": pattern, "risk_level": risk, "priority": priority,
            "status": "active", "description": "安全命令自动放行",
        })

    # ---- 黑名单：直接 deny（优先级高于白名单） ----
    block_commands = [
        ("block_rm_rf", "递归删除", r"(\brm\s+-[a-z]*[rf][a-z]*\b|\brm\s+-rf\b|\bremove-item\b.*-(recurse|force)|\brmdir\s+/s)", "fs_write", "critical", 400),
        ("block_system_path_write", "写系统路径", r"((>|>>|set-content|out-file|copy|move|del|remove-item).*(/etc/|/usr/|/bin/|/sbin/|/boot/|c:\\windows\\|c:\\program\s+files\\))", "system", "critical", 400),
        ("block_secret_read", "读取密钥/环境文件", r"(.env|\.ssh|id_rsa|id_ed25519|credentials|\.aws|\.npmrc|key\.txt|apikey|secrets?\.(json|yml|yaml|txt))", "secret", "critical", 400),
        ("block_env_dump", "环境变量导出", r"^(env|printenv|set|get-childitem\s+env:)\b", "secret", "high", 390),
        ("block_network", "外网访问", r"\b(curl|wget|invoke-webrequest|invoke-restmethod|nc|netcat|ssh|scp|sftp|ftp)\b", "network", "high", 390),
        ("block_privilege", "提权/系统账户", r"\b(sudo|runas|start-process\s+-verb\s+runas|chmod\s+777|chown|net\s+user|reg\s+add)\b", "privilege", "critical", 400),
        ("block_force_push", "强制推送", r"\bgit\s+push\b.*(--force|-f)\b", "fs_write", "high", 390),
        ("block_destructive_win", "磁盘/强制删除", r"\b(format|clear-disk|del\s+/f|del\s+/s)\b", "system", "critical", 400),
        ("block_shell_injection", "动态执行/编码命令", r"\b(powershell\s+-enc|invoke-expression|iex|downloadstring)\b", "privilege", "critical", 400),
    ]
    for code, name, pattern, category, risk, priority in block_commands:
        rules.append({
            "rule_code": code, "name": f"黑名单: {name}", "version": 1, "tier": 2,
            "effect": "deny", "category": category, "action_pattern": "*",
            "command_pattern": pattern, "risk_level": risk, "priority": priority,
            "status": "active", "description": "高危命令直接拒绝",
        })

    # ---- 显式人工审批动作 ----
    rules.append({
        "rule_code": "ask_git_push", "name": "显式转人工: git push", "version": 1, "tier": 3,
        "effect": "ask", "category": "fs_write", "action_pattern": "*",
        "command_pattern": r"^git\s+push\b", "risk_level": "high", "priority": 350,
        "status": "active", "description": "推送远端需人工审批",
    })
    return rules


def extract_command(arguments: Any) -> Optional[str]:
    """从 tool/call arguments 中提取命令原文（兼容 JSON 字符串）。"""
    if arguments is None:
        return None
    data = arguments
    if isinstance(data, str):
        text = data.strip()
        if text.startswith("{"):
            try:
                data = json.loads(text)
            except Exception:
                return text
        else:
            return text
    if isinstance(data, dict):
        for key in ("command", "cmd", "script", "cmdline", "shell_command", "input"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    if isinstance(data, list):
        parts = [str(item.get("text") if isinstance(item, dict) else item) for item in data]
        text = " ".join(p for p in parts if p).strip()
        return text or None
    return str(data).strip() or None


def command_pattern_of(command: Optional[str]) -> Optional[str]:
    """审批授权用的命令模式：默认取前 1~2 个 token，避免过度授权。"""
    if not command:
        return None
    tokens = [t for t in re.split(r"\s+", command.strip()) if t]
    if not tokens:
        return None
    head = tokens[0].lower()
    two_token_heads = {"npm", "pnpm", "yarn", "git", "dotnet", "go", "cargo", "python", "pip", "mvn", "gradle"}
    if head in two_token_heads and len(tokens) > 1:
        return f"{head} {tokens[1].lower()}"[:200]
    return head[:200]


def classify_signals(action: str, command: Optional[str], context: Dict[str, Any],
                     arguments: Any) -> Dict[str, Any]:
    """识别三档风险信号：扩展/越界写/出网/提权/密钥。"""
    ctx = context or {}
    arg_dict = arguments if isinstance(arguments, dict) else {}
    text = command or ""
    sandbox = str(arg_dict.get("sandbox_permissions") or ctx.get("sandbox_permissions") or "").lower()
    escalation = bool(
        ctx.get("escalation") or ctx.get("require_escalated") or arg_dict.get("require_escalated")
        or sandbox in ("danger-full-access", "danger-full_access")
    )
    outside = bool(ctx.get("outside_workspace") or arg_dict.get("outside_workspace"))
    network = bool(
        ctx.get("network") or re.search(
            r"\b(curl|wget|invoke-webrequest|invoke-restmethod|nc|netcat|ssh|scp|sftp|ftp)\b", text, re.I
        )
    )
    privilege = bool(
        ctx.get("privilege") or re.search(r"\b(sudo|runas|chmod\s+777|chown|net\s+user)\b", text, re.I)
    )
    secret = bool(
        ctx.get("secret_access") or re.search(
            r"(.env|\.ssh|id_rsa|id_ed25519|credentials|\.aws|\.npmrc|key\.txt|apikey)", text, re.I
        )
    )
    system_path = bool(
        ctx.get("system_path") or re.search(
            r"(/etc/|/usr/|/bin/|/sbin/|/boot/|c:\\windows\\|c:\\program\s+files\\)", text, re.I
        )
    )
    tier3 = escalation or outside or network or privilege or system_path
    if escalation:
        risk = "critical"
    elif privilege or secret:
        risk = "critical"
    elif outside or network or system_path:
        risk = "high"
    else:
        risk = "medium"
    return {
        "command": command,
        "command_pattern": command_pattern_of(command),
        "escalation": escalation,
        "outside_workspace": outside,
        "network": network,
        "privilege": privilege,
        "secret_access": secret,
        "system_path": system_path,
        "tier3": tier3,
        "risk_level": risk,
        "sandbox_permissions": sandbox or None,
    }


class HarnessPolicyRuleService:
    _seeded = False

    @classmethod
    async def ensure_defaults(cls) -> None:
        if cls._seeded:
            return
        try:
            count = await HarnessPolicyRule.all().count()
            if count == 0:
                await HarnessPolicyRule.bulk_create(
                    [HarnessPolicyRule(**rule) for rule in _default_rules()]
                )
        except Exception:
            # 表不存在/并发初始化时由上层按规则为空处理，不阻塞主链路
            pass
        cls._seeded = True

    @classmethod
    async def active_rules(cls) -> List[HarnessPolicyRule]:
        await cls.ensure_defaults()
        try:
            return await HarnessPolicyRule.filter(status="active").order_by("-priority", "rule_code").all()
        except Exception:
            return []

    @staticmethod
    def _match(rule: HarnessPolicyRule, action: str, command: Optional[str]) -> bool:
        if not fnmatch.fnmatchcase(action or "", rule.action_pattern or "*"):
            return False
        pattern = rule.command_pattern
        if pattern:
            if not command:
                return False
            try:
                return re.search(pattern, command, re.I) is not None
            except re.error:
                return False
        # 无命令正则的规则必须有动作模式约束，避免误放行所有动作
        return bool(rule.action_pattern and rule.action_pattern != "*")

    @classmethod
    async def match_rule(
        cls, action: str, command: Optional[str], effect: str,
    ) -> Optional[HarnessPolicyRule]:
        for rule in await cls.active_rules():
            if (rule.effect or "").lower() != effect:
                continue
            if cls._match(rule, action, command):
                return rule
        return None

    @classmethod
    async def find_rule(cls, rule_code: str) -> Optional[HarnessPolicyRule]:
        return await HarnessPolicyRule.get_or_none(rule_code=rule_code)

    @classmethod
    async def list_rules(cls, tier: Optional[int] = None, effect: Optional[str] = None) -> List[Dict[str, Any]]:
        await cls.ensure_defaults()
        query = HarnessPolicyRule.all()
        if tier is not None:
            query = query.filter(tier=tier)
        if effect:
            query = query.filter(effect=effect)
        rows = await query.order_by("-priority", "rule_code")
        return [cls.to_dict(row) for row in rows]

    @staticmethod
    def to_dict(rule: HarnessPolicyRule) -> Dict[str, Any]:
        return {
            "rule_code": rule.rule_code, "name": rule.name, "version": rule.version,
            "tier": rule.tier, "effect": rule.effect, "category": rule.category,
            "action_pattern": rule.action_pattern, "command_pattern": rule.command_pattern,
            "risk_level": rule.risk_level, "priority": rule.priority, "status": rule.status,
            "description": rule.description,
        }

    @classmethod
    async def upsert_rule(cls, payload: Any) -> Dict[str, Any]:
        """新增或更新规则；更新时 version 自增，实现规则版本化。"""
        data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else dict(payload)
        code = data.get("rule_code")
        existing = await HarnessPolicyRule.get_or_none(rule_code=code)
        if existing is None:
            rule = await HarnessPolicyRule.create(**data)
            return cls.to_dict(rule)
        for key, value in data.items():
            if key in ("rule_code", "version"):
                continue
            setattr(existing, key, value)
        existing.version = (existing.version or 1) + 1
        await existing.save()
        return cls.to_dict(existing)
