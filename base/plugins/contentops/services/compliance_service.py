"""合规规则引擎：DFA 关键词 + 正则 + 分级（P0/P1/P2）。

设计要点：
- 词库按归属隔离：平台级规则（owner 为 NULL）全局可见 + 租户级规则叠加。
- 每个命中带：命中词/句、位置、等级、依据条款、替换建议、置信度、规则版本。
- NLP 上下文消歧：对"最近/第一反应"等白名单短语降噪，避免误报。
- 语义/LLM 兜底由 adapt/semantic 层调用，本服务只做确定性规则检测。
"""
import re
import time
import unicodedata
from dataclasses import dataclass, asdict, field
from typing import Any, Optional

from base.common.authz import OwnerContext, owned_queryset
from base.plugins.contentops.models import ComplianceRule, ComplianceHit

# 上下文消歧白名单：这些短语里出现的绝对化词不判违规
CONTEXT_WHITELIST = [
    "第一反应", "最近", "最初", "第一步", "第一时间", "第一批", "第一时间了解",
    "顶级配置", "最后一次", "国家级新区", "第一人民医院", "天下第一关",
]

# 当前规则版本（规则库变更时可滚动）
RULE_VERSION = "1"


@dataclass
class Hit:
    matched_text: str
    position: int
    level: str
    action: str
    basis: Optional[str]
    suggestion: Optional[str]
    confidence: float
    channel: str
    rule_id: Optional[int]
    rule_version: str
    # M6 可解释性：命中所属规则层(L1-L4)与命中方法；给默认值保证既有构造点零改动
    layer: str = ""
    source: str = "keyword"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TraceStep:
    """检测管道中一个步骤的执行轨迹（过程/步骤/方法的可解释输出）。"""
    step: int
    code: str
    name: str
    method: str
    rules_scanned: int
    hits_found: int
    elapsed_ms: float
    status: str          # applied / skipped / no_match
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _in_whitelist(text: str, pos: int, matched: str) -> bool:
    """命中词是否落在消歧白名单短语内部。"""
    for phrase in CONTEXT_WHITELIST:
        start = 0
        while True:
            idx = text.find(phrase, start)
            if idx == -1:
                break
            # 命中位置落在白名单短语范围内 → 视为消歧命中
            if idx <= pos < idx + len(phrase):
                return True
            start = idx + 1
    return False


