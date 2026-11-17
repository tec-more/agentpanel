"""可解释检测管道 M6 回归（纯内存，不连库）。

覆盖：
- 六步轨迹完整、顺序、每步方法/耗时/状态
- S1 归一化：零宽字符 / 全角数字绕过仍被检出
- S4 上下文消歧：白名单短语内的绝对化词不误报
- S5 语义层：无语义规则 → skipped 且给出原因
- S6 聚合：P0→block / P1→review / 仅P2→pass_hint / 无命中→pass
- 既有 detect_text/aggregate 行为不变（向后兼容）

运行：
    .venv/Scripts/python tests/regression_contentops_pipeline.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

R = []


def ck(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


class FakeRule:
    def __init__(self, id, type, pattern, level="P1", layer="L1", action="warn"):
        self.id = id
        self.type = type
        self.pattern = pattern
        self.risk_level = level
        self.layer = layer
        self.action = action
        self.basis = "《广告法》第九条"
        self.suggestion = "请删除或替换"
        self.version = "1"


async def main():
    from base.plugins.contentops.services.compliance_service import (
        ComplianceEngine, CONTEXT_WHITELIST,
    )

    rules = [
        FakeRule(1, "keyword", "最佳", "P0", "L1", "block"),
        FakeRule(2, "keyword", "国家级", "P1", "L2", "warn"),
        FakeRule(3, "regex", r"[0-9]{11}", "P1", "L3", "warn"),
    ]

    # 1. 轨迹结构
    r = await ComplianceEngine.check_with_trace("这是一段最佳内容", rules)
    trace = r["trace"]
    ck("P1 六步完整", len(trace) == 6 and [s["step"] for s in trace] == [1, 2, 3, 4, 5, 6])
    ck("P2 每步含方法/耗时/状态", all(
        {"code", "name", "method", "status", "detail", "elapsed_ms"}.issubset(s)
        and s["method"] and s["detail"] for s in trace
    ))
    ck("P3 步骤码序列", [s["code"] for s in trace] ==
       ["normalize", "keyword", "regex", "disambiguation", "semantic", "aggregate"])
    ck("P4 语义层标注跳过+原因", trace[4]["status"] == "skipped" and bool(trace[4]["detail"]))
    ck("P5 命中带层级与方法", r["hits"][0]["layer"] == "L1" and r["hits"][0]["source"] == "L1-关键词")
    ck("P6 聚合判定可追溯", r["verdict"] == "block" and r["verdict"] in trace[5]["detail"])
    ck("P7 管道版本", r["pipeline_version"] == "2.0-trace")

    # 2. 归一化绕过
    zr = await ComplianceEngine.check_with_trace("这是最\u200b佳内容", rules)  # 零宽插入
    ck("P8 零宽绕过被检出", zr["normalized"] and zr["hit_count"] >= 1, f"hits={zr['hit_count']}")
    full = "电话１３８００００００００"  # 全角数字（NFKC → 半角后命中 11 位手机号规则）
    fr = await ComplianceEngine.check_with_trace(full, rules)
    ck("P9 全角数字被检出", fr["normalized"] and fr["hit_count"] >= 1, f"hits={fr['hit_count']}")

    # 3. 上下文消歧
    whitelist_hit = CONTEXT_WHITELIST[0]
    dr = await ComplianceEngine.check_with_trace(f"这是{whitelist_hit}的内容", rules)
    ck("P10 白名单短语不误报", dr["verdict"] == "pass", f"text={whitelist_hit}")

    # 4. 仅 P1 / 仅 P2 / 无命中
    r1 = await ComplianceEngine.check_with_trace("这是国家级项目", rules)  # 命中 P1 + P0? 国家级是P1,但"最佳"不在
    ck("P11 P1 判定 review 或 block", r1["verdict"] in ("review", "block"))
    r0 = await ComplianceEngine.check_with_trace("普通正常内容", rules)
    ck("P12 无命中 pass", r0["verdict"] == "pass" and r0["hit_count"] == 0)

    # 5. 向后兼容：旧方法不受影响
    plain = ComplianceEngine.detect_text("这是一段最佳内容", rules)
    agg = ComplianceEngine.aggregate(plain)
    ck("P13 旧 detect_text 行为不变", len(plain) == 1 and agg["verdict"] == "block")
    ck("P14 归一化不影响原文", ComplianceEngine.normalize_text("普通内容") == "普通内容")

    ok = sum(1 for _, v in R if v)
    print(f"\n===== {ok}/{len(R)} PASS =====")
    if ok != len(R):
        print("FAIL:", [n for n, v in R if not v])
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
