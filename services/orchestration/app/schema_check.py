"""启动时 DB schema 断言（fail-closed）。

P2 只做“表/关键列存在 + 最低版本”两类校验；列级类型契约（T0.3）在 P3 接入。
版本号由工程内置常量维护，`ORCH_SCHEMA_MIN_VERSION` 高于内置版本即拒绝启动，
用于阻止“代码比库旧”的部署。
"""
from typing import Any, Dict, Iterable

SUPPORTED_SCHEMA_VERSION = 1

REQUIRED_TABLES: Dict[str, tuple] = {
    "harness_session": ("session_no", "client_id", "status", "owner_type", "owner_id"),
    "harness_run": ("run_no", "session_no", "client_id", "status", "hold_id", "reserved_tokens"),
    "harness_step": ("run_id", "run_no", "node_id", "seq"),
    "harness_audit_event": ("event_no", "action", "event_source"),
    "harness_approval_request": ("approval_no", "client_id", "action"),
    "harness_approval_grant": ("approval_no", "status", "scope"),
    "harness_action_policy": ("code", "effect", "status"),
    "harness_policy_rule": ("rule_code", "effect", "version", "tier"),
    "harness_client": ("client_id", "secret_hash", "status"),
    "harness_identity": ("external_id", "status"),
    "model_price": ("provider", "model", "status"),
    "service_credential": ("service_id", "secret_hash", "status"),
    # Spec §4.2：审批人解析（只读四列）与组织配额成员校验（只读）
    "user": ("id", "username", "is_superuser", "is_active"),
    "customer_organization": ("id", "status"),
    "customer_organization_member": ("org_id", "customer_id", "status"),
}


class SchemaCheckError(RuntimeError):
    """schema 不满足编排服务的最低要求。"""


def _parse_version(raw: Any) -> int:
    text = str(raw or "").strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        raise SchemaCheckError(f"ORCH_SCHEMA_MIN_VERSION 必须为整数，当前值: {text!r}")


def _diff_tables(rows: Iterable[Any]) -> Dict[str, list]:
    present: Dict[str, set] = {}
    for row in rows:
        table = row["table_name"]
        present.setdefault(table, set()).add(row["column_name"])

    problems: Dict[str, list] = {}
    for table, columns in REQUIRED_TABLES.items():
        if table not in present:
            problems[table] = list(columns)
            continue
        missing = [col for col in columns if col not in present[table]]
        if missing:
            problems[table] = missing
    return problems


async def check_schema(readonly_db: Any, min_version: Any = "") -> Dict[str, Any]:
    required_min = _parse_version(min_version)
    if required_min > SUPPORTED_SCHEMA_VERSION:
        raise SchemaCheckError(
            f"数据库要求 schema 版本 {required_min}，当前代码仅支持 {SUPPORTED_SCHEMA_VERSION}"
        )

    rows = await readonly_db.fetch(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ANY($1::text[])",
        list(REQUIRED_TABLES.keys()),
    )
    problems = _diff_tables(rows)
    if problems:
        detail = "; ".join(f"{table} 缺列 {cols}" for table, cols in problems.items())
        raise SchemaCheckError(f"编排服务所需表/列缺失: {detail}")

    return {
        "status": "healthy",
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "tables": len(REQUIRED_TABLES),
    }
