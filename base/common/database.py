import shutil
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from tortoise.expressions import Q

from base.common.setting import settings, TORTOISE_ORM


# ============================================================
# SQL 迁移文件命名规范
# ============================================================
# 格式: {plugin}_{action}_{table}[__{field}]_{timestamp}.sql
#   plugin:    插件标识，通用迁移用 "core"
#   action:    见 _VALID_ACTIONS 预定义集合
#   table:     表名（蛇形命名，可带下划线，如 approval_flow）
#   field:     字段名（可选，用 __ 双下划线分隔，如 approval_flow__route_patterns）
#   timestamp: Unix 时间戳（秒级整数，决定执行顺序）
#
# 示例:
#   core_seed_data_system_menus_1758648000.sql
#   approval_add_column_approval_flow__route_patterns_1758648060.sql
#   mail_seed_data_message_subtype_1758648120.sql
#   mail_seed_data_menus_and_permissions_1758648180.sql
#   crm_create_table_customer_1758648240.sql
#   crm_drop_column_customer__old_field_1758648300.sql
#
# 生成工具: python -m base.common.migration_tool gen [plugin] [action] [table] [field]
# ============================================================


@dataclass(order=True)
class MigrationMeta:
    """迁移文件元数据，用于排序执行"""
    sort_key: str              # timestamp 数值（按时间排序）
    filename: str              # 文件名
    timestamp: int             # Unix 时间戳（秒）
    plugin: str                 # 插件名（"core" 表示通用）
    action: str                 # 操作类型
    table: str                  # 表名
    field: Optional[str] = None # 字段名（可选）

    @property
    def plugin_name(self) -> Optional[str]:
        """返回插件系统中的 is_enabled 检查名，core 表示始终执行"""
        return None if self.plugin == "core" else self.plugin

    @property
    def description(self) -> str:
        parts = [self.plugin, self.action, self.table]
        if self.field:
            parts.append(self.field)
        return "_".join(parts)


# 文件名解析正则：插件 + 操作 + 表 + (__字段) + _时间戳
# action 限定在预定义集合内，避免贪婪匹配把表名部分吃进去
_VALID_ACTIONS = (
    "create_table", "alter_table", "add_column", "drop_column",
    "alter_column", "seed_data", "grant", "drop_table",
    "add_index", "drop_index", "add_constraint", "drop_constraint",
    "rename_table", "rename_column", "insert_data", "update_data", "delete_data",
)
_ACTION_PATTERN = "(?:" + "|".join(_VALID_ACTIONS) + ")"

_MIGRATION_FILENAME_RE = re.compile(
    rf"^([a-z][a-z0-9]*)_"              # plugin (core/approval/mail/...)
    rf"({_ACTION_PATTERN})_"            # action (from predefined set)
    rf"([a-z][a-z0-9_]*?)"              # table (非贪婪，优先留给 __field)
    rf"(?:__([a-z][a-z0-9_]*))?"        # field (可选，用 __ 双下划线分隔)
    rf"_(\d+)"                          # timestamp (Unix 秒级整数)
    rf"\.sql$",
    re.IGNORECASE,
)


def parse_migration_filename(filename: str) -> Optional[MigrationMeta]:
    """从文件名解析迁移元数据。不符合规范的旧文件返回 None。"""
    m = _MIGRATION_FILENAME_RE.match(filename)
    if not m:
        return None
    plugin, action, table, field, ts_str = m.groups()
    try:
        ts_int = int(ts_str)
    except ValueError:
        return None
    return MigrationMeta(
        sort_key=str(ts_int).zfill(20),  # 用字符串补零保证字典序=时间序
        filename=filename,
        timestamp=ts_int,
        plugin=plugin.lower(),
        action=action.lower(),
        table=table.lower(),
        field=field.lower() if field else None,
    )


def generate_migration_filename(
    plugin: str,
    action: str,
    table: str,
    field: str = "",
    when: Optional[datetime] = None,
) -> str:
    """按规范生成迁移文件名（timestamp 在末尾，field 用 __ 与 table 分隔）。"""
    import time
    ts = int((when or datetime.now()).timestamp())
    action = action.lower().replace(" ", "_")
    table = table.lower().replace("-", "_")
    field = field.lower().replace("-", "_") if field else ""
    parts = [plugin.lower(), action, table]
    if field:
        table_field = f"{table}__{field}"
    else:
        table_field = table
    return f"{plugin.lower()}_{action}_{table_field}_{ts}.sql"


