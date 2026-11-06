from fastapi import APIRouter

from .supplier_router import supplier_router
from .purchase_router import purchase_router

purchase_api_router = APIRouter(prefix="/purchase")

purchase_api_router.include_router(supplier_router)
purchase_api_router.include_router(purchase_router)