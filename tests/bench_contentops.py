"""ContentOps M4 压测脚本：文本合规检测性能指标。

运行（项目根目录，激活 venv）：
    # 离线 dry-run（纯规则引擎，不需要 DB/MQ；默认 1000 条 × 规则集）
    .venv/Scripts/python tests/bench_contentops.py
    .venv/Scripts/python tests/bench_contentops.py --n 2000 --rules 50

指标口径（对齐开发 PRD §12 非功能需求）：
    - 单条文本合规 P95 < 500ms
    - 批量 1000 条 < 2min
    - 单次自适应生成 P95 < 5s（LLM 分支需真实供应商，本脚本只测确定性规则引擎）

说明：
- dry-run 用内存合成规则跑 ComplianceEngine.detect_text + aggregate，测引擎纯计算开销
  （不含 DB 加载规则的 I/O，属引擎性能下界）。
- 不做任何写库；规则/文本均为一次性内存对象。
"""
import argparse
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeRule:
    """内存规则对象，属性签名对齐 ComplianceRule 被 detect_text 使用的字段。"""
    def __init__(self, rid, pattern, level="P1", action="warn", rtype="keyword"):
        self.id = rid
        self.pattern = pattern
        self.risk_level = level
        self.action = action
        self.type = rtype
        self.basis = "压测合成依据"
        self.suggestion = "建议替换"
        self.version = "1"
        self.status = "active"
        self.rollout_percent = 100


BANNED = ["绝对", "最佳", "第一品牌", "国家级", "顶级", "包治百病", "100%有效", "永久"]
FILLER = ["这是一个关于产品质量的正常使用体验分享", "我们提供专业的咨询服务和解决方案",
          "欢迎关注我们的官方账号获取更多信息", "本内容仅供参考不构成任何投资建议"]


def build_rules(n: int) -> list:
    rules = []
    for i in range(n):
        if i < len(BANNED):
            rules.append(FakeRule(i + 1, BANNED[i], level="P0" if i % 3 == 0 else "P1"))
        else:
            rules.append(FakeRule(i + 1, f"合成词{i}", level="P2"))
    return rules


def build_texts(n: int) -> list[str]:
    texts = []
    for i in range(n):
        parts = [random.choice(FILLER) for _ in range(random.randint(3, 8))]
        if i % 5 == 0:
            parts.append(random.choice(BANNED))  # 20% 命中率
        texts.append("。".join(parts))
    return texts


def run(n: int, rules_n: int) -> dict:
    from base.plugins.contentops.services.compliance_service import ComplianceEngine

    rules = build_rules(rules_n)
    texts = build_texts(n)
    latencies = []
    total_hits = 0
    started = time.perf_counter()
    for text in texts:
        t0 = time.perf_counter()
        hits = ComplianceEngine.detect_text(text, rules, channel="text")
        ComplianceEngine.aggregate(hits)
        latencies.append((time.perf_counter() - t0) * 1000)
        total_hits += len(hits)
    wall = time.perf_counter() - started

    latencies.sort()

    def pct(p):
        return latencies[min(len(latencies) - 1, int(len(latencies) * p))] if latencies else 0.0

    return {
        "n": n, "rules": rules_n,
        "wall_s": round(wall, 3),
        "throughput_per_s": round(n / wall, 1) if wall else 0,
        "p50_ms": round(pct(0.50), 3),
        "p95_ms": round(pct(0.95), 3),
        "p99_ms": round(pct(0.99), 3),
        "avg_ms": round(statistics.mean(latencies), 3) if latencies else 0,
        "max_ms": round(latencies[-1], 3) if latencies else 0,
        "total_hits": total_hits,
    }


def main():
    ap = argparse.ArgumentParser(description="ContentOps 文本合规引擎压测")
    ap.add_argument("--n", type=int, default=1000, help="文本条数（默认 1000）")
    ap.add_argument("--rules", type=int, default=30, help="规则条数（默认 30）")
    args = ap.parse_args()

    random.seed(42)  # 可复现
    print(f"[bench] dry-run: n={args.n} rules={args.rules}")
    r = run(args.n, args.rules)
    print("\n===== 结果 =====")
    for k, v in r.items():
        print(f"  {k}: {v}")

    print("\n===== 指标判定（PRD §12）=====")
    ok_p95 = r["p95_ms"] < 500
    ok_batch = r["n"] <= 1000 and r["wall_s"] < 120
    print(f"  [{'PASS' if ok_p95 else 'FAIL'}] 单条 P95 < 500ms  (实测 {r['p95_ms']}ms)")
    print(f"  [{'PASS' if ok_batch else 'N/A'}] 批量 {r['n']} 条 < 120s  (实测 {r['wall_s']}s)")

    if not ok_p95:
        sys.exit(1)


if __name__ == "__main__":
    main()
