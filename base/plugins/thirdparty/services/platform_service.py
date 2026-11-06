"""
第三方平台服务
"""
from typing import List, Optional
from tortoise.exceptions import DoesNotExist
from base.plugins.thirdparty.models.platform import ThirdPartyPlatform
from base.plugins.thirdparty.schemas.platform import PlatformCreate, PlatformUpdate
class PlatformService:
    model = "platform"
    """平台服务类"""

    @staticmethod
    async def create_platform(platform_data: PlatformCreate) -> ThirdPartyPlatform:
        """创建平台"""
        platform = await ThirdPartyPlatform.create(**platform_data.model_dump())
        return platform

    @staticmethod
    async def get_platforms(skip: int = 0, limit: int = 100) -> List[ThirdPartyPlatform]:
        """获取平台列表"""
        platforms = await ThirdPartyPlatform.all().offset(skip).limit(limit)
        return platforms

    @staticmethod
    async def get_platform_by_id(platform_id: int) -> Optional[ThirdPartyPlatform]:
        """根据ID获取平台"""
        try:
            platform = await ThirdPartyPlatform.get(id=platform_id)
            return platform
        except DoesNotExist:
            return None

    @staticmethod
    async def update_platform(platform_id: int, platform_data: PlatformUpdate) -> Optional[ThirdPartyPlatform]:
        """更新平台"""
        platform = await PlatformService.get_platform_by_id(platform_id)
        if not platform:
            return None

        update_data = platform_data.model_dump(exclude_unset=True)
        await platform.update_from_dict(update_data)
        await platform.save()
        return platform

    @staticmethod
    async def delete_platform(platform_id: int) -> bool:
        """删除平台"""
        platform = await PlatformService.get_platform_by_id(platform_id)
        if not platform:
            return False

        await platform.delete()
        return True

    @staticmethod
    async def test_platform_connection(platform_id: int) -> bool:
        """测试平台连接"""
        platform = await PlatformService.get_platform_by_id(platform_id)
        if not platform:
            return False

        # TODO: 实现平台连接测试逻辑
        # 这里需要根据不同平台类型实现不同的连接测试
        # 例如：Dify可以调用其API的健康检查接口
        # Coze可以调用其API的认证接口
        return True