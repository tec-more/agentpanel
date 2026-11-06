"""
TraceEvent model - 执行 Trace 事件流（M10 基础）

溯源：
- docs/arch/03-技术选型与存储方案.md §3.3：execution_id, seq, event_type, node_id, payload(JSON), created_at；
  写入批量缓冲（每 20 条或 1s flush，R-11）；读取按 execution_id + seq 分页
- docs/arch/04-核心流程与接口契约.md §5：八类事件，seq 全局单调递增，断线 cursor 补齐
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class TraceEvent(BaseModel, TimestampMixin):
    verbose_name = "执行Trace事件"
    """执行 Trace 事件（单条事件流记录，30 天保留）"""

    execution_id = fields.BigIntField(description="执行实例 ID（workflow_execution.id）")
    seq = fields.IntField(description="事件序号（执行内全局单调递增）")
    event_type = fields.CharField(
        max_length=32,
        description="事件类型: run_started/node_started/token/node_completed/node_failed/run_paused/run_completed/run_failed",
    )
    node_id = fields.CharField(max_length=100, null=True, description="节点 ID（运行级事件为空）")
    payload = fields.JSONField(null=True, description="事件载荷（敏感字段已按 sensitive 标记打码）")

    class Meta:
        table = "trace_event"
        # 索引策略溯源 §03-4：(execution_id, seq) 回放 / (created_at) 清理
        indexes = [
            ("execution_id", "seq"),
            ("created_at",),
        ]

    def __str__(self):
        return f"TraceEvent(exec={self.execution_id}, seq={self.seq}, {self.event_type})"
