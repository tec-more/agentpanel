"""
Skill Category service
"""
from typing import List, Optional
from tortoise.exceptions import DoesNotExist, IntegrityError
from base.plugins.agent.models.skill_category import SkillCategory
from base.plugins.agent.models.skill import Skill
from base.plugins.agent.schemas.skill_category import SkillCategoryCreate, SkillCategoryUpdate
class SkillCategoryService:
    model = "skill_category"
    """Skill Category service class"""

    @staticmethod
    async def create_category(category_data: SkillCategoryCreate) -> Optional[SkillCategory]:
        """Create skill category"""
        try:
            # 先检查是否已存在同名分类
            existing = await SkillCategory.filter(name=category_data.name).first()
            if existing:
                print(f"分类名称已存在: {category_data.name}")
                return None
            
            category = await SkillCategory.create(
                name=category_data.name,
                description=category_data.description,
                parent_id=category_data.parent_id,
                sort_order=category_data.sort_order,
                status=category_data.status
            )
            return category
        except IntegrityError as e:
            print(f"数据库完整性错误: {e}")
            return None

    @staticmethod
    async def get_categories(skip: int = 0, limit: int = 100, name: str = "", status: str = "") -> List[SkillCategory]:
        """Get skill category list"""
        query = SkillCategory.all()
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        categories = await query.order_by("sort_order", "id").offset(skip).limit(limit)
        return categories

    @staticmethod
    async def get_category_by_id(category_id: int) -> Optional[SkillCategory]:
        """Get skill category by ID"""
        try:
            category = await SkillCategory.get(id=category_id)
            return category
        except DoesNotExist:
            return None

    @staticmethod
    async def update_category(category_id: int, category_data: SkillCategoryUpdate) -> Optional[SkillCategory]:
        """Update skill category"""
        category = await SkillCategoryService.get_category_by_id(category_id)
        if not category:
            return None

        update_data = category_data.model_dump(exclude_unset=True)
        await category.update_from_dict(update_data)
        await category.save()
        return category

    @staticmethod
    async def delete_category(category_id: int) -> bool:
        """Delete skill category"""
        category = await SkillCategoryService.get_category_by_id(category_id)
        if not category:
            return False

        await category.delete()
        return True

    @staticmethod
    async def get_active_categories() -> List[SkillCategory]:
        """Get active skill categories"""
        categories = await SkillCategory.filter(status="active").order_by("sort_order", "id").all()
        return categories

    @staticmethod
    async def get_category_tree(parent_id: Optional[int] = None) -> List[dict]:
        """Get category tree structure"""
        categories = await SkillCategory.filter(parent_id=parent_id, status="active").order_by("sort_order", "id").all()
        
        tree = []
        for category in categories:
            skill_count = await Skill.filter(category_id=category.id, status="active").count()
            children = await SkillCategoryService.get_category_tree(category.id)
            
            tree.append({
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "sort_order": category.sort_order,
                "status": category.status,
                "skill_count": skill_count,
                "children": children
            })
        
        return tree

    @staticmethod
    async def get_category_with_details(category_id: int) -> Optional[dict]:
        """Get category with details including parent name and skill count"""
        category = await SkillCategoryService.get_category_by_id(category_id)
        if not category:
            return None
        
        skill_count = await Skill.filter(category_id=category_id, status="active").count()
        parent_name = None
        
        if category.parent_id:
            parent = await SkillCategoryService.get_category_by_id(category.parent_id)
            if parent:
                parent_name = parent.name
        
        return {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "parent_id": category.parent_id,
            "parent_name": parent_name,
            "sort_order": category.sort_order,
            "status": category.status,
            "skill_count": skill_count,
            "created_at": category.created_at,
            "updated_at": category.updated_at
        }

    @staticmethod
    async def get_all_categories_with_details() -> List[dict]:
        """Get all categories with details"""
        categories = await SkillCategory.all().order_by("sort_order", "id")
        result = []
        
        for category in categories:
            detail = await SkillCategoryService.get_category_with_details(category.id)
            if detail:
                result.append(detail)
        
        return result

    @staticmethod
    async def get_skills_by_category(category_id: int) -> List[Skill]:
        """Get skills by category"""
        skills = await Skill.filter(category_id=category_id, status="active").all()
        return skills
