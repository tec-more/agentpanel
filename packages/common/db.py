"""数据库连接配置工厂（仅建连接，不迁移、不建表）。

- app 通过 `base/common/setting.py` 构建完整 TORTOISE_ORM（含 core/插件模型）；
- 独立服务两个入口使用 `shared_model_modules()`（必要时附加只读依赖模型）。
"""
from __future__ import annotations

from typing import List, Sequence

from packages.common.config import DbConfig, AppConfig, ServicesCommonConfig

# 共享包内模型模块（Tortoise 注册路径唯一来源）
SHARED_MODEL_MODULES: tuple[str, ...] = (
    "packages.common.models.quota",
    "packages.common.models.binding",
    "packages.common.models.reservation",
    "packages.common.models.harness",
    "packages.common.models.model_price",
    "packages.common.models.service_credential",
)

# 网关数据面在 P1 仍经 app 插件服务解析 provider 凭据（C1），故需注册 llm 模型
GATEWAY_DEPENDENCY_MODEL_MODULES: tuple[str, ...] = (
    "base.plugins.llm.models.api_key",
    "base.plugins.llm.models.model",
    "base.plugins.llm.models.provider",
    # C3：plan_service._user_role_codes 会查询 User 并 prefetch roles，
    # P1 前网关用整份 app TORTOISE_ORM（全部模型已注册），这里保持同等能力
    "base.core.users.models.users",
    "base.core.users.models.rbac",
)

# 编排不注册客户域模型：customer_organization 的 FK 会拖入 app 的 Customer 模型。
# 组织级额度校验走只读 SQL 目录（domain/organization_directory.py，Spec §4.2 只读）。


def patch_asyncpg_reset() -> bool:
    """GaussDB/openGauss 兼容补丁：连接池释放时忽略默认复位语句失败。

    asyncpg 0.30+ 会在连接归还连接池时执行 `UNLISTEN *; RESET ALL;` 等复位语句；
    openGauss 不支持 UNLISTEN，导致所有连接池（含 Tortoise 与只读池）在释放时报错。
    这里吞掉复位异常并回滚，保持与 app 原有 `base/common/database.py` 补丁一致。
    """
    try:
        import asyncpg
    except Exception:  # pragma: no cover - asyncpg 为运行期依赖
        return False

    conn_cls = asyncpg.connection.Connection
    if getattr(conn_cls.reset, "_agentpanel_patched", False):
        return True

    original_reset = conn_cls.reset

    async def _patched_reset(self, *, timeout=None):
        try:
            await original_reset(self, timeout=timeout)
        except Exception:
            try:
                await self.execute("ROLLBACK")
            except Exception:
                pass

    _patched_reset._agentpanel_patched = True
    conn_cls.reset = _patched_reset
    return True


patch_asyncpg_reset()



def shared_model_modules() -> List[str]:
    return list(SHARED_MODEL_MODULES)


def gateway_dependency_modules() -> List[str]:
    """网关独立入口需注册的共享模型（P3 D-P3-3=A）。

    仅共享 llm 模型：凭据解析走共享 `domain/credential_resolver.py`；
    客户等级/用户角色由只读 SQL 解析器读取，不再注册 User 模型。
    旧入口回滚仍使用上面的 `GATEWAY_DEPENDENCY_MODEL_MODULES` 原样清单。
    """
    return [
        "packages.common.models.llm_api_key",
        "packages.common.models.llm_model",
        "packages.common.models.llm_provider",
    ]


def _credentials(db: DbConfig) -> dict:
    return {
        "host": db.host,
        "port": db.port,
        "user": db.user,
        "password": db.password,
        "database": db.name,
        "ssl": False,
        "minsize": db.minsize,
        "maxsize": db.maxsize,
        "timeout": db.timeout,
        "command_timeout": db.command_timeout,
        "statement_cache_size": 0,
    }


def db_from_l3(config: ServicesCommonConfig) -> DbConfig:
    return config.db


def db_from_l2(config: AppConfig) -> DbConfig:
    return DbConfig(
        host=config.db_host,
        port=config.db_port,
        user=config.db_user,
        password=config.db_password,
        name=config.db_name,
        minsize=config.minsize,
        maxsize=config.maxsize,
        timeout=config.timeout,
        command_timeout=config.command_timeout,
    )


def build_tortoise_orm(db: DbConfig, model_modules: Sequence[str]) -> dict:
    """与 app 现有 TORTOISE_ORM 结构保持一致（仅连接与模型清单不同）。"""
    return {
        "connections": {
            "postgres": {
                "engine": "tortoise.backends.asyncpg",
                "credentials": _credentials(db),
            },
        },
        "apps": {
            "models": {
                "models": list(model_modules),
                "default_connection": "postgres",
            },
        },
        "use_tz": True,
        "timezone": "Asia/Shanghai",
        "db_logs": False,
    }


def stabilize_shared_model_fields() -> int:
    """把被“未注册模型”抢走的共享字段重新绑定到已注册模型。

    Tortoise 对抽象基类（BaseModel/TimestampMixin）的字段是浅共享，最后一个
    实现类的 `.model` 会覆盖前面的绑定。app 进程注册了全部模型因而无感；独立进程
    经 C1/C2 懒加载会定义 app 领域模型却不注册，导致共享字段指向未注册类，
    查询时抛 `default_connection for the model ... cannot be None`。

    这里只把 `.model` 指向未注册类的字段重绑到一个已注册模型：两者共用同一
    `models` app 连接，取值转换行为不变，也不把 app 领域模型注册进独立服务。
    """
    from tortoise import models as tortoise_models

    seen_classes: List[type] = []
    stack = list(tortoise_models.Model.__subclasses__())
    while stack:
        cls = stack.pop()
        if cls in seen_classes:
            continue
        seen_classes.append(cls)
        stack.extend(cls.__subclasses__())

    concrete = [
        cls for cls in seen_classes
        if getattr(cls, "_meta", None) and getattr(cls._meta, "fields_map", None)
        and not cls._meta.abstract
    ]
    anchor = next(
        (cls for cls in concrete if cls._meta.default_connection is not None), None
    )
    if anchor is None:
        return 0

    rebound = 0
    visited_fields = set()
    for cls in concrete:
        for field in cls._meta.fields_map.values():
            if id(field) in visited_fields:
                continue
            visited_fields.add(id(field))
            owner = getattr(field, "model", None)
            if owner is None:
                continue
            owner_meta = getattr(owner, "_meta", None)
            if owner_meta is not None and owner_meta.default_connection is None:
                field.model = anchor
                rebound += 1
    return rebound


async def init_db(orm: dict) -> None:
    from tortoise import Tortoise

    await Tortoise.init(config=orm)
    stabilize_shared_model_fields()


async def close_db() -> None:
    from tortoise import Tortoise

    await Tortoise.close_connections()
