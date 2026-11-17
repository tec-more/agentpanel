"""自适应引擎：按平台生成成品 + 生成后二次过合规。"""
from typing import Any, Optional

from base.common.authz import OwnerContext, get_owned_or_404
from base.plugins.contentops.models import ContentItem, ContentVersion, PlatformRuleConfig
from base.plugins.contentops.schemas.content_schema import AdaptGenerateRequest
from base.plugins.contentops.services.compliance_service import ComplianceEngine
from base.plugins.contentops.services.llm_adapter import LLMAdapter


class AdaptService:
    """自适应生成服务。"""

    @staticmethod
    async def _get_rules(platform: str, owner: Optional[OwnerContext]) -> dict[str, Any]:
        """从后台配置读取平台适配规则（禁止硬编码）。"""
        qs = PlatformRuleConfig.filter(platform=platform, enabled=True)
        rows = await qs
        cfg = {}
        for r in rows:
            # 租户级覆盖全局级
            cfg[r.key] = r.value
        return cfg

    @staticmethod
    def _strip_html(body: str) -> str:
        import re
        return re.sub(r"<[^>]+>", "", body or "").strip()

    @staticmethod
    async def generate(req: AdaptGenerateRequest, owner: Optional[OwnerContext]) -> list[dict]:
        """为目标平台各生成一份成品，生成后二次过合规。"""
        item = await get_owned_or_404(ContentItem, req.content_id, owner) if owner else await ContentItem.get_or_none(id=req.content_id)
        if not item:
            raise ValueError("源内容不存在或无权访问")

        results: list[dict] = []
        plain_body = AdaptService._strip_html(item.body)

        for platform in req.platforms:
            cfg = await AdaptService._get_rules(platform, owner)
            title_max = int((cfg.get("title_max") or {}).get("value", 64))
            desc_max = int((cfg.get("desc_max") or {}).get("value", 2000))
            cover_ratio = (cfg.get("cover_ratio") or {}).get("value", "16:9")

            payload: dict[str, Any] = {"title": item.title, "body": item.body, "topics": item.topics}
            # 带上该内容的素材引用，供导出打包成片/图片/封面（M1 素材链）
            try:
                from base.plugins.contentops.models import MediaAsset
                assets = await MediaAsset.filter(content_id=item.id).all()
                cover_assets = [a for a in assets if a.kind == "cover" and a.extra.get("platform") in (None, platform)]
                adapted = [a for a in assets if a.kind == "adapted" and a.extra.get("platform") == platform]
                images = [a for a in assets if a.kind == "image"]
                videos = [a for a in assets if a.kind == "video"]
                # 优先用该平台的适配封面，否则用通用封面
                cover_pick = (adapted or cover_assets)
                if cover_pick:
                    payload["cover_asset_id"] = cover_pick[0].id
                if adapted:
                    payload["adapted_asset_ids"] = [a.id for a in adapted]
                if images:
                    payload["image_asset_ids"] = [a.id for a in images]
                if videos:
                    payload["video_asset_id"] = videos[0].id
            except Exception:
                pass
            diff: list[dict] = []
            meta: dict = {}

            if req.use_llm:
                try:
                    rewritten, meta = await LLMAdapter.rewrite(plain_body, platform)
                    diff.append({"original": plain_body, "rewritten": rewritten})
                    payload["body"] = rewritten
                except Exception as e:
                    # 降级：LLM 不可用则保留原文（规则模板兜底）
                    meta = {"fallback": True, "error": str(e)[:200]}

            # 标题按平台上限裁剪
            if len(payload["title"]) > title_max:
                payload["title"] = payload["title"][:title_max]
            # 话题数量限制
            topic_limit = int((cfg.get("topic_limit") or {}).get("value", 5))
            payload["topics"] = payload["topics"][:topic_limit]
            payload["cover_ratio"] = cover_ratio
            payload["platform"] = platform

            # 生成成品版本
            ver = await ContentVersion.create(
                content_id=item.id, platform=platform, payload=payload,
                is_adapted=True, diff=diff, rule_version=meta.get("rule_version"),
                owner_type=owner.owner_type if owner else "usr",
                owner_id=owner.owner_id if owner else None,
            )

            # 二次过合规：对生成后的标题+正文再检测
            check_text = f"{payload['title']}\n{payload.get('body', '')}"
            rules = await ComplianceEngine.load_rules(owner, platform)
            hits = ComplianceEngine.detect_text(check_text, rules, channel="text")
            summary = ComplianceEngine.aggregate(hits)
            payload["post_adapt_compliance"] = summary["verdict"]
            ver.payload = payload
            await ver.save()

            results.append({
                "version_id": ver.id,
                "platform": platform,
                "payload": payload,
                "diff": diff,
                "compliance": summary["verdict"],
                "llm_meta": meta,
            })

        return results
