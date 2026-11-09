"""管理员目录（只读 SQL）。

审批人解析只取 `user` 表四列：id / username / is_superuser / is_active。
不注册 ORM 模型，避免 L3 进程依赖 L2 用户域模型（Spec §4.2 白名单）。
"""
from dataclasses import dataclass
from typing import Any, Optional

_DB_ALIAS = "postgres"


@dataclass(frozen=True)
class UserRef:
    id: int
    username: str
    is_superuser: bool


async def _fetch_one(sql: str, params: list) -> Optional[UserRef]:
    from tortoise import Tortoise

    rows = await Tortoise.get_connection(_DB_ALIAS).execute_query_dict(sql, params)
    if not rows:
        return None
    row = rows[0]
    return UserRef(
        id=int(row["id"]),
        username=str(row["username"]),
        is_superuser=bool(row["is_superuser"]),
    )


async def resolve_user(identifier: Any) -> Optional[UserRef]:
    """按用户 ID 或用户名解析激活用户（与原 `User.get_or_none` 语义一致）。"""
    if identifier is None:
        return None
    text = str(identifier).strip()
    if not text:
        return None
    try:
        user_id = int(text)
    except (TypeError, ValueError):
        return await _fetch_one(
            'SELECT id, username, is_superuser FROM "user" '
            "WHERE username = $1 AND is_active = true LIMIT 1",
            [text],
        )
    return await _fetch_one(
        'SELECT id, username, is_superuser FROM "user" '
        "WHERE id = $1 AND is_active = true LIMIT 1",
        [user_id],
    )


async def first_admin() -> Optional[UserRef]:
    """首个激活超级管理员（审批兜底审批人）。"""
    return await _fetch_one(
        'SELECT id, username, is_superuser FROM "user" '
        "WHERE is_superuser = true AND is_active = true ORDER BY id LIMIT 1",
        [],
    )
