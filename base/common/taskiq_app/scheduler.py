"""beat 侧 SchedulerApp + PG 异步引擎 + 会话工厂。

- `scheduler_app`：taskiq-beat 调度引擎（单实例，写 `scheduler_job` 表）。
- `metadata`：`SchedulerBase.metadata`（R16 验证 create_all 与迁移 SQL 对齐用）。
- beat 严格单实例（部署约束）；scheduler_id 缺省随机 uuid4（禁止固定，§5.1）。
"""
from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from taskiq_beat import SchedulerApp, SchedulerBase, SchedulerConfig

# openGauss 兼容（两处，均须在首次连库/编译 SQL 前完成）：
#  1) PGDialect 用正则解析 version()，只认 "PostgreSQL X.Y"，openGauss 的
#     "(openGauss 7.0.0-RC3 ...)" 会抛 AssertionError 让 beat 启动即崩；
#  2) taskiq-beat 模型用通用 JSON 类型，编译成 ::JSON，与 JSONB 表列不匹配，
#     openGauss 无 json->jsonb 转换会让 startup 排程失败。
from packages.common.db import (  # noqa: E402
    patch_sqlalchemy_for_gaussdb,
    patch_taskiq_beat_json_columns,
)

patch_sqlalchemy_for_gaussdb()

from .broker import broker  # noqa: E402
from .config import settings  # noqa: E402

# taskiq_beat 需先导入才有模型类可打补丁；patch 函数内部自行 import。
patch_taskiq_beat_json_columns()


_engine = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None

if settings.db_url:
    _engine = create_async_engine(settings.db_url, future=True, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
else:
    logger.warning(
        "[taskiq scheduler] TASKIQ_DB_URL 未配置：beat 无法建 PG 引擎，调度不可用"
    )

# scheduler_id 不传 → 默认 uuid4().hex（每次启动随机），满足 §5.1「禁止固定」约束。
_config = SchedulerConfig(
    sync_interval_seconds=settings.beat_sync_interval,
    idle_sleep_seconds=settings.beat_idle_sleep,
    claim_ttl_seconds=settings.lock_ttl,
    run_history_retention_days=settings.run_history_retention_days,
)

scheduler_app: Optional[SchedulerApp] = (
    SchedulerApp(broker=broker, session_factory=_session_factory, config=_config)
    if _session_factory is not None
    else None
)

# 供 R16 验证：SQLAlchemy 模型元数据（与迁移 SQL 逐字段对齐）
metadata = SchedulerBase.metadata

if scheduler_app is None:
    logger.warning("[taskiq scheduler] scheduler_app 为 None（缺 DB_URL），beat 不可用")
else:
    logger.info(
        f"[taskiq scheduler] 已构建 SchedulerApp：sync={settings.beat_sync_interval}s "
        f"claim_ttl={settings.lock_ttl}s"
    )
