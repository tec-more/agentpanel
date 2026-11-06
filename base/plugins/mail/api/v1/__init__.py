from fastapi import APIRouter

from .message_router import message_router
from .subtype_router import subtype_router
from .follower_router import follower_router
from .notification_router import notification_router
from .mapping_router import mapping_router

router = APIRouter()

router.include_router(message_router)
router.include_router(subtype_router)
router.include_router(follower_router)
router.include_router(notification_router)
router.include_router(mapping_router)
