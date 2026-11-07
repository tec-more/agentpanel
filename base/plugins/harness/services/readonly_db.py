"""L3 编排只读数据库连接

- 目的：L3 直读 L2 配置表（客户端凭据、身份、策略、价格、套餐绑定），代码层只暴露读方法；
- 强制：连接级 `default_transaction_read_only=on`，任何写/DDL 都会被 PostgreSQL 拒绝；
- 生产建议：config.conf 配置独立只读账号 `db.readonly_user` / `db.readonly_password`，
  未配置时复用主库账号，但仍受会话级只读约束；
- 自检：`verify_readonly()` 真实执行一次建表探针，确认“写会被拒”。
"""
import asyncio
from typing import Any, Dict, List, Optional

import asyncpg

from base.common.config import config
from base.common.setting import settings


def _readonly_credentials() -> Dict[str, Any]:
    user = config.get("db", "readonly_user", fallback="").strip()
    password = config.get("db", "readonly_password", fallback="") if user else ""
    if user:
        return {"user": user, "password": password}
    return {"user": settings.db_user, "password": settings.db_password}


class ReadonlyDatabase:
    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._pool is not None:
            return
        async with self._lock:
            if self._pool is not None:
                return
            creds = _readonly_credentials()
            self._pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=creds["user"],
                password=creds["password"],
                min_size=1,
                max_size=5,
                timeout=5,
                command_timeout=10,
                server_settings={
                    "default_transaction_read_only": "on",
                    "application_name": "harness-orchestration-readonly",
                },
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def fetchrow(self, sql: str, *args: Any) -> Optional[asyncpg.Record]:
        await self.connect()
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, *args)

    async def fetch(self, sql: str, *args: Any) -> List[asyncpg.Record]:
        await self.connect()
        async with self._pool.acquire() as conn:
            return await conn.fetch(sql, *args)

    async def verify_readonly(self) -> Dict[str, Any]:
        """真实探针：SELECT 1 + 会话只读标志 + 建表写探针必须被拒绝。"""
        checks: Dict[str, Any] = {}
        try:
            await self.connect()
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("SELECT 1 AS ok")
                checks["select"] = {"status": "healthy", "value": row["ok"] if row else None}

                flag = await conn.fetchval("SHOW transaction_read_only")
                checks["transaction_read_only"] = flag

                probe = "p11_readonly_probe"
                created = False
                try:
                    await conn.execute(f"CREATE TEMP TABLE {probe} (id INT)")
                    created = True
                except asyncpg.PostgresError as exc:
                    message = str(exc)
                    rejected = "read-only" in message.lower() or "read only" in message.lower()
                    checks["write_probe"] = {
                        "status": "healthy" if rejected else "unhealthy",
                        "message": message,
                    }
                finally:
                    if created:
                        try:
                            await conn.execute(f"DROP TABLE {probe}")
                        except asyncpg.PostgresError:
                            pass
                        checks["write_probe"] = {
                            "status": "unhealthy",
                            "message": "只读连接允许建表（只读约束未生效）",
                        }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "message": f"只读连接自检失败: {type(exc).__name__}: {exc}",
                "checks": checks,
            }

        healthy = (
            checks.get("select", {}).get("status") == "healthy"
            and str(checks.get("transaction_read_only") or "").lower() == "on"
            and checks.get("write_probe", {}).get("status") == "healthy"
        )
        return {
            "status": "healthy" if healthy else "unhealthy",
            "message": "只读连接可用且写操作被拒绝" if healthy else "只读约束未完全生效",
            "checks": checks,
        }

    async def credential_table_ready(self) -> Dict[str, Any]:
        """service_credential 表必须由 L2 启动流程创建；缺失时 fail-closed。"""
        try:
            await self.fetchrow("SELECT 1 AS ok FROM service_credential LIMIT 1")
            return {"status": "healthy", "message": "service_credential 可读"}
        except Exception as exc:
            return {
                "status": "unhealthy",
                "message": f"service_credential 不可读（请先启动 L2 完成建表）: {type(exc).__name__}: {exc}",
            }


_readonly_db: Optional[ReadonlyDatabase] = None


def get_readonly_db() -> ReadonlyDatabase:
    global _readonly_db
    if _readonly_db is None:
        _readonly_db = ReadonlyDatabase()
    return _readonly_db


async def close_readonly_db() -> None:
    global _readonly_db
    if _readonly_db is not None:
        await _readonly_db.close()
        _readonly_db = None