def _patch_asyncpg_for_gaussdb():
    try:
        import asyncpg
        _original_reset = asyncpg.connection.Connection.reset

        async def _patched_reset(self, *, timeout=None):
            try:
                await _original_reset(self, timeout=timeout)
            except Exception:
                try:
                    await self.execute("ROLLBACK")
                except Exception:
                    pass

        asyncpg.connection.Connection.reset = _patched_reset
        print("[DB] asyncpg reset补丁已应用(GaussDB兼容)")
    except Exception as e:
        print(f"[DB] asyncpg补丁应用失败: {e}")


_patch_asyncpg_for_gaussdb()


def _split_sql_statements(sql: str) -> "list[str]":
    """按顶层分号切分 SQL，忽略 $$...$$ 美元引号块内的分号（asyncpg.execute 仅支持单条语句）。"""
    statements: "list[str]" = []
    buf: "list[str]" = []
    in_dollar = False
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "$" and sql[i:i + 2] == "$$":
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        if not in_dollar and ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


async def _run_sql_migrations() -> None:
    """执行 migrations/*.sql 幂等迁移。

    自动扫描 migrations/ 目录，按文件名时间戳排序执行。
    文件名格式见文件顶部注释，通过 parse_migration_filename 解析元数据。
    不符合规范的旧文件会尝试从文件名推断插件归属（兼容旧文件）。
    """
    import asyncpg
    from base.common.plugin_manager import plugin_manager

    migrations_dir = Path(__file__).resolve().parent.parent.parent / "migrations"
    if not migrations_dir.exists():
        print("未找到 migrations/ 目录，跳过自定义 SQL 迁移")
        return

    def _plugin_enabled(plugin_name: str | None) -> bool:
        if plugin_name is None:
            return True
        plugin = plugin_manager.get_plugin(plugin_name) if plugin_manager else None
        if plugin is not None:
            return bool(getattr(plugin, "is_enabled", False))
        manifest = Path(__file__).resolve().parent.parent.parent / "base" / "plugins" / plugin_name / "manifest.json"
        if manifest.exists():
            try:
                import json
                m = json.loads(manifest.read_text(encoding="utf-8"))
                return bool(m.get("is_enabled", False))
            except Exception:
                pass
        return False

    # 扫描并解析所有 .sql 文件
    all_sql_files = sorted(migrations_dir.glob("*.sql"))
    if not all_sql_files:
        print("migrations/ 目录下无 .sql 文件，跳过")
        return

    parsed: list[MigrationMeta] = []
    legacy: list[Path] = []
    for f in all_sql_files:
        meta = parse_migration_filename(f.name)
        if meta:
            parsed.append(meta)
        else:
            legacy.append(f)

    # 按时间戳排序执行
    parsed.sort()

    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    try:
        executed = 0
        skipped = 0

        for meta in parsed:
            sql_file = migrations_dir / meta.filename
            if not _plugin_enabled(meta.plugin_name):
                print(f"  跳过 {meta.filename}：插件 '{meta.plugin}' 未启用")
                skipped += 1
                continue
            print(f"执行 SQL 迁移: {meta.filename}")
            sql = sql_file.read_text(encoding="utf-8")
            for stmt in _split_sql_statements(sql):
                await conn.execute(stmt)
            executed += 1

        # 兼容旧文件：从文件名推断插件名再执行
        for f in legacy:
            parts = f.stem.lower().split("_")
            inferred_plugin = None
            skip_words = {"add", "create", "init", "restore", "seed", "setup", "apply"}
            for p in parts:
                if p and p not in skip_words and p not in ("system", "menus", "data", "permission", "permissions", "menu", "menus"):
                    # 可能是插件名，查一下 manifest
                    manifest = migrations_dir.parent / "base" / "plugins" / p / "manifest.json"
                    if manifest.exists():
                        inferred_plugin = p
                        break
            if not _plugin_enabled(inferred_plugin):
                label = f"插件 '{inferred_plugin}' 未启用" if inferred_plugin else "通用但插件未启用"
                print(f"  跳过 {f.name}（旧文件推断: {label}）")
                skipped += 1
                continue
            print(f"执行 SQL 迁移（旧文件）: {f.name}")
            sql = f.read_text(encoding="utf-8")
            for stmt in _split_sql_statements(sql):
                await conn.execute(stmt)
            executed += 1

        if executed:
            print(f"自定义 SQL 迁移执行完成（{executed} 个文件执行，{skipped} 个跳过）")
        else:
            print(f"自定义 SQL 迁移全部跳过（{skipped} 个文件）")
    finally:
        await conn.close()


