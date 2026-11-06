"""
通知 Service - 收件箱 / 未读数 / 标记已读
"""
from typing import Optional, List
from datetime import datetime
from loguru import logger

from base.plugins.mail.models.notification import Notification


class NotificationService:

    @staticmethod
    async def get_inbox(user_id: int, page: int = 1, page_size: int = 20,
                         is_read: Optional[bool] = None,
                         is_starred: Optional[bool] = None,
                         message_type: Optional[str] = None,
                         model: Optional[str] = None) -> dict:
        """获取当前用户的收件箱。

        关联 message 表过滤 message_type 和 model（需要先查 message_id 集合）。
        """
        qs = Notification.filter(user_id=user_id)

        # 按 message 字段过滤需先取出符合条件的 message_id 集合
        if message_type or model:
            from base.plugins.mail.models.message import Message
            msg_qs = Message.all()
            if message_type:
                msg_qs = msg_qs.filter(message_type=message_type)
            if model:
                msg_qs = msg_qs.filter(model=model)
            msg_ids = [m.id async for m in msg_qs.only("id")]
            qs = qs.filter(message_id__in=msg_ids)

        if is_read is not None:
            qs = qs.filter(is_read=is_read)
        if is_starred is not None:
            qs = qs.filter(is_starred=is_starred)

        total = await qs.count()
        items = await qs.order_by("-created_at").offset(
            (page - 1) * page_size
        ).limit(page_size)

        # 附带 message 详情
        result_items = []
        for n in items:
            d = await n.to_dict(include_message=True)
            result_items.append(d)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": result_items,
        }

    @staticmethod
    async def get_unread_count(user_id: int) -> int:
        return await Notification.filter(user_id=user_id, is_read=False).count()

    @staticmethod
    async def mark_read(user_id: int, notification_ids: Optional[List[int]] = None) -> int:
        """标记已读。notification_ids 为空/None 时标记全部已读。"""
        qs = Notification.filter(user_id=user_id, is_read=False)
        if notification_ids:
            qs = qs.filter(id__in=notification_ids)
        count = await qs.update(is_read=True, read_datetime=datetime.now())
        return count

    @staticmethod
    async def mark_unread(user_id: int, notification_ids: Optional[List[int]] = None) -> int:
        qs = Notification.filter(user_id=user_id, is_read=True)
        if notification_ids:
            qs = qs.filter(id__in=notification_ids)
        count = await qs.update(is_read=False, read_datetime=None)
        return count

    @staticmethod
    async def set_starred(user_id: int, notification_id: int, starred: bool) -> Optional[Notification]:
        n = await Notification.get_or_none(id=notification_id, user_id=user_id)
        if not n:
            return None
        n.is_starred = starred
        await n.save()
        return n

    @staticmethod
    async def toggle_starred(user_id: int, notification_id: int) -> Optional[Notification]:
        n = await Notification.get_or_none(id=notification_id, user_id=user_id)
        if not n:
            return None
        n.is_starred = not n.is_starred
        await n.save()
        return n
