"""
Quota 模型组 - M9 配额计量（Q-D 统一套餐）

溯源：docs/arch/02-系统上下文与领域模型.md §4.2；01-需求与约束.md C-17
- QuotaPlan：统一配额套餐定义；客户会员等级(MembershipLevel.level_type)与后台角色(Role)
  双向映射到同一配额项集合（Q-D / C-17），映射关系由服务层维护，不在本表建 FK
- QuotaAccount：每主体每周期一行；Redis 计数为实时事实源，DB used 持久化对账（§03-3.6）
- UsageRecord：计量流水，精确到"用户 + 工作流 + 节点"（PRD §7.3），保留 13 个月对账
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class QuotaPlan(BaseModel, TimestampMixin):
    verbose_name = "配额套餐"
    """Quota plan definition (unified for cus/usr, Q-D)"""

    code = fields.CharField(max_length=50, unique=True, description="套餐编码（唯一）")
    name = fields.CharField(max_length=100, description="套餐名称")
    # 适用主体范围：cus=客户 / usr=后台用户 / both=通用
    scope = fields.CharField(max_length=10, default="both", description="适用范围: cus/usr/both")
    # 配额项集合：{"token": <周期额度>, "concurrency": <同时运行数>, "daily_runs": <每日运行数>,
    #             "kb_search": <检索次数>, "vector_write": <向量写入条数>, "run_budget": {...}}
    quota_items = fields.JSONField(description="配额项定义（JSON）")
    status = fields.CharField(max_length=20, default="active", description="状态: active/disabled")

    class Meta:
        table = "quota_plan"

    def __str__(self):
        return f"QuotaPlan({self.code})"


class QuotaAccount(BaseModel, TimestampMixin):
    verbose_name = "配额账户"
    """Per-owner quota account; Redis 实时计数，DB 周期对账（§03-3.6）"""

    owner_type = fields.CharField(max_length=3, description="主体类型: cus/usr")
    owner_id = fields.BigIntField(description="主体 ID")
    plan = fields.ForeignKeyField(
        "models.QuotaPlan",
        related_name="accounts",
        on_delete=fields.SET_NULL,
        null=True,
        description="绑定套餐",
    )
    period_start = fields.DatetimeField(description="周期开始时间")
    period_end = fields.DatetimeField(description="周期结束时间")
    # 周期内已用量：{"token": n, "kb_search": n, "vector_write": n, "daily_runs": n, ...}
    used = fields.JSONField(default=dict, description="周期内已用量（JSON，对账落盘值）")
    status = fields.CharField(max_length=20, default="active", description="状态: active/frozen")

    class Meta:
        table = "quota_account"
        # 索引策略溯源 §03-4：UNIQUE(owner_type, owner_id) 账户定位
        unique_together = (("owner_type", "owner_id"),)

    def __str__(self):
        return f"QuotaAccount({self.owner_type}:{self.owner_id})"


class UsageRecord(BaseModel, TimestampMixin):
    verbose_name = "用量流水"
    """Usage record; M6/M2 结算时写入，保留 13 个月对账（§03-3.6）"""

    owner_type = fields.CharField(max_length=3, description="主体类型: cus/usr")
    owner_id = fields.BigIntField(description="主体 ID")
    # 追溯维度：执行实例 + 节点（PRD §7.3 计量精确到 用户+工作流+节点）
    execution_id = fields.BigIntField(null=True, index=True, description="关联执行实例 ID")
    node_id = fields.CharField(max_length=100, null=True, description="节点 ID")
    # D1（R-09）：节点内事件序号，结算幂等键 (execution_id,node_id,seq) 组成部分
    seq = fields.BigIntField(default=0, description="节点内事件序号（幂等键组成）")
    # 资源口径：llm_token/tool_call/kb_search/vector_write/workflow_run
    resource_type = fields.CharField(max_length=50, description="计量资源类型")
    amount = fields.FloatField(default=0, description="用量数值（次数/条数等）")
    tokens_in = fields.BigIntField(default=0, description="输入 token 数")
    tokens_out = fields.BigIntField(default=0, description="输出 token 数")
    cost = fields.DecimalField(max_digits=12, decimal_places=6, default=0, description="折算成本")

    class Meta:
        table = "usage_record"
        # 索引策略溯源 §03-4：(owner_type, owner_id, created_at) 账单 / (execution_id) 单次追溯
        indexes = [
            ("owner_type", "owner_id", "created_at"),
            ("execution_id",),
        ]
        # D1（R-09）：结算幂等键硬约束 UNIQUE(execution_id,node_id,seq)
        unique_together = (("execution_id", "node_id", "seq"),)

    def __str__(self):
        return f"UsageRecord({self.owner_type}:{self.owner_id}, {self.resource_type})"
