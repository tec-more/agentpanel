"""
M9 配额域 Prometheus 指标（复用 base.common.prometheus 现有通道）

溯源：docs/arch/05 §3.1 指标清单
- quota_reject_total  Counter(item)                    配额拦截量
- llm_tokens_total    Counter(owner_type,model,direction) Token 消耗
- concurrent_runs     Gauge                            当前并发

重复注册保护：测试进程/多入口导入时静默复用已注册指标。
"""
from base.common.prometheus import registry
from prometheus_client import Counter, Gauge


def _get_or_create(factory, name, documentation, labelnames=()):
    try:
        return factory(name, documentation, labelnames, registry=registry)
    except ValueError:
        # 已注册：从注册表取回
        for collector in list(registry._names_to_collectors.values()):  # noqa: SLF001
            if getattr(collector, "_name", None) == name:
                return collector
        raise


quota_reject_total = _get_or_create(
    Counter, "quota_reject_total", "Quota rejections", ["item"]
)

llm_tokens_total = _get_or_create(
    Counter,
    "llm_tokens_total",
    "LLM token consumption",
    ["owner_type", "model", "direction"],
)

concurrent_runs = _get_or_create(
    Gauge, "concurrent_runs", "Current concurrent runs", []
)

# 灰度监控（docs/ops/grayscale-monitoring-checklist.md）：
# M-4 保底强制收尾触发（协作路径失效信号，出现即 P1 告警）
force_finalize_total = _get_or_create(
    Counter, "force_finalize_total", "Force finalize (self-rescue fallback) triggers", ["status"]
)
# M-7 节点结算超时/失败（DB 间歇性挂起信号，出现即 P2 告警）
node_settle_failure_total = _get_or_create(
    Counter, "node_settle_failure_total", "Node usage settle timeout/failure", []
)


def inc_force_finalize(status: str) -> None:
    try:
        force_finalize_total.labels(status=status).inc()
    except Exception:
        pass


def inc_settle_failure() -> None:
    try:
        node_settle_failure_total.inc()
    except Exception:
        pass


def inc_quota_reject(item: str) -> None:
    try:
        quota_reject_total.labels(item=item).inc()
    except Exception:
        pass


def inc_llm_tokens(owner_type: str, model: str, tokens_in: int = 0, tokens_out: int = 0) -> None:
    try:
        if tokens_in:
            llm_tokens_total.labels(owner_type=owner_type, model=model, direction="in").inc(tokens_in)
        if tokens_out:
            llm_tokens_total.labels(owner_type=owner_type, model=model, direction="out").inc(tokens_out)
    except Exception:
        pass
