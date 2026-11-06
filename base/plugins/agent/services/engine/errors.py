"""
M2 引擎错误类型（分类驱动重试与失败策略，04-F4）

- retryable=True（timeout/限流/5xx）→ 指数退避 1s/2s/4s，上限 3 次（不可上调，N4-4）
- retryable=False（校验/授权/4xx/能力禁用）→ 直接失败
"""
from typing import Optional


class NodeExecutionError(Exception):
    """节点执行失败（携带错误码与可重试标记）"""

    def __init__(self, code: str, message: str = "", *, retryable: bool = False,
                 retry_after: Optional[float] = None):
        self.code = code
        self.retryable = retryable
        # 429 场景服务端建议等待秒数（尊重 Retry-After，05-§1.1）
        self.retry_after = retry_after
        super().__init__(message or code)
        self.message = message or code


class ExecutionCancelled(Exception):
    """协作式取消：当前节点完成或下一个调度点终止（04-F5）"""


class NodeCapabilityDenied(NodeExecutionError):
    """节点能力运行时开关拦截（R-10：用户域 code 拒绝 / http 未过白名单）"""

    def __init__(self, message: str):
        super().__init__("NODE_CAPABILITY_DENIED", message, retryable=False)


class KBAccessDenied(NodeExecutionError):
    """知识库白名单求交为空（05-§2.2：空交集 → 拒绝）"""

    def __init__(self, message: str = "知识库不可访问或未授权"):
        super().__init__("KB_ACCESS_DENIED", message, retryable=False)


class HitlTimeout(NodeExecutionError):
    """HITL 审批超时（F6：按节点配置 timeout_action 处理）"""

    def __init__(self, node_id: str):
        super().__init__("HITL_TIMEOUT", f"HITL 节点 {node_id} 审批超时", retryable=False)
