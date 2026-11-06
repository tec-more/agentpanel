"""
关注者 API 路由
注意：固定子路径 /list /check /my-following 必须声明在动态路径之前（本路由无动态路径，但仍保持顺序）。
"""
from fastapi import APIRouter, Query
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.mail.schemas.follower_schema import FollowRequest, UnfollowRequest
from base.plugins.mail.services.follower_service import FollowerService

follower_router = APIRouter(prefix="/followers", tags=["消息-关注者"])


@follower_router.post("/follow")
async def follow(
    payload: FollowRequest,
    user_id: int = require_permission("mail:follower:manage"),
):
    """关注业务记录"""
    follower = await FollowerService.follow(
        model=payload.model,
        res_id=payload.res_id,
        user_id=user_id,
        subtype_ids=payload.subtype_ids,
    )
    return success_response(data=await follower.to_dict(include_user=True), msg="关注成功")


@follower_router.post("/unfollow")
async def unfollow(
    payload: UnfollowRequest,
    user_id: int = require_permission("mail:follower:manage"),
):
    """取消关注"""
    success = await FollowerService.unfollow(
        model=payload.model, res_id=payload.res_id, user_id=user_id,
    )
    if not success:
        return fail_response(msg="未关注该记录", code=404)
    return success_response(msg="已取消关注")


@follower_router.get("/list")
async def list_followers(
    model: str = Query(..., description="业务表名"),
    res_id: int = Query(..., description="业务记录ID"),
    user_id: int = require_permission("mail:message:view"),
):
    """获取记录的关注者列表"""
    data = await FollowerService.get_followers(model, res_id, include_user=True)
    return success_response(data={"model": model, "res_id": res_id, "followers": data, "total": len(data)})


@follower_router.get("/check")
async def check_following(
    model: str = Query(...),
    res_id: int = Query(...),
    user_id: int = require_permission("mail:follower:manage"),
):
    """检查当前用户是否关注了某记录"""
    is_following = await FollowerService.is_following(model, res_id, user_id)
    return success_response(data={"is_following": is_following})


@follower_router.get("/my-following")
async def my_following(
    model: str = Query(..., description="业务表名"),
    user_id: int = require_permission("mail:follower:manage"),
):
    """当前用户关注的某模型的记录ID列表"""
    res_ids = await FollowerService.get_my_following(model, user_id)
    return success_response(data={"model": model, "res_ids": res_ids, "total": len(res_ids)})
