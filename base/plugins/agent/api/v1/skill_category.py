"""
Skill Category API routes
"""
from typing import List
from fastapi import APIRouter, HTTPException, Request
from base.plugins.agent.schemas.skill_category import (
    SkillCategoryCreate, 
    SkillCategoryUpdate, 
    SkillCategoryResponse,
    SkillCategoryTreeResponse
)
from base.plugins.agent.services.skill_category_service import SkillCategoryService
from base.common.response import success_response, fail_response

skill_category_router = APIRouter(prefix="/skill-categories", tags=["skill-categories"])


@skill_category_router.post("/")
async def create_category(category: SkillCategoryCreate, request: Request):
    """Create a new skill category"""
    try:
        print(f"=== 创建技能分类 ===")
        print(f"接收到的数据: {category.model_dump()}")
        
        created_category = await SkillCategoryService.create_category(category)
        if not created_category:
            return fail_response(msg="创建失败，可能存在重复名称", code=400)
        
        detail = await SkillCategoryService.get_category_with_details(created_category.id)
        return success_response(data=detail, msg="分类创建成功")
    except Exception as e:
        print(f"创建分类时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return fail_response(msg=str(e))


@skill_category_router.get("/")
async def get_categories(skip: int = 0, limit: int = 100, name: str = "", status: str = ""):
    """Get all skill categories"""
    categories = await SkillCategoryService.get_all_categories_with_details()
    
    if name:
        categories = [c for c in categories if name.lower() in c["name"].lower()]
    if status:
        categories = [c for c in categories if c["status"] == status]
    
    total = len(categories)
    paged_categories = categories[skip : skip + limit]
    
    return success_response(data={"items": paged_categories, "total": total})


@skill_category_router.get("/{category_id}")
async def get_category(category_id: int):
    """Get skill category by ID"""
    detail = await SkillCategoryService.get_category_with_details(category_id)
    if not detail:
        return fail_response(msg="分类不存在", code=404)
    return success_response(data=detail)


@skill_category_router.put("/{category_id}")
async def update_category(category_id: int, category: SkillCategoryUpdate):
    """Update skill category"""
    updated_category = await SkillCategoryService.update_category(category_id, category)
    if not updated_category:
        return fail_response(msg="分类不存在", code=404)
    
    detail = await SkillCategoryService.get_category_with_details(category_id)
    return success_response(data=detail, msg="分类更新成功")


@skill_category_router.delete("/{category_id}")
async def delete_category(category_id: int):
    """Delete skill category"""
    success = await SkillCategoryService.delete_category(category_id)
    if not success:
        return fail_response(msg="分类不存在", code=404)
    return success_response(msg="分类删除成功")


@skill_category_router.get("/tree/list")
async def get_category_tree():
    """Get category tree structure"""
    tree = await SkillCategoryService.get_category_tree()
    return success_response(data=tree)


@skill_category_router.get("/active/list")
async def get_active_categories():
    """Get active skill categories"""
    categories = await SkillCategoryService.get_active_categories()
    
    result = []
    for category in categories:
        detail = await SkillCategoryService.get_category_with_details(category.id)
        if detail:
            result.append(detail)
    
    return success_response(data=result)


@skill_category_router.get("/{category_id}/skills")
async def get_skills_by_category(category_id: int):
    """Get skills by category"""
    skills = await SkillCategoryService.get_skills_by_category(category_id)
    
    from base.plugins.agent.schemas.skill import SkillResponse
    
    response = []
    for skill in skills:
        agent_count = await skill.agents.count()
        response.append(SkillResponse(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            type=skill.type,
            implementation=skill.implementation,
            status=skill.status,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
            agent_count=agent_count,
            source="database"
        ).model_dump())
    
    return success_response(data=response)
