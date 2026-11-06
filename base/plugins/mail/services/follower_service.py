"""
关注者 Service
"""
from typing import Optional, List
from loguru import logger

from base.plugins.mail.models.follower import Follower


class FollowerService:

    @staticmethod
    async def follow(model: str, res_id: int, user_id: int,
                      subtype_ids: Optional[List[int]] = None) -> Follower:
        """关注记录（已关注则更新订阅子类型）"""
        follower, created = await Follower.get_or_create(
            model=model, res_id=res_id, user_id=user_id,
            defaults={"subtype_ids": subtype_ids or []},
        )
        if not created:
            follower.subtype_ids = subtype_ids if subtype_ids is not None else []
            await follower.save()
        return follower

    @staticmethod
    async def unfollow(model: str, res_id: int, user_id: int) -> bool:
        """取消关注"""
        deleted_count = await Follower.filter(
            model=model, res_id=res_id, user_id=user_id
        ).delete()
        return deleted_count > 0

    @staticmethod
    async def get_followers(model: str, res_id: int, include_user: bool = True) -> List[dict]:
        followers = await Follower.filter(model=model, res_id=res_id).all()
        return [await f.to_dict(include_user=include_user) for f in followers]

    @staticmethod
    async def is_following(model: str, res_id: int, user_id: int) -> bool:
        return await Follower.filter(
            model=model, res_id=res_id, user_id=user_id
        ).exists()

    @staticmethod
    async def get_my_following(model: str, user_id: int) -> List[int]:
        """当前用户关注的某模型的记录ID列表"""
        followers = await Follower.filter(model=model, user_id=user_id).all()
        return [f.res_id for f in followers]

    @staticmethod
    async def get_follower_user_ids(model: str, res_id: int) -> List[int]:
        """获取记录的所有关注者用户ID（用于消息通知）"""
        followers = await Follower.filter(model=model, res_id=res_id).all()
        return [f.user_id for f in followers]

    @staticmethod
    async def filter_subscribed_user_ids(model: str, res_id: int, subtype_id: Optional[int],
                                          exclude_user_id: Optional[int] = None) -> List[int]:
        """获取订阅了指定子类型的关注者用户ID。

        follower.subtype_ids 为空列表 → 订阅全部子类型
        follower.subtype_ids 非空    → 仅当 subtype_id 在列表内
        """
        followers = await Follower.filter(model=model, res_id=res_id).all()
        result = []
        for f in followers:
            if exclude_user_id is not None and f.user_id == exclude_user_id:
                continue
            if not f.subtype_ids:
                # 空列表=订阅全部
                result.append(f.user_id)
            elif subtype_id is not None and subtype_id in f.subtype_ids:
                result.append(f.user_id)
        return result
