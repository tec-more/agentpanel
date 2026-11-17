"""客户自助读取 API（M5 客户门户）：/me/*（全部强制 CUS 主体）。

安全基线（对照 ContentOps-多租户Customer权限验证设计PRD C1 缺陷）：
- 依赖 require_customer：USR token 一律 403，杜绝后台账号访问客户自助接口；
- owner_id 一律取 JWT sub，所有查询强制按 owner.owner_id 过滤，
  **不接受任何客户端传入的 customer_id/owner_id**（纵深防御，不靠守卫单点）；
- 只复用现有 service/model 的只读方法，不触碰写端点。

挂载：customer 插件 route_prefix=/v1/customer；文件名以 _router 结尾，
由 plugin_manager 优先注册，避免被 customer.py 的 /{customer_id} 参数化路由吞掉。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from base.common.authz.context import OwnerContext
from base.common.response import success_response
from base.plugins.customer.services.cus_guard import require_customer

self_service_router = APIRouter(prefix="/me", tags=["客户自助-我的"])


def _dt(value):
    return value.isoformat() if value is not None else None


@self_service_router.get("/profile", summary="我的资料")
async def my_profile(owner: OwnerContext = Depends(require_customer)):
    """当前客户资料（脱敏：不返回 password/openid/unionid 等内部字段）。"""
    from base.plugins.customer.models.customer import Customer

    customer = await Customer.get_or_none(id=owner.owner_id)
    if not customer:
        from base.common.response import fail_response
        return fail_response(msg="客户资料不存在")
    return success_response(data={
        "id": customer.id,
        "username": customer.username,
        "nickname": customer.nickname,
        "email": customer.email,
        "phone": customer.phone,
        "avatar": customer.avatar,
        "is_active": customer.is_active,
        "is_verified": customer.is_verified,
        "last_login": _dt(customer.last_login),
        "login_count": customer.login_count,
        "created_at": _dt(customer.created_at),
    })


@self_service_router.get("/membership", summary="我的会员信息")
async def my_membership(owner: OwnerContext = Depends(require_customer)):
    from base.plugins.customer.services.purchase_service import PurchaseService

    info = await PurchaseService.get_customer_membership_info(owner.owner_id)
    return success_response(data=info)


@self_service_router.get("/orders", summary="我的订单")
async def my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    owner: OwnerContext = Depends(require_customer),
):
    from base.plugins.sales.services.order_service import OrderService

    orders = await OrderService.get_orders_by_customer(owner.owner_id, page, page_size)
    items = [await o.to_dict() for o in orders]
    return success_response(data={
        "page": page, "page_size": page_size, "items": items,
    })


@self_service_router.get("/payments", summary="我的支付记录")
async def my_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    owner: OwnerContext = Depends(require_customer),
):
    """通过订单归属过滤支付流水（order__customer_id），与客户 ID 强绑定。"""
    from base.plugins.customer.models.payment_transaction import PaymentTransaction

    query = PaymentTransaction.filter(order__customer_id=owner.owner_id)
    total = await query.count()
    rows = (
        await query.prefetch_related("order")
        .order_by("-processed_at")
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": r.id,
            "transaction_id": r.transaction_id,
            "transaction_type": r.transaction_type,
            "amount": float(r.amount or 0),
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "order_no": r.order.order_no if r.order else None,
            "processed_at": _dt(r.processed_at),
            "created_at": _dt(r.created_at),
        }
        for r in rows
    ]
    return success_response(data={
        "total": total, "page": page, "page_size": page_size, "items": items,
    })


@self_service_router.get("/organizations", summary="我的组织")
async def my_organizations(owner: OwnerContext = Depends(require_customer)):
    from base.plugins.customer.services.organization_service import CustomerOrganizationService

    items = await CustomerOrganizationService.list_my_organizations(owner.owner_id)
    return success_response(data={"items": items})
