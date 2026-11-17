"""ContentOps 请求/响应 Schema。"""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------- 内容中心 ----------
class ContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512, description="标题")
    body: str = Field(..., min_length=1, description="正文（富文本/HTML）")
    summary: Optional[str] = Field(None, description="摘要")
    media: list[dict] = Field(default_factory=list, description="图片/视频引用列表")
    topics: list[str] = Field(default_factory=list, description="话题标签")
    cover: Optional[str] = Field(None, description="封面 URL")


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=512)
    body: Optional[str] = None
    summary: Optional[str] = None
    media: Optional[list[dict]] = None
    topics: Optional[list[str]] = None
    cover: Optional[str] = None
    status: Optional[str] = None


class ContentListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=200)
    status: Optional[str] = None
    keyword: Optional[str] = None


# ---------- 合规检测 ----------
class ComplianceCheckRequest(BaseModel):
    content_id: Optional[int] = Field(None, description="源内容 ID")
    version_id: Optional[int] = Field(None, description="成品版本 ID")
    channels: list[str] = Field(default_factory=lambda: ["text"], description="检测通道: text/ocr/asr")


# ---------- 自适应生成 ----------
class AdaptGenerateRequest(BaseModel):
    content_id: int = Field(..., description="源内容 ID")
    platforms: list[str] = Field(..., min_length=1, description="目标平台列表")
    use_llm: bool = Field(default=True, description="是否使用 LLM 改写（关闭则仅规则模板）")


class VersionConfirmRequest(BaseModel):
    confirm: bool = Field(default=True, description="人工确认（导出唯一出口）")


# ---------- 审核 ----------
class ReviewDecideRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$", description="approve/reject")
    reason: Optional[str] = Field(None, description="驳回理由（reject 时必填）")


# ---------- 导出 ----------
class ExportRequest(BaseModel):
    content_id: int = Field(..., description="源内容 ID")
    platform_version_ids: dict[str, int] = Field(..., description="平台 -> 成品版本 ID")


# ---------- 台账 ----------
class LedgerCreate(BaseModel):
    version_id: int = Field(..., description="成品版本 ID")
    platform: str = Field(..., description="平台标识")
    planned_at: Optional[str] = Field(None, description="计划发布时间 ISO8601")
    note: Optional[str] = None


class LedgerUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|published|abandoned)$")
    published_at: Optional[str] = None
    note: Optional[str] = None


class EffectCreate(BaseModel):
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    favorites: int = Field(default=0, ge=0)
    source: str = Field(default="manual", pattern="^(manual|csv)$")
    stat_date: Optional[str] = None


class EffectCSVImport(BaseModel):
    csv_content: str = Field(..., description="CSV 文本内容")
    column_mapping: dict[str, str] = Field(default_factory=dict, description="CSV 列名 -> 标准字段映射")


# ---------- 规则库 ----------
class RuleCreate(BaseModel):
    layer: str = Field(..., pattern="^L[1-4]$")
    type: str = Field(default="keyword", description="keyword/regex/semantic")
    pattern: str = Field(..., min_length=1)
    risk_level: str = Field(default="P1", pattern="^P[012]$")
    action: str = Field(default="warn", description="block/warn/hint")
    basis: Optional[str] = None
    suggestion: Optional[str] = None
    category: Optional[str] = None
    platform: Optional[str] = None
    enabled: bool = True


class RuleUpdate(BaseModel):
    pattern: Optional[str] = None
    risk_level: Optional[str] = Field(None, pattern="^P[012]$")
    action: Optional[str] = None
    basis: Optional[str] = None
    suggestion: Optional[str] = None
    enabled: Optional[bool] = None
