"""
系统设置服务层
"""
from typing import Optional, List, Tuple, Dict
from tortoise.expressions import Q

from base.core.users.models.system_setting import SystemSetting
from base.core.users.schemas.system_setting import SystemSettingCreate, SystemSettingUpdate


class SystemSettingService:
    """系统设置服务类"""

    @staticmethod
    async def get_by_id(setting_id: int) -> Optional[SystemSetting]:
        """
        根据ID获取系统设置

        Args:
            setting_id: 设置ID

        Returns:
            Optional[SystemSetting]: 设置对象,不存在返回None
        """
        return await SystemSetting.filter(id=setting_id).first()

    @staticmethod
    async def get_by_key(key: str) -> Optional[SystemSetting]:
        """
        根据键获取系统设置

        Args:
            key: 设置键

        Returns:
            Optional[SystemSetting]: 设置对象,不存在返回None
        """
        return await SystemSetting.filter(key=key).first()

    @staticmethod
    async def create_setting(setting_data: SystemSettingCreate) -> SystemSetting:
        """
        创建系统设置

        Args:
            setting_data: 系统设置创建数据

        Returns:
            SystemSetting: 创建的设置对象
        """
        setting = await SystemSetting.create(
            key=setting_data.key,
            value=setting_data.value,
            name=setting_data.name,
            description=setting_data.description,
            setting_type=setting_data.setting_type,
            is_active=setting_data.is_active,
            sort=setting_data.sort,
        )
        return setting

    @staticmethod
    async def update_setting(setting_id: int, setting_data: SystemSettingUpdate) -> Optional[SystemSetting]:
        """
        更新系统设置

        Args:
            setting_id: 设置ID
            setting_data: 更新数据

        Returns:
            Optional[SystemSetting]: 更新后的设置对象
        """
        setting = await SystemSetting.filter(id=setting_id).first()
        if not setting:
            return None

        update_data = setting_data.model_dump(exclude_unset=True)
        await setting.update_from_dict(update_data).save()
        return setting

    @staticmethod
    async def update_setting_by_key(key: str, value: str) -> Optional[SystemSetting]:
        """
        根据键更新系统设置值

        Args:
            key: 设置键
            value: 设置值

        Returns:
            Optional[SystemSetting]: 更新后的设置对象
        """
        setting = await SystemSetting.filter(key=key).first()
        if not setting:
            return None

        setting.value = value
        await setting.save()
        return setting

    @staticmethod
    async def delete_setting(setting_id: int) -> bool:
        """
        删除系统设置

        Args:
            setting_id: 设置ID

        Returns:
            bool: 是否删除成功
        """
        deleted_count = await SystemSetting.filter(id=setting_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_setting_list(
            page: int = 1,
            page_size: int = 10,
            key: Optional[str] = None,
            name: Optional[str] = None,
            is_active: Optional[bool] = None,
    ) -> Tuple[List[SystemSetting], int]:
        """
        获取系统设置列表(分页)

        Args:
            page: 页码
            page_size: 每页数量
            key: 设置键(模糊搜索)
            name: 设置名称(模糊搜索)
            is_active: 是否激活

        Returns:
            Tuple[List[SystemSetting], int]: (设置列表, 总数)
        """
        query = SystemSetting.all()

        if key:
            query = query.filter(key__icontains=key)
        if name:
            query = query.filter(name__icontains=name)
        if is_active is not None:
            query = query.filter(is_active=is_active)

        total = await query.count()

        offset = (page - 1) * page_size
        settings = await query.offset(offset).limit(page_size).order_by('sort', '-created_at')

        return settings, total

    @staticmethod
    async def get_all_active_settings() -> Dict[str, str]:
        """
        获取所有激活的设置，返回键值对字典

        Returns:
            Dict[str, str]: 键值对字典
        """
        settings = await SystemSetting.filter(is_active=True).all()
        result = {}
        for setting in settings:
            result[setting.key] = setting.value
        return result

    @staticmethod
    async def check_key_exists(key: str, exclude_id: Optional[int] = None) -> bool:
        """
        检查设置键是否存在

        Args:
            key: 设置键
            exclude_id: 排除的设置ID(用于更新时检查)

        Returns:
            bool: 是否存在
        """
        query = SystemSetting.filter(key=key)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def init_default_settings():
        """
        初始化默认系统设置和菜单
        """
        # 1. 初始化系统设置菜单
        from base.core.users.models.rbac import Menu
        
        # 查找或创建系统管理父菜单
        system_admin_menu = await Menu.filter(name="系统管理", menu_type="directory").first()
        if not system_admin_menu:
            system_admin_menu = await Menu.create(
                name="系统管理",
                path="/system",
                icon="Setting",
                component="",
                parent_id=None,
                sort=9999,
                is_visible=True,
                is_cached=True,
                is_active=True,
                menu_type="directory",
                permission="system:admin",
            )
        
        # 创建系统设置子菜单
        menu_exists = await Menu.filter(name="系统设置", path="/system-setting").exists()
        if not menu_exists:
            await Menu.create(
                name="系统设置",
                path="/system-setting",
                icon="Setting",
                component="systemSetting/index",
                parent_id=system_admin_menu.id,
                sort=99,
                is_visible=True,
                is_cached=True,
                is_active=True,
                menu_type="menu",
                permission="system:setting",
            )

        # 2. 初始化默认系统设置
        default_settings = [
            {
                "key": "system_name",
                "value": "AI智能管理系统",
                "name": "系统名称",
                "description": "网站或系统的名称",
                "setting_type": "string",
                "sort": 1,
            },
            {
                "key": "system_logo",
                "value": "",
                "name": "系统Logo",
                "description": "网站或系统的Logo图片URL",
                "setting_type": "image",
                "sort": 2,
            },
            {
                "key": "system_icp",
                "value": "",
                "name": "备案号",
                "description": "网站ICP备案号",
                "setting_type": "string",
                "sort": 3,
            },
            {
                "key": "system_copyright",
                "value": "© 2024 AI智能管理系统 版权所有",
                "name": "版权信息",
                "description": "网站底部版权声明",
                "setting_type": "string",
                "sort": 4,
            },
            {
                "key": "system_description",
                "value": "一个强大的AI智能管理平台",
                "name": "系统描述",
                "description": "网站或系统的简要描述",
                "setting_type": "string",
                "sort": 5,
            },
        ]

        for setting_data in default_settings:
            exists = await SystemSetting.filter(key=setting_data["key"]).exists()
            if not exists:
                await SystemSetting.create(**setting_data)
