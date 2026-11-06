"""
部门管理API
"""
from fastapi import APIRouter, Depends, status, Query
from typing import Optional

from base.core.dept.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentTree,
    OrgType,
)
from base.core.dept.services.department_service import DepartmentService
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

router = APIRouter(prefix="/v1/departments", tags=["部门管理"])


@router.get("/list", summary="获取部门列表(分页)")
async def get_department_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量"),
        name: Optional[str] = Query(None, description="部门名称(模糊搜索)"),
        is_active: Optional[bool] = Query(None, description="是否激活"),
        type: Optional[OrgType] = Query(None, description="组织类型"),
        current_user_id: int = Depends(get_current_user_id)
):
    """获取部门列表(分页)"""
    departments, total = await DepartmentService.get_department_list(
        page=page,
        page_size=page_size,
        name=name,
        is_active=is_active,
        type=type,
    )

    dept_list = []
    for dept in departments:
        dept_dict = await dept.to_dict()
        dept_list.append(dept_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": dept_list
    }

    return SuccessResponse(data=response_data)


@router.get("/companies", summary="获取公司列表")
async def get_company_list(
        current_user_id: int = Depends(get_current_user_id)
):
    """获取所有公司列表(level=1, type=company)"""
    companies = await DepartmentService.get_companies()
    company_list = [await company.to_dict() for company in companies]
    return SuccessResponse(data=company_list)


@router.get("/tree", summary="获取部门树形结构")
async def get_department_tree(current_user_id: int = Depends(get_current_user_id)):
    """获取部门树形结构"""
    tree = await DepartmentService.build_department_tree()
    return SuccessResponse(data=tree)


@router.get("/{dept_id}", summary="获取部门详情")
async def get_department_detail(
        dept_id: int,
        current_user_id: int = Depends(get_current_user_id)
):
    """获取部门详情"""
    dept = await DepartmentService.get_by_id(dept_id)
    if not dept:
        return ErrorResponse(msg="部门不存在", status_code=status.HTTP_404_NOT_FOUND)

    dept_dict = await dept.to_dict()
    return SuccessResponse(data=dept_dict)


@router.post("", summary="创建部门")
async def create_department(
        dept_data: DepartmentCreate,
        current_user_id: int = Depends(get_current_user_id)
):
    """创建部门(管理员功能)"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    # 检查部门编码是否存在
    if await DepartmentService.check_code_exists(dept_data.code):
        return ErrorResponse(msg="部门编码已存在", status_code=status.HTTP_400_BAD_REQUEST)

    # 检查部门名称是否存在
    if await DepartmentService.check_name_exists(dept_data.name):
        return ErrorResponse(msg="部门名称已存在", status_code=status.HTTP_400_BAD_REQUEST)

    # 创建部门
    dept = await DepartmentService.create_department(dept_data)
    dept_dict = await dept.to_dict()

    return SuccessResponse(data=dept_dict, msg="创建成功")


@router.put("/{dept_id}", summary="更新部门")
async def update_department(
        dept_id: int,
        dept_data: DepartmentUpdate,
        current_user_id: int = Depends(get_current_user_id)
):
    """更新部门(管理员功能)"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    # 检查部门名称是否被其他部门使用
    if dept_data.name:
        if await DepartmentService.check_name_exists(dept_data.name, exclude_id=dept_id):
            return ErrorResponse(msg="部门名称已被其他部门使用", status_code=status.HTTP_400_BAD_REQUEST)

    dept = await DepartmentService.update_department(dept_id, dept_data)
    if not dept:
        return ErrorResponse(msg="部门不存在", status_code=status.HTTP_404_NOT_FOUND)

    dept_dict = await dept.to_dict()
    return SuccessResponse(data=dept_dict, msg="更新成功")


@router.delete("/{dept_id}", summary="删除部门")
async def delete_department(
        dept_id: int,
        current_user_id: int = Depends(get_current_user_id)
):
    """删除部门(管理员功能)"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    success = await DepartmentService.delete_department(dept_id)
    if not success:
        return ErrorResponse(
            msg="部门不存在或存在子部门,无法删除",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    return SuccessResponse(msg="删除成功")
