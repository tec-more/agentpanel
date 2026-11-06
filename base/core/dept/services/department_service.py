"""
部门服务层
"""
from typing import Optional, List, Tuple
from base.core.dept.models.department import Department, OrgType
from base.core.dept.schemas.department import DepartmentCreate, DepartmentUpdate


class DepartmentService:
    """部门服务类"""

    @staticmethod
    async def get_by_id(dept_id: int) -> Optional[Department]:
        """根据ID获取部门"""
        return await Department.filter(id=dept_id).first()

    @staticmethod
    async def get_by_code(code: str) -> Optional[Department]:
        """根据编码获取部门"""
        return await Department.filter(code=code).first()

    @staticmethod
    async def _calculate_level(parent_id: Optional[int]) -> int:
        """计算层级深度"""
        if not parent_id:
            return 1
        parent_dept = await Department.filter(id=parent_id).first()
        if not parent_dept:
            return 1
        return parent_dept.level + 1

    @staticmethod
    async def _update_subtree_levels(dept_id: int, new_base_level: int):
        """更新子部门的层级"""
        async def update_children(parent_id: int, current_level: int):
            children = await Department.filter(parent_id=parent_id).all()
            for child in children:
                child.level = current_level
                await child.save()
                await update_children(child.id, current_level + 1)

        await update_children(dept_id, new_base_level + 1)

    @staticmethod
    async def create_department(dept_data: DepartmentCreate) -> Department:
        """创建部门"""
        level = await DepartmentService._calculate_level(dept_data.parent_id)

        dept = await Department.create(
            name=dept_data.name,
            code=dept_data.code,
            parent_id=dept_data.parent_id,
            type=dept_data.type,
            level=level,
            leader_id=dept_data.leader_id,
            phone=dept_data.phone,
            email=dept_data.email,
            description=dept_data.description,
            sort=dept_data.sort,
        )
        return dept

    @staticmethod
    async def update_department(dept_id: int, dept_data: DepartmentUpdate) -> Optional[Department]:
        """更新部门"""
        dept = await Department.filter(id=dept_id).first()
        if not dept:
            return None

        update_data = dept_data.model_dump(exclude_unset=True)
        old_parent_id = dept.parent_id
        old_level = dept.level

        await dept.update_from_dict(update_data).save()

        new_parent_id = dept.parent_id
        if new_parent_id != old_parent_id:
            new_level = await DepartmentService._calculate_level(new_parent_id)
            dept.level = new_level
            await dept.save()

            if old_level != new_level:
                await DepartmentService._update_subtree_levels(dept_id, new_level)

        return dept

    @staticmethod
    async def delete_department(dept_id: int) -> bool:
        """删除部门"""
        # 检查是否有子部门
        has_children = await Department.filter(parent_id=dept_id).exists()
        if has_children:
            return False

        deleted_count = await Department.filter(id=dept_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_department_list(
            page: int = 1,
            page_size: int = 10,
            name: Optional[str] = None,
            is_active: Optional[bool] = None,
            type: Optional[OrgType] = None,
    ) -> Tuple[List[Department], int]:
        """获取部门列表(分页)"""
        query = Department.all()

        if name:
            query = query.filter(name__icontains=name)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        if type:
            query = query.filter(type=type)

        total = await query.count()

        offset = (page - 1) * page_size
        departments = await query.offset(offset).limit(page_size).order_by('sort', 'id')

        return departments, total

    @staticmethod
    async def get_all_departments() -> List[Department]:
        """获取所有部门"""
        return await Department.filter(is_active=True).order_by('sort', 'id')

    @staticmethod
    async def get_companies() -> List[Department]:
        """获取所有公司"""
        return await Department.filter(type=OrgType.COMPANY, is_active=True).order_by('sort', 'id')

    @staticmethod
    async def build_department_tree(departments: List[Department] = None) -> List[dict]:
        """构建部门树形结构"""
        if departments is None:
            departments = await DepartmentService.get_all_departments()

        # 转换为字典
        dept_list = []
        for dept in departments:
            dept_dict = await dept.to_dict()
            dept_dict['children'] = []
            dept_list.append(dept_dict)

        # 构建树形结构
        dept_map = {dept['id']: dept for dept in dept_list}
        tree = []

        for dept in dept_list:
            parent_id = dept.get('parent_id')
            if parent_id and parent_id in dept_map:
                dept_map[parent_id]['children'].append(dept)
            else:
                tree.append(dept)

        return tree

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查部门编码是否存在"""
        query = Department.filter(code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def check_name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
        """检查部门名称是否存在"""
        query = Department.filter(name=name)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()
