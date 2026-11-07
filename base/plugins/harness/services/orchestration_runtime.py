"""编排运行时角色标记。

- L2 业务进程（run.py）默认 l2：额度预占/结算/释放直接调用 L2 的 QuotaService；
- L3 编排进程（base/plugins/harness/server.py）导入时置 l3：额度写操作必须经
  L2 内部额度 API，禁止在 L3 本地直调 QuotaService 或直接写额度表。
"""
RUNTIME_ROLE = "l2"


def set_runtime_role(role: str) -> None:
    global RUNTIME_ROLE
    role = str(role or "").strip().lower()
    if role not in ("l2", "l3"):
        raise ValueError(f"未知编排运行时角色: {role}")
    RUNTIME_ROLE = role


def runtime_role() -> str:
    return RUNTIME_ROLE


def is_l3() -> bool:
    return RUNTIME_ROLE == "l3"
