"""客户自助端专用鉴权守卫（M5）。

用途：客户门户所有 /me/* 端点的统一入口。它在 require_owner 的基础上
**强制主体类型为 cus**，从根上杜绝后台员工（USR）用管理 token 读取客户自助接口，
也杜绝客户用 cus token 触碰 USR 齿轮接口（customer.py/membership.py 等旧端点）。

设计要点：
- owner_id 一律取 JWT sub（OwnerContext.owner_id），永不接收客户端传入的 id；
- 每条查询仍按 owner_id 过滤（纵深防御，不依赖守卫单点）；
- 只依赖 base.common.authz（底座），不 import 任何插件，符合装配约束。
"""
from fastapi import Depends, HTTPException, status

from base.common.authz.context import OwnerContext, require_owner


async def require_customer(owner: OwnerContext = Depends(require_owner)) -> OwnerContext:
    """要求 CUS 主体；USR token 一律 403。"""
    if not owner.is_customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该接口仅面向客户主体（cus），后台账号无权访问",
        )
    return owner
