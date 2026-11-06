"""
Skill API routes
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from base.plugins.agent.schemas.skill import SkillCreate, SkillUpdate, SkillResponse, SkillContentResponse
from base.plugins.agent.services.skill_service import SkillService
from base.common.response import success_response, fail_response

skill_router = APIRouter(prefix="/skills", tags=["skills"])


@skill_router.post("/")
async def create_skill(skill: SkillCreate):
    """Create a new skill"""
    try:
        created_skill = await SkillService.create_skill(skill)
        detail = await SkillService.get_skill_with_category(created_skill.id)
        return success_response(data=detail, msg="技能创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@skill_router.get("/")
async def get_skills(skip: int = 0, limit: int = 100, name: str = "", status: str = "", category_id: int = None):
    """Get all skills"""
    skills = await SkillService.get_all_skills_with_category()
    
    if name:
        skills = [s for s in skills if name.lower() in s["name"].lower()]
    if status:
        skills = [s for s in skills if s["status"] == status]
    if category_id:
        skills = [s for s in skills if s["category_id"] == category_id]
    
    total = len(skills)
    paged_skills = skills[skip : skip + limit]
    
    return success_response(data={"items": paged_skills, "total": total})


@skill_router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """Get skill by ID"""
    if skill_id is None or skill_id in ("null", "undefined", ""):
        return fail_response(msg="无效的技能ID", code=422)
    
    try:
        skill_id_int = int(skill_id)
    except (ValueError, TypeError):
        return fail_response(msg="无效的技能ID格式", code=422)
    
    if skill_id_int <= 0:
        return fail_response(msg="无效的技能ID", code=422)
    
    detail = await SkillService.get_skill_with_category(skill_id_int)
    if not detail:
        return fail_response(msg="技能不存在", code=404)
    
    return success_response(data=detail)


@skill_router.get("/{skill_id}/content")
async def get_skill_content(skill_id: str):
    """Get skill content (Markdown)"""
    if skill_id is None or skill_id in ("null", "undefined", ""):
        return fail_response(msg="无效的技能ID", code=422)
    
    try:
        skill_id_int = int(skill_id)
    except (ValueError, TypeError):
        return fail_response(msg="无效的技能ID格式", code=422)
    
    if skill_id_int <= 0:
        return fail_response(msg="无效的技能ID", code=422)
    
    content = await SkillService.get_skill_content(skill_id_int)
    if not content:
        return fail_response(msg="技能不存在", code=404)
    
    data = SkillContentResponse(
        id=content["id"],
        name=content["name"],
        content=content["content"]
    )
    return success_response(data=data.model_dump())


@skill_router.put("/{skill_id}")
async def update_skill(skill_id: str, skill: SkillUpdate):
    """Update skill"""
    if skill_id in ("null", "undefined", ""):
        return fail_response(msg="无效的技能ID", code=422)
    try:
        skill_id_int = int(skill_id)
    except (ValueError, TypeError):
        return fail_response(msg="无效的技能ID格式", code=422)
    
    updated_skill = await SkillService.update_skill(skill_id_int, skill)
    if not updated_skill:
        return fail_response(msg="技能不存在", code=404)
    
    detail = await SkillService.get_skill_with_category(skill_id_int)
    return success_response(data=detail, msg="技能更新成功")


@skill_router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """Delete skill"""
    if skill_id in ("null", "undefined", ""):
        return fail_response(msg="无效的技能ID", code=422)
    try:
        skill_id_int = int(skill_id)
    except (ValueError, TypeError):
        return fail_response(msg="无效的技能ID格式", code=422)
    
    success = await SkillService.delete_skill(skill_id_int)
    if not success:
        return fail_response(msg="技能不存在", code=404)
    return success_response(msg="技能删除成功")


@skill_router.get("/category/{category_id}")
async def get_skills_by_category(category_id: int):
    """Get skills by category"""
    skills = await SkillService.get_all_skills_with_category()
    filtered = [s for s in skills if s["category_id"] == category_id]
    return success_response(data=filtered)


@skill_router.get("/active/list")
async def get_active_skills():
    """Get active skills"""
    skills = await SkillService.get_all_skills_with_category()
    filtered = [s for s in skills if s["status"] == "active"]
    return success_response(data=filtered)


@skill_router.post("/{skill_id}/execute")
async def execute_skill(skill_id: str, parameters: dict):
    """Execute skill"""
    if skill_id in ("null", "undefined", ""):
        return fail_response(msg="无效的技能ID", code=422)
    try:
        skill_id_int = int(skill_id)
    except (ValueError, TypeError):
        return fail_response(msg="无效的技能ID格式", code=422)
    
    result = await SkillService.execute_skill(skill_id_int, parameters)
    return success_response(data=result, msg="技能执行成功")


@skill_router.get("/{skill_id}/usage")
async def get_skill_usage(skill_id: str):
    """Get skill usage information"""
    if skill_id in ("null", "undefined", ""):
        return fail_response(msg="无效的技能ID", code=422)
    try:
        skill_id_int = int(skill_id)
    except (ValueError, TypeError):
        return fail_response(msg="无效的技能ID格式", code=422)
    
    usage = await SkillService.get_skill_usage(skill_id_int)
    if "error" in usage:
        return fail_response(msg=usage["error"], code=404)
    return success_response(data=usage)