class ComplianceEngine:
    """确定性合规检测引擎。"""

    @staticmethod
    def _in_rollout(rule: ComplianceRule, owner: Optional[OwnerContext]) -> bool:
        """灰度放量判定：确定性哈希，保证同一 owner 对同一规则的命中稳定。

        - active / 旧数据（无 status 字段）→ 恒生效；
        - draft / archived → 不生效；
        - gray → 按 (owner_id, rule_id) 取模落到 rollout_percent 区间。
        """
        status = getattr(rule, "status", "active") or "active"
        if status == "active":
            return True
        if status in ("draft", "archived"):
            return False
        if status == "gray":
            pct = getattr(rule, "rollout_percent", 100)
            if pct is None:
                pct = 100
            if pct <= 0:
                return False
            if pct >= 100:
                return True
            owner_key = owner.owner_id if owner else 0
            # 确定性 bucket：同一 (owner, rule) 组合恒定，避免检测抖动
            bucket = (int(owner_key or 0) * 31 + int(rule.id or 0) * 17) % 100
            return bucket < pct
        return True

    @staticmethod
    async def load_rules(owner: Optional[OwnerContext], platform: Optional[str] = None) -> list[ComplianceRule]:
        """加载可见规则：平台级（owner NULL）+ 当前归属私有规则 + 灰度放量过滤。"""
        from tortoise.expressions import Q

        q = Q(enabled=True) & (Q(owner_type__isnull=True) | Q(owner_id__isnull=True))
        rules = list(await ComplianceRule.filter(q))
        if owner is not None:
            owned = await owned_queryset(ComplianceRule, owner).filter(enabled=True)
            seen = {r.id for r in rules}
            rules.extend(r for r in owned if r.id not in seen)
        if platform:
            rules = [r for r in rules if not r.platform or r.platform == platform]
        # M4 灰度：draft/archived 不生效，gray 按确定性 bucket 放量
        rules = [r for r in rules if ComplianceEngine._in_rollout(r, owner)]
        return rules

    @staticmethod
    def detect_text(text: str, rules: list[ComplianceRule], channel: str = "text") -> list[Hit]:
        """对纯文本跑关键词/正则检测，返回命中列表（含消歧）。"""
        hits: list[Hit] = []
        for rule in rules:
            if rule.type == "keyword":
                start = 0
                needle = rule.pattern
                while needle:
                    pos = text.find(needle, start)
                    if pos == -1:
                        break
                    if not _in_whitelist(text, pos, needle):
                        hits.append(Hit(
                            matched_text=needle, position=pos, level=rule.risk_level,
                            action=rule.action, basis=rule.basis, suggestion=rule.suggestion,
                            confidence=1.0, channel=channel, rule_id=rule.id,
                            rule_version=rule.version,
                        ))
                    start = pos + len(needle)
            elif rule.type == "regex":
                try:
                    for m in re.finditer(rule.pattern, text):
                        if m.start() == m.end():
                            continue
                        if not _in_whitelist(text, m.start(), m.group(0)):
                            hits.append(Hit(
                                matched_text=m.group(0), position=m.start(),
                                level=rule.risk_level, action=rule.action, basis=rule.basis,
                                suggestion=rule.suggestion, confidence=0.95, channel=channel,
                                rule_id=rule.id, rule_version=rule.version,
                            ))
                except re.error:
                    # 非法正则跳过，不让单条坏规则拖垮整次检测
                    continue
        return hits

    @staticmethod
    def aggregate(hits: list[Hit]) -> dict[str, Any]:
        """聚合分级：最高风险等级 + 是否硬拦截 + 是否需复核。"""
        levels = {h.level for h in hits}
        has_p0 = "P0" in levels
        has_p1 = "P1" in levels
        if has_p0:
            verdict = "block"       # 硬拦截，不可导出
        elif has_p1:
            verdict = "review"      # 需人工复核放行
        elif levels:
            verdict = "pass_hint"   # 仅提示
        else:
            verdict = "pass"        # 通过
        return {
            "verdict": verdict,
            "has_p0": has_p0,
            "has_p1": has_p1,
            "hit_count": len(hits),
            "level_counts": {lv: sum(1 for h in hits if h.level == lv) for lv in ("P0", "P1", "P2")},
            "rule_version": RULE_VERSION,
        }

    @staticmethod
    async def check_content(
        content_id: int,
        version_id: Optional[int],
        channels: list[str],
        owner: Optional[OwnerContext],
        platform: Optional[str] = None,
    ) -> dict[str, Any]:
        """完整检测编排：加载文本 → 跑规则 → 落命中记录 → 返回聚合结果。"""
        from base.plugins.contentops.models import ContentItem, ContentVersion

        started = time.time()
        if version_id:
            ver = await owned_queryset(ContentVersion, owner).get_or_none(id=version_id) if owner else await ContentVersion.get_or_none(id=version_id)
            if not ver:
                raise ValueError("成品版本不存在或无权访问")
            text_parts = [ver.payload.get("title", ""), ver.payload.get("body", "")]
            target_id = version_id
        else:
            item = await owned_queryset(ContentItem, owner).get_or_none(id=content_id) if owner else await ContentItem.get_or_none(id=content_id)
            if not item:
                raise ValueError("源内容不存在或无权访问")
            text_parts = [item.title, item.body, item.summary or ""]
            target_id = None

        rules = await ComplianceEngine.load_rules(owner, platform)
        hits: list[Hit] = []
        for part in text_parts:
            if part:
                hits.extend(ComplianceEngine.detect_text(part, rules, channel="text"))

        # OCR / ASR 通道预留：由多媒体服务回填文本后再走同一规则集（本期接口层接入）
        summary = ComplianceEngine.aggregate(hits)

        # 落命中记录（有 version 才关联；源内容检测仅返回，不落库）
        if version_id:
            for h in hits:
                await ComplianceHit.create(
                    content_version_id=version_id, rule_id=h.rule_id,
                    matched_text=h.matched_text, position=h.position, level=h.level,
                    basis=h.basis, suggestion=h.suggestion, confidence=h.confidence,
                    channel=h.channel, rule_version=h.rule_version,
                    owner_type=owner.owner_type if owner else "usr",
                    owner_id=owner.owner_id if owner else None,
                )

        summary["hits"] = [h.to_dict() for h in hits]
        summary["elapsed_ms"] = int((time.time() - started) * 1000)
        summary["version_id"] = version_id
        summary["content_id"] = content_id
        return summary

    # ------------------------------------------------------------------
    # M6 可解释检测管道：分步骤执行 + 逐步轨迹（过程/步骤/方法）
    # 说明：下面的 normalize/step 方法只新增，不改动上方既有 detect_text/aggregate，
    # 以保证 M1-M5 的既有调用与回归零影响。
    # ------------------------------------------------------------------

    # 零宽/不可见字符：常见绕过手段，NFKC 之后仍需显式剔除
    _INVISIBLE_CHARS = ["\u200b", "\u200c", "\u200d", "\ufeff", "\u2060", "\u00ad"]

    @staticmethod
    def normalize_text(text: str) -> str:
        """S1 归一化：NFKC(全角→半角) + 去零宽字符 + 空白折叠。

        目的：让"全角／零宽插入"等变体绕过在后续关键词/正则步骤中无处遁形。
        注意：只产出归一化副本用于检测，不改原文（position 仍以原文为准时另作映射）。
        """
        out = unicodedata.normalize("NFKC", text)
        for ch in ComplianceEngine._INVISIBLE_CHARS:
            out = out.replace(ch, "")
        out = re.sub(r"[ \t\u3000]+", " ", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out

    @staticmethod
    def _trace(
        step: int, code: str, name: str, method: str,
        rules_scanned: int, hits_found: int, started: float,
        status: str, detail: str,
    ) -> TraceStep:
        return TraceStep(
            step=step, code=code, name=name, method=method,
            rules_scanned=rules_scanned, hits_found=hits_found,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            status=status, detail=detail,
        )

    @staticmethod
    async def check_with_trace(
        text: str,
        rules: list[ComplianceRule],
        channel: str = "text",
        platform: Optional[str] = None,
        enable_semantic: bool = False,
    ) -> dict[str, Any]:
        """可解释检测管道：S1归一化→S2关键词→S3正则→S4消歧→S5语义→S6聚合。

        返回既有聚合字段（向后兼容）+ hits（含 layer/source）+ trace（逐步轨迹）。
        S5 语义层默认关闭并诚实标注 skipped + 原因，不伪装成已执行。
        """
        pipeline_started = time.perf_counter()
        trace: list[TraceStep] = []

        # ---- S1 文本归一化（检测变体绕过）----
        t = time.perf_counter()
        normalized = ComplianceEngine.normalize_text(text)
        changed = normalized != text
        trace.append(ComplianceEngine._trace(
            1, "normalize", "文本归一化",
            "NFKC 全角转半角 + 剔除零宽/不可见字符 + 折叠多余空白",
            0, 0, t, "applied",
            (f"检出变体字符，已生成归一化副本用于检测（原文 {len(text)} 字 → 归一化 {len(normalized)} 字）"
             if changed else f"文本已规范，无需修正（{len(text)} 字）"),
        ))

        # ---- 规则分层 ----
        keyword_rules = [r for r in rules if getattr(r, "type", "keyword") == "keyword"]
        regex_rules = [r for r in rules if getattr(r, "type", "") == "regex"]
        semantic_rules = [r for r in rules if getattr(r, "type", "") == "semantic"]

        # ---- S2 关键词精确匹配（DFA 字符串查找 + 消歧）----
        t = time.perf_counter()
        kw_hits: list[Hit] = []
        kw_suppressed = 0
        for rule in keyword_rules:
            needle = ComplianceEngine.normalize_text(rule.pattern) if changed else rule.pattern
            start = 0
            while needle:
                pos = normalized.find(needle, start)
                if pos == -1:
                    break
                if _in_whitelist(normalized, pos, needle):
                    kw_suppressed += 1
                else:
                    kw_hits.append(Hit(
                        matched_text=needle, position=pos, level=rule.risk_level,
                        action=rule.action, basis=rule.basis, suggestion=rule.suggestion,
                        confidence=1.0, channel=channel, rule_id=rule.id,
                        rule_version=rule.version, layer=getattr(rule, "layer", "") or "",
                        source="L1-关键词",
                    ))
                start = pos + len(needle)
        trace.append(ComplianceEngine._trace(
            2, "keyword", "关键词精确匹配",
            "按词库逐词扫描（等价于多模式 DFA），命中即记录位置/等级/依据/建议",
            len(keyword_rules), len(kw_hits), t,
            "applied" if keyword_rules else "skipped",
            (f"扫描 {len(keyword_rules)} 条关键词规则，命中 {len(kw_hits)} 处"
             if keyword_rules else "本租户无关键词规则，跳过此步"),
        ))

        # ---- S3 正则模式匹配 ----
        t = time.perf_counter()
        re_hits: list[Hit] = []
        re_invalid = 0
        re_suppressed = 0
        for rule in regex_rules:
            try:
                for m in re.finditer(rule.pattern, normalized):
                    if m.start() == m.end():
                        continue
                    if _in_whitelist(normalized, m.start(), m.group(0)):
                        re_suppressed += 1
                    else:
                        re_hits.append(Hit(
                            matched_text=m.group(0), position=m.start(), level=rule.risk_level,
                            action=rule.action, basis=rule.basis, suggestion=rule.suggestion,
                            confidence=0.95, channel=channel, rule_id=rule.id,
                            rule_version=rule.version, layer=getattr(rule, "layer", "") or "",
                            source="L2-正则",
                        ))
            except re.error:
                re_invalid += 1
                continue
        trace.append(ComplianceEngine._trace(
            3, "regex", "正则模式匹配",
            "按正则表达式扫描变形/组合违规（如手机号、变体脏话），逐条编译执行",
            len(regex_rules), len(re_hits), t,
            "applied" if regex_rules else "skipped",
            (f"扫描 {len(regex_rules)} 条正则规则，命中 {len(re_hits)} 处"
             + (f"，{re_invalid} 条非法正则已跳过" if re_invalid else "")
             if regex_rules else "本租户无正则规则，跳过此步"),
        ))

        # ---- S4 上下文消歧（白名单降噪）----
        t = time.perf_counter()
        suppressed = kw_suppressed + re_suppressed
        trace.append(ComplianceEngine._trace(
            4, "disambiguation", "上下文消歧",
            f"命中词落在白名单短语内则降噪（{len(CONTEXT_WHITELIST)} 条短语，如'第一反应/最近'）",
            len(CONTEXT_WHITELIST), suppressed, t, "applied",
            (f" suppression：{suppressed} 处绝对化命中落入白名单，已判为非违规"
             if suppressed else "本次无命中落入消歧白名单，无需降噪"),
        ))

        # ---- S5 语义 / LLM 层（诚实标注启用状态）----
        t = time.perf_counter()
        if semantic_rules and enable_semantic:
            status, detail = "skipped", (
                f"已发现 {len(semantic_rules)} 条语义规则，但当前管道未接入语义模型（需平台侧 "
                "LLMProviderConfig purpose=semantic 并经适配层调用）；本次未做语义判定"
            )
        elif semantic_rules:
            status, detail = "skipped", (
                f"发现 {len(semantic_rules)} 条语义规则但未启用语义层（enable_semantic=false），"
                "本次判定仅基于确定性规则"
            )
        else:
            status, detail = "skipped", "本租户无语义规则，无需调用语义/LLM 层"
        trace.append(ComplianceEngine._trace(
            5, "semantic", "语义/LLM 判定",
            "语义相似度/LLM 上下文判定（需平台配置语义模型，当前未接入）",
            len(semantic_rules), 0, t, status, detail,
        ))

        # ---- S6 聚合判定 ----
        t = time.perf_counter()
        hits = kw_hits + re_hits
        summary = ComplianceEngine.aggregate(hits)
        summary["needs_review"] = summary["verdict"] == "review"
        trace.append(ComplianceEngine._trace(
            6, "aggregate", "分级聚合判定",
            "取最高风险等级：含P0→block拦截；含P1→review复核；仅P2→pass_hint提示；无命中→pass",
            len(hits), summary["hit_count"], t, "applied",
            f"判定 {summary['verdict']}，命中 {summary['hit_count']} 处（P0={summary['level_counts']['P0']} / P1={summary['level_counts']['P1']} / P2={summary['level_counts']['P2']}）",
        ))

        summary.update({
            "hits": [h.to_dict() for h in hits],
            "trace": [s.to_dict() for s in trace],
            "pipeline_version": "2.0-trace",
            "rules_loaded": len(rules),
            "normalized": changed,
            "elapsed_ms": round((time.perf_counter() - pipeline_started) * 1000, 3),
            "platform": platform,
            "channel": channel,
        })
        return summary
