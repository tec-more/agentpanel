from fastapi import APIRouter

from .lead import lead_router
from .opportunity import opportunity_router
from .activity import activity_router
from .contact import contact_router
from .task import task_router
from .stats import stats_router
from .config import config_router

router = APIRouter()

router.include_router(lead_router)
router.include_router(opportunity_router)
router.include_router(activity_router)
router.include_router(contact_router)
router.include_router(task_router)
router.include_router(stats_router)
router.include_router(config_router)