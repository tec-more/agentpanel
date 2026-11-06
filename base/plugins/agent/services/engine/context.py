"""
M2 执行域上下文（ExecutionContext）

溯源：
- docs/arch/02 §5 依赖红线 / docs/arch/06 R-02：引擎内不做 JWT/归属判断，只消费接入层注入的上下文
- docs/arch/04 §4.2 节点信封：context: {owner, quota, trace_id, session}
- docs/arch/04 F2/F3：执行绑定发布版本快照（kind=run）或草稿（kind=dry_run）

引擎与节点处理器仅读取本对象；任何归属/授权判定经由 ctx 注入的 check_resource 回调
（M8 消费口，引擎不直接做归属判断）。
"""
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

# 资源复核回调：由服务层以 M8 ResourceGrantService 实现注入
# 签名：check_resource(resource_type, resource_id) -> bool
ResourceChecker = Callable[[str, Any], Awaitable[bool]]

# 执行类别
KIND_RUN = "run"
KIND_DRY_RUN = "dry_run"

# 域（与 JWT typ 同源）
DOMAIN_CUS = "cus"
DOMAIN_USR = "usr"


@dataclass
class ExecutionContext:
    """
    执行域上下文（贯穿引擎与节点处理器）

    - owner_type/owner_id: 归属主体（接入层 JWT 注入，引擎不判定）
    - domain: 执行域（cus/usr），用户域节点能力开关依据（R-10）
    - trace_id: 链路 ID（= execution_id，04-§5.2）
    - quota_hold_id: M9 预占句柄（空串表示该主体不计量）
    - kind: run/dry_run（F2：dry_run 不写长期记忆）
    - version_id: 绑定发布版本快照（C-08，运行中禁止切换）
    - session_id: 会话 ID（对话执行时注入）
    - settings: 图 settings（timeout_s/retry/trace_level/memory_mode）
    - check_resource: M8 资源复核回调（注入式，保持 R-02 解耦）
    """

    owner_type: str
    owner_id: int
    execution_id: int
    domain: str = DOMAIN_CUS
    trace_id: int = 0
    quota_hold_id: str = ""
    kind: str = KIND_RUN
    workflow_id: Optional[int] = None
    version_id: Optional[int] = None
    session_id: Optional[str] = None
    settings: Dict[str, Any] = field(default_factory=dict)
    check_resource: Optional[ResourceChecker] = None

    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = self.execution_id

    @property
    def owner(self) -> tuple:
        """M9/M5 消费的主体二元组"""
        return (self.owner_type, self.owner_id)

    @property
    def is_dry_run(self) -> bool:
        return self.kind == KIND_DRY_RUN

    async def require_resource(self, resource_type: str, resource_id: Any) -> bool:
        """资源复核（无注入回调时按未授权处理，安全侧）"""
        if self.check_resource is None:
            return False
        try:
            return bool(await self.check_resource(resource_type, resource_id))
        except Exception:
            return False

    # 节点信封 context 段（04-§4.2）
    def envelope(self) -> Dict[str, Any]:
        return {
            "owner": {"owner_type": self.owner_type, "owner_id": self.owner_id},
            "quota": {"hold_id": self.quota_hold_id},
            "trace_id": self.trace_id,
            "session": {"session_id": self.session_id},
            "domain": self.domain,
            "kind": self.kind,
        }
