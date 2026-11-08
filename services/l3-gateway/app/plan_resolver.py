"""网关侧套餐解析器：只读 SQL 版（P3 D-P3-2=B）。

与 L2 ORM 版 `base/common/quota/services/plan_resolver.py` 必须逐字段对拍
（`services/l3-gateway/tests/plan_parity.py`，覆盖 P1–P14）。

语义冻结：
- cus：customer_membership(is_active) LEFT JOIN customer_membership_level，取 level_type
  - 无记录 / expire_time 已过（naive 视为 UTC）/ 等级缺失 → "regular"；异常 → None
- usr：user_role → role，取 is_active 角色 code；异常 → []
"""
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from tortoise import connections


class SqlPlanResolver:
    async def customer_level_type(self, customer_id: int) -> Optional[str]:
        try:
            conn = connections.get("postgres")
            rows = await conn.execute_query_dict(
                """
                SELECT cm.id AS membership_id, cm.expire_time, ml.level_type
                FROM customer_membership cm
                LEFT JOIN customer_membership_level ml ON ml.id = cm.membership_level_id
                WHERE cm.customer_id = $1 AND cm.is_active = TRUE
                ORDER BY cm.id
                LIMIT 1
                """,
                [customer_id],
            )
            if not rows:
                return "regular"
            row = rows[0]
            expire_time = row.get("expire_time")
            if expire_time is not None:
                if expire_time.tzinfo is None:
                    expire_time = expire_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expire_time:
                    return "regular"
            level_type = row.get("level_type")
            if level_type:
                return getattr(level_type, "value", level_type)
            return "regular"
        except Exception as e:
            logger.warning(f"[quota] 解析客户会员等级失败 customer_id={customer_id}: {e}")
            return None

    async def user_role_codes(self, user_id: int) -> List[str]:
        try:
            conn = connections.get("postgres")
            rows = await conn.execute_query_dict(
                """
                SELECT r.code AS code
                FROM user_role ur
                JOIN role r ON r.id = ur.role_id
                WHERE ur.user_id = $1 AND r.is_active = TRUE
                ORDER BY r.id
                """,
                [user_id],
            )
            return [r["code"] for r in rows]
        except Exception as e:
            logger.warning(f"[quota] 解析用户角色失败 user_id={user_id}: {e}")
            return []
