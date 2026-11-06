from fastapi import APIRouter

from .flow_router import flow_router
from .instance_router import instance_router
from .task_router import task_router

router = APIRouter()

router.include_router(flow_router)
router.include_router(instance_router)
router.include_router(task_router)
