"""
M8 权限与归属常量定义

溯源：
- docs/用户侧智能体设计流PRD.md §7.1（归属与隔离、usr 四档 data_scope）
- docs/arch/02-系统上下文与领域模型.md §4.2（resource_grant 资源类型）
"""
from enum import Enum


class OwnerType(str, Enum):
    """归属主体类型（PRD §7.1 双主体 + 资源授权管理 PRD §6.1 组织维度）"""
    CUS = "cus"  # 客户用户（customer 插件主体）
    USR = "usr"  # 后台普通用户（core users 主体，叠加 RBAC data_scope）
    ORG = "org"  # 客户组织（customer 域组织，成员自动继承组织授权）


class DataScope(str, Enum):
    """
    usr 数据权限范围（对齐 base/core/users/models/rbac.py DataScopeEnum 语义）

    PRD §7.1 强制规则 4 约定四档：全部/本部门及以下/本部门/仅本人；
    现有 RBAC 另有 custom（自定义部门），按部门集合档处理，语义保持一致。
    """
    ALL = "all"              # 全部数据
    DEPT_TREE = "dept_tree"  # 本部门及下级部门
    DEPT = "dept"            # 本部门
    CUSTOM = "custom"        # 自定义部门集合（RBAC 既有档，按部门集合处理）
    SELF = "self"            # 仅本人


class ResourceType(str, Enum):
    """资源授权类型（PRD §7.2 授权粒度）"""
    MODEL = "model"        # 模型
    KB = "kb"              # 知识库
    TOOL = "tool"          # 工具
    AGENT = "agent"        # 子 Agent
    NODE_TYPE = "node_type"  # 节点类型


# node_type 受限类型的中文名（与 schema-validator nodeRegistry 对齐；
# 供 agent 插件 u_resource_router / admin_grant_router 两侧复用）
NODE_TYPE_LABELS = {
    "hitl": "人工节点",
    "sub_agent": "子Agent",
    "tool": "工具",
}


# ===== F8 越权限流配置（docs/arch/04 §F8 / 05 §2.1）=====
# 同主体 1 分钟内 404 越权 >10 次 → 限流 + 审计 alert
RL_SCENE_AUTHZ_404 = "authz404"
RL_WINDOW_SECONDS = 60
RL_THRESHOLD = 10
# 触发限流后的封禁时长（秒），封禁期间该主体请求直接 429
RL_BLOCK_SECONDS = 60

# Redis 计数 key 规范：rl:{scene}:{identity}
def rl_key(scene: str, identity: str) -> str:
    """越权限流计数键（identity = "{owner_type}:{owner_id}" 或 "anon:{ip}"）"""
    return f"rl:{scene}:{identity}"


def rl_block_key(scene: str, identity: str) -> str:
    """限流封禁标记键"""
    return f"rl:{scene}:block:{identity}"
