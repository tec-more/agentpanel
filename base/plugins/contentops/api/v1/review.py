"""审核工作流路由。"""
from fastapi import APIRouter, Depends, Query

from base.common.authz import OwnerContext, require_owner, require_action
from base.common.response import success_response, fail_response
from base.plugins.contentops.schemas.content_schema import ReviewDecideRequest
from base.plugins.contentops.services.review_service import ReviewService

review_router = APIRouter(prefix="/reviews", tags=["合规审核"])


@review_router.get("", summary="待办/已办审核队列")
async def queue(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:review:view"),
):
    return success_response(data={"items": await ReviewService.get_queue(status, owner)})


@review_router.post("/{task_id}/decide", summary="审核放行/驳回")
async def decide(
    task_id: int, data: ReviewDecideRequest,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:review:decide"),
):
    try:
        return success_response(data=await ReviewService.decide(task_id, data, owner, reviewer_id=user_id))
    except ValueError as e:
        return fail_response(msg=str(e), code=400)
