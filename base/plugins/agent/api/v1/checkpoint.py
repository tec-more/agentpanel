# base/plugins/agent/api/checkpoint_api.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from base.plugins.agent.services.checkpoint_service import CheckpointService
from base.common.security import get_current_user_id

router = APIRouter(prefix="/checkpoints", tags=["检查点管理"])


@router.get("/user/{user_id}", response_model=List[Dict[str, Any]])
async def get_user_checkpoints(
    user_id: str,
    current_user_id=Depends(get_current_user_id)
):
    """获取用户的所有检查点"""
    service = CheckpointService.get_instance()
    return service.get_user_checkpoints(user_id)


@router.get("/user/{user_id}/session/{session_id}", response_model=List[Dict[str, Any]])
async def get_session_checkpoints(
    user_id: str,
    session_id: str,
    current_user_id=Depends(get_current_user_id)
):
    """获取用户特定会话的检查点"""
    service = CheckpointService.get_instance()
    return service.get_session_checkpoints(user_id, session_id)


@router.get("/user/{user_id}/checkpoint/{checkpoint_id}", response_model=Dict[str, Any])
async def get_checkpoint(
    user_id: str,
    checkpoint_id: str,
    current_user_id=Depends(get_current_user_id)
):
    """获取单个检查点详情"""
    service = CheckpointService.get_instance()
    checkpoint = service.get_checkpoint(user_id, checkpoint_id)
    
    if not checkpoint:
        raise HTTPException(status_code=404, detail="检查点不存在")
    
    return checkpoint


@router.delete("/user/{user_id}/checkpoint/{checkpoint_id}", response_model=Dict[str, bool])
async def delete_checkpoint(
    user_id: str,
    checkpoint_id: str,
    current_user_id=Depends(get_current_user_id)
):
    """删除检查点"""
    service = CheckpointService.get_instance()
    success = service.delete_checkpoint(user_id, checkpoint_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="删除失败")
    
    return {"success": success}


@router.delete("/user/{user_id}/session/{session_id}", response_model=Dict[str, bool])
async def delete_session_checkpoints(
    user_id: str,
    session_id: str,
    current_user_id=Depends(get_current_user_id)
):
    """删除会话的所有检查点"""
    service = CheckpointService.get_instance()
    success = service.delete_session_checkpoints(user_id, session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="删除失败")
    
    return {"success": success}


@router.delete("/user/{user_id}", response_model=Dict[str, bool])
async def delete_user_checkpoints(
    user_id: str,
    current_user_id=Depends(get_current_user_id)
):
    """删除用户的所有检查点"""
    service = CheckpointService.get_instance()
    success = service.delete_user_checkpoints(user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="删除失败")
    
    return {"success": success}