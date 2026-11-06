"""
消息 Service - post_message 是核心方法，被 API 与事件处理器共同调用
"""
from typing import Optional, List, Any
from datetime import datetime
from loguru import logger

from base.plugins.mail.models.message import Message
from base.plugins.mail.models.notification import Notification
from base.plugins.mail.services.follower_service import FollowerService
from base.plugins.mail.services.subtype_service import SubtypeService
from base.plugins.mail.schemas.message_schema import MessageCreate, MessageUpdate, MessageListQuery


# 创建者字段候选顺序：从 record_data 中识别业务记录的创建者ID
_CREATOR_FIELD_CANDIDATES = ("created_by", "applicant_id", "user_id", "creator_id", "created_by_id")


class MessageService:

    @staticmethod
    async def post_message(
        model: Optional[str],
        res_id: Optional[int],
        body: str,
        author_id: int,
        subtype_id: Optional[int] = None,
        subtype_code: Optional[str] = None,
        message_type: str = "comment",
        subject: Optional[str] = None,
        parent_id: Optional[int] = None,
        attachment_ids: Optional[List[Any]] = None,
        is_internal: bool = False,
        record_name: Optional[str] = None,
        notify_followers: bool = True,
        extra_recipient_ids: Optional[List[int]] = None,
        notify_creator: bool = False,
        record_data: Optional[dict] = None,
    ) -> Message:
        """发布消息并生成通知。

        1. subtype_code → subtype_id（若未传 subtype_id）
        2. 创建 Message 记录
        3. 计算收件人集合：
           - extra_recipient_ids
           - notify_followers=True 时，按子类型过滤记录的关注者（剔除作者）
           - notify_creator=True 时，从 record_data 推断记录创建者并加入
        4. Notification.bulk_create([...])
        """
        # 1. 解析子类型
        if subtype_id is None and subtype_code:
            subtype = await SubtypeService.get_by_code(subtype_code)
            subtype_id = subtype.id if subtype else None
            if subtype_id is None:
                logger.warning(f"[mail] 未找到子类型编码: {subtype_code}")

        # 2. 创建消息
        msg = await Message.create(
            subject=subject,
            body=body,
            author_id=author_id,
            model=model,
            res_id=res_id,
            message_type=message_type,
            subtype_id=subtype_id,
            parent_id=parent_id,
            is_internal=is_internal,
            attachment_ids=attachment_ids or [],
            record_name=record_name,
        )

        # 3. 计算收件人
        recipient_ids: set = set(extra_recipient_ids or [])

        if notify_followers and model and res_id:
            follower_ids = await FollowerService.filter_subscribed_user_ids(
                model=model, res_id=res_id,
                subtype_id=subtype_id,
                exclude_user_id=author_id if author_id > 0 else None,
            )
            recipient_ids.update(follower_ids)

        if notify_creator and record_data:
            creator_id = MessageService._extract_creator_id(record_data)
            if creator_id and creator_id != author_id:
                recipient_ids.add(creator_id)

        # 4. 批量创建通知
        if recipient_ids:
            notifications = [
                Notification(
                    message_id=msg.id,
                    user_id=uid,
                    notification_status="ready",
                )
                for uid in recipient_ids
            ]
            await Notification.bulk_create(notifications)
            logger.info(
                f"[mail] 消息 #{msg.id} 已通知 {len(recipient_ids)} 个收件人 "
                f"(model={model}, res_id={res_id}, type={message_type})"
            )
            # WebSocket 实时推送（失败不影响主流程，前端有轮询兜底）
            try:
                from base.plugins.mail.services.ws_manager import mail_ws_manager
                from base.plugins.mail.services.notification_service import NotificationService
                msg_dict = await msg.to_dict(include_author=True, include_subtype=True)
                for uid in recipient_ids:
                    notif = await Notification.get(message_id=msg.id, user_id=uid)
                    payload = {
                        "type": "notification",
                        "notification": await notif.to_dict(include_message=False),
                        "message": msg_dict,
                        "unread_count": await NotificationService.get_unread_count(uid),
                    }
                    await mail_ws_manager.push_to_user(uid, payload)
            except Exception as e:
                logger.warning(f"[mail] WS 推送失败（不影响消息创建）: {e}")

        return msg

    @staticmethod
    def _extract_creator_id(record_data: dict) -> Optional[int]:
        """从 record_data 推断记录创建者ID"""
        if not record_data:
            return None
        for field in _CREATOR_FIELD_CANDIDATES:
            val = record_data.get(field)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    async def get_message(message_id: int) -> Optional[Message]:
        return await Message.get_or_none(id=message_id)

    @staticmethod
    async def get_thread(model: str, res_id: int, page: int = 1, page_size: int = 20) -> dict:
        """获取记录的消息线程（按 created_at 升序，便于聊天式展示）"""
        qs = Message.filter(model=model, res_id=res_id)
        total = await qs.count()
        items = await qs.order_by("created_at").offset(
            (page - 1) * page_size
        ).limit(page_size)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "model": model,
            "res_id": res_id,
            "items": [await m.to_dict(include_author=True, include_subtype=True) for m in items],
        }

    @staticmethod
    async def list_messages(query: MessageListQuery) -> dict:
        qs = Message.all()
        if query.model:
            qs = qs.filter(model=query.model)
        if query.res_id:
            qs = qs.filter(res_id=query.res_id)
        if query.message_type:
            qs = qs.filter(message_type=query.message_type)
        if query.subtype_id:
            qs = qs.filter(subtype_id=query.subtype_id)
        if query.author_id:
            qs = qs.filter(author_id=query.author_id)

        total = await qs.count()
        items = await qs.order_by("-created_at").offset(
            (query.page - 1) * query.page_size
        ).limit(query.page_size)
        return {
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
            "items": [await m.to_dict(include_author=True, include_subtype=True) for m in items],
        }

    @staticmethod
    async def update_message(message_id: int, data: MessageUpdate, user_id: int,
                              is_admin: bool = False) -> Optional[Message]:
        """更新消息（仅作者或管理员）"""
        msg = await Message.get_or_none(id=message_id)
        if not msg:
            return None
        if not is_admin and msg.author_id != user_id:
            raise PermissionError("无权编辑他人消息")
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(msg, k, v)
        await msg.save()
        return msg

    @staticmethod
    async def delete_message(message_id: int, user_id: int, is_admin: bool = False) -> bool:
        """删除消息（仅作者或管理员）；同时清理关联通知"""
        msg = await Message.get_or_none(id=message_id)
        if not msg:
            return False
        if not is_admin and msg.author_id != user_id:
            raise PermissionError("无权删除他人消息")
        await Notification.filter(message_id=message_id).delete()
        await msg.delete()
        return True
