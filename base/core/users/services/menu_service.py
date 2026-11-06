"""
菜单服务层
"""
from typing import Optional, List, Set
from base.core.users.models.rbac import Menu
from base.core.users.schemas.rbac import MenuCreate, MenuUpdate


class MenuService:
    """菜单服务类"""

    @staticmethod
    async def get_by_id(menu_id: int) -> Optional[Menu]:
        """根据ID获取菜单"""
        return await Menu.filter(id=menu_id).first()

    @staticmethod
    async def create_menu(menu_data: MenuCreate) -> Menu:
        """创建菜单"""
        menu = await Menu.create(
            name=menu_data.name,
            path=menu_data.path,
            icon=menu_data.icon,
            component=menu_data.component,
            parent_id=menu_data.parent_id,
            sort=menu_data.sort,
            is_visible=not menu_data.is_hidden,
            menu_type=menu_data.menu_type,
            permission=menu_data.permission_code,
        )
        return menu

    @staticmethod
    async def update_menu(menu_id: int, menu_data: MenuUpdate) -> Optional[Menu]:
        """更新菜单"""
        menu = await Menu.filter(id=menu_id).first()
        if not menu:
            return None

        update_dict = {}
        if menu_data.name is not None:
            update_dict['name'] = menu_data.name
        if menu_data.path is not None:
            update_dict['path'] = menu_data.path
        if menu_data.icon is not None:
            update_dict['icon'] = menu_data.icon
        if menu_data.component is not None:
            update_dict['component'] = menu_data.component
        if menu_data.parent_id is not None:
            update_dict['parent_id'] = menu_data.parent_id
        else:
            update_dict['parent_id'] = None
        if menu_data.sort is not None:
            update_dict['sort'] = menu_data.sort
        if menu_data.is_hidden is not None:
            update_dict['is_visible'] = not menu_data.is_hidden
        if menu_data.is_active is not None:
            update_dict['is_active'] = menu_data.is_active
        if menu_data.menu_type is not None:
            update_dict['menu_type'] = menu_data.menu_type
        if menu_data.permission_code is not None:
            update_dict['permission'] = menu_data.permission_code

        if update_dict:
            await menu.update_from_dict(update_dict).save()
        return menu

    @staticmethod
    async def delete_menu(menu_id: int) -> bool:
        """删除菜单"""
        # 检查是否有子菜单
        has_children = await Menu.filter(parent_id=menu_id).exists()
        if has_children:
            return False

        deleted_count = await Menu.filter(id=menu_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_menu_by_name_and_path(name: str, path: str) -> Optional[Menu]:
        """根据名称和路径查找菜单"""
        return await Menu.filter(name=name, path=path).first()

    @staticmethod
    async def batch_create_menus(menu_data_list: List[MenuCreate]) -> List[Menu]:
        """批量创建菜单"""
        created_menus = []
        for menu_data in menu_data_list:
            menu = await MenuService.create_menu(menu_data)
            created_menus.append(menu)
        return created_menus

    @staticmethod
    async def batch_update_menus(menu_updates: List[dict]) -> List[Optional[Menu]]:
        """批量更新菜单
        menu_updates 格式: [{'name': str, 'path': str, 'data': MenuUpdate}, ...]
        """
        updated_menus = []
        for update in menu_updates:
            menu = await MenuService.get_menu_by_name_and_path(update['name'], update['path'])
            if menu:
                updated_menu = await MenuService.update_menu(menu.id, update['data'])
                updated_menus.append(updated_menu)
            else:
                updated_menus.append(None)
        return updated_menus

    @staticmethod
    async def get_all_menus() -> List[Menu]:
        """获取所有菜单"""
        return await Menu.filter(is_active=True).order_by('sort', 'id')

    @staticmethod
    async def build_menu_tree(menus: List[Menu] = None) -> List[dict]:
        """构建菜单树形结构"""
        if menus is None:
            menus = await MenuService.get_all_menus()

        # 转换为字典
        menu_list = []
        for menu in menus:
            menu_dict = await menu.to_dict()
            menu_dict['children'] = []
            menu_list.append(menu_dict)

        # 构建树形结构
        menu_map = {menu['id']: menu for menu in menu_list}
        tree = []

        for menu in menu_list:
            parent_id = menu.get('parent_id')
            if parent_id and parent_id in menu_map:
                menu_map[parent_id]['children'].append(menu)
            else:
                tree.append(menu)

        return tree

    @staticmethod
    async def get_user_menus(user_id: int, is_superuser: bool) -> List[dict]:
        """获取用户可访问的菜单树"""
        if is_superuser:
            # 超级管理员返回所有可见菜单
            menus = await Menu.filter(is_active=True, is_visible=True).order_by('sort', 'id')
            return await MenuService.build_menu_tree(menus)

        # 普通用户根据权限获取菜单
        from base.core.users.services.rbac_service import PermissionService

        # 获取用户权限列表
        user_permissions = await PermissionService.get_user_permissions_with_inheritance(user_id)

        # 获取所有活动且可见的菜单
        all_menus = await Menu.filter(is_active=True, is_visible=True).order_by('sort', 'id')

        # 过滤用户有权限访问的菜单
        accessible_menus = []
        accessible_menu_ids: Set[int] = set()

        for menu in all_menus:
            # 如果菜单没有设置权限，默认允许访问
            if not menu.permission:
                accessible_menus.append(menu)
                accessible_menu_ids.add(menu.id)
            # 如果用户有对应权限
            elif menu.permission in user_permissions:
                accessible_menus.append(menu)
                accessible_menu_ids.add(menu.id)

        # 确保父菜单也被包含（即使父菜单本身需要权限）
        parent_ids_to_add: Set[int] = set()
        for menu in accessible_menus:
            parent_id = menu.parent_id
            while parent_id:
                if parent_id not in accessible_menu_ids:
                    parent_ids_to_add.add(parent_id)
                # 获取父菜单的parent_id继续向上查找
                parent_menu = next((m for m in all_menus if m.id == parent_id), None)
                if parent_menu:
                    parent_id = parent_menu.parent_id
                else:
                    break

        # 添加需要的父菜单
        if parent_ids_to_add:
            for menu in all_menus:
                if menu.id in parent_ids_to_add and menu.id not in accessible_menu_ids:
                    accessible_menus.append(menu)
                    accessible_menu_ids.add(menu.id)

        # 按sort和id重新排序
        accessible_menus.sort(key=lambda m: (m.sort, m.id))

        return await MenuService.build_menu_tree(accessible_menus)
