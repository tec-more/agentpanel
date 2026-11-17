"""合规规则模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ComplianceRule(BaseModel, TimestampMixin):
    """合规规则：L1 法律法规 / L2 行业 / L3 平台 / L4 品牌四层。"""
    layer = fields.CharField(max_length=8, description="规则层: L1/L2/L3/L4", index=True)
    type = fields.CharField(max_length=32, default="keyword", description="规则类型: keyword/regex/semantic")
    pattern = fields.CharField(max_length=1024, description="规则表达式（词/正则/语义提示词）")
    risk_level = fields.CharField(max_length=4, default="P1", description="风险等级: P0/P1/P2", index=True)
    action = fields.CharField(max_length=32, default="warn", description="动作: block/warn/hint")
    basis = fields.TextField(null=True, description="依据条款")
    suggestion = fields.TextField(null=True, description="替换建议")
    category = fields.CharField(max_length=64, null=True, description="行业/分类（医疗/金融等）")
    version = fields.CharField(max_length=64, default="1", description="规则版本", index=True)
    enabled = fields.BooleanField(default=True, description="是否启用", index=True)
    source = fields.CharField(max_length=16, default="opensource", description="来源: opensource/self/tenant")
    platform = fields.CharField(max_length=32, null=True, description="平台专属规则（NULL 表示通用）")

    # L4 品牌规则按归属隔离；L1-L3 平台级规则 owner 为 None（全局可见）
    owner_type = fields.CharField(max_length=3, null=True, description="归属主体类型: cus/usr/org；NULL=平台级")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_compliance_rule"
        ordering = ["-created_at"]
        indexes = [("layer", "enabled"), ("owner_type", "owner_id"), ("risk_level", "enabled")]
