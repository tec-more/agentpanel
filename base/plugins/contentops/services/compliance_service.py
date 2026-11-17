"""合规规则引擎：DFA 关键词 + 正则 + 分级（P0/P1/P2）。

设计要点：
- 词库按归属隔离：平台级规则（owner 为 NULL）全局可见 + 租户级规则叠加。
- 每个命中带：命中词/句、位置、等级、依据条款、替换建议、置信度、规则版本。
- NLP 上下文消歧：对"最近/第一反应"等白名单短语降噪，避免误报。
- 语义/LLM 兜底由 adapt/semantic 层调用，本服务只做确定性规则检测。
"""
import re
import time
from dataclasses import dataclass, asdict
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
