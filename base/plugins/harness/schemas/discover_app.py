"""发现应用目录的请求校验；跳转目标是安全边界，必须在此先挡一层。"""
import re
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_target_value(target: str, open_mode: str) -> str:
    """站内路径必须是站内相对路径；外链只允许 https 或回环 http，且不带 userinfo。"""
    target = target.strip()
    if not target:
        raise ValueError("跳转目标不能为空")
    if open_mode == "portal":
        if not target.startswith("/") or target.startswith("//") or "\\" in target:
            raise ValueError("站内路径必须以 / 开头且不能是协议相对地址")
        return target
    if open_mode == "link":
        parsed = urlparse(target)
        if parsed.username or parsed.password or not parsed.hostname:
            raise ValueError("外链地址无效")
        loopback = parsed.hostname in LOOPBACK_HOSTS
        if parsed.scheme == "https" or (loopback and parsed.scheme == "http"):
            return target
        raise ValueError("外链只允许 https 或本机 http 地址")
    raise ValueError("打开方式只能是 portal 或 link")


class DiscoverAppBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="应用名称")
    description: str = Field(default="", max_length=160, description="卡片副标题")
    icon_text: str = Field(default="", max_length=4, description="图标内短文本")
    icon_color: Optional[str] = Field(None, max_length=16, description="图标背景色 #RRGGBB")
    open_mode: str = Field(default="portal", description="打开方式：portal / link")
    target: str = Field(..., min_length=1, max_length=512, description="站内路径或外部 URL")
    sort: int = Field(default=0, ge=-1000, le=10000, description="排序（升序）")
    is_active: bool = Field(default=True, description="是否下发到客户端")

    @field_validator("open_mode")
    @classmethod
    def check_mode(cls, value: str) -> str:
        if value not in ("portal", "link"):
            raise ValueError("打开方式只能是 portal 或 link")
        return value

    @field_validator("icon_color")
    @classmethod
    def check_color(cls, value: Optional[str]) -> Optional[str]:
        if value in (None, ""):
            return None
        if not COLOR_PATTERN.match(value):
            raise ValueError("图标颜色需为 #RRGGBB 格式")
        return value

    @field_validator("target")
    @classmethod
    def check_target(cls, value: str, info) -> str:
        return validate_target_value(value, info.data.get("open_mode", "portal"))


class DiscoverAppUpdate(BaseModel):
    """部分更新；在路由层与现有记录合并后用 DiscoverAppBase 完整校验。"""
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = Field(None, max_length=160)
    icon_text: Optional[str] = Field(None, max_length=4)
    icon_color: Optional[str] = Field(None, max_length=16)
    open_mode: Optional[str] = Field(None)
    target: Optional[str] = Field(None, min_length=1, max_length=512)
    sort: Optional[int] = Field(None, ge=-1000, le=10000)
    is_active: Optional[bool] = Field(None)


class DiscoverAppStatusUpdate(BaseModel):
    is_active: bool = Field(..., description="是否启用")