async def init_db():
    print("开始初始化数据库...")
    print(f"模型列表: {TORTOISE_ORM['apps']['models']['models']}")
    
    try:
        from aerich import Command
        command = Command(tortoise_config=TORTOISE_ORM)
        
        try:
            print("初始化aerich...")
            await command.init()
            print("aerich初始化完成")
        except Exception as e:
            print(f"初始化aerich时出错: {e}")
            import traceback
            traceback.print_exc()

        try:
            print("执行数据库迁移...")
            await command.upgrade(run_in_transaction=True)
            print("数据库迁移完成")
        except Exception as e:
            print(f"执行数据库迁移时出错: {e}")
            print("继续执行，可能是因为迁移已应用...")
            import traceback
            traceback.print_exc()

        # 执行自定义 SQL 迁移（补齐 action 等列及默认数据），需在 generate_schemas 之前
        try:
            await _run_sql_migrations()
        except Exception as e:
            print(f"执行自定义 SQL 迁移时出错（已忽略）: {e}")
            import traceback
            traceback.print_exc()

    except ImportError:
        print("aerich 未安装，跳过迁移")
    except Exception as e:
        print(f"数据库初始化流程出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("数据库初始化流程完成")
    
async def init_data():
    await init_db()
    
    from tortoise import Tortoise
    print("初始化 Tortoise ORM...")
    try:
        await Tortoise.init(config=TORTOISE_ORM)
        print("Tortoise ORM 初始化完成")
        
        import os
        is_main_worker = os.environ.get("UVICORN_WORKER_ID") is None
        if is_main_worker:
            print("生成数据库表（主进程）...")
            try:
                await Tortoise.generate_schemas(safe=True)
                print("数据库表生成完成")
            except Exception as schema_err:
                print(f"数据库表生成部分失败: {schema_err}")
                print("尝试逐表创建缺失的表...")
                try:
                    import asyncpg as _asyncpg
                    _raw_conn = await _asyncpg.connect(
                        host=settings.db_host, port=settings.db_port,
                        user=settings.db_user, password=settings.db_password,
                        database=settings.db_name
                    )
                    from tortoise.backends.asyncpg.schema_generator import AsyncpgSchemaGenerator
                    _conn = Tortoise.get_connection('postgres')
                    _generator = AsyncpgSchemaGenerator(_conn)
                    for _app_name, _app in Tortoise.apps.items():
                        for _model_name, _model in _app.items():
                            _tbl = _model._meta.db_table
                            try:
                                _exists = await _raw_conn.fetchval(
                                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=$1)",
                                    _tbl
                                )
                                if not _exists:
                                    _table_sql = _generator._get_table_sql(_model, True)
                                    # 正确处理 _get_table_sql 的返回值
                                    # 返回值可能是：dict（包含 table_creation_string）、tuple、或 str
                                    if isinstance(_table_sql, dict):
                                        _create_sql = _table_sql.get('table_creation_string', '')
                                    elif isinstance(_table_sql, tuple):
                                        _create_sql = _table_sql[0]
                                    else:
                                        _create_sql = str(_table_sql)
                                    
                                    try:
                                        await _raw_conn.execute(_create_sql)
                                        print(f"  创建表: {_tbl}")
                                    except Exception as exec_err:
                                        print(f"  创建表 {_tbl} 失败: {exec_err}")
                                        print(f"  SQL: {_create_sql[:300]}")
                                        raise
                            except Exception as e:
                                print(f"  跳过表 {_tbl}: {str(e)[:80]}")
                    await _raw_conn.close()
                except Exception as e2:
                    print(f"逐表创建也失败: {e2}")
                print("数据库表处理完成")
        else:
            worker_id = os.environ.get("UVICORN_WORKER_ID", "unknown")
            print(f"跳过数据库表生成（worker {worker_id}，由主进程已完成）")
        
    except Exception as e:
        print(f"初始化 Tortoise ORM 时出错: {e}")
        import traceback
        traceback.print_exc()