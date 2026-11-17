"""ContentOps 插件路由聚合。

按项目约定：所有路由只由 manifest.routes 指向本目录装配，禁止入口自挂。
本文件集中 include 全部业务子路由，装配器按约定加载后套 route_prefix
并注入插件启用态依赖（plugin_route_guard）。
"""
from fastapi import APIRouter

from base.plugins.contentops.api.v1 import compliance, content, export, ledger, review, rules

router = APIRouter()
router.include_router(content.content_router)
router.include_router(compliance.compliance_router)
router.include_router(review.review_router)
router.include_router(export.export_router)
router.include_router(ledger.ledger_router)
router.include_router(rules.rules_router)
