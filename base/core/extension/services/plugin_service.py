"""
插件服务层
"""
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from tortoise.expressions import Q

from base.core.extension.models.plugin import Plugin
from base.core.extension.schemas.plugin import PluginCreate, PluginUpdate


class PluginService:
    """插件服务类"""

    @staticmethod
    async def get_by_id(plugin_id: int) -> Optional[Plugin]:
        """
        根据ID获取插件

        Args:
            plugin_id: 插件ID

        Returns:
            Optional[Plugin]: 插件对象,不存在返回None
        """
        return await Plugin.filter(id=plugin_id).first()

    @staticmethod
    async def get_by_name(name: str) -> Optional[Plugin]:
        """
        根据名称获取插件

        Args:
            name: 插件名称

        Returns:
            Optional[Plugin]: 插件对象,不存在返回None
        """
        return await Plugin.filter(name=name).first()

    @staticmethod
    async def get_plugin_list(
        page: int = 1,
        page_size: int = 10,
        is_enabled: Optional[bool] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[Plugin], int]:
        """
        获取插件列表(分页)

        Args:
            page: 页码
            page_size: 每页数量
            is_enabled: 是否启用
            keyword: 搜索关键词

        Returns:
            Tuple[List[Plugin], int]: (插件列表, 总数)
        """
        query = Plugin.all()

        if is_enabled is not None:
            query = query.filter(is_enabled=is_enabled)

        if keyword:
            query = query.filter(
                Q(name__icontains=keyword) |
                Q(display_name__icontains=keyword) |
                Q(description__icontains=keyword)
            )

        total = await query.count()
        offset = (page - 1) * page_size
        plugins = await query.offset(offset).limit(page_size).order_by("sort_order", "-created_at")

        return plugins, total

    @staticmethod
    async def create_plugin(plugin_data: PluginCreate) -> Plugin:
        """
        创建插件记录

        Args:
            plugin_data: 插件创建数据

        Returns:
            Plugin: 创建的插件对象
        """
        plugin = await Plugin.create(
            name=plugin_data.name,
            display_name=plugin_data.display_name,
            version=plugin_data.version,
            description=plugin_data.description,
            author=plugin_data.author,
            website=plugin_data.website,
            dependencies=plugin_data.dependencies,
            settings=plugin_data.settings,
            is_enabled=False,
            is_installed=True,
        )
        return plugin

    @staticmethod
    async def update_plugin(plugin_id: int, plugin_data: PluginUpdate) -> Optional[Plugin]:
        """
        更新插件

        Args:
            plugin_id: 插件ID
            plugin_data: 更新数据

        Returns:
            Optional[Plugin]: 更新后的插件对象
        """
        plugin = await Plugin.filter(id=plugin_id).first()
        if not plugin:
            return None

        update_data = plugin_data.model_dump(exclude_unset=True)
        await plugin.update_from_dict(update_data).save()
        return plugin

    @staticmethod
    async def delete_plugin(plugin_id: int) -> bool:
        """
        删除插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 是否删除成功
        """
        deleted_count = await Plugin.filter(id=plugin_id).delete()
        return deleted_count > 0

    @staticmethod
    async def enable_plugin(plugin_id: int) -> Optional[Plugin]:
        """
        启用插件

        Args:
            plugin_id: 插件ID

        Returns:
            Optional[Plugin]: 更新后的插件对象
        """
        plugin = await Plugin.filter(id=plugin_id).first()
        if not plugin:
            return None

        plugin.is_enabled = True
        await plugin.save()
        return plugin

    @staticmethod
    async def disable_plugin(plugin_id: int) -> Optional[Plugin]:
        """
        禁用插件

        Args:
            plugin_id: 插件ID

        Returns:
            Optional[Plugin]: 更新后的插件对象
        """
        plugin = await Plugin.filter(id=plugin_id).first()
        if not plugin:
            return None

        plugin.is_enabled = False
        await plugin.save()
        return plugin

    @staticmethod
    async def set_install_status(plugin_id: int, is_installed: bool) -> Optional[Plugin]:
        """
        修改插件安装状态（安装/卸载）

        - 安装：is_installed=True，is_enabled 保持 False（安装后需手动启用）
        - 卸载：is_installed=False，同时强制 is_enabled=False

        Args:
            plugin_id: 插件ID
            is_installed: 是否已安装

        Returns:
            Optional[Plugin]: 更新后的插件对象
        """
        plugin = await Plugin.filter(id=plugin_id).first()
        if not plugin:
            return None

        plugin.is_installed = is_installed
        if not is_installed:
            plugin.is_enabled = False
        await plugin.save()
        return plugin

    @staticmethod
    async def update_settings(plugin_id: int, settings: Dict[str, Any]) -> Optional[Plugin]:
        """
        更新插件设置

        Args:
            plugin_id: 插件ID
            settings: 新的设置

        Returns:
            Optional[Plugin]: 更新后的插件对象
        """
        plugin = await Plugin.filter(id=plugin_id).first()
        if not plugin:
            return None

        plugin.settings = settings
        await plugin.save()
        return plugin

    @staticmethod
    async def check_name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
        """
        检查插件名称是否存在

        Args:
            name: 插件名称
            exclude_id: 排除的插件ID

        Returns:
            bool: 是否存在
        """
        query = Plugin.filter(name=name)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def get_enabled_plugins() -> List[Plugin]:
        """
        获取所有已启用的插件

        Returns:
            List[Plugin]: 已启用的插件列表
        """
        return await Plugin.filter(is_enabled=True).order_by("sort_order")

    @staticmethod
    async def sync_plugin(
        name: str,
        display_name: str,
        version: str,
        description: str = None,
        author: str = None,
        website: str = None,
        dependencies: List[str] = None,
        is_installed: bool = False,
        is_enabled: bool = False
    ) -> Plugin:
        """
        同步插件信息(存在则更新,不存在则创建)

        Args:
            name: 插件名称
            display_name: 显示名称
            version: 版本号
            description: 描述
            author: 作者
            website: 网站
            dependencies: 依赖
            is_installed: 是否已安装
            is_enabled: 是否启用
        Returns:
            Plugin: 插件对象
        """
        plugin = await Plugin.filter(name=name).first()

        if plugin:
            plugin.display_name = display_name
            plugin.version = version
            plugin.description = description
            plugin.author = author
            plugin.website = website
            plugin.dependencies = dependencies or []
            plugin.is_installed = is_installed
            plugin.is_enabled = is_enabled
            await plugin.save()
        else:
            plugin = await Plugin.create(
                name=name,
                display_name=display_name,
                version=version,
                description=description,
                author=author,
                website=website,
                dependencies=dependencies or [],
                is_enabled=is_enabled,
                is_installed=is_installed,
            )

        return plugin
