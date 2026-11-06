"""
M11 身份关联 用户侧 API（双主体 cus/usr 均可访问）

溯源：docs/arch/04-核心流程与接口契约.md §2.1 identity 四个 API；
PRD §3.3（提示→主动确认→验证，R-14 禁止自动绑定）。

挂载：customer 插件 route_prefix=/v1/customer（沿用项目现有插件路由习惯），
最终路径 /v1/customer/identity/*；鉴权复用 T2/M8 require_owner（typ/sub 同源）。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from base.common.authz.context import OwnerContext, require_owner
from base.common.response import success_response, fail_response
from base.plugins.customer.services.identity_service import (
    IdentityError,
    IdentityService,
)

identity_router = APIRouter(prefix="/identity", tags=["身份关联"])


class LinkVerifySchema(BaseModel):
    """关联/解绑请求（需验证对方主体归属）"""
    verify_via: str = Field(..., description="验证方式: password / email_code")
    credential: str = Field(..., min_length=1, description="对方主体密码或邮箱验证码")


@identity_router.get("/link-status", summary="关联提示状态")
async def get_link_status(owner: OwnerContext = Depends(require_owner)):
    """
    检测当前主体是否可与同邮箱另一主体关联
    返回 status: none/prompted/linked/dismissed/cooldown + 对方主体打码信息（L3）
    """
    try:
        data = await IdentityService.get_link_status(owner)
        return success_response(data=data)
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)


@identity_router.post("/link", summary="发起身份关联（需验证）")
async def link_identity(
    data: LinkVerifySchema,
    owner: OwnerContext = Depends(require_owner),
):
    """用户主动发起关联；必须验证对方主体归属（L5），仅建立映射不合并资产（L8/D5）"""
    try:
        result = await IdentityService.link(owner, data.verify_via, data.credential)
        return success_response(data=result, msg="关联成功")
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)


@identity_router.post("/dismiss", summary="不再提示（30 天）")
async def dismiss_identity(owner: OwnerContext = Depends(require_owner)):
    """关闭关联提示 30 天（L7）"""
    try:
        result = await IdentityService.dismiss(owner)
        return success_response(data=result)
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)


@identity_router.post("/unlink", summary="解绑（需验证，冷却 30 天）")
async def unlink_identity(
    data: LinkVerifySchema,
    owner: OwnerContext = Depends(require_owner),
):
    """解除映射（L9/D7）：需再次验证；只解除映射不删除资产；冷却 30 天不再提示"""
    try:
        result = await IdentityService.unlink(owner, data.verify_via, data.credential)
        return success_response(data=result, msg="已解除关联")
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)


@identity_router.post("/send-code", summary="发送身份关联验证码")
async def send_link_code(owner: OwnerContext = Depends(require_owner)):
    """向当前主体邮箱发送关联验证码（限频 60 秒；SMTP 故障返回明确错误）"""
    try:
        message = await IdentityService.send_link_code(owner)
        return success_response(msg=message)
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)


@identity_router.post("/resume", summary="重新开启提示（T14+ K2）")
async def resume_identity(owner: OwnerContext = Depends(require_owner)):
    """
    将 dismissed（不再提示）恢复为 prompted；cooldown（解绑冷却）期间拒绝（L9）。
    重复调用：已 prompted 返回 not_dismissed，幂等安全。
    """
    try:
        result = await IdentityService.resume(owner)
        return success_response(data=result, msg="已重新开启提示")
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)


@identity_router.get("/audit", summary="身份操作历史（T14+ K4）")
async def get_identity_audit(owner: OwnerContext = Depends(require_owner)):
    """
    返回当前主体对的 IdentityLink.audit 事件列表（L10 用户可查）；
    无对方主体或无映射记录时返回空列表（不暴露存在性）。
    """
    try:
        data = await IdentityService.get_audit(owner)
        return success_response(data=data)
    except IdentityError as e:
        return fail_response(msg=e.message, data=e.data)
