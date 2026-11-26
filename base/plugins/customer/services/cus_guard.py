"""客户自助端专用鉴权守卫（M5）——已下沉到底座的兼容再导出。

原实现位于本文件，2026-11-26 下沉到 ``base.common.authz.require_customer``，
使 harness 等非 customer 插件无需静态 import 本插件即可使用 CUS 守卫。
保留本模块是为了兼容既有 import 路径与测试 patch 目标
（``base.plugins.customer.services.cus_guard.require_customer``）。
"""
from base.common.authz import require_customer

__all__ = ["require_customer"]
