"""审核工作流服务：待办队列 + 放行/驳回（P1 中危人工确认）。"""
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import ContentVersion, ReviewTask, ComplianceHit
from base.plugins.contentops.schemas.content_schema import ReviewDecideRequest


class ReviewService:
    """审核服务。"""

    @staticmethod
    async def create_task(version_id: int, hit_count: int, owner: Optional[OwnerContext]):
        task = await ReviewTask.create(
            content_version_id=version_id, hit_count=hit_count, status="pending",
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
        )
        return await task.to_dict()

    @staticmethod
    async def get_queue(status: str, owner: Optional[OwnerContext]):
        qs = owned_queryset(ReviewTask, owner).filter(status=status) if owner else ReviewTask.filter(status=status)
        tasks = await qs.order_by("-created_at")
        return [await t.to_dict() for t in tasks]

    @staticmethod
    async def decide(task_id: int, data: ReviewDecideRequest, owner: Optional[OwnerContext], reviewer_id: Optional[int] = None):
        task = await get_owned_or_404(ReviewTask, task_id, owner, for_write=True) if owner else await ReviewTask.get_or_none(id=task_id)
        if not task:
            raise ValueError("审核任务不存在或无权处理")
        if task.status != "pending":
            raise ValueError("该审核任务已处理")
        if data.decision == "reject" and not data.reason:
            raise ValueError("驳回时必须填写理由")

        task.decision = data.decision
        task.status = "approved" if data.decision == "approve" else "rejected"
        task.reason = data.reason
        task.reviewer_id = reviewer_id
        await task.save()

        # 放行：标记命中已处置 + 版本进入可确认态
        if data.decision == "approve":
            await ComplianceHit.filter(content_version_id=task.content_version_id, confirmed=False).update(
                confirmed=True, handled_by=reviewer_id,
            )
            ver = await ContentVersion.get_or_none(id=task.content_version_id)
            if ver:
                ver.status = "review_passed"
                await ver.save()
        else:
            ver = await ContentVersion.get_or_none(id=task.content_version_id)
            if ver:
                ver.status = "rejected"
                await ver.save()
        return await task.to_dict()

    @staticmethod
    async def confirm_version(version_id: int, confirm: bool, owner: Optional[OwnerContext]):
        """人工确认——导出的唯一出口。P0 未清除 / P1 未放行不允许确认。"""
        ver = await get_owned_or_404(ContentVersion, version_id, owner, for_write=True) if owner else await ContentVersion.get_or_none(id=version_id)
        if not ver:
            raise ValueError("成品版本不存在或无权确认")
        if not confirm:
            ver.confirmed = False
            await ver.save()
            return await ver.to_dict()

        # 检查 P0 硬拦截
        hits = await ComplianceHit.filter(content_version_id=version_id)
        has_p0 = any(h.level == "P0" and not h.confirmed for h in hits)
        has_unhandled_p1 = any(h.level == "P1" and not h.confirmed for h in hits)
        if has_p0:
            raise ValueError("存在未处置的 P0 高危命中，禁止确认导出")
        if has_unhandled_p1:
            raise ValueError("存在未放行的 P1 中危命中，请先完成审核")

        ver.confirmed = True
        ver.status = "confirmed"
        await ver.save()
        return await ver.to_dict()
